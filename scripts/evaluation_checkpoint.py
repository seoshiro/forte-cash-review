"""Safe aggregate recovery/checkpoint; never emits per-video model results.

Partial runs expose only technical completion/schema/latency aggregates. Quality
metrics are emitted only after all requested videos have stored a result.
"""
from pathlib import Path
import json,statistics,time,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from cashreview.schemas import Done
from sklearn.metrics import confusion_matrix,precision_recall_fscore_support
manifest=json.loads((ROOT/'.private/dataset/manifest.json').read_text(encoding='utf-8'))
reports=[]
for run in sorted((ROOT/'.private/experiments').glob('*-uniform-*')):
    if not (run/'frozen-config.json').is_file():continue
    config=json.loads((run/'frozen-config.json').read_text())
    if config.get('prompt_revision')!='constrained-frame-id-3':continue
    split=run.name.rsplit('-',1)[-1]
    if split not in ['train','tune']:continue
    rows=[r for r in manifest if r['split']==split and not r['error']]
    y=[];pred=[];latency=[];timing=[];invalid=0
    for index,row in enumerate(rows):
        folder=run/f'{index:03d}';result=folder/'result.json'
        if not result.is_file():continue
        try:
            data=Done.model_validate_json(result.read_text(encoding='utf-8')).model_dump()
            y.append(row['target']);pred.append(int(data['verdict']=='violation'))
            if row['target'] and pred[-1] and row['label_sec'] is not None:
                timing.append(min(abs(v['timecode_sec']-row['label_sec']) for v in data['violations']))
            metric=json.loads((folder/'metrics.json').read_text())
            latency.append(metric['elapsed_sec'])
        except Exception:invalid+=1
    complete=len(y)==len(rows) and invalid==0
    report={'run_id':run.name,'split':split,'requested':len(rows),
            'stored_valid_results':len(y),'invalid_stored_results':invalid,
            'complete':complete,'latency_mean_sec':statistics.mean(latency) if latency else None,
            'latency_max_sec':max(latency) if latency else None,
            'over_300_sec':sum(x>300 for x in latency),
            'latency_scope':'completed engine.analyze attempts only; excludes upload, queue and model load',
            'quality_status':'complete aggregate' if complete else 'withheld until split completion'}
    if complete:
        precision,recall,f1,_=precision_recall_fscore_support(y,pred,average='binary',zero_division=0)
        report.update(confusion_matrix_tn_fp_fn_tp=confusion_matrix(y,pred,labels=[0,1]).tolist(),
                      precision=precision,recall=recall,f1=f1,
                      matched_positive_timing_count=len(timing),
                      timestamp_mae_sec=statistics.mean(timing) if timing else None)
    reports.append(report)
summary={'checked_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
         'holdout_read':False,'reports':reports}
(ROOT/'.private/evaluation-checkpoint-safe-summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
print(json.dumps(summary))
