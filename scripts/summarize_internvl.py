"""Aggregate-only arithmetic; never read private pilot rows or media."""
from pathlib import Path
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    out = ROOT / '.private/internvl-control'
    report_path = out / 'safe-summary.json'
    report = json.loads(report_path.read_text())
    terminal = json.loads((out / 'run/terminal-safe-summary.json').read_text())
    registration = json.loads((out / 'registration.json').read_text())
    if (report['status'] != 'completed' or terminal['status'] != 'completed'
            or terminal['worker_exit_code'] != 0 or not terminal['cleanup_complete']
            or not report['technical_monitor_validated'] or not report['owned_runtime_cleanup_complete']):
        raise ValueError('Completed technical evidence required')
    for name, expected in registration['code_sha256'].items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != expected:
            raise ValueError('Frozen source changed')
    cfg = json.loads((ROOT / 'config/internvl-protocol.json').read_text())
    cells = report['synthetic_cells']
    if cells['visual']['completed'] != 6 or cells['no_image']['completed'] != 2:
        raise ValueError('Fixed synthetic count mismatch')
    for row in cells.values():
        if sum(row['prediction_histogram'].values()) != row['completed'] or row['normal_eos'] + row['non_eos'] != row['completed']:
            raise ValueError('Aggregate histogram/completion mismatch')
    expected_tokens = cells['visual']['completed'] * cfg['synthetic']['frames'] * 256
    if cells['visual']['image_tokens_sum'] != expected_tokens or cells['no_image']['image_tokens_sum'] != 0:
        raise ValueError('Actual image-token correspondence mismatch')
    if not report['synthetic_gate_passed'] and report['pilot']['completed'] != 0:
        raise ValueError('Pilot crossed a closed gate')
    summary = {'split': 'synthetic', 'status': 'calculated',
               'source_report_sha256': hashlib.sha256(report_path.read_bytes()).hexdigest(),
               'synthetic_calls_completed': sum(row['completed'] for row in cells.values()),
               'valid_format': sum(row['valid_format'] for row in cells.values()),
               'normal_eos': sum(row['normal_eos'] for row in cells.values()),
               'real_train_inputs_after_failed_gate': report['pilot']['completed'] if not report['synthetic_gate_passed'] else None,
               'torch_reserved_high_water_mib': report['torch_reserved_peak_observed_bytes'] / 2**20,
               'worker_rss_peak_sampled_mib': report['worker_rss_peak_bytes'] / 2**20,
               'system_available_ram_min_sampled_gib': report['system_available_ram_min_bytes'] / 2**30,
               'observed_fit_scope': 'Four generated images or no images per call; eight-frame model forward/real video not established',
               'private_pilot_rows_responses_or_media_read': False, 'bank_type_rule_or_general_visual_capacity_claim': False}
    with (out / 'calculation-safe-summary.json').open('x') as stream:
        json.dump(summary, stream, indent=2)
    print(json.dumps(summary))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(json.dumps({'status': 'not_calculated', 'technical_error_type': type(error).__name__, 'private_content_emitted': False}))
        sys.exit(1)
