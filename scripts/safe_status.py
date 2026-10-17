"""Technical/aggregate checkpoint only. Never reads semantic outputs or evidence."""
from pathlib import Path
import json,time,sys
ROOT=Path(__file__).resolve().parents[1];private=ROOT/'.private'
record={'checked_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}
for name,relative in [('pipeline','vlm-pipeline/status.json'),('security','security-safe-summary.json'),('ui','ui-qa/safe-summary.json')]:
    p=private/relative
    if p.exists():
        d=json.loads(p.read_text(encoding='utf-8'))
        if name=='ui':d={k:d[k] for k in ['status','page_errors','external_requests','elapsed_sec','detector_quality_tested']}
        record[name]=d
record['downloads']={}
for p in (private/'bootstrap').glob('*.progress.json'):
    d=json.loads(p.read_text(encoding='utf-8'))
    label='cuda_wheel' if p.name.startswith('torch-') else 'qwen_weights' if d.get('total')==4255140312 else 'dino_weights' if d.get('total')==88249960 else 'portable_runtime'
    record['downloads'][label]=d
split=json.loads((private/'dataset/split.json').read_text(encoding='utf-8'))
record['holdout_opened']=split['holdout_opened']
(private/'status-safe-summary.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
if '--compact' in sys.argv:
    print(json.dumps({'checked_utc':record['checked_utc'],'stage':record.get('pipeline',{}).get('stage'),'downloads':{k:{'bytes':v['bytes'],'total':v['total'],'remaining_bytes':v['total']-v['bytes'],'updated_utc':v['updated_utc']} for k,v in record['downloads'].items() if k in ['qwen_weights','cuda_wheel']},'holdout_opened':record['holdout_opened']}))
else:print(json.dumps(record))
