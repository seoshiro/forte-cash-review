"""One visual-first control, then conditional fixed TRAIN proxy pilot. Safe output."""
from pathlib import Path
import datetime
import hashlib
import importlib.metadata
import json
import os
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', HF_HUB_DISABLE_TELEMETRY='1', DO_NOT_TRACK='1')
from cashreview.supervision import supervise, await_start_gate, ControlSummary, atomic_json, write_progress

OUT = ROOT / '.private/internvl-control'
MODEL = ROOT / 'models/internvl3_5-1b-hf'
FILES = ['config/internvl-protocol.json', 'config/internvl-artifacts.json', 'internvl_candidate/fixtures.py',
         'internvl_candidate/runtime.py', 'scripts/internvl_experiment.py', 'tests/test_internvl_control.py',
         'scripts/internvl_processor_preflight.py',
         'cashreview/video.py', 'cashreview/research_split.py', 'cashreview/offline.py', 'cashreview/supervision.py', 'requirements-patched-lock.txt']


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def inventory():
    provenance = json.loads((MODEL / 'provenance.json').read_text())
    cfg = json.loads((ROOT / 'config/internvl-artifacts.json').read_text())
    if provenance['revision'] != cfg['revision'] or provenance['weight_license'] != 'apache-2.0':
        raise ValueError('Model provenance mismatch')
    expected = {row['filename']: row for row in cfg['artifacts']}
    if len(expected) != len(cfg['artifacts']) or set(provenance['artifact_sha256']) != set(expected) | {'official-model-card.md'}:
        raise ValueError('Model provenance inventory is incomplete or extra')
    if {p.name for p in MODEL.iterdir()} != set(expected) | {'provenance.json'}:
        raise ValueError('Unexpected load-affecting model directory contents')
    for name, row in expected.items():
        if (MODEL / name).stat().st_size != row['bytes'] or (row['sha256'] is not None and row['sha256'] != provenance['artifact_sha256'][name]):
            raise ValueError('Pinned artifact size or official digest differs')
    result = {}
    for name, expected in provenance['artifact_sha256'].items():
        path = ROOT / '.private/internvl-prepare' / name if name == 'official-model-card.md' else MODEL / name
        if sha(path) != expected:
            raise ValueError('Model artifact identity mismatch')
        result[str(path.relative_to(ROOT))] = expected
    result[str((MODEL / 'provenance.json').relative_to(ROOT))] = sha(MODEL / 'provenance.json')
    return result


def synthetic_cases():
    return [(0, 'EXIT'), (0, 'ENTER'), (0, 'STAY'), (0, None),
            (1, 'STAY'), (1, 'ENTER'), (1, 'EXIT'), (1, None)]


def synthetic_digest(cfg):
    from internvl_candidate.fixtures import frames, prompt
    digest = hashlib.sha256()
    for layout, state in synthetic_cases():
        digest.update(prompt(layout).encode('utf-8'))
        digest.update((state or 'UNKNOWN').encode('ascii'))
        for image in frames(state, layout, cfg) if state else []:
            digest.update(image.tobytes())
    return digest.hexdigest()


def register():
    from cashreview.research_split import unique_train_contents
    from internvl_candidate.fixtures import pilot_selection
    cfg = json.loads((ROOT / FILES[0]).read_text())
    processor_check = json.loads((ROOT / '.private/internvl-prepare/processor-native-kwargs-safe-summary.json').read_text())
    if processor_check['status'] != 'processor_verified_no_model_forward' or [r['observed_image_tokens'] for r in processor_check['conditions']] != [0, 1024, 2048]:
        raise ValueError('Native processor prerequisite not verified')
    rows = unique_train_contents(json.loads((ROOT / '.private/dataset/manifest.json').read_text(encoding='utf-8')))
    selected = pilot_selection(rows)
    if len(selected) != cfg['pilot']['sources']:
        raise ValueError('Pilot count mismatch')
    OUT.mkdir(exist_ok=True)
    record = {'protocol_id': cfg['protocol_id'], 'registered_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'code_sha256': {name: sha(ROOT / name) for name in FILES}, 'model_artifact_sha256': inventory(),
              'manifest_sha256': sha(ROOT / '.private/dataset/manifest.json'), 'split_sha256': sha(ROOT / '.private/dataset/split.json'),
              'pilot_sources': selected, 'synthetic_input_and_expected_sha256': synthetic_digest(cfg),
              'versions': {name: importlib.metadata.version(name) for name in ['torch', 'transformers', 'numpy', 'pillow', 'av']},
              'runs_allowed': 1}
    with (OUT / 'registration.json').open('x') as stream:
        json.dump(record, stream, indent=2)
    print(json.dumps({'registered': True, 'registration_sha256': sha(OUT / 'registration.json'),
                      'synthetic_controls': len(synthetic_cases()), 'conditional_train_sources': len(selected), 'model_started': False}))


def verify(record):
    if {name: sha(ROOT / name) for name in FILES} != record['code_sha256'] or inventory() != record['model_artifact_sha256']:
        raise ValueError('Frozen code/model artifacts changed')
    if sha(ROOT / '.private/dataset/manifest.json') != record['manifest_sha256'] or sha(ROOT / '.private/dataset/split.json') != record['split_sha256']:
        raise ValueError('Frozen dataset metadata changed')
    if synthetic_digest(json.loads((ROOT / FILES[0]).read_text())) != record['synthetic_input_and_expected_sha256']:
        raise ValueError('Frozen synthetic inputs changed')


def synthetic_gate(rows):
    return (rows['visual']['completed'] == rows['visual']['correct'] == rows['visual']['valid_format'] == rows['visual']['normal_eos'] == 6
            and rows['no_image']['completed'] == rows['no_image']['correct'] == rows['no_image']['valid_format'] == rows['no_image']['normal_eos'] == 2)


def pilot_summary(rows):
    table = [[0, 0, 0], [0, 0, 0]]  # Ground-truth binary label x YES/NO/UNKNOWN.
    errors = []
    for row in rows:
        table[row['target']][['YES', 'NO', 'UNKNOWN'].index(row['departed'])] += 1
        if row['target'] == 1 and row['departed'] == 'YES' and row['label_point_distance_sec'] is not None:
            errors.append(row['label_point_distance_sec'])
    completed = len(rows)
    unknown = table[0][2] + table[1][2]
    continuation = (completed == 6 and unknown <= 1 and table[1][0] >= 2 and table[0][0] <= 1
                    and max((r['complete_video_wall_sec'] for r in rows), default=999) <= 70)
    return {'completed': completed, 'table_rows_binary_0_1_cols_departure_yes_no_unknown': table,
            'covered': completed-unknown, 'unknown': unknown, 'coverage': (completed-unknown)/completed if completed else None,
            'decode_and_inference_sec_sum': sum(r['decode_and_inference_sec'] for r in rows),
            'decode_and_inference_sec_max': max((r['decode_and_inference_sec'] for r in rows), default=None),
            'complete_video_wall_sec_max': max((r['complete_video_wall_sec'] for r in rows), default=None),
            'positive_yes_point_distance_sec_mean': sum(errors)/len(errors) if errors else None, 'point_distance_n': len(errors),
            'continuation_gate_passed': continuation, 'action_type_or_legal_accuracy_established': False,
            'scope': 'Exploratory association with binary TRAIN labels; point distance is not physical-action localization accuracy'}


def worker():
    run, deadline = await_start_gate()
    tick = time.monotonic()
    model = watch = None
    completed_pilot = []
    rows = {name: {'completed': 0, 'correct': 0, 'valid_format': 0, 'normal_eos': 0, 'non_eos': 0,
                   'prediction_histogram': {s: 0 for s in ['EXIT', 'ENTER', 'STAY', 'UNKNOWN', 'INVALID']},
                   'latency_sec_sum': 0., 'latency_sec_max': 0., 'input_tokens_sum': 0, 'image_tokens_sum': 0}
            for name in ['visual', 'no_image']}
    summary = {}
    report = ControlSummary(status='failed', completed_cases=0, passed_cases=0, total_cases=1, failure='exception')
    try:
        from cashreview.offline import deny_network
        deny_network()
        from internvl_candidate.runtime import LocalRuntime, ResourceWatch
        from internvl_candidate.fixtures import frames, prompt, parse, pilot_prompt
        from cashreview.video import sample
        from PIL import ImageOps
        cfg = json.loads((ROOT / FILES[0]).read_text())
        registration = json.loads((OUT / 'registration.json').read_text())
        verify(registration)
        watch = ResourceWatch(run, cfg)
        watch.start()
        model = LocalRuntime(MODEL, cfg, watch, deadline)
        synthetic_start = time.monotonic()
        for layout, state in synthetic_cases():
            supplied = frames(state, layout, cfg) if state else []
            text, measured = model.observe(supplied, prompt(layout), min(deadline, time.monotonic()+cfg['inference']['synthetic_call_sec']))
            parsed = parse(text)
            row = rows['visual' if state else 'no_image']
            row['completed'] += 1
            row['valid_format'] += int(parsed is not None)
            row['normal_eos'] += int(measured['normal_eos'])
            row['non_eos'] += int(not measured['normal_eos'])
            row['correct'] += int(parsed is not None and parsed['state'] == (state or 'UNKNOWN') and measured['normal_eos'])
            row['prediction_histogram'][parsed['state'] if parsed else 'INVALID'] += 1
            row['latency_sec_sum'] += measured['elapsed_sec']
            row['latency_sec_max'] = max(row['latency_sec_max'], measured['elapsed_sec'])
            row['input_tokens_sum'] += measured['input_tokens']
            row['image_tokens_sum'] += measured['image_tokens']
            atomic_json(run / 'aggregate-progress-safe-summary.json', {'split': 'synthetic', 'cells': rows, 'raw_responses_saved': False})
            write_progress(run, 'synthetic_visual', 0, 0, 1)
        synth_elapsed = time.monotonic()-synthetic_start
        gate = synthetic_gate(rows)
        pilot = {'status': 'NOT_RUN_SYNTHETIC_GATE_FAILED', 'completed': 0}
        if gate:
            pilot_started = time.monotonic()
            pilot_deadline = min(deadline, pilot_started+cfg['budget']['pilot_phase_sec'])
            for source in registration['pilot_sources']:
                video_started = time.monotonic()
                video_deadline = min(pilot_deadline, video_started+cfg['budget']['pilot_video_sec'])
                watch.deadline = video_deadline
                if source['split'] != 'train' or sha(source['path']) != source['sha256']:
                    raise ValueError('Selected TRAIN source changed')
                count = cfg['pilot']['frames']
                times = [source['duration_sec']*(.05+.9*i/(count-1)) for i in range(count)]
                sampled = sample(Path(source['path']), times, max_side=448)
                if len(sampled) != count:
                    raise ValueError('Incomplete fixed frame coverage')
                supplied = [ImageOps.pad(frame.image, (448, 448), color='white', centering=(.5, .5)) for frame in sampled]
                text, measured = model.observe(supplied, pilot_prompt(), min(video_deadline, time.monotonic()+cfg['inference']['pilot_call_sec']))
                parsed = parse(text, pilot=True, count=count)
                if parsed is None or not measured['normal_eos']:
                    raise ValueError('Pilot response format or EOS failure')
                index = parsed['frame_index']
                point_distance = abs(sampled[index].sec-source['label_sec']) if parsed['departed'] == 'YES' and source['label_sec'] is not None else None
                elapsed = time.monotonic()-video_started
                if sha(source['path']) != source['sha256'] or time.monotonic() > video_deadline:
                    raise TimeoutError('Late or changed TRAIN source')
                completed_pilot.append({'sha256': source['sha256'], 'target': source['target'], 'departed': parsed['departed'],
                                        'frame_index': index, 'label_point_distance_sec': point_distance, 'decode_and_inference_sec': elapsed,
                                        'complete_video_wall_sec': time.monotonic()-video_started})
                atomic_json(run / 'structured-private-pilot-rows.json', completed_pilot, deadline=video_deadline)
                atomic_json(run / 'pilot-aggregate-safe-summary.json', dict(split='train', **pilot_summary(completed_pilot)), deadline=video_deadline)
                completed_pilot[-1]['complete_video_wall_sec'] = time.monotonic()-video_started
                if time.monotonic() > video_deadline:
                    raise TimeoutError('Late complete pilot video')
                watch.deadline = pilot_deadline
            atomic_json(run / 'structured-private-pilot-rows.json', completed_pilot, deadline=pilot_deadline)
            atomic_json(run / 'pilot-aggregate-safe-summary.json', dict(split='train', **pilot_summary(completed_pilot)), deadline=pilot_deadline)
            pilot = dict(status='completed_proxy_only', **pilot_summary(completed_pilot))
        verify(registration)
        if gate:
            if time.monotonic() > pilot_deadline:
                raise TimeoutError('Late complete pilot phase')
            pilot['phase_wall_including_final_identity_sec'] = time.monotonic()-pilot_started
            watch.deadline = deadline
        complete = gate and pilot.get('continuation_gate_passed') is True
        summary = {'status': 'completed', 'split': 'synthetic', 'protocol_id': cfg['protocol_id'], 'synthetic_cells': rows,
                   'synthetic_gate_passed': gate, 'pilot': pilot, 'native_transformers_load_sec': model.load_sec,
                   'synthetic_phase_sec': synth_elapsed, 'semantic_status': 'assessed_synthetic_only' if all(r['valid_format'] == r['normal_eos'] == r['completed'] for r in rows.values()) else 'PARTIAL_FORMAT_OR_NON_EOS',
                   'compound_continuation_assertion_passed': complete, 'bank_type_or_rule_validated': False,
                   'raw_model_responses_or_logs_saved': False, 'tune_holdout_notes_or_cloud_inference_used': False}
        report = ControlSummary(status='completed', completed_cases=1, passed_cases=int(complete), total_cases=1)
    except Exception as error:
        summary = {'status': 'failed', 'split': 'synthetic', 'technical_error_type': type(error).__name__,
                   'synthetic_cells': rows, 'pilot_completed': len(completed_pilot), 'synthetic_gate_passed': None,
                   'semantic_status': 'NOT_ASSESSED_TECHNICAL_FAILURE', 'compound_continuation_assertion_passed': False,
                   'raw_private_content_emitted': False}
    finally:
        try:
            exceeded = watch is not None and not watch.check_torch_reserved()
            if model:
                model.close()
            if watch:
                resources = watch.stop()
                summary.update(resources)
                exceeded = exceeded or not resources.get('torch_resource_limit_passed', True)
            if exceeded:
                summary.update(status='failed', technical_error_type='ResourceLimitError', synthetic_gate_passed=None,
                               compound_continuation_assertion_passed=False, semantic_status='NOT_ASSESSED_TECHNICAL_FAILURE')
                report = ControlSummary(status='failed', completed_cases=0, passed_cases=0, total_cases=1, failure='exception')
            summary['owned_runtime_cleanup_complete'] = True
        except Exception:
            summary.update(status='failed', technical_error_type='CleanupError', synthetic_gate_passed=None,
                           compound_continuation_assertion_passed=False, semantic_status='NOT_ASSESSED_TECHNICAL_FAILURE', owned_runtime_cleanup_complete=False)
            report = ControlSummary(status='failed', completed_cases=0, passed_cases=0, total_cases=1, failure='exception')
        summary['worker_elapsed_including_cleanup_sec'] = time.monotonic()-tick
    atomic_json(run / 'internvl-safe-summary.json', summary)
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
            terminal = supervise([sys.executable, str(Path(__file__).resolve()), 'worker'], OUT / 'run', 900, 1, str(ROOT))
            print(json.dumps({'technical_monitor': terminal}), flush=True)
            if terminal['status'] != 'completed':
                raise SystemExit(1)
            summary = json.loads((OUT / 'run/internvl-safe-summary.json').read_text())
            summary['technical_monitor_validated'] = True
            atomic_json(OUT / 'safe-summary.json', summary)
            print(json.dumps(summary), flush=True)
        else:
            raise ValueError('Unknown action')
    except Exception as error:
        print(json.dumps({'status': 'not_started_or_failed', 'technical_error_type': type(error).__name__, 'raw_private_content_emitted': False}))
        sys.exit(1)
