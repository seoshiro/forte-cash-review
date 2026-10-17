"""Register one supervised temporal TRAIN experiment; private predictions stay local."""
from pathlib import Path
import sys,os,json,time,datetime,argparse,hashlib,importlib.metadata as metadata
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from cashreview.supervision import atomic_json,supervise,await_start_gate,ControlSummary
OUT=ROOT/'.private/xclip-temporal-recipe-control'
FILES=['config/xclip-temporal-recipe-protocol.json','xclip_candidate/temporal_head.py','scripts/xclip_temporal_recipe.py',
    'tests/test_xclip_temporal.py','tests/test_recipe_diagnostic.py','xclip_candidate/recipe_diagnostic.py','xclip_candidate/learnability.py',
    '.private/temporal-learnability/registration.json','.private/temporal-learnability/safe-summary.json','scripts/audit_train_preparation.py','scripts/manifest.py','tests/test_manifest_validation.py',
    'xclip_candidate/linear_head.py','xclip_candidate/evaluate.py','xclip_candidate/features.py','scripts/xclip_linear.py',
    'scripts/xclip_experiment.py','cashreview/research_split.py','cashreview/video.py','cashreview/offline.py',
    'cashreview/supervision.py','cashreview/processes.py','qvt_candidate/evaluate.py','requirements-patched-lock.txt',
    '.private/dataset/manifest.json','.private/dataset/split.json','.private/train-preparation-audit/safe-summary.json',
    '.private/xclip-control/registration.json','.private/xclip-control/feature-registration.json','.private/xclip-control/safe-summary.json']


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def inputs():
    from scripts.xclip_linear import inputs as original
    rows,inventory=original()
    if any(sha(row['path'])!=row['sha256'] for row in rows):raise ValueError('Original TRAIN source changed')
    return rows,inventory


def verify(registration):
    if {name:sha(ROOT/name) for name in FILES}!=registration['code_sha256']:raise ValueError('Frozen experiment source changed')
    if {name:metadata.version(name) for name in registration['versions']}!=registration['versions']:raise ValueError('Runtime versions changed')
    rows,inventory=inputs()
    if inventory!=registration['cache_sha256'] or [r['sha256'] for r in rows]!=registration['source_sha256']:raise ValueError('Frozen TRAIN selection changed')
    return rows


def execute_learning(items,cfg,check,progress):
    from threadpoolctl import threadpool_limits
    from xclip_candidate.temporal_head import evaluate,fit_head
    from cashreview.offline import deny_network
    deny_network()
    with threadpool_limits(limits=1):
        summary,private=evaluate(items,cfg,check,progress);check()
        tick=time.monotonic();head,_=fit_head(items,cfg,check);elapsed=time.monotonic()-tick
        check()
    return summary,private,head,elapsed


def register():
    import psutil
    OUT.mkdir(exist_ok=True)
    if (OUT/'registration.json').exists():raise RuntimeError('No registration overwrite')
    cfg=json.loads((ROOT/'config/xclip-temporal-recipe-protocol.json').read_text())
    available=psutil.virtual_memory().available/2**20
    if available<cfg['budget']['minimum_available_ram_before_mib']:raise RuntimeError('RAM preflight refused')
    audit=json.loads((ROOT/'.private/train-preparation-audit/safe-summary.json').read_text())
    if audit['status']!='PASS' or audit['observed_preparation_bug'] or audit['manifest_split_or_cache_regenerated']:raise ValueError('Preparation audit required')
    diagnostic=OUT.parent/'temporal-learnability/registration.json'
    if sha(diagnostic)!=cfg['recipe_selection']['diagnostic_registration_sha256']:raise ValueError('Diagnostic registration changed')
    rows,inventory=inputs()
    record={'protocol_id':cfg['protocol_id'],'registered_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'code_sha256':{name:sha(ROOT/name) for name in FILES},'source_sha256':[r['sha256'] for r in rows],
        'cache_sha256':inventory,'versions':{name:metadata.version(name) for name in ['torch','numpy','scikit-learn','safetensors','threadpoolctl']},
        'train_unique_contents':len(rows),'train_auto_groups':len({r['group'] for r in rows}),'available_ram_mib':available,
        'tune_used_for_fit_or_selection':False,'holdout_used':False,'post_tune_exploratory_train':True}
    with (OUT/'registration.json').open('x') as stream:json.dump(record,stream,indent=2)
    print(json.dumps({'registered':True,'protocol_id':cfg['protocol_id'],'registration_sha256':sha(OUT/'registration.json'),
        'train_unique_contents':len(rows),'train_groups':record['train_auto_groups'],'available_ram_mib':available}),flush=True)


def worker():
    run,deadline=await_start_gate();start=time.monotonic();phase='preflight';completed=0
    try:
        os.environ.update(CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',
            HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1',DO_NOT_TRACK='1')
        import psutil
        cfg=json.loads((ROOT/'config/xclip-temporal-recipe-protocol.json').read_text());budget=cfg['budget'];minimum=float('inf')
        def check():
            nonlocal minimum
            if time.monotonic()>=deadline:raise TimeoutError('Owned experiment deadline')
            memory=psutil.Process().memory_info();available=psutil.virtual_memory().available/2**20;minimum=min(minimum,available)
            if available<budget['minimum_available_ram_during_mib']:raise RuntimeError('RAM margin')
            if memory.peak_wset/2**20>budget['maximum_peak_working_set_mib']:raise RuntimeError('Peak working-set budget')
        if psutil.virtual_memory().available/2**20<budget['minimum_available_ram_before_mib']:raise RuntimeError('RAM preflight refused')
        check();registration=json.loads((OUT/'registration.json').read_text());selected=verify(registration);check()
        phase='cpu_imports'
        import numpy as np,torch
        from safetensors.torch import save_file
        torch.set_num_threads(1);torch.set_num_interop_threads(1);torch.use_deterministic_algorithms(True);check()
        items=[]
        for row in selected:
            with np.load(ROOT/'.private/xclip-control/features'/f"{row['sha256']}.npz",allow_pickle=False) as data:
                item={key:np.array(data[key]) for key in ['ordered','times']}
            item.update({key:row[key] for key in ['sha256','target','label_sec','group']});items.append(item)
        def progress(count):
            nonlocal completed
            completed=count;check();print(json.dumps({'completed_cv_folds':count,'total_cv_folds':24,'per_video_outputs_emitted':False}),flush=True)
        phase='train_group_cv_and_fixed_full_train_fit'
        summary,private,head,full_fit_sec=execute_learning(items,cfg,check,progress)
        from xclip_candidate.learnability import training_fit
        from xclip_candidate.recipe_diagnostic import exposure_report,full_fit_gate
        from threadpoolctl import threadpool_limits
        with threadpool_limits(limits=1):
            summary['full_train_fit_diagnostic']=training_fit(head,items)
        summary['full_train_fit_gate_passed']=full_fit_gate(summary['full_train_fit_diagnostic'],cfg['full_train_fit_gate'])
        diagnostic=json.loads((OUT.parent/'temporal-learnability/registration.json').read_text())
        summary['diagnostic_exposure_strata']=exposure_report(private,items,diagnostic['selected_source_sha256'])
        summary['adaptive_recipe_selected_on_four_train_groups']=True
        summary['independent_validation']=False
        check()
        phase='fixed_full_train_pack';folder=OUT/'final-train-pack';folder.mkdir(exist_ok=False)
        np.savez_compressed(folder/'projection.npz',mean=head[0][0],basis=head[0][1])
        save_file({key:value.detach().cpu().contiguous() for key,value in head[1].state_dict().items()},str(folder/'head.safetensors'))
        atomic_json(folder/'metadata.json',{'protocol_id':cfg['protocol_id'],'registration_sha256':sha(OUT/'registration.json'),
            'feature_registration_sha256':sha(ROOT/'.private/xclip-control/feature-registration.json'),
            'trainable_parameters':sum(p.numel() for p in head[1].parameters()),'threshold_logit':0.,
            'projection_sha256':sha(folder/'projection.npz'),'head_sha256':sha(folder/'head.safetensors'),
            'type':'unverified','rule':'not_assessed','release_eligible':False,'cv_binary_gate_passed':summary['binary_gate_passed']},deadline=deadline)
        completed=25;check()
        phase='final_integrity_and_persistence';verify(registration);check()
        atomic_json(run/'private-oof-results.json',private,deadline=deadline)
        summary.update(status='completed',protocol_id=cfg['protocol_id'],split='train',scope=cfg['scope'],
            train_unique_contents=len(items),train_auto_groups=24,cv_folds=24,full_train_fits=1,trainable_parameters=209,
            fixed_optimizer_steps=cfg['head']['steps'],full_train_fit_sec=full_fit_sec,worker_wall_sec=time.monotonic()-start,
            process_peak_working_set_mib=psutil.Process().memory_info().peak_wset/2**20,minimum_available_system_ram_mib=minimum,
            cpu_threads=1,gpu_used=False,new_bank_decoding=False,cache_and_sources_unchanged=True,
            tune_used=False,holdout_used=False,post_tune_exploratory_train=True,per_video_outputs_emitted=False,
            annotations_or_private_predictions_read=False,baseline_or_deployment_pack_changed=False,
            semantic_types_rules_or_evidence_validated=False,release_eligible=False,official_score=False,
            registration_sha256=sha(OUT/'registration.json'),resource_guard_scope='Discrete working-set/RAM checks each training step; owned process enforces wall deadline')
        atomic_json(run/'quality-safe-summary.json',summary,deadline=deadline);check()
        atomic_json(run/'worker-safe-summary.json',ControlSummary(status='completed',completed_cases=25,passed_cases=25,total_cases=25).model_dump(),deadline=deadline)
        check()
    except Exception as error:
        (run/'quality-safe-summary.json').unlink(missing_ok=True);(run/'worker-safe-summary.json').unlink(missing_ok=True)
        atomic_json(run/'failure-safe-summary.json',{'status':'failed','phase':phase,'technical_error_type':type(error).__name__,
            'completed_technical_fits':completed,'per_video_outputs_emitted':False,'repeat_authorized':False})
        atomic_json(run/'worker-safe-summary.json',ControlSummary(status='failed',completed_cases=completed,passed_cases=completed,total_cases=25,failure='exception').model_dump())
        raise SystemExit(1)


def run():
    cfg=json.loads((ROOT/'config/xclip-temporal-recipe-protocol.json').read_text());verify(json.loads((OUT/'registration.json').read_text()))
    with (OUT/'attempt.json').open('x') as stream:json.dump({'started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()},stream)
    terminal=supervise([sys.executable,str(Path(__file__).resolve()),'worker'],OUT/'run',cfg['budget']['wall_sec'],25,str(ROOT))
    print(json.dumps({'technical_monitor':terminal}),flush=True)
    if terminal['quality_gate_passed'] and terminal['cleanup_complete']:
        summary=json.loads((OUT/'run/quality-safe-summary.json').read_text());summary['technical_monitor_validated']=True
    else:
        summary={'status':'failed','technical_monitor_validated':False,'release_eligible':False,'repeat_authorized':False}
        path=OUT/'run/failure-safe-summary.json'
        if path.exists():summary.update(json.loads(path.read_text()))
    atomic_json(OUT/'safe-summary.json',summary);print(json.dumps(summary),flush=True)
    if summary['status']!='completed':raise SystemExit(1)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['register','run','worker']);a=p.parse_args()
    try:globals()[a.action]()
    except Exception as error:print(json.dumps({'status':'failed','technical_error_type':type(error).__name__,'raw_private_content_emitted':False}));sys.exit(1)
