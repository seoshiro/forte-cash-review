"""One controlled TRAIN train-fit diagnostic; safe aggregate output only."""
from pathlib import Path
import sys,os,json,time,hashlib,datetime,argparse,importlib.metadata as metadata
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from cashreview.supervision import atomic_json,supervise,await_start_gate,ControlSummary
OUT=ROOT/'.private/temporal-learnability'
FILES=['config/temporal-learnability-protocol.json','scripts/temporal_learnability.py','xclip_candidate/learnability.py',
    'tests/test_learnability.py','xclip_candidate/temporal_head.py','config/xclip-temporal-protocol.json',
    'scripts/xclip_temporal.py','cashreview/supervision.py','cashreview/offline.py','cashreview/processes.py',
    'xclip_candidate/linear_head.py','xclip_candidate/evaluate.py','cashreview/research_split.py',
    '.private/xclip-temporal-control/registration.json','.private/xclip-temporal-control/safe-summary.json',
    '.private/xclip-temporal-control/final-train-pack/metadata.json',
    '.private/xclip-temporal-control/final-train-pack/projection.npz',
    '.private/xclip-temporal-control/final-train-pack/head.safetensors']


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def inputs():
    from scripts.xclip_temporal import verify
    return verify(json.loads((ROOT/'.private/xclip-temporal-control/registration.json').read_text()))


def selected(rows):
    from collections import defaultdict
    # Same deterministic algorithm as diagnostic subset(), without Torch import at registration.
    chosen=[];groups=set()
    for target in (0,1):
        count=0
        for row in sorted(rows,key=lambda r:r['sha256']):
            if row['target']==target and row['group'] not in groups:
                chosen.append(row);groups.add(row['group']);count+=1
                if count==2:break
        if count!=2:raise ValueError('Distinct TRAIN subset unavailable')
    return chosen


def verify(reg):
    if any(sha(ROOT/name)!=value for name,value in reg['code_sha256'].items()):raise ValueError('Frozen diagnostic changed')
    if {name:metadata.version(name) for name in reg['versions']}!=reg['versions']:raise ValueError('Runtime changed')
    rows=inputs()
    if [row['sha256'] for row in selected(rows)]!=reg['selected_source_sha256']:raise ValueError('Diagnostic subset changed')
    return rows


def register():
    import psutil
    cfg=json.loads((ROOT/'config/temporal-learnability-protocol.json').read_text());available=psutil.virtual_memory().available/2**20
    if available<cfg['budget']['minimum_available_ram_before_mib']:raise RuntimeError('RAM preflight refused')
    rows=inputs();chosen=selected(rows);OUT.mkdir(exist_ok=True)
    reg={'protocol_id':cfg['protocol_id'],'registered_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'code_sha256':{name:sha(ROOT/name) for name in FILES},'selected_source_sha256':[row['sha256'] for row in chosen],
        'versions':{name:metadata.version(name) for name in ['torch','numpy','safetensors','threadpoolctl']},
        'subset_videos':4,'subset_groups':4,'positive':2,'negative':2,'available_ram_mib':available,
        'no_group_split_changed':True,'train_fit_only_not_validation':True,'tune_used':False,'holdout_used':False}
    with (OUT/'registration.json').open('x') as stream:json.dump(reg,stream,indent=2)
    print(json.dumps({'registered':True,'protocol_id':cfg['protocol_id'],'registration_sha256':sha(OUT/'registration.json'),
        'train_fit_subset_videos':4,'distinct_train_groups':4,'gpu_used':False}),flush=True)


def worker():
    run,deadline=await_start_gate();phase='preflight';completed=0;start=time.monotonic()
    try:
        os.environ.update(CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',
            HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',DO_NOT_TRACK='1')
        import psutil
        cfg=json.loads((ROOT/'config/temporal-learnability-protocol.json').read_text());minimum=float('inf')
        def check():
            nonlocal minimum
            if time.monotonic()>=deadline:raise TimeoutError('Diagnostic deadline')
            available=psutil.virtual_memory().available/2**20;minimum=min(minimum,available)
            if available<cfg['budget']['minimum_available_ram_during_mib']:raise RuntimeError('RAM margin')
            if psutil.Process().memory_info().peak_wset/2**20>cfg['budget']['maximum_peak_working_set_mib']:raise RuntimeError('Working-set budget')
        if psutil.virtual_memory().available/2**20<cfg['budget']['minimum_available_ram_before_mib']:raise RuntimeError('RAM preflight refused')
        reg=json.loads((OUT/'registration.json').read_text());rows=verify(reg);check()
        import numpy as np,torch
        from threadpoolctl import threadpool_limits
        from safetensors.torch import load_file
        from xclip_candidate.temporal_head import TemporalHead,fit_projection
        from xclip_candidate.learnability import subset,training_fit,arm
        from cashreview.offline import deny_network
        torch.set_num_threads(1);torch.set_num_interop_threads(1);torch.use_deterministic_algorithms(True);deny_network();check()
        items=[]
        for row in rows:
            with np.load(ROOT/'.private/xclip-control/features'/f"{row['sha256']}.npz",allow_pickle=False) as cache:
                item={key:np.array(cache[key]) for key in ['ordered','times']}
            item.update({key:row[key] for key in ['sha256','target','label_sec','group']});items.append(item)
        chosen=subset(items)
        if [i['sha256'] for i in chosen]!=reg['selected_source_sha256']:raise ValueError('Torch subset selection differs')
        phase='fixed_subset_train_fit';results={}
        with threadpool_limits(limits=1):
            projection=fit_projection(chosen,8);check()
            for name,recipe in cfg['arms'].items():
                results[name]=arm(chosen,projection,cfg,recipe,check);completed+=1;check()
                print(json.dumps({'completed_diagnostic_arms':completed,'total_diagnostic_arms':2,'per_video_outputs_emitted':False}),flush=True)
            phase='existing_full_train_pack_rescore';directory=ROOT/cfg['existing_full_train_pack']
            pack=json.loads((directory/'metadata.json').read_text())
            if sha(directory/'projection.npz')!=pack['projection_sha256'] or sha(directory/'head.safetensors')!=pack['head_sha256']:raise ValueError('Existing fitted pack changed')
            with np.load(directory/'projection.npz',allow_pickle=False) as data:projection=(np.array(data['mean']),np.array(data['basis']))
            model=TemporalHead();model.load_state_dict(load_file(str(directory/'head.safetensors')),strict=True)
            existing=training_fit((projection,model),items);completed+=1;check()
        saved=json.loads((ROOT/'.private/xclip-temporal-control/safe-summary.json').read_text())['results']['temporal_head']
        control=results['overfit_positive_control']['after'];gate=cfg['overfit_diagnostic_gate']
        cm=control['confusion_matrix_tn_fp_fn_tp'];passed=bool(cm==[[2,0],[0,2]] and control['point_negative_max_eval_loss']<=gate['point_negative_max_eval_loss_max']
            and control['positive_point_logits_above_threshold_count']==2 and control['negative_video_max_logits_below_threshold_count']==2)
        verify(reg);check()
        summary={'status':'completed','protocol_id':cfg['protocol_id'],'scope':cfg['purpose'],'arms':results,
            'subset_videos':4,'subset_train_groups':4,'subset_positive':2,'subset_negative':2,
            'maximum_positive_label_to_center_gap_sec':max(float(np.min(abs(i['times']-i['label_sec']))) for i in chosen if i['target']),
            'existing_full_train_pack_train_fit':existing,'saved_group_cv_aggregate':{key:saved[key] for key in ['videos','confusion_matrix_tn_fp_fn_tp','f1','recall']},
            'overfit_control_passed':passed,'worker_wall_sec_before_persistence':time.monotonic()-start,
            'process_peak_working_set_mib':psutil.Process().memory_info().peak_wset/2**20,'minimum_available_system_ram_mib':minimum,
            'registered_sources_unchanged':True,'registration_sha256':sha(OUT/'registration.json'),
            'train_fit_only_not_validation':True,'cpu_threads':1,'gpu_used':False,'new_bank_decoding':False,
            'tune_used':False,'holdout_used':False,'group_split_changed':False,'prior_model_pack_changed':False,
            'per_video_outputs_emitted':False,'release_eligible':False,'semantic_recognition_validated':False}
        atomic_json(run/'diagnostic-safe-summary.json',summary,deadline=deadline);check()
        atomic_json(run/'worker-safe-summary.json',ControlSummary(status='completed',completed_cases=3,passed_cases=3,total_cases=3).model_dump(),deadline=deadline);check()
    except Exception as error:
        (run/'diagnostic-safe-summary.json').unlink(missing_ok=True);(run/'worker-safe-summary.json').unlink(missing_ok=True)
        atomic_json(run/'failure-safe-summary.json',{'status':'failed','phase':phase,'technical_error_type':type(error).__name__,
            'completed_technical_cases':completed,'per_video_outputs_emitted':False,'repeat_authorized':False})
        atomic_json(run/'worker-safe-summary.json',ControlSummary(status='failed',completed_cases=completed,passed_cases=completed,total_cases=3,failure='exception').model_dump())
        raise SystemExit(1)


def run():
    reg=json.loads((OUT/'registration.json').read_text());verify(reg)
    with (OUT/'attempt.json').open('x') as stream:json.dump({'started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()},stream)
    cfg=json.loads((ROOT/'config/temporal-learnability-protocol.json').read_text())
    monitor=supervise([sys.executable,str(Path(__file__).resolve()),'worker'],OUT/'run',cfg['budget']['wall_sec'],3,str(ROOT))
    print(json.dumps({'technical_monitor':monitor}),flush=True)
    if monitor['quality_gate_passed'] and monitor['cleanup_complete']:
        summary=json.loads((OUT/'run/diagnostic-safe-summary.json').read_text());summary['technical_monitor_validated']=True
    else:
        summary={'status':'failed','technical_monitor_validated':False,'repeat_authorized':False}
        path=OUT/'run/failure-safe-summary.json'
        if path.exists():summary.update(json.loads(path.read_text()))
    atomic_json(OUT/'safe-summary.json',summary);print(json.dumps(summary),flush=True)
    if summary['status']!='completed':raise SystemExit(1)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['register','run','worker']);args=p.parse_args()
    try:globals()[args.action]()
    except Exception as error:print(json.dumps({'status':'failed','technical_error_type':type(error).__name__,'raw_private_content_emitted':False}));sys.exit(1)
