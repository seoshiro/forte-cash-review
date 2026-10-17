"""Paired TRAIN/TUNE video-level candidate, reuses private local embeddings."""
from pathlib import Path
import json,numpy as np,time,statistics,joblib,hashlib
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import confusion_matrix,precision_recall_fscore_support
ROOT=Path(__file__).resolve().parents[1];cfg_path=ROOT/'config/video-baseline.json';cfg=json.loads(cfg_path.read_text());out=ROOT/'.private/video-baseline';out.mkdir(parents=True,exist_ok=True)
(out/'frozen-config.json').write_bytes(cfg_path.read_bytes());(out/'frozen-split.json').write_bytes((ROOT/'.private/dataset/split.json').read_bytes())
rows=json.loads((ROOT/'.private/dataset/manifest.json').read_text(encoding='utf-8'));items=[]
for r in rows:
    if r['split'] not in ['train','tune'] or r['error']:continue
    z=np.load(ROOT/'.private/cpu-baseline/features'/(r['sha256']+'.npz'));items.append((r,z['times'],z['features']))
def selected(n,strategy):return np.unique(np.linspace(0,n-1,min(12,n)).astype(int)) if strategy=='uniform' else np.arange(n)
def describe(f):
    diffs=np.diff(f,axis=0) if len(f)>1 else np.zeros_like(f)
    return np.concatenate([f.mean(0),f.std(0),f[-1]-f[0],np.abs(diffs).mean(0)])
train=[x for x in items if x[0]['split']=='train'];X=np.array([describe(f[selected(len(f),'uniform')]) for r,t,f in train]);y=np.array([r['target'] for r,t,f in train])
clf=make_pipeline(StandardScaler(),LogisticRegression(C=cfg['C'],class_weight='balanced',random_state=cfg['seed'],max_iter=2000));clf.fit(X,y);joblib.dump(clf,out/'video-proposal.joblib')
results={};private=[]
for strategy in ['uniform','dense_sequence']:
    truth=[];pred=[];errors=[];centers=[];start=time.monotonic()
    for r,t,f in items:
        if r['split']!='tune':continue
        idx=selected(len(f),strategy);v=f[idx];times=t[idx];score=float(clf.predict_proba(describe(v)[None])[0,1]);guess=int(score>=cfg['threshold'])
        # Candidate time is visual change, not a semantic action assertion.
        changes=np.linalg.norm(np.diff(v,axis=0),axis=1);which=int(np.argmax(changes)+1) if len(changes) else 0;sec=float(times[which]);truth.append(r['target']);pred.append(guess);centers.append(len(idx))
        if r['target'] and guess:errors.append(abs(sec-r['label_sec']))
        private.append({'sha256':r['sha256'],'strategy':strategy,'score':score,'prediction':guess,'candidate_time_sec':sec,'truth':r['target']})
    p,rec,f1,_=precision_recall_fscore_support(truth,pred,average='binary',zero_division=0)
    results[strategy]={'videos':len(truth),'confusion_matrix_tn_fp_fn_tp':confusion_matrix(truth,pred,labels=[0,1]).tolist(),'precision':p,'recall':rec,'f1':f1,'timestamp_matched_positive_count':len(errors),'timestamp_mae_sec':statistics.mean(errors) if errors else None,'candidate_frames_mean':statistics.mean(centers),'postprocess_total_sec':time.monotonic()-start}
summary={'scope':cfg['scope'],'train_videos':len(train),'tune_videos':sum(r['split']=='tune' for r,t,f in items),'results':results,'holdout_opened':False,'official_score':False,'config_sha256':hashlib.file_digest(cfg_path.open('rb'),'sha256').hexdigest(),'limitations':['Preliminary scene groups require local human review.','Candidate timestamps are based on embedding change; semantic localization not established.','Shared dense feature cache excludes extraction from reported postprocess time.','This is another experiment on the same tuning split, not a new independent test.']}
(out/'private-predictions.json').write_text(json.dumps(private),encoding='utf-8');(out/'safe-summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');print(json.dumps(summary))
