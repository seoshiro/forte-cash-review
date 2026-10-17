"""One fixed fold-only discriminative head; predictions accept features/PTS only."""
import time,warnings
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.exceptions import ConvergenceWarning
from sklearn.metrics import roc_auc_score
from .evaluate import unit,centroids,score_video
from qvt_candidate.evaluate import metrics


def validate_items(items):
    if not items or len({i['sha256'] for i in items})!=len(items):raise ValueError('Unique contents required')
    dimensions=set()
    for item in items:
        f=np.asarray(item['ordered']);t=np.asarray(item['times'])
        if f.ndim!=2 or t.ndim!=1 or len(t)!=len(f) or len(t)<2:raise ValueError('Invalid cached arrays')
        if not np.isfinite(f).all() or not np.isfinite(t).all() or np.any(np.diff(t)<=0) or t[0]<0:raise ValueError('Invalid features or PTS')
        if np.any(np.linalg.norm(f,axis=1)<1e-9):raise ValueError('Degenerate vector')
        if type(item['target']) is not int or item['target'] not in (0,1):raise ValueError('Invalid binary target')
        point=item['label_sec']
        if item['target'] and (point is None or not np.isfinite(point) or point<0):raise ValueError('Positive needs point')
        if not item['target'] and point is not None:raise ValueError('Negative has no point')
        if not isinstance(item['group'],str) or not item['group']:raise ValueError('Group required')
        dimensions.add(f.shape[1])
    if len(dimensions)!=1:raise ValueError('Inconsistent feature dimension')


def supervised_windows(train):
    counts={c:sum(item['target']==c for item in train) for c in (0,1)}
    if not all(counts.values()):raise ValueError('Both classes required inside train fold')
    X=[];y=[];weights=[]
    for item in train:
        vectors=unit(np.asarray(item['ordered'],dtype=np.float64))
        indices=[int(np.argmin(abs(item['times']-item['label_sec'])))] if item['target'] else list(range(len(vectors)))
        weight=len(train)/(2*counts[item['target']]*len(indices))
        for index in indices:X.append(vectors[index]);y.append(item['target']);weights.append(weight)
    return np.asarray(X),np.asarray(y),np.asarray(weights)


def fit_head(train,cfg):
    X,y,weights=supervised_windows(train);h=cfg['head']
    scaler=StandardScaler().fit(X,sample_weight=weights)
    model=LogisticRegression(C=h['C'],penalty=h['penalty'],solver=h['solver'],fit_intercept=h['fit_intercept'],
        class_weight=h['class_weight'],tol=h['tol'],max_iter=h['max_iter'],random_state=h['seed'])
    with warnings.catch_warnings():
        warnings.simplefilter('error',ConvergenceWarning)
        model.fit(scaler.transform(X),y,sample_weight=weights)
    if not np.isfinite(model.coef_).all() or not np.isfinite(model.intercept_).all():raise ValueError('Nonfinite head')
    return scaler,model


def predict_head(head,features,times,threshold_logit):
    # No label, official point, name, group or source digest is accepted.
    scaler,model=head;scores=model.decision_function(scaler.transform(unit(np.asarray(features,dtype=np.float64))))
    if len(scores)!=len(times) or not np.isfinite(scores).all():raise ValueError('Invalid scores')
    index=int(np.argmax(scores))
    return {'prediction':int(scores[index]>=threshold_logit),'score':float(scores[index]),'time_sec':float(times[index])}


def report(records):
    result=metrics(records);errors=[r['error_sec'] for r in records if r['truth']]
    result.update(video_roc_auc=float(roc_auc_score([r['truth'] for r in records],[r['score'] for r in records])),
        all_positive_candidate_point_count=len(errors),all_positive_candidate_point_mae_sec=float(np.mean(errors)),
        all_positive_candidate_point_median_error_sec=float(np.median(errors)))
    return result


def evaluate(items,cfg,check=lambda:None):
    validate_items(items);groups=sorted({i['group'] for i in items});records={'baseline':[],'linear_head':[]}
    costs={name:{'fold_fit_sec':[],'video_score_sec':[]} for name in records};iterations=[]
    for group in groups:
        check();train=[i for i in items if i['group']!=group];test=[i for i in items if i['group']==group]
        if not train or not test or {i['group'] for i in train}&{i['group'] for i in test}:raise ValueError('Group exclusion failed')
        start=time.perf_counter();p,n=centroids(train,'ordered');costs['baseline']['fold_fit_sec'].append(time.perf_counter()-start)
        start=time.perf_counter();head=fit_head(train,cfg);costs['linear_head']['fold_fit_sec'].append(time.perf_counter()-start)
        iterations.append(int(head[1].n_iter_.max()));check()
        for item in test:
            start=time.perf_counter();score,sec=score_video(item['ordered'],item['times'],p,n,'max')
            costs['baseline']['video_score_sec'].append(time.perf_counter()-start)
            a={'prediction':int(score>=0),'score':score,'time_sec':sec}
            start=time.perf_counter();b=predict_head(head,item['ordered'],item['times'],cfg['head']['threshold_logit'])
            costs['linear_head']['video_score_sec'].append(time.perf_counter()-start)
            for name,row in [('baseline',a),('linear_head',b)]:
                row.update(truth=item['target'],source_sha256=item['sha256'],group=group,
                    error_sec=abs(row['time_sec']-item['label_sec']) if item['target'] else None)
                records[name].append(row)
            check()
    aggregate={name:report(rows) for name,rows in records.items()}
    a={r['source_sha256']:r for r in records['baseline']};b={r['source_sha256']:r for r in records['linear_head']}
    common=[key for key in a if a[key]['truth'] and a[key]['prediction'] and b[key]['prediction']]
    paired={'common_true_positive_count':len(common),
        'baseline_candidate_point_mae_sec':float(np.mean([a[key]['error_sec'] for key in common])) if common else None,
        'linear_candidate_point_mae_sec':float(np.mean([b[key]['error_sec'] for key in common])) if common else None}
    runtime={name:{key+'_sum':float(sum(vals)) for key,vals in values.items()} for name,values in costs.items()}
    for name in costs:
        runtime[name].update(folds=len(groups),scored_videos=len(items),video_score_sec_mean=float(np.mean(costs[name]['video_score_sec'])),
            video_score_sec_max=max(costs[name]['video_score_sec']))
    gate=cfg['binary_gate'];cm=aggregate['linear_head']['confusion_matrix_tn_fp_fn_tp']
    binary=cm[1][0]<=gate['fn_max'] and cm[0][1]<=gate['fp_max'] and aggregate['linear_head']['f1']>=gate['f1_min']
    point=bool(common and aggregate['linear_head']['all_positive_candidate_point_mae_sec']<=aggregate['baseline']['all_positive_candidate_point_mae_sec']
        and paired['linear_candidate_point_mae_sec']<=paired['baseline_candidate_point_mae_sec'])
    return {'results':aggregate,'paired_point_diagnostic':paired,'cache_only_cpu_runtime':runtime,
        'maximum_optimizer_iterations':max(iterations),'binary_gate_passed':bool(binary),
        'point_non_regression_gate_passed':point,'joint_useful_gate_passed':bool(binary and point)},records
