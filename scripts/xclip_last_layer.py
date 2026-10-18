"""One registered local TRAIN prefix/replay/last-layer experiment; aggregates only."""
from pathlib import Path
import argparse, datetime, hashlib, importlib.metadata as metadata, json, os, subprocess, sys, time
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from cashreview.supervision import atomic_json, supervise, await_start_gate, ControlSummary
OUT = ROOT / '.private/xclip-last-layer-control'
CONFIG = 'config/xclip-last-layer-protocol.json'
FILES = [CONFIG, 'scripts/xclip_last_layer.py', 'xclip_candidate/last_layer.py', 'xclip_candidate/last_layer_cache.py',
         'tests/test_xclip_last_layer.py', 'xclip_candidate/features.py', 'xclip_candidate/temporal_head.py',
         'xclip_candidate/linear_head.py', 'xclip_candidate/evaluate.py', 'scripts/xclip_linear.py', 'scripts/xclip_experiment.py',
         'cashreview/video.py', 'cashreview/research_split.py', 'cashreview/offline.py', 'cashreview/supervision.py', 'cashreview/processes.py',
         'qvt_candidate/evaluate.py', 'gguf_candidate/runtime.py', 'requirements-patched-lock.txt',
         '.private/dataset/manifest.json', '.private/dataset/split.json', '.private/xclip-control/registration.json',
         '.private/xclip-control/feature-registration.json', '.private/xclip-control/safe-summary.json',
         '.private/xclip-experimental-v2/prototypes.json', '.private/xclip-experimental-v2/prototypes.npz',
         'static/research.html', 'static/research.js', 'static/research.css', 'cashreview/api.py', 'scripts/run_xclip_experimental.py',
         'models/xclip-base-patch32/config.json', 'models/xclip-base-patch32/preprocessor_config.json',
         'models/xclip-base-patch32/provenance.json', 'models/xclip-base-patch32/model.safetensors', 'config/xclip-artifacts.json', 'config/xclip-protocol.json']
TOTAL = 76


def sha(path):
    with Path(path).open('rb') as stream: return hashlib.file_digest(stream, 'sha256').hexdigest()


def inputs():
    from scripts.xclip_linear import inputs as verified
    rows, inventory = verified()
    if any(sha(row['path']) != row['sha256'] for row in rows): raise ValueError('Original TRAIN source changed')
    return rows, inventory


def verify(registration):
    if {name: sha(ROOT / name) for name in FILES} != registration['code_sha256']: raise ValueError('Frozen experiment source changed')
    if {name: metadata.version(name) for name in registration['versions']} != registration['versions']: raise ValueError('Runtime changed')
    rows, inventory = inputs()
    if inventory != registration['cache_sha256'] or [r['sha256'] for r in rows] != registration['source_sha256']: raise ValueError('Frozen TRAIN inputs changed')
    return rows


def register():
    import psutil
    cfg = json.loads((ROOT / CONFIG).read_text()); OUT.mkdir(exist_ok=True)
    if (OUT / 'registration.json').exists(): raise RuntimeError('No registration overwrite')
    available = psutil.virtual_memory().available / 2**20
    if available < cfg['budget']['min_available_ram_before_mib']: raise RuntimeError('RAM preflight refused')
    result = subprocess.run(['nvidia-smi', '--query-gpu=memory.total,memory.free', '--format=csv,noheader,nounits'],
                            capture_output=True, text=True, timeout=10, creationflags=subprocess.CREATE_NO_WINDOW, check=True)
    lines = result.stdout.strip().splitlines()
    if len(lines) != 1: raise ValueError('One selected GPU required')
    total, free = (int(x.strip()) for x in lines[0].split(','))
    if free < cfg['budget']['min_free_gpu_before_mib'] or total < cfg['budget']['max_torch_reserved_mib']: raise RuntimeError('GPU preflight refused')
    rows, inventory = inputs()
    record = {'protocol_id': cfg['protocol_id'], 'registered_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'code_sha256': {name: sha(ROOT / name) for name in FILES}, 'source_sha256': [r['sha256'] for r in rows],
              'cache_sha256': inventory, 'versions': {name: metadata.version(name) for name in ['torch', 'transformers', 'av', 'numpy', 'scikit-learn', 'safetensors', 'threadpoolctl', 'Pillow', 'psutil']},
              'train_videos': 26, 'groups': 24, 'available_ram_mib': available, 'gpu_total_mib': total, 'gpu_free_mib': free,
              'adaptive_exploratory_train': True, 'independent_validation': False, 'tune_used': False, 'holdout_used': False}
    with (OUT / 'registration.json').open('x') as stream: json.dump(record, stream, indent=2)
    print(json.dumps({'registered': True, 'protocol_id': cfg['protocol_id'], 'registration_sha256': sha(OUT / 'registration.json'),
                      'available_ram_mib': available, 'gpu_free_mib': free, 'worker_processes': 1, 'tune_used': False, 'holdout_used': False}), flush=True)


def worker():
    run, deadline = await_start_gate(); start = time.monotonic(); phase = 'preflight'; completed = 0; torch = None
    try:
        os.environ.update(CUDA_VISIBLE_DEVICES='0', OMP_NUM_THREADS='2', MKL_NUM_THREADS='2', OPENBLAS_NUM_THREADS='2',
                          HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', HF_HUB_DISABLE_TELEMETRY='1', DO_NOT_TRACK='1',
                          CUBLAS_WORKSPACE_CONFIG=':4096:8', TOKENIZERS_PARALLELISM='false')
        import psutil, numpy as np
        cfg = json.loads((ROOT / CONFIG).read_text()); budget = cfg['budget']; minimum = float('inf'); minimum_gpu = float('inf')
        phase_deadline = deadline
        def check():
            nonlocal minimum, minimum_gpu
            if time.monotonic() >= min(deadline, phase_deadline): raise TimeoutError('Registered phase or owned wall budget exceeded')
            memory = psutil.Process().memory_info(); available = psutil.virtual_memory().available / 2**20; minimum = min(minimum, available)
            if available < budget['min_available_ram_during_mib'] or memory.peak_wset / 2**20 > budget['max_peak_working_set_mib']:
                raise RuntimeError('Registered host memory budget exceeded')
            if torch is not None and torch.cuda.is_initialized():
                free, _ = torch.cuda.mem_get_info(); minimum_gpu = min(minimum_gpu, free / 2**20)
                if free / 2**20 < budget['min_free_gpu_during_mib'] or torch.cuda.max_memory_reserved() / 2**20 > budget['max_torch_reserved_mib']:
                    raise RuntimeError('Registered GPU memory budget exceeded')
        if psutil.virtual_memory().available / 2**20 < budget['min_available_ram_before_mib']: raise RuntimeError('RAM preflight refused')
        registration = json.loads((OUT / 'registration.json').read_text()); rows = verify(registration); check()
        from cashreview.offline import deny_network
        deny_network()
        import torch as imported_torch
        torch = imported_torch
        from threadpoolctl import threadpool_limits
        from xclip_candidate.features import Encoder
        from xclip_candidate.last_layer_cache import extract, ReplayMismatch
        from xclip_candidate.last_layer import PREFIX_KEYS, replay, Adapter, evaluate, fit, training_report, validate_prefix, validate_embeddings, replay_metrics
        from safetensors.torch import save_file
        import gc
        torch.set_num_threads(2); torch.set_num_interop_threads(2); torch.use_deterministic_algorithms(True)
        torch.backends.cudnn.benchmark = False; torch.backends.cudnn.deterministic = True
        torch.cuda.reset_peak_memory_stats()
        if torch.cuda.mem_get_info()[0] / 2**20 < budget['min_free_gpu_before_mib']: raise RuntimeError('GPU preflight refused')
        check(); phase = 'prefix_and_zero_adapter_replay'; phase_start = time.monotonic(); phase_deadline = phase_start + budget['prefix_phase_wall_sec']
        encoder = Encoder(ROOT, json.loads((ROOT / 'config/xclip-protocol.json').read_text()), check)
        directory = OUT / 'prefix'; directory.mkdir(exist_ok=False); inventory = {}; stats = []; items = []
        for row in rows:
            check()
            with np.load(ROOT / '.private/xclip-control/features' / (row['sha256'] + '.npz'), allow_pickle=False) as cache:
                old = np.array(cache['ordered']); times = np.array(cache['times'])
            prefix, technical = extract(encoder, row['path'], old, times, cfg, check)
            path = directory / (row['sha256'] + '.npz'); np.savez_compressed(path, **prefix); inventory[path.name] = sha(path)
            # Actual persisted bytes are reloaded for all subsequent replay/training.
            with np.load(path, allow_pickle=False) as cache:
                loaded = {key: np.array(cache[key]) for key in PREFIX_KEYS}; references = np.array(cache['reference']); saved_times = np.array(cache['times'])
            if not np.array_equal(times, saved_times): raise ValueError('Persisted PTS mismatch')
            validate_prefix(loaded, len(times))
            if references.shape != (2, len(times), 512): raise ValueError('Persisted reference shape mismatch')
            for view in range(2): validate_embeddings(references[view])
            zero = Adapter(cfg['model']).to('cuda:0').eval()
            with torch.inference_mode():
                for view in range(2):
                    for offset in range(0, len(times), budget['batch_windows']):
                        values = {key: torch.as_tensor(loaded[key][view, offset:offset + budget['batch_windows']], device='cuda:0') for key in PREFIX_KEYS}
                        reference = torch.as_tensor(references[view, offset:offset + budget['batch_windows']], device='cuda:0')
                        error, _ = replay_metrics(replay(values, zero(values['h'])).cpu().numpy(), reference.cpu().numpy())
                        technical['same_forward_replay_max_absolute_error'] = max(error, technical['same_forward_replay_max_absolute_error'])
                        if error > cfg['replay']['same_forward_max_absolute_embedding_error']: raise ReplayMismatch('persisted_cache', maximum_absolute_error=error)
                        check()
            del zero, values, reference, prefix, references
            item = {'ordered': old, 'times': times, 'prefix': loaded, **{key: row[key] for key in ['sha256', 'group', 'target', 'label_sec']}}
            items.append(item); stats.append(technical); completed += 1
            print(json.dumps({'phase': phase, 'completed_train_prefixes': completed, 'total_train_prefixes': 26, 'semantic_outputs_emitted': False}), flush=True)
        replay_summary = {'status': 'PASS', 'windows': sum(r['windows'] for r in stats), 'views': 2, 'videos': 26,
                          'same_forward_max_absolute_embedding_error': max(r['same_forward_replay_max_absolute_error'] for r in stats),
                          'historical_original_max_absolute_embedding_error': max(r['historical_original_max_absolute_error'] for r in stats),
                          'historical_original_minimum_cosine': min(r['historical_original_minimum_cosine'] for r in stats),
                          'maximum_pts_grid_error_sec': max(r['maximum_pts_grid_error_sec'] for r in stats),
                          'phase_wall_sec': time.monotonic() - phase_start, 'training_started': False, 'zero_adapter_replay_is_not_ml_quality': True}
        if replay_summary['windows'] != 678: raise ValueError('Fixed TRAIN window count changed')
        atomic_json(OUT / 'prefix-registration.json', {'registration_sha256': sha(OUT / 'registration.json'), 'cache_sha256': inventory, 'replay_passed_before_training': True}, deadline=deadline)
        atomic_json(OUT / 'replay-safe-summary.json', replay_summary, deadline=deadline)
        print(json.dumps({'zero_adapter_replay': replay_summary}), flush=True)
        del encoder; gc.collect(); torch.cuda.empty_cache(); check()
        if any(sha(directory / name) != digest for name, digest in inventory.items()): raise ValueError('Prefix cache changed before CV')
        verify(registration); check(); phase = 'fixed_group_oof_and_full_train'; phase_start = time.monotonic(); phase_deadline = phase_start + budget['learning_phase_wall_sec']
        def progress(count):
            nonlocal completed
            completed = 26 + count; check()
            print(json.dumps({'phase': phase, 'completed_cv_fits': count, 'total_cv_fits': 48, 'semantic_outputs_emitted': False}), flush=True)
        with threadpool_limits(limits=2):
            summary, private = evaluate(items, cfg, check, progress); full = {}; full_cost = {}
            for name, enabled in [('regularized_frozen_head', False), ('last_layer_adapter', True)]:
                fitted, cost = fit(items, cfg, enabled, check); full[name] = training_report(fitted, items, cfg, check); full_cost[name] = cost
                if enabled:
                    folder = OUT / 'final-train-pack'; folder.mkdir(exist_ok=False)
                    np.savez_compressed(folder / 'projection.npz', mean=fitted[0][0], basis=fitted[0][1])
                    save_file({('head.' + key): value.detach().cpu().contiguous() for key, value in fitted[1].state_dict().items()} |
                              {('adapter.' + key): value.detach().cpu().contiguous() for key, value in fitted[2].state_dict().items()}, str(folder / 'head-adapter.safetensors'))
                    atomic_json(folder / 'metadata.json', {'registration_sha256': sha(OUT / 'registration.json'),
                                'projection_sha256': sha(folder / 'projection.npz'), 'head_adapter_sha256': sha(folder / 'head-adapter.safetensors'),
                                'adapter_parameters': 5120, 'head_parameters': 209, 'type': 'unverified', 'rule': 'not_assessed', 'release_eligible': False}, deadline=deadline)
                del fitted; torch.cuda.empty_cache(); completed += 1; check()
        learning_sec = time.monotonic() - phase_start; check(); phase = 'final_integrity_and_persistence'; phase_deadline = deadline
        verify(registration)
        if any(sha(directory / name) != digest for name, digest in inventory.items()): raise ValueError('Prefix cache changed after CV')
        check(); atomic_json(run / 'private-oof-results.json', private, deadline=deadline)
        summary.update(status='completed', protocol_id=cfg['protocol_id'], split='train', scope=cfg['scope'],
                       train_videos=26, groups=24, cv_fits=48, full_train_fits=2, fixed_optimizer_steps=500,
                       replay=replay_summary, full_train_diagnostics=full, full_train_fit_costs=full_cost, learning_phase_wall_sec=learning_sec,
                       worker_wall_sec=time.monotonic() - start, torch_peak_reserved_mib=torch.cuda.max_memory_reserved() / 2**20,
                       process_peak_working_set_mib=psutil.Process().memory_info().peak_wset / 2**20,
                       minimum_available_system_ram_mib=minimum, minimum_free_gpu_mib=minimum_gpu,
                       adaptive_exploratory_train=True, independent_validation=False, tune_used=False, holdout_used=False,
                       source_split_baseline_and_research_ui_preserved=True, cloud_inference_used=False, per_video_outputs_emitted=False,
                       semantic_types_rules_or_evidence_validated=False, release_eligible=False, official_score=False,
                       registration_sha256=sha(OUT / 'registration.json'))
        atomic_json(run / 'quality-safe-summary.json', summary, deadline=deadline)
        atomic_json(run / 'worker-safe-summary.json', ControlSummary(status='completed', completed_cases=TOTAL, passed_cases=TOTAL, total_cases=TOTAL).model_dump(), deadline=deadline); check()
    except Exception as error:
        (run / 'quality-safe-summary.json').unlink(missing_ok=True); (run / 'worker-safe-summary.json').unlink(missing_ok=True)
        technical = {}
        if 'ReplayMismatch' in locals() and isinstance(error, ReplayMismatch):
            technical = {'safe_replay_error_code': error.safe_code, 'aggregate_replay_diagnostic': error.safe_technical_values}
        atomic_json(run / 'failure-safe-summary.json', {'status': 'failed', 'phase': phase, 'technical_error_type': type(error).__name__, **technical,
                    'completed_technical_cases': completed, 'model_quality_established': False, 'tune_used': False, 'holdout_used': False,
                    'raw_private_content_emitted': False, 'repeat_authorized': False})
        atomic_json(run / 'worker-safe-summary.json', ControlSummary(status='failed', completed_cases=completed, passed_cases=completed, total_cases=TOTAL, failure='exception').model_dump())
        raise SystemExit(1)


def run():
    cfg = json.loads((ROOT / CONFIG).read_text()); verify(json.loads((OUT / 'registration.json').read_text()))
    with (OUT / 'attempt.json').open('x') as stream: json.dump({'started_utc': datetime.datetime.now(datetime.timezone.utc).isoformat()}, stream)
    terminal = supervise([sys.executable, str(Path(__file__).resolve()), 'worker'], OUT / 'run', cfg['budget']['owned_wall_sec'], TOTAL, str(ROOT))
    print(json.dumps({'technical_monitor': terminal}), flush=True)
    if terminal['quality_gate_passed'] and terminal['cleanup_complete']:
        summary = json.loads((OUT / 'run/quality-safe-summary.json').read_text()); summary['technical_monitor_validated'] = True
    else:
        summary = {'status': 'failed', 'technical_monitor_validated': False, 'release_eligible': False, 'repeat_authorized': False}
        path = OUT / 'run/failure-safe-summary.json'
        if path.exists(): summary.update(json.loads(path.read_text()))
    atomic_json(OUT / 'safe-summary.json', summary); print(json.dumps(summary), flush=True)
    if summary['status'] != 'completed': raise SystemExit(1)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('action', choices=['register', 'run', 'worker']); args = parser.parse_args()
    try: globals()[args.action]()
    except Exception as error:
        print(json.dumps({'status': 'failed', 'technical_error_type': type(error).__name__, 'raw_private_content_emitted': False})); sys.exit(1)
