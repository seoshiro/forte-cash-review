"""FullTRAIN parameter-only aggregate audit; no media, labels or predictions."""
from pathlib import Path
import hashlib, json, math, sys
import numpy as np
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from cashreview.supervision import atomic_json
from scripts.summarize_xclip_last_layer import EXPECTED_REGISTRATION
OUT = ROOT / '.private/xclip-last-layer-control'


def sha(path):
    with path.open('rb') as stream: return hashlib.file_digest(stream, 'sha256').hexdigest()


def parameter_metrics(a, b, scale):
    a = np.asarray(a, dtype=np.float64); b = np.asarray(b, dtype=np.float64)
    if a.shape != (2, 2048) or b.shape != (512, 2) or not np.isfinite(a).all() or not np.isfinite(b).all() or not math.isfinite(scale):
        raise ValueError('Invalid fixed adapter parameter arrays')
    a_norm = float(np.linalg.norm(a)); b_norm = float(np.linalg.norm(b)); delta_norm = float(np.linalg.norm((b @ a) * scale))
    return {'a_frobenius_norm': a_norm, 'b_frobenius_norm': b_norm, 'effective_delta_map_frobenius_norm': delta_norm,
            'b_changed_from_zero_initialization': b_norm > 0, 'effective_delta_map_nonzero': delta_norm > 0,
            'adapter_parameter_count': int(a.size + b.size)}


def main():
    destination = OUT / 'weights-safe-summary.json'; destination.unlink(missing_ok=True)
    if sha(OUT / 'registration.json') != EXPECTED_REGISTRATION: raise ValueError('Registered identity changed')
    result = json.loads((OUT / 'safe-summary.json').read_text())
    if result['status'] != 'completed' or not result['technical_monitor_validated']: raise ValueError('No completed experiment')
    folder = OUT / 'final-train-pack'; metadata = json.loads((folder / 'metadata.json').read_text())
    weights = folder / 'head-adapter.safetensors'
    if metadata['registration_sha256'] != EXPECTED_REGISTRATION or sha(weights) != metadata['head_adapter_sha256']: raise ValueError('Private fitted pack changed')
    from safetensors.numpy import load_file
    values = load_file(weights)
    record = parameter_metrics(values['adapter.a.weight'], values['adapter.b.weight'], 1.)
    record.update(status='PASS', registration_sha256=EXPECTED_REGISTRATION, pack_sha256=sha(weights),
                  scope='Parameter-only fullTRAIN fit audit; not quality, inference, or verification of every OOF fold',
                  raw_weight_values_emitted=False, model_evaluation_or_fit=False, release_eligible=False)
    atomic_json(destination, record); print(json.dumps(record))


if __name__ == '__main__':
    try: main()
    except Exception as error:
        print(json.dumps({'status': 'failed', 'technical_error_type': type(error).__name__, 'raw_private_content_emitted': False})); sys.exit(1)
