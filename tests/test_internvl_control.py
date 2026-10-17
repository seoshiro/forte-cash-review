from pathlib import Path
import copy
import json
import time
import numpy as np
import pytest
from internvl_candidate.fixtures import frames, prompt, parse, pilot_selection
from scripts.internvl_experiment import synthetic_cases, synthetic_gate, pilot_summary

ROOT = Path(__file__).resolve().parents[1]
CFG = json.loads((ROOT / 'config/internvl-protocol.json').read_text())


@pytest.mark.parametrize('layout', [0, 1])
def test_independent_pixel_oracle_reversal_and_no_action_label_in_generated_pixels(layout):
    sides = (40, 290) if layout == 0 else (158, 408)
    expected = {'EXIT': (True, False, False), 'ENTER': (False, True, False), 'STAY': (True, True, True)}
    images = {state: frames(state, layout, CFG) for state in expected}
    for state, sequence in images.items():
        flags = []
        for image in sequence:
            pixels = np.asarray(image)
            red = (pixels[:, :, 0] > 200) & (pixels[:, :, 1] < 40) & (pixels[:, :, 2] < 40)
            ys, xs = np.where(red)
            assert len(xs) > 500 and image.size == (448, 448) and not image.info
            flags.append(bool(xs.min() > sides[0] and xs.max() < sides[1] and ys.min() > 90 and ys.max() < 390))
        assert (flags[0], flags[-1], all(flags)) == expected[state]
    assert all(a.tobytes() == b.tobytes() for a, b in zip(images['ENTER'], reversed(images['EXIT'])))
    assert 'ordered images F0,F1,F2,F3' in prompt(layout)


def test_strict_parser_expected_classes_fences_and_unknown_pilot_semantics():
    assert parse('```json\n{"state":"ENTER"}\n```') == {'state': 'ENTER'}
    assert parse('{"departed":"UNKNOWN","frame_index":null}', pilot=True) == {'departed': 'UNKNOWN', 'frame_index': None}
    for text in ['{"state":"EXIT","state":"ENTER"}', '{"state":"EXIT","rule":"fake"}', 'EXIT', '{"state":"cashier"}']:
        assert parse(text) is None
    for value in [{'departed': 'YES', 'frame_index': True}, {'departed': 'YES', 'frame_index': 8},
                  {'departed': 'NO', 'frame_index': 0}, {'departed': 'UNKNOWN', 'frame_index': 1}]:
        assert parse(json.dumps(value), pilot=True) is None


def test_all_eight_controls_required_for_gate_and_blank_conditions_are_not_numeric_gates():
    assert len(synthetic_cases()) == 8 and sum(state is None for _, state in synthetic_cases()) == 2
    assert prompt(0) != prompt(1)
    rows = {key: dict(completed=count, correct=count, valid_format=count, normal_eos=count) for key, count in [('visual', 6), ('no_image', 2)]}
    assert synthetic_gate(rows)
    for key in rows:
        for field in rows[key]:
            changed = copy.deepcopy(rows)
            changed[key][field] -= 1
            assert not synthetic_gate(changed)


def test_selection_freezes_balanced_unique_groups_by_hash_and_never_selects_held_out():
    rows = [{'sha256': f'{i:064x}', 'target': int(i >= 4), 'group': 'g'+str(i), 'split': 'train'} for i in range(8)]
    selected = pilot_selection(list(reversed(rows)))
    assert len(selected) == 6 and len({r['group'] for r in selected}) == 6
    assert [r['sha256'] for r in selected] == [f'{i:064x}' for i in [0, 1, 2, 4, 5, 6]]
    assert sum(r['target'] for r in selected) == 3
    with pytest.raises(ValueError):
        pilot_selection([r for r in rows if r['target'] == 0])
    held_out = dict(rows[0], split='holdout')
    with pytest.raises(ValueError):
        pilot_selection(rows + [held_out])


def test_proxy_table_keeps_unknown_separate_and_does_not_establish_action_accuracy():
    rows = [{'target': int(i >= 3), 'departed': 'UNKNOWN', 'label_point_distance_sec': None, 'decode_and_inference_sec': 1., 'complete_video_wall_sec': 1.} for i in range(6)]
    summary = pilot_summary(rows)
    assert summary['table_rows_binary_0_1_cols_departure_yes_no_unknown'] == [[0, 0, 3], [0, 0, 3]]
    assert summary['coverage'] == 0 and not summary['continuation_gate_passed']
    assert not summary['action_type_or_legal_accuracy_established']


@pytest.mark.parametrize('mode', ['semantic_failure', 'pass', 'late_posthash'])
def test_real_worker_transition_uses_only_synthetic_mocks_and_frozen_pilot_after_gate(tmp_path, monkeypatch, mode):
    import scripts.internvl_experiment as runner
    import internvl_candidate.runtime as local_runtime
    import cashreview.offline as offline
    import cashreview.video as video
    from PIL import Image
    from types import SimpleNamespace
    synthetic_pass = mode != 'semantic_failure'
    clock = [time.monotonic()]
    hash_calls = []
    selected = [{'path': str(tmp_path / ('fixture'+str(i)+'.mov')), 'sha256': 'mock', 'split': 'train',
                 'target': int(i >= 3), 'label_sec': 1. if i >= 3 else None, 'duration_sec': 10.} for i in range(6)]
    (tmp_path / 'registration.json').write_text(json.dumps({'pilot_sources': selected}))
    calls = []
    class Watch:
        def __init__(self, *args):
            self.deadline = None
        def start(self):
            pass
        def check_torch_reserved(self):
            return True
        def stop(self):
            return {'mock_resource_watch': True}
    class Runtime:
        load_sec = 0.
        def __init__(self, *args):
            pass
        def observe(self, images, text, deadline):
            index = len(calls)
            calls.append((len(images), text))
            assert 'fixture' not in text and 'mock' not in text
            if index < 8:
                state = synthetic_cases()[index][1] or 'UNKNOWN'
                if not synthetic_pass and index == 0:
                    state = 'STAY'
                answer = {'state': state}
            else:
                answer = {'departed': 'UNKNOWN', 'frame_index': None}
            return json.dumps(answer), {'normal_eos': True, 'elapsed_sec': .01, 'input_tokens': 1, 'image_tokens': len(images)*256}
        def close(self):
            pass
    monkeypatch.setattr(runner, 'OUT', tmp_path)
    monkeypatch.setattr(runner, 'time', SimpleNamespace(monotonic=lambda: clock[0]))
    monkeypatch.setattr(runner, 'await_start_gate', lambda: (tmp_path, clock[0]+900))
    monkeypatch.setattr(runner, 'verify', lambda value: None)
    def source_sha(path):
        hash_calls.append(path)
        if mode == 'late_posthash' and len(hash_calls) == 2:
            clock[0] += 80
        return 'mock'
    monkeypatch.setattr(runner, 'sha', source_sha)
    monkeypatch.setattr(local_runtime, 'LocalRuntime', Runtime)
    monkeypatch.setattr(local_runtime, 'ResourceWatch', Watch)
    monkeypatch.setattr(offline, 'deny_network', lambda: None)
    monkeypatch.setattr(video, 'sample', lambda *args, **kwargs: [video.Sample(float(i), Image.new('RGB', (448, 448))) for i in range(8)])
    if mode == 'late_posthash':
        with pytest.raises(SystemExit):
            runner.worker()
    else:
        runner.worker()
    assert len(calls) == (9 if mode == 'late_posthash' else 14 if synthetic_pass else 8)
    assert [count for count, _ in calls[:8]] == [4, 4, 4, 0, 4, 4, 4, 0]
    summary = json.loads((tmp_path / 'internvl-safe-summary.json').read_text())
    assert summary['owned_runtime_cleanup_complete']
    if mode == 'late_posthash':
        assert summary['status'] == 'failed' and summary['synthetic_gate_passed'] is None
        assert summary['technical_error_type'] == 'TimeoutError' and summary['pilot_completed'] == 0
    elif synthetic_pass:
        assert summary['synthetic_gate_passed'] is True
        assert summary['pilot']['completed'] == 6 and summary['pilot']['unknown'] == 6
        assert not summary['pilot']['continuation_gate_passed']
    else:
        assert summary['synthetic_gate_passed'] is False
        assert summary['pilot']['completed'] == 0


@pytest.mark.parametrize('failed', [False, True])
def test_observe_restores_outer_video_deadline_even_after_error(monkeypatch, failed):
    from types import SimpleNamespace
    from internvl_candidate.runtime import LocalRuntime
    runtime = object.__new__(LocalRuntime)
    runtime.watch = SimpleNamespace(deadline=100.)
    def inner(images, prompt_text, deadline):
        assert deadline == runtime.watch.deadline == 80.
        if failed:
            raise ValueError('Synthetic error')
        return 'safe'
    runtime._observe = inner
    if failed:
        with pytest.raises(ValueError):
            runtime.observe([], 'safe synthetic', 80.)
    else:
        assert runtime.observe([], 'safe synthetic', 80.) == 'safe'
    assert runtime.watch.deadline == 100.


def test_model_inventory_rejects_missing_extra_and_different_pinned_artifacts(tmp_path, monkeypatch):
    import hashlib
    import scripts.internvl_experiment as runner
    model = tmp_path / 'models/candidate'
    prepare = tmp_path / '.private/internvl-prepare'
    config = tmp_path / 'config'
    for path in [model, prepare, config]:
        path.mkdir(parents=True)
    blobs = {'model.safetensors': b'synthetic weights, not a real model', 'config.json': b'{}'}
    card = b'public synthetic license fixture'
    (prepare / 'official-model-card.md').write_bytes(card)
    digests = {name: hashlib.sha256(blob).hexdigest() for name, blob in blobs.items()}
    for name, blob in blobs.items():
        (model / name).write_bytes(blob)
    cfg = {'revision': 'fixed', 'artifacts': [{'filename': name, 'bytes': len(blob), 'sha256': digests[name]} for name, blob in blobs.items()]}
    cfg_path = config / 'internvl-artifacts.json'
    cfg_path.write_text(json.dumps(cfg))
    provenance = {'revision': 'fixed', 'weight_license': 'apache-2.0', 'artifact_sha256': dict(digests, **{'official-model-card.md': hashlib.sha256(card).hexdigest()})}
    provenance_path = model / 'provenance.json'
    provenance_path.write_text(json.dumps(provenance))
    monkeypatch.setattr(runner, 'ROOT', tmp_path)
    monkeypatch.setattr(runner, 'MODEL', model)
    assert len(runner.inventory()) == 4
    changed = copy.deepcopy(provenance)
    del changed['artifact_sha256']['config.json']
    provenance_path.write_text(json.dumps(changed))
    with pytest.raises(ValueError):
        runner.inventory()
    provenance_path.write_text(json.dumps(provenance))
    extra = model / 'pytorch_model.bin'
    extra.write_bytes(b'not permitted')
    with pytest.raises(ValueError):
        runner.inventory()
    extra.unlink()
    cfg['artifacts'][0]['sha256'] = '0'*64
    cfg_path.write_text(json.dumps(cfg))
    with pytest.raises(ValueError):
        runner.inventory()


def test_synchronous_torch_high_water_check_catches_short_peak_without_polling(tmp_path, monkeypatch):
    import sys
    from types import SimpleNamespace
    from internvl_candidate.runtime import ResourceWatch
    peak = [0]
    fake = SimpleNamespace(cuda=SimpleNamespace(is_initialized=lambda: True, max_memory_reserved=lambda: peak[0]))
    monkeypatch.setitem(sys.modules, 'torch', fake)
    watch = ResourceWatch(tmp_path, CFG)
    assert watch.check_torch_reserved()
    peak[0] = CFG['resources']['torch_reserved_cap_bytes'] + 1
    assert not watch.check_torch_reserved()
    result = watch.stop()
    assert not result['torch_resource_limit_passed']
    assert result['torch_reserved_peak_observed_bytes'] == peak[0]
