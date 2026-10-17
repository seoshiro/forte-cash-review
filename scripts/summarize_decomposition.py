"""Derive aggregate claims only; never read model responses or bank material."""
from pathlib import Path
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    out = ROOT / '.private/qwen-decomposition'
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
    cfg = json.loads((ROOT / 'config/qwen-decomposition-protocol.json').read_text())
    families = {}
    first_definition = 0
    totals = dict.fromkeys(['completed', 'correct', 'valid_format', 'stop', 'truncated', 'technical_errors'], 0)
    for cell in cfg['cells']:
        row = report['cells'][cell['id']]
        family = families.setdefault(cell['family'], {'completed': 0, 'correct': 0})
        family['completed'] += row['completed']
        family['correct'] += row['correct']
        for key in totals:
            totals[key] += row[key]
        if cell['family'] == 'facts':
            if sum(row['fact_histogram'].values()) + row['fact_invalid_format'] != row['completed']:
                raise ValueError('Fact count mismatch')
        else:
            cm = row['confusion_rows_exit_enter_stay_cols_exit_enter_stay_invalid']
            if sum(map(sum, cm)) != row['completed'] or sum(row['label_histogram'].values()) != row['completed']:
                raise ValueError('Label count mismatch')
            if cell['family'] == 'direct':
                first_definition += sum(line[cell['definition_order']] for line in cm)
    if totals['completed'] != report['calls_completed'] or totals['completed'] != cfg['budget']['calls']:
        raise ValueError('Call total mismatch')
    facts = report['cells']['numeric_facts']
    if sum(facts['field_correct_by_name'].values()) != facts['field_correct']:
        raise ValueError('Field count mismatch')
    summary = {
        'split': 'synthetic', 'status': 'calculated',
        'source_report_sha256': hashlib.sha256((out / 'safe-summary.json').read_bytes()).hexdigest(),
        'families': families, 'totals': totals,
        'numeric_fields_correct': facts['field_correct'],
        'numeric_fields_evaluated': facts['completed'] * 3,
        'direct_first_definition_selection': first_definition,
        'definition_and_allowed_orders_separated': True,
        'root_cause_or_bank_quality_established': False,
        'raw_responses_or_bank_material_read': False,
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
