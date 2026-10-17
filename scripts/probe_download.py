"""Two 1 MiB public weight transfer probes; no source data or credentials."""
from pathlib import Path
import httpx,time,json
root=Path(__file__).resolve().parents[1]
metadata=list((root/'models/qwen3-vl-2b/.cache/huggingface/download').glob('*.metadata'))
revisions={p.read_text().splitlines()[0] for p in metadata}
if len(revisions)!=1:raise RuntimeError('Model revision not unique')
url=f'https://huggingface.co/Qwen/Qwen3-VL-2B-Instruct/resolve/{revisions.pop()}/model.safetensors'
rows=[]
with httpx.Client(timeout=httpx.Timeout(30,connect=15),follow_redirects=True,trust_env=False) as c:
    for name in ['origin_redirect','resolved_cdn']:
        start=time.monotonic();row={'probe':name}
        try:
            with c.stream('GET',url,headers={'Range':'bytes=0-1048575','Accept-Encoding':'identity'}) as r:
                if r.status_code!=206 or r.headers.get('content-range','')!='bytes 0-1048575/4255140312':raise ValueError('Public server did not respect bounded range')
                size=0
                for chunk in r.iter_bytes(32768):
                    size+=len(chunk)
                    if size>1048576:raise ValueError('Probe range exceeded')
                    if time.monotonic()-start>45:raise TimeoutError('Probe wall budget exceeded')
                row.update(status=r.status_code,bytes=size,elapsed_sec=time.monotonic()-start)
                if name=='origin_redirect':url=str(r.url)
        except (httpx.HTTPError,ValueError,TimeoutError) as e:row.update(error_type=type(e).__name__,elapsed_sec=time.monotonic()-start)
        rows.append(row)
(root/'.private/download-probe-safe-summary.json').write_text(json.dumps({'public_artifact_probes':rows},indent=2),encoding='utf-8')
print(json.dumps(rows))
