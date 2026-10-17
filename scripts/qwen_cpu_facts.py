"""One owned CPU-backend primitive control; generated inputs, aggregate output."""
from pathlib import Path
import datetime
import hashlib
import json
import os
import subprocess
import sys
import threading
import time
import psutil

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from cashreview.supervision import supervise, await_start_gate, ControlSummary, atomic_json, write_progress
from xclip_candidate.experimental import sha
from scripts.qwen_text_discrimination import SyntheticClient, bounded_json
from scripts.qwen_decomposition import record_cell, revoke as revoke_base

OUT = ROOT / '.private/qwen-cpu-facts'
FILES = ['config/qwen-cpu-facts-protocol.json', 'hybrid_candidate/cpu_facts.py', 'scripts/qwen_cpu_facts.py', 'tests/test_cpu_facts.py',
         'hybrid_candidate/decomposition.py', 'scripts/qwen_decomposition.py', 'hybrid_candidate/discrimination.py',
         'scripts/qwen_text_discrimination.py', 'hybrid_candidate/action_controls.py', 'gguf_candidate/runtime.py',
         'scripts/hybrid_experiment.py', 'cashreview/supervision.py', 'config/gguf-artifacts.json', 'requirements-patched-lock.txt']


def expected_digest(cfg):
    from hybrid_candidate.decomposition import expected
    return hashlib.sha256(json.dumps([expected(a, c, cfg) for a in cfg['actions'] for c in cfg['text_cells'] + [cfg['visual_cell']]], sort_keys=True).encode('ascii')).hexdigest()


def request_digest(cfg):
    from hybrid_candidate.decomposition import body
    from hybrid_candidate.cpu_facts import visual_body
    requests = [body(a, c, cfg) for a in cfg['actions'] for c in cfg['text_cells']]
    requests += [visual_body(a, cfg) for a in cfg['actions']]
    return hashlib.sha256(json.dumps(requests, sort_keys=True).encode('utf-8')).hexdigest()


def revoke(summary, error_type):
    revoke_base(summary, error_type)
    summary.update(text_gate_passed=None, visual_gate_passed=None, image_semantics_status='NOT_ASSESSED_TECHNICAL_FAILURE')


def verify(record):
    from scripts.hybrid_experiment import native_identity
    if {name: sha(ROOT / name) for name in FILES} != record['code_sha256']:
        raise ValueError('Frozen CPU control source changed')
    if native_identity() != record['native_artifact_sha256']:
        raise ValueError('Native identity changed')
    if expected_digest(json.loads((ROOT / FILES[0]).read_text())) != record['expected_answer_sha256']:
        raise ValueError('Expected synthetic answers changed')
    if request_digest(json.loads((ROOT / FILES[0]).read_text())) != record['request_body_sha256']:
        raise ValueError('Frozen synthetic request bodies changed')


def register():
    from scripts.hybrid_experiment import native_identity
    cfg = json.loads((ROOT / FILES[0]).read_text())
    if len(cfg['actions']) * len(cfg['text_cells']) != 6 or cfg['budget']['max_calls'] != 9:
        raise ValueError('Frozen count mismatch')
    OUT.mkdir(exist_ok=True)
    record = {'protocol_id': cfg['protocol_id'], 'registered_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'code_sha256': {name: sha(ROOT / name) for name in FILES}, 'native_artifact_sha256': native_identity(),
              'expected_answer_sha256': expected_digest(cfg), 'request_body_sha256': request_digest(cfg), 'runs_allowed': 1}
    with (OUT / 'registration.json').open('x') as stream:
        json.dump(record, stream, indent=2)
    print(json.dumps({'registered': True, 'registration_sha256': sha(OUT / 'registration.json'), 'model_started': False}))


class ControlClient(SyntheticClient):
    def request(self, method, path, **kwargs):
        if (method, path) not in {('GET', '/health'), ('POST', '/v1/chat/completions')}:
            raise ValueError('Non-control endpoint rejected')
        if path == '/v1/chat/completions' and self.generation_calls >= 9:
            raise ValueError('Frozen call limit')
        return super().request(method, path, **kwargs)


def native_args(server, cfg):
    c, b = cfg['inference'], cfg['backend']
    if (b['device'], b['mmproj_device'], b['gpu_layers']) != ('none', 'none', '0'):
        raise ValueError('Only the registered requested CPU backend is allowed')
    return [str(server.exe), '--offline', '--model', str(server.models['text']), '--mmproj', str(server.models['projector']),
            '--device', b['device'], '--mmproj-device', b['mmproj_device'], '--gpu-layers', b['gpu_layers'], '--fit', 'off',
            '--ctx-size', str(c['ctx_size']), '--parallel', '1', '--threads', str(b['threads']), '--batch-size', '512', '--ubatch-size', '128',
            '--image-min-tokens', str(c['image_min_tokens']), '--image-max-tokens', str(c['image_max_tokens']), '--mtmd-batch-max-tokens', '512',
            '--host', '127.0.0.1', '--port', str(server.port), '--no-webui', '--no-agent', '--no-ui-mcp-proxy',
            '--cors-origins', 'http://127.0.0.1', '--no-cors-credentials', '--api-key', 'temporary-local-native-test-only', '--log-disable']


def start_native(server, cfg, deadline):
    args = native_args(server, cfg)
    env = {k: v for k, v in os.environ.items() if not k.startswith(('LLAMA_', 'MTMD_', 'HF_')) and k not in ['CASH_API_KEY', 'OPENAI_API_KEY', 'ANTHROPIC_API_KEY']}
    env['PATH'] = str(server.exe.parent) + os.pathsep + env.get('PATH', '')
    tick = time.monotonic()
    server.process = subprocess.Popen(args, cwd=server.exe.parent, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
    limit = min(deadline, tick + cfg['budget']['startup_sec'])
    while time.monotonic() < limit:
        if server.process.poll() is not None:
            raise RuntimeError('Native startup exited')
        try:
            if server.client.get(server.base + '/health', timeout=min(1., max(.001, limit-time.monotonic()))).status_code == 200:
                if time.monotonic() >= limit:
                    raise TimeoutError('Late native readiness')
                return time.monotonic() - tick
        except Exception:
            pass
        time.sleep(.1)
    raise TimeoutError('Bounded native readiness failed')


class MemoryMeter:
    def __init__(self, server):
        self.server = server
        self.stop_event = threading.Event()
        self.native = []
        self.worker = []
        self.available = []
        self.thread = None

    def start(self):
        def loop():
            while not self.stop_event.is_set():
                try:
                    self.worker.append(psutil.Process().memory_info().rss)
                    self.available.append(psutil.virtual_memory().available)
                    if self.server.process and self.server.process.poll() is None:
                        self.native.append(psutil.Process(self.server.process.pid).memory_info().rss)
                except psutil.Error:
                    pass
                self.stop_event.wait(.5)
        self.thread = threading.Thread(target=loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(3)
        if self.thread and self.thread.is_alive():
            raise RuntimeError('Memory meter cleanup failed')
        return {'native_rss_peak_bytes': max(self.native) if self.native else None,
                'worker_rss_peak_bytes': max(self.worker) if self.worker else None,
                'system_available_ram_min_bytes': min(self.available) if self.available else None,
                'native_rss_samples': len(self.native), 'ram_scope': 'Sampled resident sets separately, not committed memory; system availability includes other processes'}


def execute(server, action, case, cfg, deadline, row, hashes, visual=False):
    from hybrid_candidate.decomposition import body, score, KEYS
    from hybrid_candidate.cpu_facts import visual_body, derive_state
    from hybrid_candidate.discrimination import extract_response, no_duplicate_keys
    request = visual_body(action, cfg) if visual else body(action, case, cfg)
    row['attempted'] += 1
    tick = time.monotonic()
    stop = min(deadline, tick + cfg['inference']['image_request_sec' if visual else 'per_request_sec'])
    hashes.add(hashlib.sha256(json.dumps(request['messages'], sort_keys=True).encode('utf-8')).hexdigest())
    value = bounded_json(server, 'POST', '/v1/chat/completions', stop, request)
    text, finish, usage = extract_response(value)
    result = score(text, finish, action, case, cfg)
    if time.monotonic() >= stop:
        raise TimeoutError('Late parsed CPU control response')
    row['completed'] += 1
    for key in ['correct', 'valid_format', 'stop', 'truncated', 'field_correct']:
        row[key] += int(result[key])
    for key, match in result['field_matches'].items():
        row['field_correct_by_name'][key] += match
    if case['family'] == 'facts':
        if result['fact_code'] is not None:
            row['fact_histogram'][result['fact_code']] += 1
        else:
            row['fact_invalid_format'] += 1
        row['derived_state_correct'] += int(result['valid_format'] and finish == 'stop' and derive_state(json.loads(text, object_pairs_hook=no_duplicate_keys)) == action)
    else:
        row['label_histogram'][result['label'] or 'INVALID'] += 1
        row['confusion_rows_exit_enter_stay_cols_exit_enter_stay_invalid'][cfg['actions'].index(action)][cfg['actions'].index(result['semantic']) if result['semantic'] else 3] += 1
    if all(type(usage[k]) is int and usage[k] >= 0 for k in usage):
        row['input_tokens_sum'] += usage['prompt_tokens']
        row['output_tokens_sum'] += usage['completion_tokens']
    else:
        row['usage_missing'] += 1
    elapsed = time.monotonic() - tick
    row['latency_sec_sum'] += elapsed
    row['latency_sec_max'] = max(row['latency_sec_max'], elapsed)


def text_gate(cells):
    return all(cells[name]['completed'] == cells[name]['correct'] == cells[name]['valid_format'] == cells[name]['stop'] == 3
               and cells[name]['truncated'] == cells[name]['technical_errors'] == 0 for name in ['numeric_facts', 'symbolic_binding']) and cells['numeric_facts']['field_correct'] == 9


def semantic_status(cells):
    return 'assessed_synthetic_only' if all(row['truncated'] == row['technical_errors'] == 0 and row['valid_format'] == row['completed'] for row in cells.values()) else 'PARTIAL_FORMAT_OR_TRUNCATION'


def publish_progress(run, visual=False):
    write_progress(run, 'synthetic_visual' if visual else 'synthetic_text', 0, 0, 1)


def worker():
    run, deadline = await_start_gate()
    tick = time.monotonic()
    server = meter = ram = None
    active = None
    cells = {}
    summary = {}
    report = ControlSummary(status='failed', completed_cases=0, passed_cases=0, total_cases=1, failure='exception')
    try:
        from gguf_candidate.runtime import NativeServer, DeviceMeter
        cfg = json.loads((ROOT / FILES[0]).read_text())
        registration = json.loads((OUT / 'registration.json').read_text())
        verify(registration)
        cells = {c['id']: dict(record_cell(), derived_state_correct=0) for c in cfg['text_cells'] + [cfg['visual_cell']]}
        meter = DeviceMeter()
        meter.start()
        server = NativeServer(run / 'native', image_max_tokens=1024)
        server.client = ControlClient(server.client, server.base)
        ram = MemoryMeter(server)
        ram.start()
        load = start_native(server, cfg, deadline)
        phase_start = time.monotonic()
        hashes = set()
        for index, action in enumerate(cfg['actions']):
            order = cfg['text_cells'][index % 2:] + cfg['text_cells'][:index % 2]
            for case in order:
                active = case['id']
                execute(server, action, case, cfg, deadline, cells[active], hashes)
                active = None
                atomic_json(run / 'aggregate-progress-safe-summary.json', {'split': 'synthetic', 'cells': cells, 'raw_responses_saved': False})
                publish_progress(run)
        text_elapsed = time.monotonic() - phase_start
        gate = text_gate(cells)
        image_elapsed = 0.
        if gate:
            phase_start = time.monotonic()
            for action in cfg['actions']:
                active = cfg['visual_cell']['id']
                execute(server, action, cfg['visual_cell'], cfg, deadline, cells[active], hashes, visual=True)
                active = None
                atomic_json(run / 'aggregate-progress-safe-summary.json', {'split': 'synthetic', 'cells': cells, 'raw_responses_saved': False})
                publish_progress(run, visual=True)
            image_elapsed = time.monotonic() - phase_start
        verify(registration)
        visual = cells['visual_facts']
        passed = gate and visual['correct'] == visual['derived_state_correct'] == visual['stop'] == 3
        summary = {'split': 'synthetic', 'status': 'completed', 'protocol_id': cfg['protocol_id'], 'cells': cells,
                   'text_gate_passed': gate, 'visual_gate_passed': passed if gate else None,
                   'semantic_status': semantic_status(cells), 'image_semantics_status': semantic_status({'visual_facts': visual}) if gate else 'NOT_RUN_TEXT_GATE_FAILED',
                   'compound_quality_assertion_passed': passed, 'calls_completed': sum(c['completed'] for c in cells.values()),
                   'generation_calls_attempted': server.client.generation_calls, 'unique_request_message_hash_count': len(hashes),
                   'native_load_sec': load, 'text_phase_sec': text_elapsed, 'image_phase_sec': image_elapsed,
                   'requested_cpu_backend': True, 'effective_backend_implementation_independently_verified': False,
                   'direct_label_classification_run': False, 'raw_responses_prompts_or_logs_saved': False,
                   'bank_notes_train_tune_or_holdout_read': False, 'causal_backend_or_bank_quality_claim': False,
                   'monitor_scope': 'One compound assertion; not model call count'}
        report = ControlSummary(status='completed', completed_cases=1, passed_cases=int(passed), total_cases=1)
    except Exception as error:
        if active in cells:
            cells[active]['technical_errors'] += 1
        summary = {'split': 'synthetic', 'cells': cells, 'calls_completed': sum(c['completed'] for c in cells.values()), 'raw_private_content_emitted': False}
        revoke(summary, type(error).__name__)
    finally:
        before = after = None
        requested = clean = False
        if server:
            before = server.process.poll() if server.process else None
            requested = server.process is not None and before is None
            try:
                server.close()
                after = server.process.wait(timeout=3) if server.process else None
                clean = server.process is None or after is not None
            except Exception:
                revoke(summary, 'NativeCleanupError')
                report = ControlSummary(status='failed', completed_cases=0, passed_cases=0, total_cases=1, failure='exception')
            if before is not None:
                revoke(summary, 'NativeExitedBeforeCleanup')
                report = ControlSummary(status='failed', completed_cases=0, passed_cases=0, total_cases=1, failure='server_exit' if before else 'exception', server_exit_code=before)
        for observer in [ram, meter]:
            if observer:
                try:
                    summary.update(observer.stop())
                except Exception:
                    revoke(summary, 'ResourceMeterError')
                    report = ControlSummary(status='failed', completed_cases=0, passed_cases=0, total_cases=1, failure='exception')
        summary.update(native_exit_before_cleanup=before, native_exit_after_cleanup=after, native_shutdown_requested=requested,
                       native_cleanup_complete=clean, worker_elapsed_including_cleanup_sec=time.monotonic()-tick)
    atomic_json(run / 'cpu-facts-safe-summary.json', summary)
    atomic_json(run / 'worker-safe-summary.json', report.model_dump())
    if report.status != 'completed':
        raise SystemExit(1)


if __name__ == '__main__':
    try:
        action = sys.argv[1]
        if action == 'register':
            register()
        elif action == 'worker':
            worker()
        elif action == 'run':
            terminal = supervise([sys.executable, str(Path(__file__).resolve()), 'worker'], OUT / 'run', 480, 1, str(ROOT))
            print(json.dumps({'technical_monitor': terminal}), flush=True)
            if terminal['status'] != 'completed':
                raise SystemExit(1)
            summary = json.loads((OUT / 'run/cpu-facts-safe-summary.json').read_text())
            summary['technical_monitor_validated'] = True
            atomic_json(OUT / 'safe-summary.json', summary)
            print(json.dumps(summary), flush=True)
        else:
            raise ValueError('Unknown action')
    except Exception as error:
        print(json.dumps({'status': 'not_started_or_failed', 'technical_error_type': type(error).__name__, 'raw_private_content_emitted': False}))
        sys.exit(1)
