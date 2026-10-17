"""Frozen cached-feature centroids; no new media/encoder/manual annotation reads."""
from pathlib import Path
import json,os,sys,hashlib,time
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));os.chdir(ROOT)
from cashreview.offline import deny_network
import numpy as np
from sklearn.metrics import roc_auc_score
from cashreview.research_split import unique_train_contents
from qvt_candidate.features import representations
from qvt_candidate.evaluate import metrics
OUT=ROOT/'.private/prototype-cache'


def unit(values):return values/np.maximum(np.linalg.norm(values,axis=-1,keepdims=True),1e-9)


def cache_inventory(items,root):
    inventory={}
    for item in items:
        path=Path(root)/'.private/qvt-control/features'/(item['sha256']+'.npz')
        inventory[str(path.relative_to(root))]=hashlib.sha256(path.read_bytes()).hexdigest()
    return inventory


def verify_inventory(inventory,root):
    return all(hashlib.sha256((Path(root)/name).read_bytes()).hexdigest()==sha for name,sha in inventory.items())


def centroids(items,arm):
    positive=[];negative=[]
    for item in items:
        vectors=unit(representations(item['features'])[arm])
        if item['target']:
            index=int(np.argmin(abs(item['times']-item['label_sec'])));positive.append(vectors[index])
        else:negative.append(vectors.mean(0))
    if not positive or not negative:raise ValueError('Both classes required')
    return unit(np.mean(positive,axis=0)),unit(np.mean(negative,axis=0))


def main():
    deny_network()
    started=time.monotonic();OUT.mkdir(exist_ok=True)
    if (OUT/'registration.json').exists():raise RuntimeError('Bounded diagnostic cannot be repeated')
    paths=['config/prototype-cache-protocol.json','scripts/prototype_cache_diagnostic.py','cashreview/research_split.py',
        'qvt_candidate/features.py','qvt_candidate/evaluate.py','.private/dataset/manifest.json','.private/dataset/split.json']
    frozen={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths}
    cfg=json.loads((ROOT/'config/prototype-cache-protocol.json').read_text())
    items=unique_train_contents(json.loads((ROOT/'.private/dataset/manifest.json').read_text(encoding='utf-8')))
    feature_inputs=cache_inventory(items,ROOT)
    registration={'protocol_id':cfg['protocol_id'],'frozen_sha256':frozen,'source_sha256':[i['sha256'] for i in items],
        'feature_inputs_sha256':feature_inputs,'registered_before_feature_array_read':True,'holdout_opened':False}
    (OUT/'registration.json').write_text(json.dumps(registration,indent=2),encoding='utf-8')
    for item in items:
        with np.load(ROOT/'.private/qvt-control/features'/(item['sha256']+'.npz'),allow_pickle=False) as data:
            item['times']=data['times'];item['features']=data['features']
    reports={};private={};groups=sorted({i['group'] for i in items})
    for arm in ['static','temporal']:
        records=[]
        for group in groups:
            positive,negative=centroids([i for i in items if i['group']!=group],arm)
            for item in items:
                if item['group']!=group:continue
                vectors=unit(representations(item['features'])[arm]);scores=vectors@positive-vectors@negative
                index=int(np.argmax(scores));score=float(scores[index]);guess=int(score>=cfg['threshold'])
                records.append({'source_sha256':item['sha256'],'truth':item['target'],'prediction':guess,'score':score,
                    'time_sec':float(item['times'][index]),'error_sec':abs(item['times'][index]-item['label_sec']) if item['target'] else None})
        report=metrics(records);report['video_roc_auc']=float(roc_auc_score([r['truth'] for r in records],[r['score'] for r in records]))
        report['ranking_signal_gate_passed']=report['video_roc_auc']>=cfg['ranking_signal_gate_auc_min']
        reports[arm]=report;private[arm]=records
    if time.monotonic()-started>cfg['budget_wall_sec']:raise TimeoutError('Diagnostic budget exceeded')
    code_unchanged=all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==sha for p,sha in frozen.items())
    cache_unchanged=verify_inventory(feature_inputs,ROOT)
    unchanged=code_unchanged and cache_unchanged
    summary={'split':'train','scope':cfg['scope'],'train_unique_contents':len(items),'train_auto_groups':len(groups),
        'results':reports,'frozen_sources_unchanged':unchanged,'frozen_cache_inputs_unchanged':cache_unchanged,'elapsed_sec':time.monotonic()-started,
        'new_encoder_inference':False,'new_downloads':False,'manual_annotations_read':False,'tune_run':False,'holdout_opened':False,
        'threshold_selected_after_results':False,'release_eligible':False,'official_score':False}
    (OUT/'private-results.json').write_text(json.dumps(private),encoding='utf-8')
    (OUT/'safe-summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');print(json.dumps(summary),flush=True)


if __name__=='__main__':
    try:main()
    except Exception as error:
        print(json.dumps({'status':'failed','technical_error_type':type(error).__name__,'contents_emitted':False}));sys.exit(1)
