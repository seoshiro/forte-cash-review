"""Verify only saved technical aggregates; never rerun a model or open traces."""
from pathlib import Path
import json,math,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts import last_layer_diagnostic as experiment
from cashreview.supervision import atomic_json
EXPECTED='16463126a8297f504975c5b7aaaf05f400f47a8dcf85d7bed0196b51034fda30'


def main():
    output=experiment.OUT/'calculation-safe-summary.json';output.unlink(missing_ok=True)
    cfg,_=experiment.verify(EXPECTED)
    result=json.loads((experiment.OUT/'safe-summary.json').read_text());terminal=json.loads((experiment.OUT/'run/terminal-safe-summary.json').read_text())
    assert result['status']=='completed' and result['candidate_fit_completed'] and result['optimizer_steps']==500
    assert result['zero_adapter_max_absolute_error']==0 and result['registration_sha256']==EXPECTED
    assert not result['historical_failure_origin_proven'] and not result['predictions_or_quality_metrics_computed'] and not result['quality_established']
    assert not result['tune_used'] and not result['holdout_used']
    assert result['technical_monitor']==terminal and terminal['status']=='completed' and terminal['cleanup_complete']
    assert terminal['completed_cases']==terminal['passed_cases']==terminal['expected_cases']==1 and terminal['worker_exit_code']==0
    assert terminal['budget_sec']==180 and terminal['elapsed_sec']<=180 and not terminal['deadline_exceeded']
    resource=result['resources'];assert all(type(v) in (int,float) and math.isfinite(v) for v in resource.values())
    assert resource['peak_working_set_mib']<=4096 and resource['torch_peak_reserved_mib']<=5000
    assert resource['minimum_available_ram_mib']>=1024 and resource['minimum_free_gpu_mib']>=256
    report={'status':'PASS','scope':'Technical candidate-boundary fit/replay/resource/source verification; no historical cause or quality established',
            'registration_sha256':EXPECTED,'optimizer_steps_verified':500,'candidate_fit_ordinal':cfg['candidate_next_fit_ordinal'],
            'additional_evaluation_or_fit':False,'historical_failure_origin_proven':False,'release_eligible':False}
    atomic_json(output,report);print(json.dumps(report))


if __name__=='__main__':
    try:main()
    except Exception as error:print(json.dumps({'status':'failed','technical_error_type':type(error).__name__,'raw_private_content_emitted':False}));sys.exit(1)
