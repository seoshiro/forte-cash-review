"""Reproduce only aggregate synthetic measurements after a completed CPU run."""
from pathlib import Path
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    out = ROOT / '.private/qwen-cpu-facts'
    report = json.loads((out / 'safe-summary.json').read_text())
    terminal = json.loads((out / 'run/terminal-safe-summary.json').read_text())
    registration = json.loads((out / 'registration.json').read_text())
    if (report['status'] != 'completed' or terminal['status'] != 'completed'
            or terminal['worker_exit_code'] != 0 or not terminal['cleanup_complete']
            or not report['technical_monitor_validated']):
        raise ValueError('Completed technical evidence required')
    for name, expected in registration['code_sha256'].items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != expected:
            raise ValueError('Frozen source changed')
    cells = report['cells']
    if cells['numeric_facts']['completed'] != 3 or cells['symbolic_binding']['completed'] != 3:
        raise ValueError('Text call count mismatch')
    expected_images = 3 if report['text_gate_passed'] else 0
    if cells['visual_facts']['completed'] != expected_images:
        raise ValueError('Conditional image gate mismatch')
    totals = {key: sum(row[key] for row in cells.values())
              for key in ['completed', 'valid_format', 'stop', 'truncated', 'technical_errors']}
    if totals['completed'] != report['calls_completed'] or totals['completed'] != report['generation_calls_attempted']:
        raise ValueError('Attempt/completion count mismatch')
    for name in ['numeric_facts', 'visual_facts']:
        row = cells[name]
        if sum(row['fact_histogram'].values()) + row['fact_invalid_format'] != row['completed']:
            raise ValueError('Fact histogram mismatch')
        if sum(row['field_correct_by_name'].values()) != row['field_correct']:
            raise ValueError('Boolean field score mismatch')
    binding = cells['symbolic_binding']
    if sum(binding['label_histogram'].values()) != binding['completed']:
        raise ValueError('Binding histogram mismatch')
    summary = {
        'split': 'synthetic', 'status': 'calculated',
        'source_report_sha256': hashlib.sha256((out / 'safe-summary.json').read_bytes()).hexdigest(),
        'totals': totals,
        'numeric_fields_evaluated': cells['numeric_facts']['completed'] * 3,
        'visual_fields_evaluated': cells['visual_facts']['completed'] * 3,
        'native_rss_peak_observed_mib': report['native_rss_peak_bytes'] / 2**20 if report['native_rss_peak_bytes'] is not None else None,
        'worker_rss_peak_observed_mib': report['worker_rss_peak_bytes'] / 2**20 if report['worker_rss_peak_bytes'] is not None else None,
        'system_available_ram_min_observed_gib': report['system_available_ram_min_bytes'] / 2**30 if report['system_available_ram_min_bytes'] is not None else None,
        'rss_is_sampled_not_windows_lifetime_high_water': True,
        'raw_responses_or_bank_material_read': False,
        'causal_backend_or_bank_quality_claim': False,
    }
    with (out / 'calculation-safe-summary.json').open('x') as stream:
        json.dump(summary, stream, indent=2)
    print(json.dumps(summary))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(json.dumps({'status': 'not_calculated', 'technical_error_type': type(error).__name__, 'raw_private_content_emitted': False}))
        sys.exit(1)
