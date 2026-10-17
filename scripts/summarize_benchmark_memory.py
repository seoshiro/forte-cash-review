"""Freeze aggregate gauges up to benchmark completion, excluding later TUNE."""
from pathlib import Path
from datetime import datetime,timezone
import json
ROOT=Path(__file__).resolve().parents[1];private=ROOT/'.private'
end=datetime.fromtimestamp((private/'benchmark/safe-summary.json').stat().st_mtime,timezone.utc)
records=json.loads((private/'memory-watch/gauge-samples.json').read_text())
records=[r for r in records if datetime.fromisoformat(r['checked_utc'].replace('Z','+00:00'))<=end]
best=max(records,key=lambda r:r['process_gauges']['Shared Usage']['mib'])
summary={'samples':len(records),'scope':'TRAIN benchmark phase only; no inference content read',
         'max_gauge_mib':{name:max(r['process_gauges'][name]['mib'] for r in records) for name in ['Dedicated Usage','Shared Usage','Total Committed']},
         'min_adapter_free_mib':min(r['nvidia_smi_mib'][0]['fb_free'] for r in records),
         'shared_peak_snapshot':best,'gauge_maxima_not_necessarily_simultaneous':True}
(private/'benchmark-memory-safe-summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
bench=json.loads((private/'benchmark/safe-summary.json').read_text())
budget={'sample_count':bench['sample_count'],'configured_max_windows':5,
        'observed_window_max_sec':bench['inference_sec_max'],
        'load_plus_five_observed_max_windows_sec':bench['model_load_sec']+5*bench['inference_sec_max'],
        'scope':'projection from three six-frame observations; excludes upload, refinement, startup and queue; not a measured full-video latency or guaranteed bound'}
(private/'latency-budget-safe-summary.json').write_text(json.dumps(budget,indent=2),encoding='utf-8')
print(json.dumps({'memory':summary,'budget_projection':budget}))
