"""Fit deployment prototypes from frozen TRAIN cache only; no new inference."""
from pathlib import Path
import sys,json,time,importlib.metadata as metadata
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from xclip_candidate.experimental import sha,FROZEN_INPUTS,encoder_artifacts,PACK_DIRECTORY


def main():
    import numpy as np
    from scripts.xclip_experiment import verify,rows
    from xclip_candidate.evaluate import centroids
    tick=time.monotonic();original=ROOT/'.private/xclip-control';out=ROOT/PACK_DIRECTORY
    if out.exists():raise RuntimeError('Experimental prototype pack exists; no overwrite')
    registration=json.loads((original/'registration.json').read_text());verify(registration)
    artifacts=encoder_artifacts()
    if any(registration['frozen_sha256'].get(name)!=digest for name,digest in artifacts.items()):raise ValueError('Encoder artifacts differ from original feature registration')
    selected=rows();inventory=json.loads((original/'feature-registration.json').read_text())['artifact_sha256']
    if set(inventory)!={r['sha256']+'.npz' for r in selected}:raise ValueError('Exact TRAIN cache coverage required')
    items=[]
    for row in selected:
        path=original/'features'/(row['sha256']+'.npz')
        if sha(path)!=inventory[path.name]:raise ValueError('Frozen cache mismatch')
        with np.load(path,allow_pickle=False) as data:item={'ordered':np.array(data['ordered']),'times':np.array(data['times'])}
        item.update({k:row[k] for k in ['target','label_sec']});items.append(item)
    positive,negative=centroids(items,'ordered')
    if any(sha(original/'features'/name)!=digest for name,digest in inventory.items()):raise ValueError('Cache changed during fit')
    verify(registration)
    if encoder_artifacts()!=artifacts:raise ValueError('Encoder artifacts changed during fit')
    out.mkdir()
    np.savez_compressed(out/'prototypes.npz',positive=positive.astype(np.float32),negative=negative.astype(np.float32))
    record={'schema_version':2,'arm':'ordered','pooling':'max','threshold':0.0,'release_eligible':False,
        'encoder_artifact_sha256':artifacts,
        'original_registration_sha256':sha(original/'registration.json'),'feature_registration_sha256':sha(original/'feature-registration.json'),
        'prototype_sha256':sha(out/'prototypes.npz'),'frozen_code_sha256':{name:sha(ROOT/name) for name in FROZEN_INPUTS},
        'versions':{name:metadata.version(name) for name in ['torch','transformers','numpy','av']},
        'train_unique_contents':len(selected),'train_auto_groups':len({r['group'] for r in selected}),
        'positive_train_contents':sum(r['target'] for r in selected),'negative_train_contents':sum(not r['target'] for r in selected),
        'fit_wall_sec':time.monotonic()-tick,'new_feature_or_video_inference_run':False,'tune_used':False,'holdout_used':False,
        'quality_claim':'No in-sample deployment-fit metric is computed; preserved group OOF results belong to the original baseline.'}
    (out/'prototypes.json').write_text(json.dumps(record,indent=2))
    safe={k:v for k,v in record.items() if k not in ['frozen_code_sha256','versions','encoder_artifact_sha256']}
    (out/'safe-summary.json').write_text(json.dumps(safe,indent=2));print(json.dumps(safe),flush=True)


if __name__=='__main__':
    try:main()
    except Exception as e:print(json.dumps({'status':'failed','technical_error_type':type(e).__name__,'raw_private_content_emitted':False}));sys.exit(1)
