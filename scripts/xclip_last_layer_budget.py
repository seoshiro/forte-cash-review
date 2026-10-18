"""One explicitly authorized identical restart; wall cap only, no ML changes."""
from pathlib import Path
import argparse, copy, datetime, json, sys
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from scripts import xclip_last_layer as original
from cashreview.supervision import atomic_json, supervise

OLD_OUT = ROOT / '.private/xclip-last-layer-control'
OUT = ROOT / '.private/xclip-last-layer-budget1800'
CONFIG = 'config/xclip-last-layer-budget1800.json'
OLD_REGISTRATION = 'f0aabcef076d54fe7997a8abd27aa0dccb50abede8a6a651b3fb2e0137a8d077'
ADDED_FILES = [CONFIG, 'scripts/xclip_last_layer_budget.py', 'tests/test_last_layer_budget.py']


def validate_identical_protocol(previous, current):
    expected = copy.deepcopy(previous)
    expected['protocol_id'] = 'XCLIP-LAST-LAYER-01-BUDGET1800'
    expected['budget']['owned_wall_sec'] = 1800
    expected['budget']['learning_phase_wall_sec'] = 1800
    if current != expected: raise ValueError('Only registered wall limits and protocol identity may change')


def configure():
    previous = json.loads((ROOT / original.CONFIG).read_text())
    current = json.loads((ROOT / CONFIG).read_text())
    validate_identical_protocol(previous, current)
    if original.sha(OLD_OUT / 'registration.json') != OLD_REGISTRATION: raise ValueError('Prior registration changed')
    original.verify(json.loads((OLD_OUT / 'registration.json').read_text()))
    old_result = json.loads((OLD_OUT / 'safe-summary.json').read_text())
    terminal = json.loads((OLD_OUT / 'run/terminal-safe-summary.json').read_text())
    if not (old_result['status'] == 'failed' and old_result['technical_error_type'] == 'TimeoutError'
            and old_result['phase'] == 'fixed_group_oof_and_full_train' and terminal['cleanup_complete']):
        raise ValueError('Prior attempt is not the preserved closed timeout')
    original.OUT = OUT; original.CONFIG = CONFIG; original.FILES = original.FILES + ADDED_FILES
    return current


def verified_registration(expected):
    if expected is None or original.sha(OUT / 'registration.json') != expected: raise ValueError('Pinned continuation registration required')
    registration = json.loads((OUT / 'registration.json').read_text())
    original.verify(registration)
    return registration


def run(expected):
    cfg = json.loads((ROOT / CONFIG).read_text()); verified_registration(expected)
    # No fit or optimizer checkpoints exist in the old runner: restart every fit.
    with (OUT / 'attempt.json').open('x') as stream:
        json.dump({'started_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                   'prior_registration_sha256': OLD_REGISTRATION, 'restart_from_step_zero': True,
                   'reason': 'Explicit continuation authorization after technical timeout; no reliable optimizer/RNG resume',
                   'partial_metrics_used_for_selection': False, 'registration_sha256': expected}, stream)
    terminal = supervise([sys.executable, str(Path(__file__).resolve()), 'worker', '--registration-sha256', expected],
                         OUT / 'run', cfg['budget']['owned_wall_sec'], original.TOTAL, str(ROOT))
    print(json.dumps({'technical_monitor': terminal}), flush=True)
    if terminal['quality_gate_passed'] and terminal['cleanup_complete']:
        summary = json.loads((OUT / 'run/quality-safe-summary.json').read_text()); summary['technical_monitor_validated'] = True
    else:
        summary = {'status': 'failed', 'technical_monitor_validated': False, 'release_eligible': False, 'repeat_authorized': False}
        path = OUT / 'run/failure-safe-summary.json'
        if path.exists(): summary.update(json.loads(path.read_text()))
    summary.update(prior_registration_sha256=OLD_REGISTRATION, authorized_identical_full_restart=True,
                   partial_metrics_used_for_selection=False, owned_wall_cap_sec=1800)
    atomic_json(OUT / 'safe-summary.json', summary); print(json.dumps(summary), flush=True)
    if summary['status'] != 'completed': raise SystemExit(1)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('action', choices=['register', 'run', 'worker'])
    parser.add_argument('--registration-sha256'); args = parser.parse_args()
    try:
        configure()
        if args.action == 'register': original.register()
        elif args.action == 'run': run(args.registration_sha256)
        else:
            verified_registration(args.registration_sha256); original.worker()
    except Exception as error:
        print(json.dumps({'status': 'failed', 'technical_error_type': type(error).__name__, 'raw_private_content_emitted': False})); sys.exit(1)
