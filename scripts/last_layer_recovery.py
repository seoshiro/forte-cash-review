"""One checkpointed, diagnosed identical TRAIN pass. No output below aggregate level."""
from pathlib import Path
import argparse,datetime,json,os,sys,time
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from cashreview.supervision import atomic_json,supervise,await_start_gate,ControlSummary,write_progress
from cashreview.technical_diagnostics import TechnicalGuardError,safe_exception,save_private_trace
from scripts import last_layer_diagnostic as prior
OUT=ROOT/'.private/xclip-last-layer-recovery';CONFIG='config/last-layer-recovery.json'
FILES=[CONFIG,'scripts/last_layer_recovery.py','xclip_candidate/fit_checkpoints.py','tests/test_fit_checkpoints.py']


def base():
    cfg=json.loads((ROOT/CONFIG).read_text());prior.verify(cfg['prior_diagnostic_registration_sha256'])
    return cfg,json.loads((ROOT/prior.previous.CONFIG).read_text())


def register():
    cfg,_=base();OUT.mkdir(exist_ok=False)
    record={'protocol_id':cfg['protocol_id'],'registered_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'code_sha256':{name:prior.previous.original.sha(ROOT/name) for name in FILES},'prior_diagnostic_registration_sha256':cfg['prior_diagnostic_registration_sha256']}
    atomic_json(OUT/'registration.json',record)
    print(json.dumps({'registered':True,'registration_sha256':prior.previous.original.sha(OUT/'registration.json'),'cv_fits':48,'full_train_fits':2,'owned_wall_cap_sec':1800,'tune_used':False,'holdout_used':False}),flush=True)


def verify(expected):
    cfg,recipe=base()
    if prior.previous.original.sha(OUT/'registration.json')!=expected:raise ValueError('Recovery registration changed')
    record=json.loads((OUT/'registration.json').read_text())
    if {name:prior.previous.original.sha(ROOT/name) for name in FILES}!=record['code_sha256']:raise ValueError('Recovery source changed')
    return cfg,recipe


def worker(expected):
    run,deadline=await_start_gate();started=time.monotonic();phase='preflight';cache=None;torch=None;resources={};minimum_ram=float('inf');minimum_gpu=float('inf');last_write=0.
    try:
        os.environ.update(CUDA_VISIBLE_DEVICES='0',OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1',DO_NOT_TRACK='1',CUBLAS_WORKSPACE_CONFIG=':4096:8',TOKENIZERS_PARALLELISM='false')
        import psutil,numpy as np
        cfg,recipe=verify(expected);budget=recipe['budget'];cutoff=datetime.datetime.fromisoformat(cfg['absolute_cutoff_utc']).timestamp()
        if psutil.virtual_memory().available/2**20<budget['min_available_ram_before_mib']:raise TechnicalGuardError('host_memory_guard')
        from cashreview.offline import deny_network
        deny_network()
        import torch as imported
        torch=imported
        from threadpoolctl import threadpool_limits
        import xclip_candidate.last_layer as model
        from xclip_candidate.fit_checkpoints import CompletedFits
        torch.set_num_threads(2);torch.set_num_interop_threads(2);torch.use_deterministic_algorithms(True)
        torch.backends.cudnn.benchmark=False;torch.backends.cudnn.deterministic=True;torch.cuda.reset_peak_memory_stats()
        def check(force=False):
            nonlocal resources,minimum_ram,minimum_gpu,last_write
            info=psutil.Process().memory_info();available=psutil.virtual_memory().available/2**20;minimum_ram=min(minimum_ram,available)
            resources={'elapsed_sec':time.monotonic()-started,'rss_mib':info.rss/2**20,'peak_working_set_mib':info.peak_wset/2**20,'available_ram_mib':available,'minimum_available_ram_mib':minimum_ram}
            if torch.cuda.is_initialized():
                free,_=torch.cuda.mem_get_info();minimum_gpu=min(minimum_gpu,free/2**20)
                resources.update(torch_allocated_mib=torch.cuda.memory_allocated()/2**20,torch_reserved_mib=torch.cuda.memory_reserved()/2**20,torch_peak_allocated_mib=torch.cuda.max_memory_allocated()/2**20,torch_peak_reserved_mib=torch.cuda.max_memory_reserved()/2**20,gpu_free_mib=free/2**20,minimum_free_gpu_mib=minimum_gpu)
            if force or time.monotonic()-last_write>=5:
                atomic_json(run/'resource-safe-summary.json',{'phase':phase,'active_fit_ordinal':cache.active_index if cache else None,'completed_fit_checkpoints':cache.count() if cache else 0,'resources':resources});last_write=time.monotonic()
            if time.monotonic()>=deadline or time.time()>=cutoff:raise TechnicalGuardError('deadline_guard')
            if available<budget['min_available_ram_during_mib'] or info.peak_wset/2**20>budget['max_peak_working_set_mib']:raise TechnicalGuardError('host_memory_guard')
            if resources.get('gpu_free_mib',99999)<budget['min_free_gpu_during_mib'] or resources.get('torch_peak_reserved_mib',0)>budget['max_torch_reserved_mib']:raise TechnicalGuardError('gpu_memory_guard')
        check()
        if torch.cuda.mem_get_info()[0]/2**20<budget['min_free_gpu_before_mib']:raise TechnicalGuardError('gpu_memory_guard')
        phase='saved_prefix_replay';items=[];maximum=0.;prefix_reg=json.loads((prior.previous.OUT/'prefix-registration.json').read_text())
        for row in prior.previous.original.inputs()[0]:
            path=prior.previous.OUT/'prefix'/(row['sha256']+'.npz')
            if prior.previous.original.sha(path)!=prefix_reg['cache_sha256'][path.name]:raise ValueError('Prefix bytes changed')
            with np.load(path,allow_pickle=False) as values:prefix={k:np.array(values[k]) for k in model.PREFIX_KEYS};times=np.array(values['times']);reference=np.array(values['reference'])
            with np.load(ROOT/'.private/xclip-control/features'/(row['sha256']+'.npz'),allow_pickle=False) as values:old=np.array(values['ordered']);old_times=np.array(values['times'])
            if not np.array_equal(times,old_times):raise ValueError('PTS changed')
            model.validate_prefix(prefix,len(times));zero=model.Adapter(recipe['model']).to('cuda:0').eval()
            with torch.inference_mode():
                for view in range(2):
                    for offset in range(0,len(times),budget['batch_windows']):
                        values={k:torch.as_tensor(prefix[k][view,offset:offset+budget['batch_windows']],device='cuda:0') for k in model.PREFIX_KEYS}
                        error,_=model.replay_metrics(model.replay(values,zero(values['h'])).cpu().numpy(),reference[view,offset:offset+budget['batch_windows']]);maximum=max(maximum,error);check()
            del values,zero,reference
            items.append({'ordered':old,'prefix':prefix,'times':times,**{k:row[k] for k in ['sha256','group','target','label_sec']}})
        if maximum>recipe['replay']['same_forward_max_absolute_embedding_error'] or len(items)!=26:raise ValueError('Replay failed')
        atomic_json(OUT/'replay-safe-summary.json',{'status':'PASS','videos':26,'windows':sum(len(i['times']) for i in items),'views':2,'maximum_absolute_error':maximum,'quality_established':False})
        write_progress(run,'fixture',26,26,76);torch.cuda.empty_cache()
        def committed(count):
            write_progress(run,'fixture',26+count,26+count,76)
            check(True)
        original_fit=model.fit;cache=CompletedFits(OUT/'fits',expected,original_fit,committed,maximum=50)
        phase='grouped_oof';tick=time.monotonic()
        with threadpool_limits(limits=2):
            model.fit=cache
            try:summary,private=model.evaluate(items,recipe,check)
            finally:model.fit=original_fit
            if cache.calls!=48 or cache.count()!=48:raise ValueError('OOF fit count changed')
            phase='full_train_diagnostics';full={};costs={}
            for name,enabled in [('regularized_frozen_head',False),('last_layer_adapter',True)]:
                fitted,cost=cache(items,recipe,enabled,check);full[name]=model.training_report(fitted,items,recipe,check);costs[name]=cost
                del fitted;torch.cuda.empty_cache();check()
        phase='final_persistence';check();prior.previous.original.verify(json.loads((prior.previous.OUT/'registration.json').read_text()))
        atomic_json(run/'private-oof-results.json',private,deadline=deadline)
        summary.update(status='completed',protocol_id=cfg['protocol_id'],registration_sha256=expected,split='train',scope='Adaptive exploratory reused-TRAIN grouped OOF; no independent/type/rule acceptance',
                       cv_fits=48,full_train_fits=2,checkpoint_count=cache.count(),full_train_diagnostics=full,full_train_fit_costs=costs,
                       zero_adapter_max_absolute_error=maximum,resources=resources,learning_phase_wall_sec=time.monotonic()-tick,worker_wall_sec=time.monotonic()-started,
                       tune_used=False,holdout_used=False,independent_validation=False,adaptive_exploratory_train=True,release_eligible=False,official_score=False,
                       semantic_types_rules_or_evidence_validated=False,source_split_baseline_and_research_ui_preserved=True,per_video_outputs_emitted=False,cloud_inference_used=False)
        atomic_json(run/'quality-safe-summary.json',summary,deadline=deadline)
        atomic_json(run/'worker-safe-summary.json',ControlSummary(status='completed',completed_cases=76,passed_cases=76,total_cases=76).model_dump(),deadline=deadline)
    except Exception as error:
        save_private_trace(error,run/'private-stack-trace.txt');count=cache.count() if cache else 0
        atomic_json(run/'failure-safe-summary.json',{'status':'failed','phase':phase,'active_fit_ordinal':cache.active_index if cache else None,'completed_fit_checkpoints':count,
                    'diagnostic':safe_exception(error,ROOT,resources),'registration_sha256':expected,'quality_established':False,'tune_used':False,'holdout_used':False,'release_eligible':False})
        atomic_json(run/'worker-safe-summary.json',ControlSummary(status='failed',completed_cases=26+count if cache else 0,passed_cases=26+count if cache else 0,total_cases=76,failure='exception').model_dump());raise SystemExit(1)


def run(expected):
    cfg,_=verify(expected)
    with (OUT/'attempt.json').open('x') as stream:json.dump({'registration_sha256':expected,'one_fixed_checkpointed_pass':True},stream)
    terminal=supervise([sys.executable,str(Path(__file__).resolve()),'worker','--registration-sha256',expected],OUT/'run',cfg['owned_wall_sec'],76,str(ROOT))
    name='quality-safe-summary.json' if terminal['quality_gate_passed'] and terminal['cleanup_complete'] else 'failure-safe-summary.json'
    path=OUT/'run'/name;result=json.loads(path.read_text()) if path.exists() else {'status':'failed','release_eligible':False}
    result['technical_monitor']=terminal;atomic_json(OUT/'safe-summary.json',result);print(json.dumps(result),flush=True)
    if result['status']!='completed':raise SystemExit(1)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['register','run','worker']);parser.add_argument('--registration-sha256');args=parser.parse_args()
    try:
        if args.action=='register':register()
        elif args.action=='run':run(args.registration_sha256)
        else:worker(args.registration_sha256)
    except Exception as error:print(json.dumps({'status':'failed','diagnostic':safe_exception(error,ROOT)}));sys.exit(1)
