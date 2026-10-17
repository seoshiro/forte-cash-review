"""Bounded aggregate Windows GPU gauges; no model or dataset access."""
from pathlib import Path
import subprocess,sys,time,json
ROOT=Path(__file__).resolve().parents[1]
out=ROOT/'.private/memory-watch';out.mkdir(exist_ok=True)
end=time.monotonic()+600;records=[]
while time.monotonic()<end:
    result=subprocess.run([sys.executable,'scripts/observe_gpu_memory.py'],cwd=ROOT,capture_output=True,text=True,timeout=20)
    if result.returncode==0:
        record=json.loads(result.stdout)
        if record.get('owned_model_processes',0) and any(x['matching_counter_instances'] for x in record.get('process_gauges',{}).values()):records.append(record)
        if records and not record.get('owned_model_processes'):break
    summary={'samples_with_matching_process_counter':len(records),
             'scope':'independent gauge maxima, not simultaneous; synthetic and TRAIN benchmark only',
             'bank_data_read':False,'max_process_mib':{},'max_adapter_mib':{}}
    for name in ['Dedicated Usage','Shared Usage','Total Committed']:
        summary['max_process_mib'][name]=max((r['process_gauges'][name]['mib'] for r in records),default=None)
    for name in ['physical_total','driver_reserved','fb_used','fb_free']:
        summary['max_adapter_mib'][name]=max((r['nvidia_smi_mib'][0][name] for r in records if r.get('nvidia_smi_mib')),default=None)
    summary['updated_utc']=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())
    (out/'safe-summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    (out/'gauge-samples.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
    time.sleep(5)
print(json.dumps(summary))
