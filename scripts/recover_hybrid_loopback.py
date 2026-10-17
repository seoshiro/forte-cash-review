"""One technical recovery before any completed control; preserve original attempt."""
from pathlib import Path
import json,hashlib,datetime,sys,traceback
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import scripts.hybrid_experiment as experiment


def main():
    original=ROOT/'.private/hybrid-r22';recovery=ROOT/'.private/hybrid-r22-recovery'
    status=json.loads((original/'status.json').read_text())
    if status.get('status')!='failed' or status.get('technical_error_type')!='TimeoutError':raise RuntimeError('Original startup interruption not confirmed')
    if not any(f.get('file')=='runtime.py' and f.get('line')==75 for f in status.get('locations',[])):raise RuntimeError('Failure was not the frozen native startup timeout')
    if (original/'control-progress-safe-summary.json').exists() or (original/'synthetic-safe-summary.json').exists() or list((original/'controls').glob('*.private.json')):raise RuntimeError('Control results already exist; recovery prohibited')
    if (original/'train-safe-summary.json').exists() or list((original/'results').glob('*.private.json')):raise RuntimeError('Prior TRAIN exists; recovery prohibited')
    probe=json.loads((original/'escalated-loopback-safe-summary.json').read_text())
    if not probe.get('completed') or not probe.get('temporary_loopback_health_passed'):raise RuntimeError('Loopback access is not confirmed')
    registration=(original/'registration.json').read_bytes();record=json.loads(registration)
    experiment.verify(record)
    recovery.mkdir(exist_ok=True)
    # Exclusive amendment and normal exclusive attempt marker prevent repeats.
    amendment={'reason':'Initial native readiness timed out before any completed control. Sandbox loopback connect returned Windows10013; a separately approved harmless loopback probe passed outside the network sandbox.',
        'created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'original_registration_sha256':hashlib.sha256(registration).hexdigest(),
        'original_failure_sha256':experiment.sha(original/'status.json'),'recovery_helper_sha256':experiment.sha(Path(__file__)),
        'original_attempt_preserved':True,'completed_controls_before_recovery':0,'train_runs_before_recovery':0,
        'maximum_technical_recovery_attempts':1,'all_parameters_code_weights_cache_splits_unchanged':True,
        'not_a_retry_after_semantic_results':True,'os_network_or_security_settings_changed':False,'persistent_credentials_created':False}
    with (recovery/'recovery-registration.json').open('x',encoding='utf-8') as stream:json.dump(amendment,stream,indent=2)
    with (recovery/'registration.json').open('xb') as stream:stream.write(registration)
    experiment.OUT=recovery
    print(json.dumps({'technical_recovery_registered':True,'original_registration_sha256':amendment['original_registration_sha256'],
        'completed_controls_before_recovery':0,'train_runs_before_recovery':0,'parameters_changed':False}),flush=True)
    try:experiment.run()
    except Exception as error:
        safe={'status':'failed','technical_error_type':type(error).__name__,
            'locations':[{'file':Path(f.filename).name,'line':f.lineno} for f in traceback.extract_tb(error.__traceback__)],
            'raw_content_emitted':False,'tune_run':False,'holdout_media_inference':False,'attempt_owned_by_this_invocation':experiment.ATTEMPT_OWNED}
        experiment.write('failure-safe-summary.json' if experiment.ATTEMPT_OWNED else 'rejected-invocation-safe-summary.json',safe)
        if experiment.ATTEMPT_OWNED:
            experiment.write('status.json',safe)
            summary=recovery/'train-safe-summary.json'
            if summary.exists():
                data=json.loads(summary.read_text());data.update(status='failed',useful_hybrid_gate_passed=False,technical_failures=1);experiment.write(summary.name,data)
        print(json.dumps(safe),flush=True);return 1
    return 0


if __name__=='__main__':
    try:sys.exit(main())
    except Exception as error:
        print(json.dumps({'recovery_not_started':True,'technical_error_type':type(error).__name__,'raw_content_emitted':False}),flush=True);sys.exit(1)
