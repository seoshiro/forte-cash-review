"""Aggregate adaptive TRAIN diagnostics without exposing individual records."""
from .linear_head import report


def exposure_report(records, items, selected_sha256):
    by_sha = {item['sha256']: item for item in items}
    if len(selected_sha256) != 4 or len(set(selected_sha256)) != 4:
        raise ValueError('Exactly four diagnostic contents required')
    if not set(selected_sha256) <= by_sha.keys():
        raise ValueError('Diagnostic selection outside TRAIN')
    exposed = {by_sha[key]['group'] for key in selected_sha256}
    all_groups = {item['group'] for item in items}
    if len(exposed) != 4 or len(all_groups) != 24:
        raise ValueError('Fixed diagnostic group scope changed')
    result = {}
    for name, chosen in [('diagnostic_exposed_groups', exposed),
                         ('remaining_train_groups', all_groups - exposed)]:
        expected = {item['sha256'] for item in items if item['group'] in chosen}
        reports = {}
        for model, rows in records.items():
            selected = [row for row in rows if row['group'] in chosen]
            if len(selected) != len(expected) or {r['source_sha256'] for r in selected} != expected:
                raise ValueError('OOF stratum coverage mismatch')
            if {row['truth'] for row in selected} != {0, 1}:
                raise ValueError('Both classes required for registered stratum metrics')
            reports[model] = report(selected)
        result[name] = {'groups': len(chosen), 'videos': len(expected), 'results': reports,
                        'independent_validation': False}
    return result


def full_fit_gate(result, gate):
    return bool(result['point_negative_max_eval_loss'] <= gate['maximum_eval_loss']
                and result['confusion_matrix_tn_fp_fn_tp'] == gate['confusion_matrix_tn_fp_fn_tp']
                and result['positive_point_logits_above_threshold_count'] == gate['positive_point_count']
                and result['negative_video_max_logits_below_threshold_count'] == gate['negative_video_count'])
