"""Aggregate-only fit diagnostics and split checks. Holdout features never read."""
from pathlib import Path
import json,collections,numpy as np,joblib,time
from sklearn.metrics import confusion_matrix,precision_recall_fscore_support
ROOT=Path(__file__).resolve().parents[1]
manifest=json.loads((ROOT/'.private/dataset/manifest.json').read_text(encoding='utf-8'))
split=json.loads((ROOT/'.private/dataset/split.json').read_text(encoding='utf-8'))
groups=collections.defaultdict(set);hashes=collections.defaultdict(set)
for r in manifest:groups[r['group']].add(r['split']);hashes[r['sha256']].add(r['split'])
def sequence(f):
    result=[]
    for i in range(len(f)):
        w=f[max(0,i-1):min(len(f),i+2)];delta=w[-1]-w[0];result.append(np.concatenate([w.mean(0),delta,np.abs(delta)]))
    return np.array(result)
def video(f):
    delta=np.diff(f,axis=0) if len(f)>1 else np.zeros_like(f)
    return np.concatenate([f.mean(0),f.std(0),f[-1]-f[0],np.abs(delta).mean(0)])
models={k:joblib.load(ROOT/'.private'/p) for k,p in {'window':'cpu-baseline/event-proposal.joblib','video':'video-baseline/video-proposal.joblib'}.items()}
reports={}
for subset in ['train','tune']:
    data=[r for r in manifest if r['split']==subset and not r['error']]
    for method in ['window_uniform','window_refine','video_uniform','video_dense']:
        truth=[];pred=[];errors=[]
        for r in data:
            z=np.load(ROOT/'.private/cpu-baseline/features'/(r['sha256']+'.npz'));times=z['times'];f=z['features'];idx=np.unique(np.linspace(0,len(f)-1,min(12,len(f))).astype(int))
            if method.startswith('window'):
                desc=sequence(f);scores=models['window'].predict_proba(desc[idx])[:,1]
                if method=='window_refine':
                    candidates=set(idx.tolist())
                    for i in idx[np.argsort(scores)[-3:]]:candidates.update(np.where(abs(times-times[i])<=4)[0].tolist())
                    idx=np.array(sorted(candidates));scores=models['window'].predict_proba(desc[idx])[:,1]
                best=int(np.argmax(scores));guess=int(scores[best]>=.5);sec=float(times[idx[best]])
            else:
                if method=='video_dense':idx=np.arange(len(f))
                selected=f[idx];score=float(models['video'].predict_proba(video(selected)[None])[0,1]);guess=int(score>=.5);changes=np.linalg.norm(np.diff(selected,axis=0),axis=1);sec=float(times[idx[int(np.argmax(changes)+1) if len(changes) else 0]])
            truth.append(r['target']);pred.append(guess)
            if r['target'] and guess:errors.append(abs(sec-r['label_sec']))
        p,rec,f1,_=precision_recall_fscore_support(truth,pred,average='binary',zero_division=0)
        reports[subset+'_'+method]={'videos':len(data),'confusion_matrix_tn_fp_fn_tp':confusion_matrix(truth,pred,labels=[0,1]).tolist(),'precision':p,'recall':rec,'f1':f1,'matched_timing_count':len(errors),'timestamp_mae_sec':float(np.mean(errors)) if errors else None}
audit={'checked_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'holdout_opened':split['holdout_opened'],'groups_crossing_split':sum(len(v)>1 for v in groups.values()),'exact_hashes_crossing_split':sum(len(v)>1 for v in hashes.values()),'exact_unique_hashes':len(hashes),'preliminary_groups':len(groups),'group_counts':{part:len({r['group'] for r in manifest if r['split']==part}) for part in ['train','tune','holdout']},'predictor_inputs':'Pixel-derived embeddings and chronological within-video differences only. SHA256 is cache key; file name, normalized ID, row order and labels are not classifier features. Targets/timestamps used for train selection and evaluation only.','adjacent_take_independence':'NOT VERIFIED by human: automatic sha256/dhash grouping only','reports':reports,'train_metric_scope':'in-sample fit diagnostic, not validation performance','tune_metric_scope':'repeated exploratory use, not independent final test'}
out=ROOT/'.private/baseline-audit';out.mkdir(exist_ok=True);(out/'safe-summary.json').write_text(json.dumps(audit,indent=2),encoding='utf-8');print(json.dumps(audit))
