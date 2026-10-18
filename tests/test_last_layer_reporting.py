import copy
import pytest
from scripts.summarize_xclip_last_layer import validate_terminal


def fixtures():
    return ({'status': 'failed', 'technical_monitor_validated': False, 'release_eligible': False,
             'model_quality_established': False, 'completed_technical_cases': 4},
            {'status': 'failed', 'expected_cases': 76, 'completed_cases': 4, 'passed_cases': 4,
             'quality_gate_passed': False, 'cleanup_complete': True, 'reason': 'exception',
             'worker_exit_code': 1, 'worker_report_valid': True, 'deadline_exceeded': False})


def test_preserved_failed_attempt_requires_matching_failed_terminal():
    record, terminal = fixtures(); validate_terminal(record, terminal)
    for field, value in [('status', 'completed'), ('quality_gate_passed', True), ('completed_cases', 5), ('expected_cases', 3), ('worker_exit_code', 0)]:
        changed = copy.deepcopy(terminal); changed[field] = value
        with pytest.raises(AssertionError): validate_terminal(record, changed)


@pytest.mark.parametrize('status', ['running', 'unknown'])
def test_unfinished_or_unknown_status_cannot_be_verified_as_failed(status):
    record, terminal = fixtures(); record['status'] = status
    with pytest.raises(AssertionError): validate_terminal(record, terminal)


def test_parameter_audit_distinguishes_zero_adapter_from_effective_change():
    import numpy as np
    from scripts.inspect_last_layer_weights import parameter_metrics
    a = np.ones((2, 2048)); b = np.zeros((512, 2))
    zero = parameter_metrics(a, b, 1.)
    assert not zero['effective_delta_map_nonzero'] and zero['effective_delta_map_frobenius_norm'] == 0
    b[0, 0] = 1
    changed = parameter_metrics(a, b, 1.)
    assert changed['b_changed_from_zero_initialization'] and changed['effective_delta_map_nonzero']
    assert changed['effective_delta_map_frobenius_norm'] == np.sqrt(2048)
