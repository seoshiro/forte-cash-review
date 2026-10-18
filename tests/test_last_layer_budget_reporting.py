"""Report authority tests use artificial aggregate-only fixtures."""
import json
from pathlib import Path
import pytest
from scripts.summarize_xclip_last_layer import main, sha


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True); path.write_text(json.dumps(data))


def fixture(tmp_path):
    root = Path(__file__).resolve().parents[1]
    cfg = json.loads((root / 'config/xclip-last-layer-budget1800.json').read_text())
    config = tmp_path / 'protocol.json'; write(config, cfg)
    reg = tmp_path / 'registration.json'; write(reg, {'code_sha256': {}})
    record = {'status': 'failed', 'technical_monitor_validated': False, 'release_eligible': False,
              'model_quality_established': False, 'completed_technical_cases': 0, 'phase': 'preflight'}
    terminal = {'status': 'failed', 'expected_cases': 76, 'completed_cases': 0, 'passed_cases': 0,
                'quality_gate_passed': False, 'cleanup_complete': True, 'reason': 'exception',
                'worker_exit_code': 1, 'worker_report_valid': True, 'deadline_exceeded': False, 'budget_sec': 1800}
    write(tmp_path / 'safe-summary.json', record); write(tmp_path / 'run/terminal-safe-summary.json', terminal)
    return config, reg, terminal


def test_explicit_report_identity_and_cap_are_used(tmp_path):
    config, reg, _ = fixture(tmp_path); verified = []
    main(out=tmp_path, config_path=config, expected_registration=sha(reg), verifier=lambda r: verified.append(r))
    result = json.loads((tmp_path / 'calculation-safe-summary.json').read_text())
    assert result['status'] == 'PASS' and result['experiment_status'] == 'failed'
    assert result['registration_sha256'] == sha(reg) and verified == [{'code_sha256': {}}]
    assert not result['model_quality_established'] and not result['additional_evaluation_or_fit']


@pytest.mark.parametrize('bad', ['registration', 'cap'])
def test_report_revokes_stale_pass_before_identity_or_cap_failure(tmp_path, bad):
    config, reg, terminal = fixture(tmp_path)
    destination = tmp_path / 'calculation-safe-summary.json'; write(destination, {'status': 'PASS'})
    if bad == 'cap':
        terminal['budget_sec'] = 600; write(tmp_path / 'run/terminal-safe-summary.json', terminal)
    with pytest.raises(AssertionError):
        main(out=tmp_path, config_path=config, expected_registration='wrong' if bad == 'registration' else sha(reg), verifier=lambda r: None)
    assert not destination.exists()


@pytest.mark.parametrize('learning_sec,accepted', [(1200, True), (1801, False)])
def test_completed_report_checks_expanded_cap_without_changing_quality_math(tmp_path, monkeypatch, learning_sec, accepted):
    import scripts.summarize_xclip_last_layer as helper
    config, reg, terminal = fixture(tmp_path)
    replay = {'phase_wall_sec': 250.}
    monkeypatch.setattr(helper, 'verify_saved_replay', lambda cfg, registered, out: replay)
    # Enable the saved-replay branch; contents are mocked for this budget test only.
    write(tmp_path / 'replay-safe-summary.json', {})
    def metrics(cm, f1, recall, mae, tp):
        return {'confusion_matrix_tn_fp_fn_tp': cm, 'videos': 26, 'f1': f1, 'recall': recall,
                'all_positive_candidate_point_count': 14, 'timestamp_matched_positive_videos': tp,
                'all_positive_candidate_point_mae_sec': mae}
    record = {'status': 'completed', 'registration_sha256': sha(reg), 'technical_monitor_validated': True,
              'replay': replay, 'results': {'baseline': metrics([[6, 6], [2, 12]], .75, 12/14, 9., 12),
              'last_layer_adapter': metrics([[12, 0], [0, 14]], 1., 1., 8., 14),
              'regularized_frozen_head': metrics([[6, 6], [2, 12]], .75, 12/14, 9., 12)},
              'paired_point_diagnostic': {'common_true_positive_count': 12, 'baseline_point_mae_sec': 9., 'adapter_point_mae_sec': 8.},
              'binary_gate_passed': True, 'point_gate_passed': True, 'joint_gate_passed': True,
              'source_split_baseline_and_research_ui_preserved': True, 'adaptive_exploratory_train': True,
              'torch_peak_reserved_mib': 100., 'process_peak_working_set_mib': 100., 'learning_phase_wall_sec': learning_sec}
    for key in ['tune_used', 'holdout_used', 'independent_validation', 'cloud_inference_used', 'per_video_outputs_emitted', 'release_eligible', 'official_score']:
        record[key] = False
    terminal.update(status='completed', reason='completed', completed_cases=76, passed_cases=76, quality_gate_passed=True, worker_exit_code=0, elapsed_sec=1500.)
    write(tmp_path / 'safe-summary.json', record); write(tmp_path / 'run/terminal-safe-summary.json', terminal)
    folder = tmp_path / 'final-train-pack'; folder.mkdir()
    for name in ['projection.npz', 'head-adapter.safetensors']: (folder / name).write_bytes(b'artificial-hash-fixture')
    write(folder / 'metadata.json', {'registration_sha256': sha(reg), 'release_eligible': False,
          'projection_sha256': sha(folder / 'projection.npz'), 'head_adapter_sha256': sha(folder / 'head-adapter.safetensors')})
    if accepted:
        main(out=tmp_path, config_path=config, expected_registration=sha(reg), verifier=lambda r: None)
        result = json.loads((tmp_path / 'calculation-safe-summary.json').read_text())
        assert result['derived_joint_gate'] and result['adapter_minus_baseline_f1'] == .25 and not result['release_eligible']
    else:
        with pytest.raises(AssertionError): main(out=tmp_path, config_path=config, expected_registration=sha(reg), verifier=lambda r: None)
        assert not (tmp_path / 'calculation-safe-summary.json').exists()
