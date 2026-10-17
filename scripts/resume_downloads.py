"""Range-resumable public artifact downloads, SHA256 verified before local install.

No dataset, credentials, user descriptions or cloud inference are used.
"""
from pathlib import Path
import argparse, hashlib, json, re, time, urllib.parse, os, subprocess, sys
import httpx

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'.private/bootstrap';OUT.mkdir(parents=True,exist_ok=True)


def fetch(url,path,total,digest):
    sys.path.insert(0,str(ROOT))
    from scripts.download_chunks import fetch as bounded_fetch
    bounded_fetch(url,path,total,digest,progress=OUT/(path.name+'.progress.json'))


def qwen():
    target=ROOT/'models/qwen3-vl-2b';cache=target/'.cache/huggingface/download'
    # Commit hashes of already downloaded official metadata must all agree.
    metadata=list(cache.glob('*.metadata'))
    commits={p.read_text(encoding='utf-8').splitlines()[0] for p in metadata if p.stat().st_size}
    if len(commits)!=1:raise RuntimeError('Model revision not pinned consistently')
    revision=commits.pop()
    if not re.fullmatch('[0-9a-f]{40}',revision):raise RuntimeError('Invalid commit')
    url=f'https://huggingface.co/Qwen/Qwen3-VL-2B-Instruct/resolve/{revision}/model.safetensors'
    with httpx.Client(follow_redirects=False,timeout=30,trust_env=False) as c:
        r=c.head(url)
        if r.status_code not in (200,302,307):r.raise_for_status()
        digest=r.headers.get('x-linked-etag','').strip('"');total=int(r.headers.get('x-linked-size','0'))
    if not re.fullmatch('[0-9a-f]{64}',digest) or not total:raise RuntimeError('Official artifact hash/size unavailable')
    complete=target/'model.safetensors'
    candidates=[p for p in cache.glob('*.incomplete') if digest in p.name]
    partial=complete if complete.exists() else candidates[0] if len(candidates)==1 else OUT/'qwen-model.partial'
    fetch(url,partial,total,digest)
    if partial!=complete:partial.replace(complete)
    card=(target/'README.md').read_text(encoding='utf-8')
    if 'license: apache-2.0' not in card.lower():raise RuntimeError('License not verified')
    record={'repo':'Qwen/Qwen3-VL-2B-Instruct','revision':revision,'weights_license':'Apache-2.0','weights_sha256':digest,'weights_bytes':total,'code_license':'Apache-2.0: Transformers and official Qwen3-VL'}
    (ROOT/'models/provenance.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
    return record


def cuda():
    index='https://download.pytorch.org/whl/cu128/torch/'
    with httpx.Client(timeout=40,follow_redirects=True,trust_env=False) as c:html=c.get(index).raise_for_status().text
    links=re.findall(r'href="([^"]+)"',html)
    links=[urllib.parse.urljoin(index,x.replace('&amp;','&')) for x in links if 'torch-2.8.0%2Bcu128-cp312-cp312-win_amd64.whl' in x]
    if len(links)!=1:raise RuntimeError('Official wheel not unique')
    full=links[0];url,frag=urllib.parse.urldefrag(full);digest=urllib.parse.parse_qs(frag).get('sha256',[''])[0]
    if not re.fullmatch('[0-9a-f]{64}',digest):raise RuntimeError('Official wheel hash missing')
    with httpx.Client(timeout=40,follow_redirects=True,trust_env=False) as c:
        with c.stream('GET',url,headers={'Range':'bytes=0-0'}) as r:
            r.raise_for_status();total=int(r.headers.get('content-range','/0').split('/')[-1])
    if not total:raise RuntimeError('Wheel size missing')
    path=OUT/'torch-2.8.0+cu128-cp312-cp312-win_amd64.whl';fetch(url,path,total,digest)
    uv=Path(r'C:\Users\gokusen\AppData\Local\Microsoft\WinGet\Packages\astral-sh.uv_Microsoft.Winget.Source_8wekyb3d8bbwe\uv.exe')
    env=os.environ.copy();env['UV_CACHE_DIR']=str(ROOT/'.cache');env['UV_HTTP_TIMEOUT']='600'
    subprocess.run([str(uv),'pip','install','--python',sys.executable,str(path),'torchvision==0.23.0','--index-url','https://download.pytorch.org/whl/cu128','--no-progress'],env=env,check=True)
    return {'torch':'2.8.0+cu128','sha256':digest,'bytes':total}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('artifact',choices=['qwen','cuda']);a=p.parse_args()
    (OUT/(a.artifact+'-status.json')).write_text(json.dumps({'status':'downloading','artifact':a.artifact,'started_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}),encoding='utf-8')
    try:
        result=qwen() if a.artifact=='qwen' else cuda();status={'status':'done','artifact':a.artifact,'result':result}
    except Exception as e:
        status={'status':'failed','artifact':a.artifact,'error_type':type(e).__name__,'reason':str(e)[:120] if not isinstance(e,httpx.HTTPError) else 'Public artifact network request failed'}
    (OUT/(a.artifact+'-status.json')).write_text(json.dumps(status,indent=2),encoding='utf-8');print(json.dumps(status))
    sys.exit(status['status']!='done')
