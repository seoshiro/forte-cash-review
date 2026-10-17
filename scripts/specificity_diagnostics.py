"""Aggregate-only controls and local mechanical checks; no private text output."""
from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[1];source=ROOT/'.private/structured/tune-uniform.safe-summary.json'
report=json.loads(source.read_text());tn,fp=report['confusion_matrix_tn_fp_fn_tp'][0];fn,tp=report['confusion_matrix_tn_fp_fn_tp'][1]
def metric(tn,fp,fn,tp):
    precision=tp/(tp+fp) if tp+fp else 0.;recall=tp/(tp+fn) if tp+fn else 0.;specificity=tn/(tn+fp) if tn+fp else 0.
    return {'tn':tn,'fp':fp,'fn':fn,'tp':tp,'precision':precision,'recall':recall,
            'specificity':specificity,'balanced_accuracy':(specificity+recall)/2,
            'f1':2*precision*recall/(precision+recall) if precision+recall else 0.}
negative=tn+fp;positive=fn+tp
controls={'split':'tune','videos':negative+positive,'results':{
    'baseline':metric(tn,fp,fn,tp),'always_positive':metric(0,negative,0,positive),
    'always_negative':metric(negative,0,positive,0)},
    'official_score':False,'limitation':'Repeated exploratory TUNE; preliminary scene groups; controls do not detect actions.'}
(ROOT/'.private/always-controls-safe-summary.json').write_text(json.dumps(controls,indent=2),encoding='utf-8')
counts={'videos':0,'observations':0,'empty_observations':0,'raw_events':0,
        'conditions_false_events':0,'below_threshold_events':0,'qualifying_events':0,
        'scope':'aggregate mechanics from stored TUNE observations; no descriptions, per-video annotations or rule IDs emitted'}
run=ROOT/'.private/experiments'/report['run_id']
for file in run.glob('*/observations.json'):
    counts['videos']+=1
    for observation in json.loads(file.read_text(encoding='utf-8')):
        value=observation.get('result',observation.get('refinement',{}));events=value.get('events',[])
        counts['observations']+=1;counts['empty_observations']+=not events;counts['raw_events']+=len(events)
        counts['conditions_false_events']+=sum(e['all_conditions_visible'] is False for e in events)
        counts['below_threshold_events']+=sum(e['confidence']<.8 for e in events)
        counts['qualifying_events']+=sum(e['all_conditions_visible'] is True and e['confidence']>=.8 for e in events)
(ROOT/'.private/local-mechanics-safe-summary.json').write_text(json.dumps(counts,indent=2),encoding='utf-8')
print(json.dumps({'controls':controls,'local_mechanics':counts}))
