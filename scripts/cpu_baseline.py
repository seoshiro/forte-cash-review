"""Real TRAIN/TUNE only. Raw frames/features/predictions stay local.

Weakly supervised event proposals, NOT a legal-rule/type detector.
"""
from pathlib import Path
import os,sys,time,json,hashlib,statistics
os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1',DO_NOT_TRACK='1')
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));os.chdir(ROOT)
from cashreview.offline import deny_network
deny_network()
import numpy as np,torch,joblib,psutil
from transformers import AutoImageProcessor,AutoModel
from cashreview.video import sample
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import confusion_matrix,precision_recall_fscore_support


def descriptors(features):
    out=[]
    for i in range(len(features)):
        window=features[max(0,i-1):min(len(features),i+2)]
        delta=window[-1]-window[0]
        out.append(np.concatenate([window.mean(0),delta,np.abs(delta)]))
    return np.asarray(out)


def main():
    cfg=json.loads(Path('config/cpu-baseline.json').read_text());data=json.loads(Path('.private/dataset/manifest.json').read_text(encoding='utf-8'))
    rows=sorted([r for r in data if r['split'] in ['train','tune'] and not r['error']],key=lambda r:r['split']!='train')
    run=Path('.private/cpu-baseline');run.mkdir(parents=True,exist_ok=True);cache=run/'features';cache.mkdir(exist_ok=True)
    (run/'frozen-config.json').write_text(json.dumps(cfg,indent=2),encoding='utf-8');(run/'frozen-split.json').write_bytes(Path('.private/dataset/split.json').read_bytes())
    torch.set_num_threads(4);start=time.monotonic();path=ROOT/'models/dinov2-small'
    processor=AutoImageProcessor.from_pretrained(str(path),local_files_only=True,use_fast=False)
    model=AutoModel.from_pretrained(str(path),local_files_only=True,use_safetensors=True).eval()
    load_sec=time.monotonic()-start;feature_times=[];items=[];frame_counts=[]
    for j,r in enumerate(rows):
        start=time.monotonic();file=cache/(r['sha256']+'.npz')
        if file.exists():
            z=np.load(file);times=z['times'];features=z['features'];elapsed=float(z['elapsed'])
        else:
            # Dense extraction is shared for paired quality evaluation. Its cost is reported separately.
            frames=sample(Path(r['path']),np.arange(0,max(.01,r['duration_sec']-.1),cfg['frame_step_sec']).tolist(),max_side=224)
            times=np.array([f.sec for f in frames]);embeddings=[]
            with torch.inference_mode():
                for k in range(0,len(frames),4):
                    inputs=processor(images=[f.image for f in frames[k:k+4]],return_tensors='pt')
                    embeddings.append(model(**inputs).last_hidden_state[:,0].cpu().numpy())
            features=np.concatenate(embeddings);features/=np.maximum(np.linalg.norm(features,axis=1,keepdims=True),1e-9);elapsed=time.monotonic()-start
            np.savez_compressed(file,times=times,features=features,elapsed=elapsed)
        items.append((r,times,descriptors(features)));feature_times.append(elapsed);frame_counts.append(len(times))
        if j==2:
            technical={'train_videos':3,'device':'cpu','backbone':cfg['backbone'],'load_sec':load_sec,'feature_latency_mean_sec':statistics.mean(feature_times),'feature_latency_max_sec':max(feature_times),'frames_total':sum(frame_counts),'process_rss_mib':psutil.Process().memory_info().rss/2**20,'gpu_vram':'not used'}
            (run/'technical-benchmark.json').write_text(json.dumps(technical,indent=2),encoding='utf-8');print(json.dumps(technical),flush=True)
        print(json.dumps({'feature_videos_complete':j+1,'total_train_tune':len(rows)}),flush=True)
    X=[];y=[];weights=[]
    train_counts={k:sum(r['split']=='train' and r['target']==k for r,_,_ in items) for k in [0,1]};train_total=sum(train_counts.values())
    for r,times,desc in items:
        if r['split']!='train':continue
        if r['target']:
            center=int(np.argmin(abs(times-r['label_sec'])));idx=np.arange(max(0,center-1),min(len(times),center+2));label=1
        else:idx=np.unique(np.linspace(0,len(times)-1,min(12,len(times))).astype(int));label=0
        for i in idx:X.append(desc[i]);y.append(label);weights.append(train_total/(2*train_counts[label]*len(idx)))
    clf=make_pipeline(StandardScaler(),LogisticRegression(C=cfg['C'],random_state=cfg['seed'],max_iter=2000))
    clf.fit(np.array(X),np.array(y),logisticregression__sample_weight=np.array(weights));joblib.dump(clf,run/'event-proposal.joblib')
    results={};private=[]
    for strategy in ['uniform','coarse_refine']:
        truth=[];prediction=[];errors=[];count=[];t0=time.monotonic()
        for r,times,desc in items:
            if r['split']!='tune':continue
            uniform=np.unique(np.linspace(0,len(times)-1,min(cfg['uniform_centers'],len(times))).astype(int));scores=clf.predict_proba(desc[uniform])[:,1];idx=uniform
            if strategy=='coarse_refine':
                selected=uniform[np.argsort(scores)[-cfg['refine_candidates']:]]
                candidates=set(uniform.tolist())
                for i in selected:candidates.update(np.where(abs(times-times[i])<=cfg['refine_radius_sec'])[0].tolist())
                idx=np.array(sorted(candidates));scores=clf.predict_proba(desc[idx])[:,1]
            best=int(np.argmax(scores));guess=int(scores[best]>=cfg['threshold']);t=float(times[idx[best]]);truth.append(r['target']);prediction.append(guess);count.append(len(idx))
            if r['target'] and guess:errors.append(abs(t-r['label_sec']))
            private.append({'sha256':r['sha256'],'strategy':strategy,'truth':r['target'],'score':float(scores[best]),'prediction':guess,'time_sec':t})
        precision,recall,f1,_=precision_recall_fscore_support(truth,prediction,average='binary',zero_division=0)
        results[strategy]={'videos':len(truth),'confusion_matrix_tn_fp_fn_tp':confusion_matrix(truth,prediction,labels=[0,1]).tolist(),'precision':precision,'recall':recall,'f1':f1,'timing_matched_positive_videos':len(errors),'timestamp_mae_sec':statistics.mean(errors) if errors else None,'timestamp_median_error_sec':statistics.median(errors) if errors else None,'candidate_centers_mean':statistics.mean(count),'postprocess_total_sec':time.monotonic()-t0}
    summary={'scope':'Internal binary event proposal baseline; no event type/normative/evidence relevance validation','holdout_opened':False,'train_videos':sum(r['split']=='train' for r,_,_ in items),'tune_videos':sum(r['split']=='tune' for r,_,_ in items),'backbone':cfg['backbone'],'device':'cpu','torch':torch.__version__,'load_sec':load_sec,'feature_latency_mean_sec':statistics.mean(feature_times),'feature_latency_max_sec':max(feature_times),'frames_mean':statistics.mean(frame_counts),'process_rss_mib':psutil.Process().memory_info().rss/2**20,'results':results,'official_score':False,'config_sha256':hashlib.file_digest(Path('config/cpu-baseline.json').open('rb'),'sha256').hexdigest(),'limitations':['Preliminary duplicate groups: scene-family leakage needs human review.','Single annotation timestamp is not exhaustive event ground truth.','Quality comparison shares precomputed dense features; postprocess time is not full end-to-end latency.','Threshold/config fixed before tuning run; repeated tuning is not an independent final evaluation.','Backbone image embeddings and sequence differences may capture scene/pose correlations rather than actions. No legal conclusions.']}
    (run/'private-predictions.json').write_text(json.dumps(private),encoding='utf-8');(run/'safe-summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');print(json.dumps(summary),flush=True)

if __name__=='__main__':
    try:main()
    except Exception as e:
        import traceback
        out=Path('.private/cpu-baseline');out.mkdir(parents=True,exist_ok=True);status={'status':'failed','error_type':type(e).__name__,'stack_locations':[{'file':Path(f.filename).name,'line':f.lineno,'function':f.name} for f in traceback.extract_tb(e.__traceback__)]};(out/'failure.json').write_text(json.dumps(status),encoding='utf-8');print(json.dumps({'status':'failed','error_type':type(e).__name__}));sys.exit(1)
