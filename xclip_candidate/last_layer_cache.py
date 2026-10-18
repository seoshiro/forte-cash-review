"""Local-only final-layer prefix extraction and aggregate zero-adapter replay."""
from pathlib import Path
import time
import numpy as np
from PIL import ImageEnhance
from .features import window_targets, match_pts
from .last_layer import PREFIX_KEYS, capture_final_fc2, replay, Adapter, validate_prefix, validate_embeddings, replay_metrics


class ReplayMismatch(ValueError):
    def __init__(self, code, **technical_values):
        super().__init__('Registered replay gate failed')
        allowed = {'same_forward_cache', 'historical_original', 'persisted_cache', 'pts_grid'}
        if code not in allowed or not all(isinstance(v, (int, float)) and np.isfinite(v) for v in technical_values.values()):
            raise ValueError('Invalid safe replay diagnostic')
        self.safe_code = code; self.safe_technical_values = technical_values


def extract(encoder, path, original_features, original_times, cfg, check):
    from cashreview.video import validate_input, sample
    torch = encoder.torch; start = time.monotonic(); info = validate_input(Path(path)); source_cfg = encoder.cfg
    validate_embeddings(original_features)
    if original_times.ndim != 1 or len(original_times) != len(original_features) or not np.isfinite(original_times).all() or np.any(np.diff(original_times) <= 0):
        raise ValueError('Invalid historical replay PTS')
    targets = window_targets(info['duration_sec'], source_cfg)
    if len(targets) > cfg['budget']['max_windows_per_video']: raise ValueError('Window resource bound')
    requests = sorted(set(round(float(t), 6) for t in targets.flatten()))
    frames = sample(Path(path), requests, max_side=source_cfg['features']['decode_max_side'])
    pts = np.array([frame.sec for frame in frames]); clips = []; centers = []
    for times in targets:
        indices = match_pts(pts, times, source_cfg['features']['pts_match_tolerance_sec'])
        clips.append([frames[int(i)].image for i in indices]); centers.append(float((pts[indices[0]] + pts[indices[-1]]) / 2))
    times = np.array(centers)
    if times.shape != original_times.shape or np.max(abs(times - original_times)) > cfg['replay']['times_max_absolute_error_sec']:
        raise ReplayMismatch('pts_grid', current_windows=len(times), historical_windows=len(original_times))
    adapter = Adapter(cfg['model']).to('cuda:0').eval()
    views = []; references = []; max_replay = 0.; original_max = 0.; minimum_cosine = 1.
    for view in range(2):
        prefix_parts = {key: [] for key in PREFIX_KEYS}; reference_parts = []
        for start_at in range(0, len(clips), cfg['budget']['batch_windows']):
            check(); part = clips[start_at:start_at + cfg['budget']['batch_windows']]
            if view:
                part = [[ImageEnhance.Contrast(ImageEnhance.Brightness(frame).enhance(.9)).enhance(1.1) for frame in clip] for clip in part]
            values = encoder.processor(images=part, return_tensors='pt')['pixel_values']
            if tuple(values.shape) != (len(part), 8, 3, 224, 224): raise ValueError('Processor layout changed')
            values = values.to(device='cuda:0', dtype=torch.float16)
            with torch.inference_mode(), capture_final_fc2(encoder.model) as captured:
                pooled = encoder.model.get_video_features(pixel_values=values).pooler_output.float()
                reference = pooled / pooled.norm(dim=-1, keepdim=True).clamp_min(1e-9)
                arrays = {key: captured[key].cpu().numpy().copy() for key in PREFIX_KEYS}
                # Exercise the actual cached zero-adapter path, not direct hook tensors.
                reloaded = {key: torch.as_tensor(value, device='cuda:0') for key, value in arrays.items()}
                reconstructed = replay(reloaded, adapter(reloaded['h']))
                current = reference.cpu().numpy()
                error, _ = replay_metrics(reconstructed.cpu().numpy(), current); max_replay = max(max_replay, error)
                if error > cfg['replay']['same_forward_max_absolute_embedding_error']:
                    raise ReplayMismatch('same_forward_cache', maximum_absolute_error=error)
            for key in PREFIX_KEYS: prefix_parts[key].append(arrays[key])
            reference_parts.append(current); torch.cuda.synchronize(); check()
        values = {key: np.concatenate(parts) for key, parts in prefix_parts.items()}
        current = np.concatenate(reference_parts); views.append(values); references.append(current)
        if view == 0:
            if current.shape != original_features.shape: raise ValueError('Historical feature layout changed')
            original_max, minimum_cosine = replay_metrics(current, original_features)
            if original_max > cfg['replay']['historical_original_max_absolute_embedding_error'] or minimum_cosine < cfg['replay']['historical_original_minimum_cosine']:
                raise ReplayMismatch('historical_original', maximum_absolute_error=original_max, minimum_cosine=minimum_cosine)
    prefix = {key: np.stack([v[key] for v in views]) for key in PREFIX_KEYS}
    validate_prefix(prefix, len(times))
    prefix.update(times=times, reference=np.stack(references))
    del adapter, frames, clips
    return prefix, {'windows': len(times), 'views': 2, 'same_forward_replay_max_absolute_error': max_replay,
                    'historical_original_max_absolute_error': original_max, 'historical_original_minimum_cosine': minimum_cosine,
                    'maximum_pts_grid_error_sec': float(np.max(abs(times - original_times))),
                    'elapsed_sec': time.monotonic() - start}
