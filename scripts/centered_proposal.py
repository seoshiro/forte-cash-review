"""TRAIN group-CV feature debiasing experiment; aggregate-only stdout, holdout closed."""
from pathlib import Path
import os,sys,json,time,hashlib,statistics
os.environ.update(OMP_NUM_THREADS='4',MKL_NUM_THREADS='4',OPENBLAS_NUM_THREADS='4')
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));os.chdir(ROOT)
from cashreview.offline import deny_network
deny_network()
import numpy as np,joblib
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.metrics import confusion_matrix,precision_recall_fscore_support,balanced_accuracy_score,roc_auc_score

cfg_path=ROOT/'config/centered-proposal.json';cfg=json.loads(cfg_path.read_text())
out=ROOT/'.private/centered-proposal';out.mkdir(parents=True,exist_ok=True)
(out/'protocol.json').write_bytes(cfg_path.read_bytes())
(out/'frozen-split.json').write_bytes((ROOT/'.private/dataset/split.json').read_bytes())
rows=json.loads((ROOT/'.private/dataset/manifest.json').read_text(encoding='utf-8'))


def load(split,variant):
    items=[]
    for r in rows:
        if r['split']!=split or r['error']:continue
        path=ROOT/'.private/cpu-baseline/features'/(r['sha256']+'.npz')
        z=np.load(path);f=z['features'];desc=[]
        for i in range(len(f)):
            w=f[max(0,i-1):min(len(f),i+2)];delta=w[-1]-w[0]
            base=w.mean(0)-(f.mean(0) if variant=='centered_sequence' else 0)
            desc.append(np.concatenate([base,delta,np.abs(delta)]))
        items.append((r,z['times'],np.array(desc)))
    return items


def fit(items,C):
    counts={v:sum(r['target']==v for r,_,_ in items) for v in [0,1]};X=[];y=[];weights=[]
    for r,t,d in items:
        label=r['target']
        if label:
            i=int(np.argmin(abs(t-r['label_sec'])));idx=np.arange(max(0,i-1),min(len(t),i+2))
        else:idx=np.unique(np.linspace(0,len(t)-1,min(12,len(t))).astype(int))
        X.extend(d[idx]);y.extend([label]*len(idx));weights.extend([len(items)/(2*counts[label]*len(idx))]*len(idx))
    model=make_pipeline(StandardScaler(),LogisticRegression(C=C,max_iter=2000,random_state=cfg['seed']))
    model.fit(np.array(X),np.array(y),logisticregression__sample_weight=np.array(weights));return model


def score(model,item,strategy):
    r,t,d=item;idx=np.unique(np.linspace(0,len(t)-1,min(cfg['uniform_centers'],len(t))).astype(int))
    p=model.predict_proba(d[idx])[:,1]
    if strategy=='coarse_refine':
        selected=idx[np.argsort(p)[-cfg['refine_candidates']:]];candidates=set(idx.tolist())
        for i in selected:candidates.update(np.where(abs(t-t[i])<=cfg['refine_radius_sec'])[0].tolist())
        idx=np.array(sorted(candidates));p=model.predict_proba(d[idx])[:,1]
    best=int(np.argmax(p));return float(p[best]),float(t[idx[best]])


def metrics(truth,scores,threshold,timing=None):
    pred=np.array(scores)>=threshold;p,r,f,_=precision_recall_fscore_support(truth,pred,average='binary',zero_division=0)
    result={'videos':len(truth),'confusion_matrix_tn_fp_fn_tp':confusion_matrix(truth,pred,labels=[0,1]).tolist(),'precision':p,'recall':r,'f1':f,'balanced_accuracy':balanced_accuracy_score(truth,pred),'roc_auc':roc_auc_score(truth,scores)}
    if timing is not None:
        errors=[abs(sec-target) for label,guess,(sec,target) in zip(truth,pred,timing) if label and guess and target is not None]
        result.update(timestamp_matched_positive_count=len(errors),timestamp_mae_sec=statistics.mean(errors) if errors else None)
    return result


started=time.monotonic();results={};selected={};private=[]
for variant in cfg['variants']:
    train=load('train',variant);truth=[r['target'] for r,_,_ in train];groups=[r['group'] for r,_,_ in train]
    folds=list(StratifiedGroupKFold(n_splits=cfg['train_group_folds'],shuffle=True,random_state=cfg['seed']).split(np.zeros(len(train)),truth,groups))
    candidates={s:[] for s in ['uniform','coarse_refine']}
    for C in cfg['C_candidates']:
        oof={s:np.zeros(len(train)) for s in candidates}
        for fit_idx,test_idx in folds:
            model=fit([train[i] for i in fit_idx],C)
            for i in test_idx:
                for strategy in candidates:oof[strategy][i]=score(model,train[i],strategy)[0]
        for strategy in candidates:
            for threshold in cfg['threshold_candidates']:
                m=metrics(truth,oof[strategy],threshold)
                candidates[strategy].append({'C':C,'threshold':threshold,'train_cv':m})
    selected[variant]={s:max(values,key=lambda x:(x['train_cv']['balanced_accuracy'],x['train_cv']['f1'],x['train_cv']['precision'],-x['C'])) for s,values in candidates.items()}
    # Save train-only choices BEFORE loading/evaluating tuning features and labels.
    (out/('selected-before-tune-'+variant+'.json')).write_text(json.dumps(selected[variant],indent=2),encoding='utf-8')
    tune=load('tune',variant);tune_truth=[r['target'] for r,_,_ in tune]
    for strategy,choice in selected[variant].items():
        model=fit(train,choice['C']);joblib.dump(model,out/(variant+'-'+strategy+'.joblib'))
        scored=[score(model,item,strategy) for item in tune]
        results['tune_'+variant+'_'+strategy]=metrics(tune_truth,[x[0] for x in scored],choice['threshold'],[(x[1],item[0]['label_sec']) for x,item in zip(scored,tune)])
        results['train_cv_'+variant+'_'+strategy]=choice['train_cv']
        for item,(value,sec) in zip(tune,scored):private.append({'sha256':item[0]['sha256'],'variant':variant,'strategy':strategy,'score':value,'timestamp_sec':sec,'truth':item[0]['target']})
control_truth=[r['target'] for r,_,_ in tune]
results['tune_constant_positive']=metrics(control_truth,np.ones(len(tune)),.5)
results['tune_constant_negative']=metrics(control_truth,np.zeros(len(tune)),.5)
summary={'scope':cfg['scope'],'hypothesis':cfg['hypothesis'],'train_videos':len(train),'tune_videos':len(tune),'results':results,'selection_source':'train-only group CV','postprocess_total_sec':time.monotonic()-started,'holdout_opened':False,'official_score':False,'limitations':['Same exploratory tuning split reused; this is not independent final evidence.','Preliminary scene groups need human review.','Shared cached DINO extraction excluded from timing.','One timestamp is incomplete event truth; semantic type and evidence relevance unmeasured.']}
(out/'safe-summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
(out/'private-predictions.json').write_text(json.dumps(private),encoding='utf-8')
print(json.dumps(summary))
