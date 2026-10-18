"""Bounded final-fc2 residual adaptation. All media/results remain local."""
import math, time
from contextlib import contextmanager
import numpy as np
import torch
from torch import nn
from .temporal_head import fit_projection, supervised_loss
from .linear_head import validate_items, report
from .evaluate import centroids, score_video

PREFIX_KEYS = ('h', 'fc2', 'residual', 'outer')


@contextmanager
def capture_final_fc2(model):
    layer = model.mit.encoder.layers[-1]; captured = {}
    def pre(name):
        def hook(module, args): captured[name] = args[0].detach().clone()
        return hook
    def output(module, args, value): captured['fc2'] = value.detach().clone()
    hooks = [model.mit.register_forward_pre_hook(pre('outer')),
             layer.layer_norm2.register_forward_pre_hook(pre('residual')),
             layer.mlp.fc2.register_forward_pre_hook(pre('h')),
             layer.mlp.fc2.register_forward_hook(output)]
    try: yield captured
    finally:
        for hook in hooks: hook.remove()


def replay(prefix, delta=None):
    # Preserve the original fp16 addition/mean boundaries; no mean-input shortcut.
    base = prefix['fc2']; dtype = base.dtype
    if delta is not None: base = (base.float() + delta).to(dtype)
    inner = (prefix['residual'] + base).to(dtype)
    outer = (inner + prefix['outer']).to(dtype)
    pooled = outer.mean(dim=1).float()
    return nn.functional.normalize(pooled, dim=-1)


class Adapter(nn.Module):
    def __init__(self, cfg):
        super().__init__(); rank = cfg['rank']
        self.a = nn.Linear(2048, rank, bias=False)
        self.b = nn.Linear(rank, 512, bias=False)
        nn.init.normal_(self.a.weight, std=1 / math.sqrt(2048)); nn.init.zeros_(self.b.weight)
        self.scale = cfg['alpha'] / rank
        if cfg['adapter_input_dropout'] != 0: raise ValueError('This fixed adapter uses no input dropout')
    def forward(self, h): return self.b(self.a(h.float())) * self.scale


class Head(nn.Module):
    def __init__(self, cfg):
        super().__init__()
        self.network = nn.Sequential(nn.Conv1d(8, cfg['channels'], 3), nn.GELU(),
                                     nn.Dropout(cfg['dropout']), nn.Conv1d(cfg['channels'], 1, 1))
    def forward(self, x):
        # Explicit endpoint copies give replicate padding without CUDA pad-backward.
        x = torch.cat((x[:, :, :1], x, x[:, :, -1:]), dim=-1)
        return self.network(x).squeeze(1)


def validate_prefix(prefix, length):
    for key in PREFIX_KEYS:
        value = np.asarray(prefix[key]); dim = 2048 if key == 'h' else 512
        if value.shape != (2, length, 8, dim) or value.dtype != np.float16 or not np.isfinite(value).all():
            raise ValueError('Invalid registered prefix array')


def validate_embeddings(values):
    values = np.asarray(values)
    if values.ndim != 2 or values.shape[1] != 512 or not np.isfinite(values).all():
        raise ValueError('Nonfinite or invalid replay embeddings')
    norms = np.linalg.norm(values.astype(np.float64), axis=-1)
    if not np.isfinite(norms).all() or np.any(norms < 1e-9): raise ValueError('Degenerate replay embeddings')


def replay_metrics(reconstructed, reference):
    reconstructed = np.asarray(reconstructed); reference = np.asarray(reference)
    validate_embeddings(reconstructed); validate_embeddings(reference)
    if reconstructed.shape != reference.shape: raise ValueError('Replay embedding shape mismatch')
    a = reconstructed.astype(np.float64); b = reference.astype(np.float64)
    error = float(np.max(abs(a - b)))
    cosine = float(np.min(np.sum(a * b, axis=-1) / (np.linalg.norm(a, axis=-1) * np.linalg.norm(b, axis=-1))))
    if not math.isfinite(error) or not math.isfinite(cosine): raise ValueError('Nonfinite replay metric')
    return error, cosine


def batches(items, projection, device):
    lengths = [len(i['times']) for i in items]; longest = max(lengths)
    for item in items: validate_prefix(item['prefix'], len(item['times']))
    prefix = [{k: torch.as_tensor(np.concatenate([i['prefix'][k][view] for i in items]), device=device)
               for k in PREFIX_KEYS} for view in range(2)]
    offsets = np.cumsum([0] + lengths[:-1]); mapping = np.stack([offset + np.minimum(np.arange(longest), length - 1)
                                                              for offset, length in zip(offsets, lengths)])
    valid = torch.arange(longest, device=device)[None, :] < torch.tensor(lengths, device=device)[:, None]
    positive = [j for j, i in enumerate(items) if i['target']]
    negative = [j for j, i in enumerate(items) if not i['target']]
    points = [int(np.argmin(abs(items[j]['times'] - items[j]['label_sec']))) for j in positive]
    if not positive or not negative: raise ValueError('Both classes required in train fold')
    weights = torch.tensor(np.concatenate([np.full(n, 1 / (len(items) * n)) for n in lengths]), device=device, dtype=torch.float32)
    return {'prefix': prefix, 'mapping': torch.tensor(mapping, device=device), 'valid': valid,
            'positive': positive, 'negative': negative, 'points': points, 'weights': weights,
            'projection': tuple(torch.as_tensor(v, device=device, dtype=torch.float32) for v in projection)}


def features(adapter, prefix): return replay(prefix, None if adapter is None else adapter(prefix['h']))


def logits_for(head, vectors, packed):
    mean, basis = packed['projection']; projected = (vectors - mean) @ basis
    return head(projected[packed['mapping']].permute(0, 2, 1))


def fit(items, cfg, enabled, check=lambda: None, device='cuda:0'):
    start = time.monotonic(); projection = fit_projection(items, 8); check()
    torch.manual_seed(cfg['head']['seed'])
    head = Head(cfg['head']).to(device); adapter = Adapter(cfg['model']).to(device) if enabled else None
    if sum(p.numel() for p in head.parameters()) != 209: raise ValueError('Head parameter mismatch')
    if adapter is not None and sum(p.numel() for p in adapter.parameters()) != cfg['model']['adapter_parameters']:
        raise ValueError('Adapter parameter mismatch')
    packed = batches(items, projection, device)
    with torch.no_grad(): base = [replay(p) for p in packed['prefix']]
    groups = [{'params': head.parameters(), 'lr': cfg['head']['learning_rate'], 'weight_decay': cfg['head']['weight_decay']}]
    if adapter is not None:
        groups.append({'params': adapter.parameters(), 'lr': cfg['adapter_optimizer']['learning_rate'],
                       'weight_decay': cfg['adapter_optimizer']['weight_decay']})
    optimizer = torch.optim.AdamW(groups)
    # Both arms see the same head initialization and subsequent dropout RNG stream.
    torch.manual_seed(cfg['head']['seed'] + 1)
    head.train(); last = None; first_gradient = None; final_gradient = None
    parameters = list(head.parameters()) + ([] if adapter is None else list(adapter.parameters()))
    for step in range(cfg['head']['steps']):
        check(); optimizer.zero_grad(set_to_none=True); view = step % 2
        vectors = base[view] if adapter is None else features(adapter, packed['prefix'][view])
        logits = logits_for(head, vectors, packed)
        task = supervised_loss(logits, packed['valid'], packed['positive'], packed['points'], packed['negative'])
        anchor = torch.sum((vectors - base[view]).square().sum(-1) * packed['weights'])
        loss = task + cfg['adapter_optimizer']['anchor_strength'] * anchor
        if not torch.isfinite(loss): raise ValueError('Nonfinite adapter training loss')
        loss.backward()
        norm = nn.utils.clip_grad_norm_(parameters, cfg['adapter_optimizer']['gradient_clip_l2'], error_if_nonfinite=True)
        first_gradient = float(norm) if first_gradient is None else first_gradient; final_gradient = float(norm)
        optimizer.step(); last = {'task_loss': float(task.detach()), 'anchor_distance': float(anchor.detach()), 'total_loss': float(loss.detach())}
    if any(int(v['step']) != cfg['head']['steps'] for v in optimizer.state.values()): raise ValueError('Optimizer step mismatch')
    if not all(torch.isfinite(p).all() for p in parameters): raise ValueError('Nonfinite fitted parameters')
    head.eval(); check()
    return (projection, head, adapter), {'elapsed_sec': time.monotonic() - start, 'optimizer_steps': cfg['head']['steps'],
                                       'first_gradient_l2': first_gradient, 'last_gradient_l2': final_gradient, 'last_train_losses': last}


def predict(fitted, prefix, times, threshold=0.):
    # No source name/hash, group, label or official timestamp is accepted.
    projection, head, adapter = fitted; head.eval(); device = next(head.parameters()).device
    times = np.asarray(times)
    if times.ndim != 1 or len(times) < 2 or not np.isfinite(times).all() or np.any(np.diff(times) <= 0):
        raise ValueError('Invalid inference PTS')
    validate_prefix(prefix, len(times))
    original = {key: torch.as_tensor(prefix[key][0], device=device) for key in PREFIX_KEYS}
    with torch.inference_mode():
        vectors = features(adapter, original)
        mean, basis = (torch.as_tensor(v, dtype=torch.float32, device=device) for v in projection)
        scores = head(((vectors - mean) @ basis).T[None])[0].float().cpu().numpy()
    if not np.isfinite(scores).all(): raise ValueError('Nonfinite inference scores')
    index = int(np.argmax(scores))
    return {'prediction': int(scores[index] >= threshold), 'score': float(scores[index]), 'time_sec': float(times[index])}


def training_report(fitted, items, cfg, check=lambda: None):
    packed = batches(items, fitted[0], next(fitted[1].parameters()).device)
    with torch.inference_mode():
        logits = logits_for(fitted[1], features(fitted[2], packed['prefix'][0]), packed)
        loss = supervised_loss(logits, packed['valid'], packed['positive'], packed['points'], packed['negative'])
        point = logits[packed['positive'], packed['points']]; negative = logits[packed['negative']].masked_fill(~packed['valid'][packed['negative']], -torch.inf).max(1).values
    records = []
    for item in items:
        row = predict(fitted, item['prefix'], item['times']); row.update(truth=item['target'], error_sec=abs(row['time_sec'] - item['label_sec']) if item['target'] else None)
        records.append(row); check()
    return {'scope': 'In-sample fullTRAIN diagnostic only, not validation', 'results': report(records),
            'eval_task_loss': float(loss), 'positive_point_logits_above_threshold_count': int((point >= 0).sum()),
            'negative_video_max_logits_below_threshold_count': int((negative < 0).sum())}


def evaluate(items, cfg, check=lambda: None, progress=lambda count: None):
    validate_items(items)
    # Validate every held/train prefix before the first fit, not lazily per fold.
    for item in items:
        validate_prefix(item['prefix'], len(item['times'])); validate_embeddings(item['ordered'])
    groups = sorted({i['group'] for i in items})
    if len(groups) != 24 or len(items) != 26: raise ValueError('Fixed TRAIN scope changed')
    records = {name: [] for name in ['baseline', 'regularized_frozen_head', 'last_layer_adapter']}; costs = {name: [] for name in records if name != 'baseline'}
    completed = 0
    for group in groups:
        train = [i for i in items if i['group'] != group]; test = [i for i in items if i['group'] == group]
        if {i['sha256'] for i in train} & {i['sha256'] for i in test}: raise ValueError('Group leakage')
        p, n = centroids(train, 'ordered')
        for item in test:
            score, sec = score_video(item['ordered'], item['times'], p, n, 'max')
            records['baseline'].append({'prediction': int(score >= 0), 'score': score, 'time_sec': sec, 'truth': item['target'],
                                       'source_sha256': item['sha256'], 'group': group, 'error_sec': abs(sec - item['label_sec']) if item['target'] else None})
        for name, enabled in [('regularized_frozen_head', False), ('last_layer_adapter', True)]:
            fitted, cost = fit(train, cfg, enabled, check); costs[name].append(cost)
            for item in test:
                row = predict(fitted, item['prefix'], item['times'], cfg['evaluation']['threshold_logit'])
                row.update(truth=item['target'], source_sha256=item['sha256'], group=group,
                           error_sec=abs(row['time_sec'] - item['label_sec']) if item['target'] else None)
                records[name].append(row); check()
            del fitted; torch.cuda.empty_cache(); completed += 1; progress(completed); check()
    results = {name: report(rows) for name, rows in records.items()}
    baseline = results['baseline']; candidate = results['last_layer_adapter']; control = results['regularized_frozen_head']
    if baseline['confusion_matrix_tn_fp_fn_tp'] != cfg['evaluation']['baseline_cm'] or abs(baseline['f1'] - .75) > 1e-12:
        raise ValueError('Original baseline reproduction failed')
    a = {r['source_sha256']: r for r in records['baseline']}; b = {r['source_sha256']: r for r in records['last_layer_adapter']}
    common = [key for key in a if a[key]['truth'] and a[key]['prediction'] and b[key]['prediction']]
    paired = {'common_true_positive_count': len(common), 'baseline_point_mae_sec': float(np.mean([a[k]['error_sec'] for k in common])) if common else None,
              'adapter_point_mae_sec': float(np.mean([b[k]['error_sec'] for k in common])) if common else None}
    cm = candidate['confusion_matrix_tn_fp_fn_tp']; gate = cfg['gates']
    binary = cm[1][0] <= gate['fn_max'] and cm[0][1] <= gate['fp_max'] and candidate['f1'] >= gate['f1_min'] and candidate['f1'] > control['f1']
    point = bool(common and candidate['all_positive_candidate_point_mae_sec'] <= baseline['all_positive_candidate_point_mae_sec'] and paired['adapter_point_mae_sec'] <= paired['baseline_point_mae_sec'])
    return {'results': results, 'paired_point_diagnostic': paired, 'binary_gate_passed': bool(binary), 'point_gate_passed': point,
            'joint_gate_passed': bool(binary and point), 'fit_costs_aggregate': {name: {'fits': len(rows), 'elapsed_sec_sum': sum(r['elapsed_sec'] for r in rows),
               'elapsed_sec_max': max(r['elapsed_sec'] for r in rows), 'last_total_loss_mean': float(np.mean([r['last_train_losses']['total_loss'] for r in rows]))} for name, rows in costs.items()}}, records
