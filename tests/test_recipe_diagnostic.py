import copy
import pytest
from xclip_candidate.recipe_diagnostic import exposure_report, full_fit_gate


def fixture():
    items = [{'sha256': str(i), 'group': str(i)} for i in range(24)]
    rows = [{'source_sha256': str(i), 'group': str(i), 'truth': i % 2,
             'prediction': i % 2, 'score': float(i % 2),
             'error_sec': 1.0 if i % 2 else None} for i in range(24)]
    return items, {'baseline': rows, 'temporal_head': copy.deepcopy(rows)}


def test_exposure_uses_whole_groups_including_other_contents():
    items, records = fixture()
    items.append({'sha256': 'extra', 'group': '0'})
    for rows in records.values():
        rows.append(dict(rows[0], source_sha256='extra'))
    result = exposure_report(records, items, ['0', '1', '2', '3'])
    assert result['diagnostic_exposed_groups']['videos'] == 5
    assert result['remaining_train_groups']['groups'] == 20
    assert result['remaining_train_groups']['results']['temporal_head']['f1'] == 1
    assert not result['remaining_train_groups']['independent_validation']


def test_exposure_rejects_missing_oof_and_selection_outside_train():
    items, records = fixture()
    records['temporal_head'].pop()
    with pytest.raises(ValueError, match='coverage'):
        exposure_report(records, items, ['0', '1', '2', '3'])
    with pytest.raises(ValueError, match='outside'):
        exposure_report(records, items, ['0', '1', '2', 'missing'])


def test_full_fit_gate_requires_point_fit_not_only_video_fit():
    gate = {'maximum_eval_loss': .05, 'confusion_matrix_tn_fp_fn_tp': [[12, 0], [0, 14]],
            'positive_point_count': 14, 'negative_video_count': 12}
    fit = {'point_negative_max_eval_loss': .01,
           'confusion_matrix_tn_fp_fn_tp': [[12, 0], [0, 14]],
           'positive_point_logits_above_threshold_count': 14,
           'negative_video_max_logits_below_threshold_count': 12}
    assert full_fit_gate(fit, gate)
    fit['positive_point_logits_above_threshold_count'] = 13
    assert not full_fit_gate(fit, gate)


def test_recipe_actual_learning_entry_denies_network_before_fits(monkeypatch):
    from scripts.xclip_temporal_recipe import execute_learning
    from cashreview import offline
    from xclip_candidate import temporal_head
    events = []
    monkeypatch.setattr(offline, 'deny_network', lambda: events.append('network_denied'))
    def evaluate(items, cfg, check, progress):
        assert events == ['network_denied']
        events.append('cv')
        return {}, {}
    def fit(items, cfg, check):
        assert events == ['network_denied', 'cv']
        events.append('full_fit')
        return 'head', 0.0
    monkeypatch.setattr(temporal_head, 'evaluate', evaluate)
    monkeypatch.setattr(temporal_head, 'fit_head', fit)
    assert execute_learning([], {}, lambda: None, lambda n: None)[2] == 'head'
    assert events == ['network_denied', 'cv', 'full_fit']
