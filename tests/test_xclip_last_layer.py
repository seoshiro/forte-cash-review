import copy, inspect, json
from pathlib import Path
import numpy as np
import pytest
import torch
from xclip_candidate.last_layer import Adapter, Head, replay, capture_final_fc2, validate_prefix, predict
from xclip_candidate.temporal_head import TemporalHead


def config(): return json.loads((Path(__file__).resolve().parents[1] / 'config/xclip-last-layer-protocol.json').read_text())


def synthetic_prefix(windows=3):
    rng = np.random.default_rng(49)
    return {key: rng.normal(size=(2, windows, 8, 2048 if key == 'h' else 512)).astype(np.float16)
            for key in ['h', 'fc2', 'residual', 'outer']}


def test_zero_adapter_preserves_fp16_residual_and_pool_rounding():
    cfg = config(); p = {k: torch.from_numpy(v[0]) for k, v in synthetic_prefix().items()}
    adapter = Adapter(cfg['model'])
    assert sum(x.numel() for x in adapter.parameters()) == 5120
    assert torch.count_nonzero(adapter(p['h'])) == 0
    expected = ((p['residual'] + p['fc2']) + p['outer']).mean(1).float()
    expected = torch.nn.functional.normalize(expected, dim=-1)
    assert torch.equal(replay(p), expected) and torch.equal(replay(p, adapter(p['h'])), expected)
    replay(p, adapter(p['h'])).sum().backward()
    assert adapter.b.weight.grad.abs().sum() > 0
    assert torch.count_nonzero(adapter.a.weight.grad) == 0


def test_explicit_padding_matches_original_head_outputs_and_gradients():
    cfg = config()['head']; cfg['dropout'] = 0
    torch.manual_seed(1); old = TemporalHead(dropout=0)
    new = Head(cfg); new.load_state_dict(old.state_dict())
    x = torch.randn(2, 8, 7, requires_grad=True); y = x.detach().clone().requires_grad_()
    a = old(x); b = new(y)
    assert torch.equal(a, b)
    a.sum().backward(); b.sum().backward(); assert torch.allclose(x.grad, y.grad)
    assert sum(p.numel() for p in new.parameters()) == 209


def test_capture_hooks_are_removed_even_if_forward_fails():
    from types import SimpleNamespace
    class MIT(torch.nn.Module):
        def __init__(self):
            super().__init__(); self.encoder = SimpleNamespace(layers=[SimpleNamespace(layer_norm2=torch.nn.Identity(), mlp=SimpleNamespace(fc2=torch.nn.Identity()))])
    model = SimpleNamespace(mit=MIT())
    modules = [model.mit, model.mit.encoder.layers[0].layer_norm2, model.mit.encoder.layers[0].mlp.fc2]
    with pytest.raises(RuntimeError):
        with capture_final_fc2(model): raise RuntimeError('synthetic error')
    assert all(not m._forward_pre_hooks and not m._forward_hooks for m in modules)


def test_prefix_shape_and_inference_input_boundary():
    prefix = synthetic_prefix(); validate_prefix(prefix, 3)
    bad = copy.deepcopy(prefix); bad['h'] = bad['h'][0]
    with pytest.raises(ValueError): validate_prefix(bad, 3)
    assert list(inspect.signature(predict).parameters) == ['fitted', 'prefix', 'times', 'threshold']


def test_actual_random_mit_hooks_reproduce_its_pooler_without_pretrained_data():
    from types import SimpleNamespace
    from transformers import XCLIPVisionConfig
    from transformers.models.x_clip.modeling_x_clip import XCLIPMultiframeIntegrationTransformer
    torch.set_num_threads(1); torch.manual_seed(48)
    cfg = XCLIPVisionConfig(hidden_size=512, intermediate_size=2048, num_hidden_layers=1,
                           num_attention_heads=8, num_frames=8)
    cfg._attn_implementation = 'eager'
    mit = XCLIPMultiframeIntegrationTransformer(cfg).half().eval()
    with torch.no_grad():
        for parameter in mit.parameters(): parameter.normal_(std=.01)
    model = SimpleNamespace(mit=mit); values = torch.randn(2, 8, 512).half()
    with torch.inference_mode(), capture_final_fc2(model) as captured:
        reference = torch.nn.functional.normalize(mit(values).pooler_output.float(), dim=-1)
        assert torch.equal(replay(captured), reference)


def test_fixed_training_path_updates_both_arms_on_synthetic_prefix_only():
    from xclip_candidate.last_layer import fit, training_report
    cfg = config(); cfg['head']['steps'] = 2; torch.set_num_threads(1)
    rng = np.random.default_rng(172)
    items = []
    for index in range(6):
        prefix = synthetic_prefix(4)
        prefix['outer'] = prefix['outer'] + np.float16(index * .02)
        original = replay({k: torch.from_numpy(v[0]) for k, v in prefix.items()}).numpy()
        items.append({'ordered': original + rng.normal(0, .0001, original.shape), 'prefix': prefix,
                      'times': np.arange(4, dtype=float), 'target': index % 2,
                      'label_sec': 1. if index % 2 else None})
    for enabled in (False, True):
        fitted, cost = fit(items, cfg, enabled, device='cpu')
        assert cost['optimizer_steps'] == 2 and cost['first_gradient_l2'] > 0
        report = training_report(fitted, items, cfg)
        assert report['results']['videos'] == 6 and np.isfinite(report['eval_task_loss'])


@pytest.mark.parametrize('bad', [float('nan'), float('inf'), 0.0])
def test_replay_metrics_reject_nonfinite_or_zero_embeddings(bad):
    from xclip_candidate.last_layer import replay_metrics
    good = np.ones((3, 512), dtype=np.float32); invalid = good.copy(); invalid[2] = bad
    with pytest.raises(ValueError): replay_metrics(good, invalid)
    with pytest.raises(ValueError): replay_metrics(invalid, good)


@pytest.mark.parametrize('bad', [float('nan'), float('inf')])
def test_bad_held_prefix_is_rejected_before_any_group_fit(monkeypatch, bad):
    import xclip_candidate.last_layer as module
    prefix = synthetic_prefix(); original = replay({k: torch.from_numpy(v[0]) for k, v in prefix.items()}).numpy()
    items = [{'sha256': str(i), 'group': str(i % 24), 'target': i % 2, 'label_sec': 1. if i % 2 else None,
              'ordered': original.copy(), 'times': np.arange(3, dtype=float), 'prefix': copy.deepcopy(prefix)} for i in range(26)]
    items[-1]['prefix']['h'][0, 0, 0, 0] = bad
    calls = []; monkeypatch.setattr(module, 'fit', lambda *args, **kwargs: calls.append('forbidden_fit'))
    with pytest.raises(ValueError, match='prefix'): module.evaluate(items, config())
    assert calls == []
