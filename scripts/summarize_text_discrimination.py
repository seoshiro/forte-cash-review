"""Derive only aggregate diagnostic claims from the completed safe report."""
from pathlib import Path
import sys,json,hashlib
ROOT=Path(__file__).resolve().parents[1]


def main():
    out=ROOT/'.private/qwen-text-discrimination'
    report=json.loads((out/'safe-summary.json').read_text());terminal=json.loads((out/'run/terminal-safe-summary.json').read_text())
    if report['status']!='completed' or terminal['status']!='completed' or terminal['worker_exit_code']!=0 or not terminal['cleanup_complete']:
        raise ValueError('Completed technical evidence required')
    cfg_path=ROOT/'config/qwen-text-discrimination.json';registration=json.loads((out/'registration.json').read_text())
    if hashlib.sha256(cfg_path.read_bytes()).hexdigest()!=registration['code_sha256']['config/qwen-text-discrimination.json']:
        raise ValueError('Frozen configuration changed')
    cfg=json.loads(cfg_path.read_text());cells=report['cells'];families={};first_rule=0;constant_cells=0
    for case in cfg['text_cells']:
        row=cells[case['id']];cm=row['confusion_rows_exit_enter_stay_cols_exit_enter_stay_invalid']
        if sum(map(sum,cm))!=row['completed'] or sum(row['token_histogram'].values())!=row['completed']:
            raise ValueError('Inconsistent aggregate counts')
        group=families.setdefault(case['family'],{'completed':0,'correct':0})
        group['completed']+=row['completed'];group['correct']+=row['correct']
        if case['family']=='geometry':
            column=1 if case.get('reorder_prompt') else 0
            first_rule+=sum(line[column] for line in cm)
            constant_cells+=int(max(sum(line[i] for line in cm) for i in range(4))==row['completed'])
    fields=['completed','correct','valid_format','stop','truncated','technical_errors','input_render_verified']
    totals={key:sum(row[key] for row in cells.values()) for key in fields}
    if totals['completed']!=report['text_calls_completed']+report['image_calls_completed']:raise ValueError('Call total mismatch')
    summary={'split':'synthetic','status':'calculated','source_report_sha256':hashlib.sha256((out/'safe-summary.json').read_bytes()).hexdigest(),
        # Retained report-key spelling: this count means first DEFINITION only.
        # It does not establish selection of the first allowed-list token.
        'families':families,'totals':totals,'geometry_first_prompt_rule_or_allowed_token_selection':first_rule,
        'geometry_cells_with_constant_decoded_semantics':constant_cells,
        'first_definition_vs_first_allowed_list_not_separated':True,'underlying_arithmetic_binding_capacity_backend_cause_identified':False,
        'old_probe_prediction_identity_not_inferred':True,'raw_responses_or_bank_data_read':False}
    with (out/'calculation-safe-summary.json').open('x') as stream:json.dump(summary,stream,indent=2)
    print(json.dumps(summary))


if __name__=='__main__':
    try:main()
    except Exception as error:
        print(json.dumps({'status':'not_calculated','technical_error_type':type(error).__name__,'raw_private_content_emitted':False}));sys.exit(1)
