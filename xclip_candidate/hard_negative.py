"""One fixed training-fold hard-negative prototype, no model/media access."""
import numpy as np
from .evaluate import centroids,unit,score_video
from qvt_candidate.evaluate import metrics
from sklearn.metrics import roc_auc_score


def fit(items,cfg):
    positive,_=centroids(items,'ordered');negative=[];spec=cfg['negative_prototype']
    for item in items:
        if item['target']:continue
        vectors=unit(item['ordered']);scores=vectors@positive;selected=[]
        for index in np.argsort(-scores,kind='stable'):
            if all(abs(float(item['times'][index])-float(item['times'][i]))>=spec['minimum_center_separation_sec'] for i in selected):selected.append(int(index))
            if len(selected)==spec['windows_per_negative_video']:break
        if len(selected)!=spec['windows_per_negative_video']:raise ValueError('Registered separated negative-window count unavailable')
        negative.append(vectors[selected].mean(0))
    if not negative:raise ValueError('Negative TRAIN examples required')
    result=unit(np.mean(negative,axis=0))
    if np.linalg.norm(result)<.99:raise ValueError('Degenerate hard-negative prototype')
    return positive,result


def evaluate(items,cfg):
    arms={'baseline':[],'hard_negative':[]}
    for group in sorted({i['group'] for i in items}):
        training=[i for i in items if i['group']!=group]
        prototypes={'baseline':centroids(training,'ordered'),'hard_negative':fit(training,cfg)}
        for item in items:
            if item['group']!=group:continue
            for arm,(positive,negative) in prototypes.items():
                score,sec=score_video(item['ordered'],item['times'],positive,negative,'max')
                arms[arm].append({'truth':item['target'],'prediction':int(score>=0),'score':score,
                    'error_sec':abs(sec-item['label_sec']) if item['target'] else None,'source_sha256':item['sha256']})
    aggregate={}
    for name,rows in arms.items():
        aggregate[name]=metrics(rows);aggregate[name]['video_roc_auc']=float(roc_auc_score([r['truth'] for r in rows],[r['score'] for r in rows]))
    return aggregate,arms
