"""Grouped evaluation. Official labels stay on the supervision/evaluation side."""
import numpy as np
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import confusion_matrix,precision_recall_fscore_support
from qvt_candidate.features import representations


def fit(train,arm,cfg):
    X=[];y=[];weights=[]
    counts={label:sum(item['target']==label for item in train) for label in [0,1]}
    if not all(counts.values()):raise ValueError('Training fold needs both labels')
    for item in train:
        f=representations(item['features'])[arm]
        indices=[int(np.argmin(abs(item['times']-item['label_sec'])))] if item['target'] else list(range(len(f)))
        for i in indices:
            X.append(f[i]);y.append(item['target']);weights.append(len(train)/(2*counts[item['target']]*len(indices)))
    head=cfg['head']
    model=make_pipeline(StandardScaler(),LogisticRegression(C=head['C'],solver=head['solver'],
        max_iter=head['max_iter'],random_state=head['seed']))
    model.fit(np.asarray(X),np.array(y),logisticregression__sample_weight=np.array(weights))
    return model


def predict(model,times,features,arm,threshold):
    # Pure content features + decoded PTS: no label, name, source ID or oracle center.
    scores=model.predict_proba(representations(features)[arm])[:,1]
    index=int(np.argmax(scores))
    return {'prediction':int(scores[index]>=threshold),'time_sec':float(times[index]),'score':float(scores[index])}


def metrics(records):
    truth=[r['truth'] for r in records];pred=[r['prediction'] for r in records]
    cm=confusion_matrix(truth,pred,labels=[0,1]).tolist();tn,fp,fn,tp=cm[0][0],cm[0][1],cm[1][0],cm[1][1]
    p,rec,f1,_=precision_recall_fscore_support(truth,pred,average='binary',zero_division=0)
    errors=[r['error_sec'] for r in records if r['truth'] and r['prediction'] and r['error_sec'] is not None]
    specificity=tn/(tn+fp) if tn+fp else 0
    return {'videos':len(records),'confusion_matrix_tn_fp_fn_tp':cm,'precision':float(p),'recall':float(rec),
        'f1':float(f1),'specificity':specificity,'balanced_accuracy':(float(rec)+specificity)/2,
        'timestamp_matched_positive_videos':len(errors),'timestamp_mae_sec':float(np.mean(errors)) if errors else None,
        'timestamp_median_error_sec':float(np.median(errors)) if errors else None}


def grouped_oof(items,cfg):
    groups=sorted(set(item['group'] for item in items));private={};reports={}
    for arm in ['static','temporal']:
        records=[]
        for group in groups:
            model=fit([item for item in items if item['group']!=group],arm,cfg)
            for item in items:
                if item['group']!=group:continue
                row=predict(model,item['times'],item['features'],arm,cfg['head']['threshold'])
                row.update(truth=item['target'],source_sha256=item['sha256'],group=group,
                    error_sec=abs(row['time_sec']-item['label_sec']) if item['target'] else None)
                records.append(row)
        private[arm]=records;reports[arm]=metrics(records)
    for value,name in [(0,'constant_negative'),(1,'constant_positive')]:
        reports[name]=metrics([{'truth':item['target'],'prediction':value,'error_sec':None} for item in items])
        reports[name]['timestamp_mae_sec']=None;reports[name]['timestamp_median_error_sec']=None
    return reports,private


def accepted(reports,cfg):
    a=cfg['acceptance'];r=reports['temporal'];s=reports['static']
    quality=(r['recall']>=a['train_group_oof_recall_min'] and r['specificity']>=a['train_group_oof_specificity_min']
        and r['balanced_accuracy']>=a['train_group_oof_balanced_accuracy_min'] and r['f1']>=a['train_group_oof_f1_min']
        and r['timestamp_mae_sec'] is not None and r['timestamp_mae_sec']<=a['train_timestamp_mae_max_sec'])
    timing_advantage=(r['timestamp_mae_sec'] is not None and s['timestamp_mae_sec'] is not None
        and r['timestamp_mae_sec']<=s['timestamp_mae_sec']-1 and r['f1']>=s['f1'])
    advantage=r['balanced_accuracy']>=s['balanced_accuracy']+0.05 or timing_advantage
    return bool(quality and advantage and r['balanced_accuracy']>0.5)
