"""Fixed bag/window comparison with group isolation."""
import numpy as np
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from qvt_candidate.evaluate import metrics


def fit(items,arm,cfg):
    X=[];y=[];weights=[];counts={v:sum(item['target']==v for item in items) for v in [0,1]}
    if not all(counts.values()):raise ValueError('Both training classes required')
    for item in items:
        if arm=='bag':values=item['bag'][None]
        elif item['target']:
            index=int(np.argmin(abs(item['window_times']-item['label_sec'])));values=item['windows'][index:index+1]
        else:values=item['windows']
        for value in values:
            X.append(value);y.append(item['target']);weights.append(len(items)/(2*counts[item['target']]*len(values)))
    head=cfg['head'];model=make_pipeline(StandardScaler(),LogisticRegression(C=head['C'],solver=head['solver'],
        random_state=head['seed'],max_iter=head['max_iter']))
    model.fit(np.asarray(X),np.asarray(y),logisticregression__sample_weight=np.asarray(weights));return model


def score(model,features,arm):
    # This interface has no label, point timestamp, ID or original filename.
    values=features['bag'][None] if arm=='bag' else features['windows']
    scores=model.predict_proba(values)[:,1]
    return float(scores[0] if arm=='bag' else max(scores))


def grouped_oof(items,cfg):
    results={};private={}
    for arm in ['window','bag']:
        records=[]
        for group in sorted({item['group'] for item in items}):
            model=fit([item for item in items if item['group']!=group],arm,cfg)
            for item in items:
                if item['group']!=group:continue
                value=score(model,{'bag':item['bag'],'windows':item['windows']},arm)
                records.append({'truth':item['target'],'prediction':int(value>=cfg['head']['threshold']),
                    'score':value,'error_sec':None,'source_sha256':item['sha256']})
        results[arm]=metrics(records);private[arm]=records
    for value,name in [(0,'constant_negative'),(1,'constant_positive')]:
        results[name]=metrics([{'truth':i['target'],'prediction':value,'error_sec':None} for i in items])
    return results,private


def accepted(results,cfg):
    r=results['bag'];w=results['window'];a=cfg['acceptance']
    return bool(r['recall']>=a['bag_recall_min'] and r['specificity']>=a['bag_specificity_min']
        and r['balanced_accuracy']>=a['bag_balanced_accuracy_min'] and r['f1']>=a['bag_f1_min']
        and r['balanced_accuracy']>=w['balanced_accuracy']+a['bag_balanced_accuracy_advantage_over_window_min'])
