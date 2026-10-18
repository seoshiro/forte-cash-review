"""Verify saved aggregate last-layer results/integrity; never decode or refit."""
from pathlib import Path
import hashlib, json, math, sys
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from cashreview.supervision import atomic_json
OUT = ROOT / '.private/xclip-last-layer-control'
EXPECTED_REGISTRATION = 'f0aabcef076d54fe7997a8abd27aa0dccb50abede8a6a651b3fb2e0137a8d077'


def sha(path):
    with path.open('rb') as stream: return hashlib.file_digest(stream, 'sha256').hexdigest()


def validate_terminal(r, terminal):
    assert r['status'] in ('completed', 'failed')
    assert terminal['expected_cases'] == 76 and terminal['cleanup_complete'] is True
    completed = terminal['completed_cases']; passed = terminal['passed_cases']
    assert type(completed) is int and type(passed) is int and 0 <= passed <= completed <= 76
    if r['status'] == 'completed':
        assert terminal['status'] == 'completed' and terminal['worker_report_valid'] is True
        assert r['technical_monitor_validated'] is True and terminal['quality_gate_passed'] is True
        assert terminal['worker_exit_code'] == 0 and completed == passed == 76 and not terminal['deadline_exceeded']
    else:
        assert terminal['status'] == 'failed' and terminal['quality_gate_passed'] is False
        assert r['technical_monitor_validated'] is False and r.get('release_eligible') is False and 'results' not in r
        assert not r.get('model_quality_established', False)
        assert terminal['reason'] in {'exception', 'deadline', 'monitor_exception', 'worker_exit', 'invalid_worker_report', 'missing_worker_report', 'server_exit', 'terminal_write_failed'}
        if 'completed_technical_cases' in r: assert r['completed_technical_cases'] == completed
        if terminal['worker_exit_code'] == 0:
            assert terminal['reason'] in {'deadline', 'invalid_worker_report', 'missing_worker_report', 'terminal_write_failed'}


def verify_saved_replay(cfg, reg, out=OUT):
    OUT = out
    replay = json.loads((OUT / 'replay-safe-summary.json').read_text()); gate = cfg['replay']
    assert replay['status'] == 'PASS' and replay['videos'] == 26 and replay['windows'] == 678 and replay['views'] == 2
    assert not replay['training_started'] and replay['zero_adapter_replay_is_not_ml_quality']
    for key in ['same_forward_max_absolute_embedding_error', 'historical_original_max_absolute_embedding_error', 'historical_original_minimum_cosine', 'maximum_pts_grid_error_sec']:
        assert math.isfinite(replay[key])
    assert replay['same_forward_max_absolute_embedding_error'] <= gate['same_forward_max_absolute_embedding_error']
    assert replay['historical_original_max_absolute_embedding_error'] <= gate['historical_original_max_absolute_embedding_error']
    assert replay['historical_original_minimum_cosine'] >= gate['historical_original_minimum_cosine']
    assert replay['maximum_pts_grid_error_sec'] <= gate['times_max_absolute_error_sec']
    prefix_reg = json.loads((OUT / 'prefix-registration.json').read_text())
    assert prefix_reg['registration_sha256'] == sha(reg) and prefix_reg['replay_passed_before_training']
    inventory = prefix_reg['cache_sha256']; assert len(inventory) == 26
    assert {p.name for p in (OUT / 'prefix').iterdir()} == set(inventory)
    assert all(sha(OUT / 'prefix' / name) == value for name, value in inventory.items())
    return replay


def main(*, out=None, config_path='config/xclip-last-layer-protocol.json', expected_registration=EXPECTED_REGISTRATION, verifier=None):
    if out is None: out = OUT
    destination = out / 'calculation-safe-summary.json'; destination.unlink(missing_ok=True)
    r = json.loads((out / 'safe-summary.json').read_text()); terminal = json.loads((out / 'run/terminal-safe-summary.json').read_text())
    cfg = json.loads((ROOT / config_path).read_text())
    reg = out / 'registration.json'
    assert sha(reg) == expected_registration
    registered = json.loads(reg.read_text()); hashes = registered['code_sha256']
    assert all(sha(ROOT / name) == value for name, value in hashes.items())
    if verifier is None:
        from scripts.xclip_last_layer import verify
        verifier = verify
    verifier(registered)  # Original source/cache bytes and runtime identity; no decoding.
    validate_terminal(r, terminal)
    assert terminal['budget_sec'] == cfg['budget']['owned_wall_sec']
    saved_replay = verify_saved_replay(cfg, reg, out) if (out / 'replay-safe-summary.json').exists() else None
    if r['status'] == 'failed':
        if r.get('phase') == 'fixed_group_oof_and_full_train': assert saved_replay is not None
        report = {'status': 'PASS', 'scope': 'Verification of preserved failed technical attempt only', 'experiment_status': 'failed',
                  'registration_sha256': sha(reg), 'owned_cleanup_confirmed': True, 'additional_evaluation_or_fit': False,
                  'model_quality_established': False, 'retry_authorized': False,
                  'registered_sources_original_cache_and_baseline_verified': True,
                  'saved_prefix_replay_and_hashes_verified': saved_replay is not None,
                  'completed_cv_fits': max(0,min(48,terminal['completed_cases']-26)), 'planned_cv_fits': 48}
        atomic_json(destination, report); print(json.dumps(report)); return
    assert sha(reg) == r['registration_sha256']
    assert terminal['worker_exit_code'] == 0 and terminal['cleanup_complete'] and terminal['quality_gate_passed']
    assert terminal['completed_cases'] == terminal['expected_cases'] == 76 and not terminal['deadline_exceeded']
    assert r['replay'] == saved_replay
    replay = saved_replay
    for value in r['results'].values():
        (tn, fp), (fn, tp) = value['confusion_matrix_tn_fp_fn_tp']
        assert tn + fp == 12 and fn + tp == 14 and value['videos'] == 26
        expected_f1 = 2 * tp / (2 * tp + fp + fn) if (2 * tp + fp + fn) else 0.
        assert abs(value['f1'] - expected_f1) < 1e-12
        assert abs(value['recall'] - tp / 14) < 1e-12
        assert value['all_positive_candidate_point_count'] == 14 and value['timestamp_matched_positive_videos'] == tp
        if tp == 0: assert value['timestamp_mae_sec'] is None
    a = r['results']['baseline']; b = r['results']['last_layer_adapter']; c = r['results']['regularized_frozen_head']
    assert a['confusion_matrix_tn_fp_fn_tp'] == cfg['evaluation']['baseline_cm'] and a['f1'] == .75
    cm = b['confusion_matrix_tn_fp_fn_tp']; g = cfg['gates']
    binary = cm[1][0] <= g['fn_max'] and cm[0][1] <= g['fp_max'] and b['f1'] >= g['f1_min'] and b['f1'] > c['f1']
    paired = r['paired_point_diagnostic']; common = paired['common_true_positive_count']
    assert max(0, a['confusion_matrix_tn_fp_fn_tp'][1][1] + cm[1][1] - 14) <= common <= min(a['confusion_matrix_tn_fp_fn_tp'][1][1], cm[1][1])
    point = bool(common and b['all_positive_candidate_point_mae_sec'] <= a['all_positive_candidate_point_mae_sec'] and paired['adapter_point_mae_sec'] <= paired['baseline_point_mae_sec'])
    assert r['binary_gate_passed'] == binary and r['point_gate_passed'] == point and r['joint_gate_passed'] == bool(binary and point)
    for key in ['tune_used', 'holdout_used', 'independent_validation', 'cloud_inference_used', 'per_video_outputs_emitted', 'release_eligible', 'official_score']:
        assert r[key] is False
    assert r['source_split_baseline_and_research_ui_preserved'] and r['adaptive_exploratory_train']
    budget = cfg['budget']
    assert terminal['elapsed_sec'] <= budget['owned_wall_sec']
    assert r['torch_peak_reserved_mib'] <= budget['max_torch_reserved_mib'] and r['process_peak_working_set_mib'] <= budget['max_peak_working_set_mib']
    assert r['learning_phase_wall_sec'] <= budget['learning_phase_wall_sec'] and replay['phase_wall_sec'] <= budget['prefix_phase_wall_sec']
    folder = out / 'final-train-pack'; pack = json.loads((folder / 'metadata.json').read_text())
    assert pack['registration_sha256'] == sha(reg) and not pack['release_eligible']
    assert sha(folder / 'projection.npz') == pack['projection_sha256'] and sha(folder / 'head-adapter.safetensors') == pack['head_adapter_sha256']
    report = {'status': 'PASS', 'experiment_status': 'completed', 'scope': 'Aggregate arithmetic, registered source and artifact verification only',
              'registration_sha256': sha(reg), 'registered_source_files': len(hashes), 'registered_sources_unchanged': True,
              'prefix_and_final_pack_hashes_verified': True, 'derived_binary_gate': binary, 'derived_point_gate': point,
              'derived_joint_gate': bool(binary and point), 'adapter_minus_baseline_f1': b['f1'] - a['f1'],
              'adapter_minus_matched_head_f1': b['f1'] - c['f1'], 'monitor_wall_sec_including_cleanup': terminal['elapsed_sec'],
              'additional_evaluation_or_fit': False, 'release_eligible': False}
    atomic_json(destination, report); print(json.dumps(report))


if __name__ == '__main__':
    try: main()
    except Exception as error:
        print(json.dumps({'status': 'failed', 'technical_error_type': type(error).__name__, 'raw_private_content_emitted': False})); sys.exit(1)
