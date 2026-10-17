"""Register and supervise one cache-only TRAIN experiment; safe aggregates only."""
from pathlib import Path
import sys,os,json,time,datetime,argparse,hashlib,importlib.metadata as metadata
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from cashreview.supervision import atomic_json,supervise,await_start_gate,ControlSummary
OUT=ROOT/'.private/xclip-linear-control'
FILES=['config/xclip-linear-protocol.json','xclip_candidate/linear_head.py','scripts/xclip_linear.py',
    'xclip_candidate/evaluate.py','qvt_candidate/evaluate.py','cashreview/research_split.py','scripts/xclip_experiment.py',
    'cashreview/supervision.py','cashreview/offline.py','requirements-patched-lock.txt','tests/test_xclip_linear.py',
    '.private/xclip-control/registration.json','.private/xclip-control/feature-registration.json','.private/xclip-control/safe-summary.json']


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def persist_success(run,summary,check,deadline):
    quality=run/'quality-safe-summary.json';worker_report=run/'worker-safe-summary.json'
    try:
        summary.update(check());atomic_json(quality,summary,deadline=deadline)
        atomic_json(worker_report,ControlSummary(status='completed',completed_cases=24,passed_cases=24,total_cases=24).model_dump(),deadline=deadline)
        summary.update(check());atomic_json(quality,summary,deadline=deadline)
        check()
    except BaseException:
        quality.unlink(missing_ok=True);worker_report.unlink(missing_ok=True)
        raise


def inputs():
    from scripts.xclip_experiment import rows,verify
    original=json.loads((ROOT/'.private/xclip-control/registration.json').read_text());verify(original)
    selected=rows();inventory=json.loads((ROOT/'.private/xclip-control/feature-registration.json').read_text())['artifact_sha256']
    cache=ROOT/'.private/xclip-control/features'
    if set(inventory)!={r['sha256']+'.npz' for r in selected} or {p.name for p in cache.iterdir()}!=set(inventory):raise ValueError('Exact original TRAIN cache required')
    if any(not (cache/name).is_file() or (cache/name).is_symlink() or sha(cache/name)!=digest for name,digest in inventory.items()):raise ValueError('Original cache changed')
    return selected,inventory


def verify_registered(registration):
    if {n:sha(ROOT/n) for n in FILES}!=registration['code_sha256']:raise ValueError('Registered code changed')
    if {n:metadata.version(n) for n in registration['versions']}!=registration['versions']:raise ValueError('Version changed')
    selected,inventory=inputs()
    if inventory!=registration['cache_sha256'] or [r['sha256'] for r in selected]!=registration['source_sha256']:raise ValueError('Registered TRAIN inputs changed')
    return selected


def register():
    import psutil
    cfg=json.loads((ROOT/'config/xclip-linear-protocol.json').read_text());OUT.mkdir(exist_ok=True)
    if (OUT/'registration.json').exists():raise RuntimeError('No registration overwrite')
    available=psutil.virtual_memory().available
    if available/2**20<cfg['budget']['minimum_available_ram_mib_before']:raise RuntimeError('RAM reserve insufficient')
    selected,inventory=inputs()
    record={'protocol_id':cfg['protocol_id'],'registered_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'code_sha256':{n:sha(ROOT/n) for n in FILES},'cache_sha256':inventory,'source_sha256':[r['sha256'] for r in selected],
        'versions':{n:metadata.version(n) for n in ['numpy','scipy','scikit-learn','threadpoolctl','psutil']},
        'available_system_ram_bytes':available,'cpu_threads':cfg['budget']['cpu_threads']}
    with (OUT/'registration.json').open('x',encoding='utf-8') as stream:json.dump(record,stream,indent=2)
    print(json.dumps({'registered':True,'registration_sha256':sha(OUT/'registration.json'),'available_ram_mib':available/2**20,
        'train_unique_videos':len(selected),'new_gpu_inference':False,'media_opened':False}))


def worker():
    run,deadline=await_start_gate();start=time.monotonic()
    os.environ.update(OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1')
    from cashreview.offline import deny_network
    deny_network()
    try:
        import numpy as np,psutil
        from threadpoolctl import threadpool_limits
        from xclip_candidate.linear_head import evaluate
        cfg=json.loads((ROOT/'config/xclip-linear-protocol.json').read_text());registration=json.loads((OUT/'registration.json').read_text())
        minimum_ram=psutil.virtual_memory().available;process=psutil.Process();peak=0
        def check():
            nonlocal minimum_ram,peak
            minimum_ram=min(minimum_ram,psutil.virtual_memory().available);peak=max(peak,process.memory_info().peak_wset)
            if time.monotonic()>=deadline:raise TimeoutError('CPU experiment budget')
            if minimum_ram/2**20<cfg['budget']['minimum_available_ram_mib_during'] or peak/2**20>cfg['budget']['max_process_peak_rss_mib']:raise RuntimeError('RAM budget')
            return {'process_peak_working_set_mib':peak/2**20,'minimum_available_system_ram_mib':minimum_ram/2**20}
        check()
        if psutil.virtual_memory().available/2**20<cfg['budget']['minimum_available_ram_mib_before']:raise RuntimeError('Pre-fit RAM reserve')
        selected=verify_registered(registration);items=[];selection=cfg['selection']
        if len(selected)!=selection['unique_train_videos'] or len({r['group'] for r in selected})!=selection['automatic_train_groups'] or sum(r['target'] for r in selected)!=selection['positive_videos']:raise ValueError('TRAIN count mismatch')
        for row in selected:
            with np.load(ROOT/'.private/xclip-control/features'/(row['sha256']+'.npz'),allow_pickle=False) as data:
                item={'ordered':np.array(data['ordered']),'times':np.array(data['times'])}
            if item['ordered'].ndim!=2 or item['ordered'].shape[1]!=selection['feature_dim']:raise ValueError('Feature dimension mismatch')
            item.update({k:row[k] for k in ['group','target','label_sec','sha256']});items.append(item);check()
        if psutil.virtual_memory().available/2**20<cfg['budget']['minimum_available_ram_mib_before']:raise RuntimeError('Immediate pre-fit RAM reserve')
        fit_start=time.monotonic()
        with threadpool_limits(limits=cfg['budget']['cpu_threads']):aggregate,private=evaluate(items,cfg,check)
        fit_sec=time.monotonic()-fit_start;check();verify_registered(registration);check()
        baseline=aggregate['results']['baseline'];cm=baseline['confusion_matrix_tn_fp_fn_tp']
        if ([*cm[0],*cm[1]]!=cfg['baseline_expected_tn_fp_fn_tp'] or abs(baseline['f1']-cfg['baseline_expected_f1'])>1e-12
            or abs(baseline['timestamp_mae_sec']-cfg['baseline_expected_tp_point_mae_sec'])>1e-6
            or baseline['timestamp_matched_positive_videos']!=cfg['baseline_expected_tp_point_count']
            or abs(baseline['video_roc_auc']-cfg['baseline_expected_roc_auc'])>1e-12):raise ValueError('Saved baseline not reproduced')
        atomic_json(run/'private-oof-results.json',private,deadline=deadline);check()
        summary={'status':'completed','protocol_id':cfg['protocol_id'],'split':'train',**aggregate,
            'train_unique_contents':len(items),'train_auto_groups':len({i['group'] for i in items}),'positive_videos':sum(i['target'] for i in items),
            'baseline_reproduced':True,'original_cache_and_registration_unchanged':True,'cache_evaluation_wall_sec':fit_sec,
            'worker_wall_sec_before_final_persistence':time.monotonic()-start,'process_peak_working_set_mib':peak/2**20,
            'minimum_available_system_ram_mib':minimum_ram/2**20,'new_gpu_inference':False,'media_opened':False,
            'tune_used':False,'holdout_used':False,'annotations_read':False,'per_video_outputs_emitted':False,
            'type_rule_evidence_validated':False,'release_eligible':False,'baseline_or_deployment_pack_changed':False,'limits':cfg['limits']}
        persist_success(run,summary,check,deadline)
    except Exception as error:
        path=run/'quality-safe-summary.json'
        if path.exists():path.unlink()
        (run/'worker-safe-summary.json').unlink(missing_ok=True)
        atomic_json(path,{'status':'failed','technical_error_type':type(error).__name__,'release_eligible':False,'per_video_outputs_emitted':False})
        atomic_json(run/'worker-safe-summary.json',ControlSummary(status='failed',completed_cases=0,passed_cases=0,total_cases=24,failure='exception').model_dump())
        raise SystemExit(1)


def main(action):
    if action=='register':return register()
    if action=='worker':return worker()
    cfg=json.loads((ROOT/'config/xclip-linear-protocol.json').read_text())
    report=supervise([sys.executable,str(Path(__file__).resolve()),'worker'],OUT/'run',cfg['budget']['wall_sec'],24,str(ROOT))
    print(json.dumps({'technical_monitor':report}),flush=True)
    if not report['quality_gate_passed']:
        failure={'status':'failed','technical_monitor_validated':False,'release_eligible':False,'per_video_outputs_emitted':False}
        child=OUT/'run/quality-safe-summary.json'
        if child.exists():failure['technical_error_type']=json.loads(child.read_text()).get('technical_error_type','Unknown')
        atomic_json(OUT/'safe-summary.json',failure);print(json.dumps(failure));raise SystemExit(1)
    summary=json.loads((OUT/'run/quality-safe-summary.json').read_text());summary['technical_monitor_validated']=True
    atomic_json(OUT/'safe-summary.json',summary);print(json.dumps(summary),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['register','run','worker']);a=parser.parse_args()
    try:main(a.action)
    except Exception as error:print(json.dumps({'rejected_or_failed':True,'technical_error_type':type(error).__name__,'per_video_outputs_emitted':False}));sys.exit(1)
