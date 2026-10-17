"""Local TRAIN-only rename and row-permutation check; aggregate booleans only."""
from pathlib import Path
import os,sys,json,hashlib,shutil
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));os.chdir(ROOT)
os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1')
from cashreview.offline import deny_network
deny_network()
from cashreview.video import sample
import torch,numpy as np,joblib
from transformers import AutoImageProcessor,AutoModel
manifest=json.loads((ROOT/'.private/dataset/manifest.json').read_text(encoding='utf-8'));row=next(r for r in manifest if r['split']=='train' and not r['error'])
original=Path(row['path']);before=hashlib.file_digest(original.open('rb'),'sha256').hexdigest()
if before!=row['sha256']:raise RuntimeError('Source changed since manifest; stop')
out=ROOT/'.private/baseline-audit';out.mkdir(exist_ok=True);copy=out/'renamed-local-input.mov';shutil.copyfile(original,copy)
torch.set_num_threads(4);path=ROOT/'models/dinov2-small';processor=AutoImageProcessor.from_pretrained(str(path),local_files_only=True,use_fast=False);model=AutoModel.from_pretrained(str(path),local_files_only=True,use_safetensors=True).eval()
def embedding(path):
    frames=sample(path,[0,row['duration_sec']/2,max(0,row['duration_sec']-.2)],224)
    with torch.inference_mode():f=model(**processor(images=[x.image for x in frames],return_tensors='pt')).last_hidden_state[:,0].numpy()
    return f/np.maximum(np.linalg.norm(f,axis=1,keepdims=True),1e-9)
def describe(f):
    d=np.diff(f,axis=0);return np.concatenate([f.mean(0),f.std(0),f[-1]-f[0],np.abs(d).mean(0)])
a=embedding(original);b=embedding(copy);clf=joblib.load(ROOT/'.private/video-baseline/video-proposal.joblib');pa=clf.predict_proba(describe(a)[None]);pb=clf.predict_proba(describe(b)[None])
items=[]
for r in manifest:
    if r['split']!='tune':continue
    z=np.load(ROOT/'.private/cpu-baseline/features'/(r['sha256']+'.npz'));f=z['features'];idx=np.unique(np.linspace(0,len(f)-1,min(12,len(f))).astype(int));items.append(describe(f[idx]))
x=np.array(items);normal=clf.predict_proba(x);reverse=clf.predict_proba(x[::-1])[::-1]
classes={}
for r in manifest:classes.setdefault(r['sha256'],set()).add(r['target'])
report={'renamed_train_inputs_tested':1,'identical_source_bytes':hashlib.file_digest(copy.open('rb'),'sha256').hexdigest()==before,'same_features_after_rename':bool(np.allclose(a,b,atol=1e-6)),'same_prediction_after_rename':bool(np.allclose(pa,pb,atol=1e-6)),'source_hash_unchanged':hashlib.file_digest(original.open('rb'),'sha256').hexdigest()==before,'tune_row_order_invariance':bool(np.allclose(normal,reverse,atol=1e-12)),'duplicate_hash_label_conflicts':sum(len(x)>1 for x in classes.values()),'holdout_features_read':False,'scope':'DINO video proposal research only; full VLM API rename check still required'}
(out/'invariance.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report))
