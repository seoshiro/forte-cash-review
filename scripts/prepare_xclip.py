"""Official public weights only; fixed artifact identity; no media or inference."""
from pathlib import Path
import json,time,sys,hashlib,httpx
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.download_chunks import fetch


def main():
    cfg=json.loads((ROOT/'config/xclip-artifacts.json').read_text());out=ROOT/'.private/xclip-prepare';out.mkdir(exist_ok=True)
    metadata=json.loads((out/'metadata.json').read_text())
    if metadata['revision']!=cfg['revision'] or metadata['license']!='mit':raise ValueError('Official revision/license mismatch')
    weight=next(row for row in metadata['artifacts'] if row['rfilename']==cfg['weight_file'])
    if weight['lfs']['sha256']!=cfg['weight_sha256'] or weight['size']!=cfg['weight_bytes']:raise ValueError('Official LFS identity mismatch')
    model=ROOT/'models/xclip-base-patch32';model.mkdir(exist_ok=True);started=time.monotonic();digests={}
    with httpx.Client(timeout=30,follow_redirects=True,trust_env=False) as client:
        for name in cfg['small_files']:
            response=client.get(f"https://huggingface.co/{cfg['repo']}/resolve/{cfg['revision']}/{name}")
            response.raise_for_status();raw=response.content
            if len(raw)>100_000:raise ValueError('Unexpected small artifact size')
            (model/name).write_bytes(raw);digests[name]=hashlib.sha256(raw).hexdigest()
        response=client.get('https://raw.githubusercontent.com/microsoft/VideoX/master/LICENSE');response.raise_for_status();license_text=response.content
        if b'MIT License' not in license_text or b'Permission is hereby granted' not in license_text:raise ValueError('MIT code license missing')
        (out/'upstream-MIT-license.txt').write_bytes(license_text)
        digests['upstream-MIT-license.txt']=hashlib.sha256(license_text).hexdigest()
    fetch(f"https://huggingface.co/{cfg['repo']}/resolve/{cfg['revision']}/{cfg['weight_file']}",
        model/cfg['weight_file'],cfg['weight_bytes'],cfg['weight_sha256'],budget_sec=cfg['download_budget_sec'],progress=out/'download-progress.json')
    digests[cfg['weight_file']]=cfg['weight_sha256']
    provenance={'repo':cfg['repo'],'revision':cfg['revision'],'weights_license':'MIT from official model metadata/model card',
        'code_license':cfg['code_license'],'artifact_sha256':digests,'weight_bytes':cfg['weight_bytes']}
    (model/'provenance.json').write_text(json.dumps(provenance,indent=2),encoding='utf-8')
    report={'status':'weights_verified','weights_bytes':cfg['weight_bytes'],'download_and_hash_sec':time.monotonic()-started,
        'small_artifacts':len(cfg['small_files']),'sha256_verified':True,'revision':cfg['revision'],
        'model_inference_started':False,'data_transmitted':False,'new_credentials_created':False}
    (out/'safe-summary.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report),flush=True)


if __name__=='__main__':
    try:main()
    except Exception as error:
        report={'status':'failed','technical_error_type':type(error).__name__,'model_inference_started':False,'data_transmitted':False}
        (ROOT/'.private/xclip-prepare/failure-safe-summary.json').write_text(json.dumps(report),encoding='utf-8')
        print(json.dumps(report),flush=True);sys.exit(1)
