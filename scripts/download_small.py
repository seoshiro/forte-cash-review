"""Small CPU backbone, public Apache-2.0 weights. No dataset access."""
from pathlib import Path
import sys,os,json,hashlib,httpx
os.environ.update(HF_HUB_DISABLE_TELEMETRY='1',HF_HUB_DISABLE_XET='1')
from huggingface_hub import HfApi
sys.path.insert(0,str(Path(__file__).resolve().parent))
from resume_downloads import fetch
root=Path(__file__).resolve().parents[1];out=root/'models/dinov2-small';out.mkdir(parents=True,exist_ok=True)
try:
    info=HfApi(token=False).model_info('facebook/dinov2-small');rev=info.sha
    with httpx.Client(timeout=30,trust_env=False,follow_redirects=True) as c:
        for name in ['config.json','preprocessor_config.json','README.md']:
            r=c.get(f'https://huggingface.co/facebook/dinov2-small/resolve/{rev}/{name}');r.raise_for_status();(out/name).write_bytes(r.content)
    if 'license: apache-2.0' not in (out/'README.md').read_text(encoding='utf-8').lower():raise RuntimeError('Official license metadata missing')
    url=f'https://huggingface.co/facebook/dinov2-small/resolve/{rev}/model.safetensors'
    with httpx.Client(timeout=30,trust_env=False,follow_redirects=False) as c:
        r=c.head(url)
        if r.status_code not in (200,302,307):r.raise_for_status()
        digest=r.headers.get('x-linked-etag','').strip('"');total=int(r.headers.get('x-linked-size','0'))
    if len(digest)!=64 or not total:raise RuntimeError('Official hash/size missing')
    if not (out/'model.safetensors').exists():
        partial=out/'model.partial';fetch(url,partial,total,digest);partial.replace(out/'model.safetensors')
    if hashlib.file_digest((out/'model.safetensors').open('rb'),'sha256').hexdigest()!=digest:raise RuntimeError('Invalid model hash')
    status={'status':'done','repo':'facebook/dinov2-small','revision':rev,'sha256':digest,'bytes':total,'weights_license':'Apache-2.0','code_license':'Apache-2.0 (Transformers / facebookresearch dinov2)'}
    (out/'provenance.json').write_text(json.dumps(status,indent=2),encoding='utf-8')
except Exception as e:
    status={'status':'failed','error_type':type(e).__name__,'reason':'Public backbone download or integrity check failed'}
(root/'.private/bootstrap/dino-status.json').write_text(json.dumps(status,indent=2),encoding='utf-8');print(json.dumps(status));sys.exit(status['status']!='done')
