"""Bounded alternate official Qwen distribution probe; no second model download."""
from pathlib import Path
import httpx,json,time,hashlib
root=Path(__file__).resolve().parents[1]
cache=root/'models/qwen3-vl-2b/.cache/huggingface/download'
revisions={p.read_text().splitlines()[0] for p in cache.glob('*.metadata')}
if len(revisions)!=1:raise RuntimeError('Pinned Hugging Face revision not unique')
with httpx.Client(timeout=20,follow_redirects=False,trust_env=False) as c:
    h=c.head(f'https://huggingface.co/Qwen/Qwen3-VL-2B-Instruct/resolve/{revisions.pop()}/model.safetensors')
    if h.status_code not in (200,302,307):h.raise_for_status()
    digest=h.headers.get('x-linked-etag','').strip('"')
meta=json.loads((root/'.private/modelscope-metadata.json').read_text())
f=next(x for x in meta['files'] if x['Name']=='model.safetensors')
if f['Sha256']!=digest or f['Size']!=4255140312:raise RuntimeError('Official distributions differ')
url=f"https://modelscope.cn/models/Qwen/Qwen3-VL-2B-Instruct/resolve/{f['Revision']}/model.safetensors"
row={'same_official_weight_sha256':True,'bytes_requested':1048576,'source':'official Qwen ModelScope','revision':f['Revision']}
start=time.monotonic()
try:
    with httpx.Client(timeout=httpx.Timeout(15,connect=10),follow_redirects=True,trust_env=False) as c:
        with c.stream('GET',url,headers={'Range':'bytes=0-1048575','Accept-Encoding':'identity'}) as r:
            row['status']=r.status_code
            if r.status_code!=206 or r.headers.get('content-range','')!='bytes 0-1048575/4255140312':raise ValueError('Bounded range not respected')
            b=bytearray()
            for chunk in r.iter_bytes(32768):
                b.extend(chunk)
                if len(b)>1048576 or time.monotonic()-start>45:raise TimeoutError('Probe limit reached')
            partial=next(cache.glob('*.incomplete'))
            with partial.open('rb') as existing:row['matches_existing_prefix']=bytes(b)==existing.read(1048576)
            row['bytes_received']=len(b)
except (httpx.HTTPError,ValueError,TimeoutError) as e:row['error_type']=type(e).__name__
row['elapsed_sec']=time.monotonic()-start
(root/'.private/mirror-probe-safe-summary.json').write_text(json.dumps(row,indent=2),encoding='utf-8')
print(json.dumps(row))
