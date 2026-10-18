"""One candidate failed-boundary fit, original recipe, no semantic/quality output."""
from pathlib import Path
import argparse, datetime, json, os, sys, time
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from cashreview.supervision import atomic_json, supervise, await_start_gate, ControlSummary
from cashreview.technical_diagnostics import TechnicalGuardError, safe_exception, save_private_trace
from scripts import xclip_last_layer_budget as previous
OUT = ROOT / '.private/xclip-last-layer-diagnostic'
CONFIG = 'config/last-layer-diagnostic.json'
FILES = [CONFIG, 'scripts/last_layer_diagnostic.py', 'cashreview/technical_diagnostics.py', 'tests/test_technical_diagnostics.py']


def prior():
    cfg = json.loads((ROOT / CONFIG).read_text()); previous.configure()
    reg = previous.verified_registration(cfg['prior_registration_sha256'])
    failure = json.loads((previous.OUT / 'safe-summary.json').read_text())
    terminal = json.loads((previous.OUT / 'run/terminal-safe-summary.json').read_text())
    if not (failure['technical_error_type'] == 'RuntimeError' and failure['completed_technical_cases'] - 26 == cfg['completed_cv_fits']
            and terminal['cleanup_complete'] and not terminal['deadline_exceeded']): raise ValueError('Failure boundary changed')
    return cfg, reg


def register():
    import psutil
    cfg, reg = prior(); OUT.mkdir(exist_ok=False)
    record = {'protocol_id': cfg['protocol_id'], 'registered_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'code_sha256': {name: previous.original.sha(ROOT / name) for name in FILES},
              'prior_registration_sha256': cfg['prior_registration_sha256'],
              'prefix_registration_sha256': previous.original.sha(previous.OUT / 'prefix-registration.json'),
              'failure_report_sha256': previous.original.sha(previous.OUT / 'safe-summary.json'),
              'available_ram_before_mib': psutil.virtual_memory().available / 2**20,
              'tune_used': False, 'holdout_used': False}
    atomic_json(OUT / 'registration.json', record)
    print(json.dumps({'registered': True, 'registration_sha256': previous.original.sha(OUT / 'registration.json'),
                      'candidate_fit_ordinal': 38, 'historical_origin_proven': False, 'maximum_attempts': 1}), flush=True)


def verify(expected):
    cfg, reg = prior()
    if previous.original.sha(OUT / 'registration.json') != expected: raise ValueError('Diagnostic registration changed')
    record = json.loads((OUT / 'registration.json').read_text())
    if {name: previous.original.sha(ROOT / name) for name in FILES} != record['code_sha256']: raise ValueError('Diagnostic source changed')
    if previous.original.sha(previous.OUT / 'prefix-registration.json') != record['prefix_registration_sha256']: raise ValueError('Prefix registration changed')
    if previous.original.sha(previous.OUT / 'safe-summary.json') != record['failure_report_sha256']: raise ValueError('Failure report changed')
    return cfg, reg


def worker(expected):
    run, deadline = await_start_gate(); started = time.monotonic(); phase = 'preflight'; resources = {}; checks = 0; torch = None
    minimum_ram = float('inf'); minimum_gpu = float('inf'); last_write = 0.
    try:
        os.environ.update(CUDA_VISIBLE_DEVICES='0', OMP_NUM_THREADS='2', MKL_NUM_THREADS='2', OPENBLAS_NUM_THREADS='2',
                          HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', HF_HUB_DISABLE_TELEMETRY='1', DO_NOT_TRACK='1',
                          CUBLAS_WORKSPACE_CONFIG=':4096:8', TOKENIZERS_PARALLELISM='false')
        import psutil, numpy as np
        cfg, reg = verify(expected); recipe = json.loads((ROOT / previous.CONFIG).read_text()); budget = recipe['budget']
        if psutil.virtual_memory().available / 2**20 < budget['min_available_ram_before_mib']: raise TechnicalGuardError('host_memory_guard')
        from cashreview.offline import deny_network
        deny_network()
        import torch as imported_torch
        torch = imported_torch
        from threadpoolctl import threadpool_limits
        from xclip_candidate.last_layer import PREFIX_KEYS, validate_prefix, replay, Adapter, replay_metrics, fit
        torch.set_num_threads(2); torch.set_num_interop_threads(2); torch.use_deterministic_algorithms(True)
        torch.backends.cudnn.benchmark = False; torch.backends.cudnn.deterministic = True; torch.cuda.reset_peak_memory_stats()
        def check():
            nonlocal resources, checks, minimum_ram, minimum_gpu, last_write
            checks += 1; info = psutil.Process().memory_info(); available = psutil.virtual_memory().available / 2**20
            minimum_ram = min(minimum_ram, available)
            resources = {'elapsed_sec': time.monotonic()-started, 'rss_mib': info.rss/2**20, 'peak_working_set_mib': info.peak_wset/2**20,
                         'available_ram_mib': available, 'minimum_available_ram_mib': minimum_ram, 'check_calls': checks}
            if torch.cuda.is_initialized():
                free, _ = torch.cuda.mem_get_info(); minimum_gpu = min(minimum_gpu, free/2**20)
                resources.update(torch_allocated_mib=torch.cuda.memory_allocated()/2**20, torch_reserved_mib=torch.cuda.memory_reserved()/2**20,
                                 torch_peak_allocated_mib=torch.cuda.max_memory_allocated()/2**20, torch_peak_reserved_mib=torch.cuda.max_memory_reserved()/2**20,
                                 gpu_free_mib=free/2**20, minimum_free_gpu_mib=minimum_gpu)
            caller = sys._getframe(1)
            if caller.f_code is fit.__code__ and type(caller.f_locals.get('step')) is int: resources['optimizer_step'] = caller.f_locals['step']
            if time.monotonic()-last_write >= 5:
                atomic_json(run/'resource-safe-summary.json', {'phase':phase, 'resources':resources}); last_write=time.monotonic()
            if time.monotonic() >= deadline: raise TechnicalGuardError('deadline_guard')
            if available < budget['min_available_ram_during_mib'] or info.peak_wset/2**20 > budget['max_peak_working_set_mib']: raise TechnicalGuardError('host_memory_guard')
            if resources.get('gpu_free_mib', 99999) < budget['min_free_gpu_during_mib'] or resources.get('torch_peak_reserved_mib', 0) > budget['max_torch_reserved_mib']: raise TechnicalGuardError('gpu_memory_guard')
        check()
        if torch.cuda.mem_get_info()[0]/2**20 < budget['min_free_gpu_before_mib']: raise TechnicalGuardError('gpu_memory_guard')
        phase = 'load_and_zero_adapter_replay'; items = []; maximum = 0.
        prefix_reg = json.loads((previous.OUT/'prefix-registration.json').read_text()); rows = previous.original.inputs()[0]
        for row in rows:
            path = previous.OUT/'prefix'/(row['sha256']+'.npz')
            if previous.original.sha(path) != prefix_reg['cache_sha256'][path.name]: raise ValueError('Prefix bytes changed')
            with np.load(path,allow_pickle=False) as cache: prefix = {key:np.array(cache[key]) for key in PREFIX_KEYS}; times=np.array(cache['times']); reference=np.array(cache['reference'])
            with np.load(ROOT/'.private/xclip-control/features'/(row['sha256']+'.npz'),allow_pickle=False) as cache:
                old=np.array(cache['ordered']); old_times=np.array(cache['times'])
            if not np.array_equal(times,old_times): raise ValueError('Saved PTS changed')
            validate_prefix(prefix,len(times)); adapter=Adapter(recipe['model']).to('cuda:0').eval()
            with torch.inference_mode():
                for view in range(2):
                    for offset in range(0,len(times),budget['batch_windows']):
                        values={key:torch.as_tensor(prefix[key][view,offset:offset+budget['batch_windows']],device='cuda:0') for key in PREFIX_KEYS}
                        error,_=replay_metrics(replay(values,adapter(values['h'])).cpu().numpy(),reference[view,offset:offset+budget['batch_windows']]); maximum=max(maximum,error); check()
            del adapter,values,reference
            items.append({'ordered':old,'times':times,'prefix':prefix,**{key:row[key] for key in ['sha256','group','target','label_sec']}})
        if maximum > recipe['replay']['same_forward_max_absolute_embedding_error']: raise ValueError('Saved zero adapter replay mismatch')
        groups=sorted({i['group'] for i in items}); group=groups[cfg['group_ordinal']-1]
        train=[i for i in items if i['group']!=group]
        if len(groups)!=24 or len(items)!=26 or cfg['candidate_next_fit_ordinal'] != cfg['completed_cv_fits']+1: raise ValueError('Fixed diagnostic scope changed')
        torch.cuda.empty_cache(); phase='candidate_next_fit_38_original_recipe'; check()
        with threadpool_limits(limits=2):
            fitted,cost=fit(train,recipe,True,check)
        # No prediction, training report, validation loss or semantic output is requested.
        del fitted; torch.cuda.empty_cache(); check()
        atomic_json(run/'diagnostic-safe-summary.json', {'status':'completed','candidate_fit_completed':True,'optimizer_steps':cost['optimizer_steps'],
                    'zero_adapter_max_absolute_error':maximum,'resources':resources,'historical_failure_origin_proven':False,
                    'quality_established':False,'predictions_or_quality_metrics_computed':False,'tune_used':False,'holdout_used':False,'registration_sha256':expected}, deadline=deadline)
        atomic_json(run/'worker-safe-summary.json',ControlSummary(status='completed',completed_cases=1,passed_cases=1,total_cases=1).model_dump(),deadline=deadline)
    except Exception as error:
        save_private_trace(error,run/'private-stack-trace.txt')
        report={'status':'failed','phase':phase,'diagnostic':safe_exception(error,ROOT,resources),'historical_failure_origin_proven':False,
                'quality_established':False,'predictions_or_quality_metrics_computed':False,'tune_used':False,'holdout_used':False,'registration_sha256':expected}
        atomic_json(run/'diagnostic-safe-summary.json',report)
        atomic_json(run/'worker-safe-summary.json',ControlSummary(status='failed',completed_cases=0,passed_cases=0,total_cases=1,failure='exception').model_dump())
        raise SystemExit(1)


def run(expected):
    cfg,_=verify(expected)
    with (OUT/'attempt.json').open('x') as stream:json.dump({'single_candidate_boundary_diagnostic':True,'registration_sha256':expected},stream)
    terminal=supervise([sys.executable,str(Path(__file__).resolve()),'worker','--registration-sha256',expected],OUT/'run',cfg['owned_wall_sec'],1,str(ROOT))
    result=json.loads((OUT/'run/diagnostic-safe-summary.json').read_text()) if (OUT/'run/diagnostic-safe-summary.json').exists() else {'status':'failed','diagnostic_report_available':False}
    result['technical_monitor']=terminal; atomic_json(OUT/'safe-summary.json',result);print(json.dumps(result),flush=True)
    if result['status']!='completed':raise SystemExit(1)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['register','run','worker']);parser.add_argument('--registration-sha256');args=parser.parse_args()
    try:
        if args.action=='register':register()
        elif args.action=='run':run(args.registration_sha256)
        else:worker(args.registration_sha256)
    except Exception as error:
        print(json.dumps({'status':'failed','diagnostic':safe_exception(error,ROOT),'raw_private_content_emitted':False}));sys.exit(1)
