"""Verify saved aggregate learnability arithmetic/integrity; never refit."""
from pathlib import Path
import hashlib, json, math, sys
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '.private/temporal-learnability'
sys.path.insert(0,str(ROOT))
from cashreview.supervision import atomic_json


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    (OUT / 'calculation-safe-summary.json').unlink(missing_ok=True)
    reg = OUT / 'registration.json'
    r = json.loads((OUT / 'safe-summary.json').read_text())
    terminal = json.loads((OUT / 'run/terminal-safe-summary.json').read_text())
    cfg = json.loads((ROOT / 'config/temporal-learnability-protocol.json').read_text())
    assert sha(reg) == r['registration_sha256']
    hashes = json.loads(reg.read_text())['code_sha256']
    assert all(sha(ROOT / name) == value for name, value in hashes.items())
    assert r['status'] == 'completed' and terminal['cleanup_complete'] and terminal['worker_exit_code'] == 0
    assert terminal['completed_cases'] == terminal['expected_cases'] == 3 and terminal['quality_gate_passed']
    for name, result in r['arms'].items():
        steps = cfg['arms'][name]['steps']
        assert result['optimizer_steps_applied'] == result['adamw_state_step_min'] == result['adamw_state_step_max'] == steps
        assert result['gradient_l2_first'] > 0 and result['minimum_gradient_l2'] > 0 and result['parameter_delta_l2'] > 0
        probe = result['zero_logit_gradient_check']
        assert abs(probe['loss'] - math.log(2)) < 1e-6
        assert abs(probe['positive_gradient_sum'] + .25) < 1e-6 and abs(probe['negative_gradient_sum'] - .25) < 1e-6
        for when in ['before', 'after']:
            cm = result[when]['confusion_matrix_tn_fp_fn_tp']
            assert sum(cm[0]) == sum(cm[1]) == 2 and result[when]['train_fit_only_not_validation']
    control = r['arms']['overfit_positive_control']['after']
    passed = control['point_negative_max_eval_loss'] <= cfg['overfit_diagnostic_gate']['point_negative_max_eval_loss_max'] and control['confusion_matrix_tn_fp_fn_tp'] == [[2, 0], [0, 2]] and control['positive_point_logits_above_threshold_count'] == control['negative_video_max_logits_below_threshold_count'] == 2
    assert passed == r['overfit_control_passed']
    report = {'status': 'PASS', 'registration_sha256': sha(reg), 'registered_sources_unchanged': True,
              'optimizer_and_zero_logit_sign_checks_verified': True, 'derived_overfit_control_passed': passed,
              'train_fit_only_not_validation': True, 'additional_fits_or_evaluation': False,
              'monitor_wall_sec': terminal['elapsed_sec']}
    atomic_json(OUT / 'calculation-safe-summary.json',report)
    print(json.dumps(report))


if __name__ == '__main__':
    try: main()
    except Exception as error:
        print(json.dumps({'status': 'failed', 'technical_error_type': type(error).__name__})); sys.exit(1)
