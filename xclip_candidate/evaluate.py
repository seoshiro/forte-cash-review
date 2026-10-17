"""Equal-video cosine centroids; fixed raw max and two-window persistence."""
import numpy as np
from sklearn.metrics import roc_auc_score
from qvt_candidate.evaluate import metrics


def unit(values):return values/np.maximum(np.linalg.norm(values,axis=-1,keepdims=True),1e-9)


def centroids(items,arm):
    positive=[];negative=[]
    for item in items:
        vectors=unit(item[arm])
        if item['target']:
            index=int(np.argmin(abs(item['times']-item['label_sec'])));positive.append(vectors[index])
        else:negative.append(vectors.mean(0))
    if not positive or not negative:raise ValueError('Each fold needs both classes')
    p=unit(np.mean(positive,axis=0));n=unit(np.mean(negative,axis=0))
    if min(np.linalg.norm(p),np.linalg.norm(n))<.99:raise ValueError('Degenerate centroid')
    return p,n


def pool(scores,times,mode):
    scores=np.asarray(scores);times=np.asarray(times)
    if len(scores)!=len(times) or len(scores)<2 or not np.isfinite(scores).all():raise ValueError('Invalid window scores')
    if mode=='max':index=int(np.argmax(scores));return float(scores[index]),float(times[index])
    if mode!='persistence':raise ValueError('Unknown fixed pooling')
    pairs=np.minimum(scores[:-1],scores[1:]);index=int(np.argmax(pairs))
    return float(pairs[index]),float((times[index]+times[index+1])/2)


def score_video(features,times,positive,negative,mode):
    # No source ID, filename, label or oracle point is accepted here.
    vectors=unit(features);scores=vectors@positive-vectors@negative
    return pool(scores,times,mode)


def grouped_oof(items,cfg):
    results={};private={};threshold=cfg['decision']['threshold']
    for arm in ['ordered','repeated']:
        records={mode:[] for mode in ['max','persistence']}
        for group in sorted({item['group'] for item in items}):
            positive,negative=centroids([item for item in items if item['group']!=group],arm)
            for item in items:
                if item['group']!=group:continue
                for mode in records:
                    score,sec=score_video(item[arm],item['times'],positive,negative,mode)
                    records[mode].append({'truth':item['target'],'prediction':int(score>=threshold),'score':score,
                        'time_sec':sec,'error_sec':abs(sec-item['label_sec']) if item['target'] else None,'source_sha256':item['sha256']})
        for mode,rows in records.items():
            name=arm+'_'+mode;result=metrics(rows)
            result['video_roc_auc']=float(roc_auc_score([r['truth'] for r in rows],[r['score'] for r in rows]))
            results[name]=result;private[name]=rows
    for value,name in [(0,'constant_negative'),(1,'constant_positive')]:
        results[name]=metrics([{'truth':item['target'],'prediction':value,'error_sec':None} for item in items])
    return results,private


def accepted(results,cfg):
    p=results['ordered_persistence'];r=results['repeated_persistence'];m=results['ordered_max'];a=cfg['acceptance']
    return bool(p['recall']>=a['ordered_persistence_recall_min'] and p['specificity']>=a['ordered_persistence_specificity_min']
        and p['f1']>=a['ordered_persistence_f1_min'] and p['balanced_accuracy']>=a['ordered_persistence_balanced_accuracy_min']
        and p['balanced_accuracy']>=r['balanced_accuracy']+a['ordered_vs_repeated_persistence_balanced_accuracy_gain_min']
        and p['confusion_matrix_tn_fp_fn_tp'][1][0]<=m['confusion_matrix_tn_fp_fn_tp'][1][0]
        and m['confusion_matrix_tn_fp_fn_tp'][0][1]-p['confusion_matrix_tn_fp_fn_tp'][0][1]>=a['persistence_fp_reduction_min'])
