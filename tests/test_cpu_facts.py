from pathlib import Path
from io import BytesIO
import base64
import copy
import json
import time
import numpy as np
import pytest
from PIL import Image
from hybrid_candidate.cpu_facts import visual_body, derive_state
from hybrid_candidate.decomposition import body
from scripts.qwen_cpu_facts import native_args, execute, record_cell, ControlClient, text_gate, semantic_status, revoke

ROOT = Path(__file__).resolve().parents[1]
CFG = json.loads((ROOT / 'config/qwen-cpu-facts-protocol.json').read_text())
OLD = json.loads((ROOT / 'config/qwen-decomposition-protocol.json').read_text())
TRUTH = {'exit': {'first_inside': True, 'last_inside': False, 'all_inside': False},
         'enter': {'first_inside': False, 'last_inside': True, 'all_inside': False},
         'stay': {'first_inside': True, 'last_inside': True, 'all_inside': True}}


@pytest.mark.parametrize('action', list(TRUTH))
def test_old_six_text_bodies_identical_and_visual_jpegs_match_independent_positions(action):
    for index, case in enumerate(CFG['text_cells']):
        assert body(action, case, CFG) == body(action, OLD['cells'][index], OLD)
    request = visual_body(action, CFG)
    assert set(request) == {'messages', 'temperature', 'seed', 'max_tokens', 'cache_prompt', 'stream', 'n'}
    content = request['messages'][0]['content']
    images = [x['image_url']['url'] for x in content if x['type'] == 'image_url']
    text = ' '.join(x['text'] for x in content if x['type'] == 'text')
    assert len(images) == 4 and len(content) == 9
    assert not any(x in text for x in ['Rectangle [', 'center x', 'radius=', 'ALPHA', 'BETA', 'GAMMA', 'exit:', 'enter:', 'stay:'])
    expected_x = {'exit': [70, 110, 165, 220], 'enter': [220, 165, 110, 70], 'stay': [70, 95, 125, 150]}[action]
    observed = []
    for data, x in zip(images, expected_x):
        image = Image.open(BytesIO(base64.b64decode(data.split(',', 1)[1], validate=True)))
        assert image.format == 'JPEG' and image.size == (256, 256)
        pixels = np.asarray(image).astype(int)
        red = (pixels[:, :, 0] > 150) & (pixels[:, :, 1] < 100) & (pixels[:, :, 2] < 100)
        ys, xs = np.where(red)
        assert len(xs) > 150 and abs(xs.mean() - x) < 1 and abs(ys.mean() - 120) < 1
        observed.append(bool(xs.min() > 24 and xs.max() < 180 and ys.min() > 24 and ys.max() < 232))
    assert dict(zip(['first_inside', 'last_inside', 'all_inside'], [observed[0], observed[-1], all(observed)])) == TRUTH[action]
    assert derive_state(TRUTH[action]) == action


def test_deterministic_mapping_rejects_inconsistent_incomplete_and_numeric_alias_facts():
    for facts in [{}, {'first_inside': True, 'last_inside': False, 'all_inside': True},
                  {'first_inside': 1, 'last_inside': False, 'all_inside': False},
                  {'first_inside': True, 'last_inside': True, 'all_inside': False}]:
        assert derive_state(facts) is None


def test_native_configuration_is_offline_loopback_cpu_and_has_no_template_or_bias_override():
    class Server:
        exe = Path('runtime/llama-server.exe')
        models = {'text': Path('model.gguf'), 'projector': Path('projector.gguf')}
        port = 12345
    args = native_args(Server(), CFG)
    for flag, value in [('--device', 'none'), ('--mmproj-device', 'none'), ('--gpu-layers', '0'), ('--host', '127.0.0.1'), ('--fit', 'off')]:
        assert args[args.index(flag) + 1] == value
    assert '--offline' in args and '--log-disable' in args
    assert not any('template' in x or 'logit-bias' in x for x in args)
    changed = copy.deepcopy(CFG)
    changed['backend']['device'] = 'CUDA0'
    with pytest.raises(ValueError):
        native_args(Server(), changed)


def test_actual_visual_request_and_parser_use_facts_without_output_oracle_injection():
    captured = []
    answer = TRUTH['enter']
    class Response:
        status_code = 200
        content = b'{}'
        def json(self):
            return {'choices': [{'message': {'content': json.dumps(answer)}, 'finish_reason': 'stop'}], 'usage': {'prompt_tokens': 1, 'completion_tokens': 1}}
    class Client:
        def request(self, method, path, **kwargs):
            captured.append((method, path, kwargs))
            return Response()
    class Server:
        client = Client()
    row = dict(record_cell(), derived_state_correct=0)
    execute(Server(), 'enter', CFG['visual_cell'], CFG, time.monotonic() + 60, row, set(), visual=True)
    assert row['completed'] == row['correct'] == row['derived_state_correct'] == 1 and row['field_correct'] == 3
    assert len(captured) == 1 and captured[0][:2] == ('POST', '/v1/chat/completions')
    assert captured[0][2]['json'] == visual_body('enter', CFG)


def test_gate_requires_all_six_normal_exact_calls_and_all_nine_numeric_fields():
    cells = {name: dict(record_cell(), derived_state_correct=0) for name in ['numeric_facts', 'symbolic_binding']}
    for row in cells.values():
        row.update(completed=3, correct=3, valid_format=3, stop=3)
    cells['numeric_facts']['field_correct'] = 9
    assert text_gate(cells)
    for name, key, value in [('numeric_facts', 'field_correct', 8), ('symbolic_binding', 'correct', 2), ('numeric_facts', 'truncated', 1), ('symbolic_binding', 'technical_errors', 1)]:
        changed = copy.deepcopy(cells)
        changed[name][key] = value
        assert not text_gate(changed)
    cells['numeric_facts']['truncated'] = 1
    assert semantic_status(cells) == 'PARTIAL_FORMAT_OR_TRUNCATION'
    summary = {'semantic_status': 'assessed_synthetic_only', 'text_gate_passed': True, 'visual_gate_passed': True}
    revoke(summary, 'NativeCleanupError')
    assert summary['text_gate_passed'] is None and summary['visual_gate_passed'] is None
    assert summary['image_semantics_status'] == 'NOT_ASSESSED_TECHNICAL_FAILURE'


def test_total_call_limit_and_no_rendering_or_external_endpoints():
    class Client:
        def request(self, *args, **kwargs):
            return None
    client = ControlClient(Client(), 'http://127.0.0.1:12345')
    for _ in range(9):
        client.request('POST', '/v1/chat/completions')
    with pytest.raises(ValueError):
        client.request('POST', '/v1/chat/completions')
    for method, path in [('GET', '/props'), ('POST', '/apply-template'), ('POST', '/api/v1/analyze')]:
        with pytest.raises(ValueError):
            client.request(method, path)


@pytest.mark.parametrize('visual,phase', [(False, 'synthetic_text'), (True, 'synthetic_visual')])
def test_actual_control_progress_publishes_supervisor_accepted_schema(tmp_path, visual, phase):
    from scripts.qwen_cpu_facts import publish_progress
    from cashreview.supervision import ProgressSummary
    publish_progress(tmp_path, visual=visual)
    value = ProgressSummary.model_validate_json((tmp_path / 'progress-safe-summary.json').read_text())
    assert value.phase == phase and value.total_cases == 1 and value.completed_cases == value.passed_cases == 0
