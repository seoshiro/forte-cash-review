"""Download hash-pinned official GGUF/CUDA artifacts; no GPU, install or listener."""
from pathlib import Path
import argparse,json,sys,urllib.request,urllib.parse,hashlib,zipfile,stat,time
from concurrent.futures import ThreadPoolExecutor
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.download_chunks import fetch

def main():
    p=argparse.ArgumentParser();p.add_argument('--prepare',action='store_true');a=p.parse_args()
    cfg=json.loads((ROOT/'config/gguf-artifacts.json').read_text());out=ROOT/'.private/gguf-preflight';out.mkdir(exist_ok=True)
    metadata=json.loads((out/'model-metadata.json').read_text())
    if metadata['sha']!=cfg['revision'] or metadata.get('cardData',{}).get('license')!='apache-2.0':raise RuntimeError('Official weight license/revision mismatch')
    licenses={
        'weights-model-card.md':'https://huggingface.co/'+cfg['model']+'/resolve/'+cfg['revision']+'/README.md',
        'weights-license-standard.txt':'https://www.apache.org/licenses/LICENSE-2.0.txt',
        'runtime-license.txt':'https://raw.githubusercontent.com/ggml-org/llama.cpp/'+cfg['runtime_tag']+'/LICENSE'}
    for name,url in licenses.items():
        with urllib.request.urlopen(url,timeout=30) as response:raw=response.read(100_000)
        if name=='runtime-license.txt' and b'Permission is hereby granted' not in raw:raise RuntimeError('MIT license text missing')
        if name=='weights-license-standard.txt' and b'Apache License' not in raw:raise RuntimeError('Apache license text missing')
        (out/name).write_bytes(raw)
    if not a.prepare:
        print(json.dumps({'mode':'verified_plan','weight_license':cfg['weight_license'],'runtime_license':cfg['runtime_license'],'weight_bytes':cfg['weight_bytes'],'downloads_started':False}));return
    def artifact(row):
        host=urllib.parse.urlsplit(row['url']).hostname
        if host not in {'huggingface.co','github.com'}:raise RuntimeError('Unexpected artifact source')
        folder=ROOT/'models/qwen3vl-4b-gguf' if row['kind']=='model' else out/'downloads';folder.mkdir(parents=True,exist_ok=True)
        target=folder/row['filename']
        if target.resolve().parent!=folder.resolve():raise RuntimeError('Invalid artifact filename')
        fetch(row['url'],target,row['bytes'],row['sha256'],progress=out/(row['filename']+'.progress.json'))
        print(json.dumps({'verified_artifact':row['filename'],'bytes':row['bytes']}),flush=True)
        return row,target
    # Two independent downloads, each with bounded chunk workers. No model load.
    with ThreadPoolExecutor(max_workers=2) as pool:completed=list(pool.map(artifact,cfg['artifacts']))
    runtime=ROOT/'.private/llama-cuda124-b11712';runtime.mkdir(exist_ok=True)
    for row,path in completed:
        if row['kind']!='runtime':continue
        with zipfile.ZipFile(path) as archive:
            for member in archive.infolist():
                target=(runtime/member.filename).resolve()
                if not target.is_relative_to(runtime.resolve()) or stat.S_ISLNK(member.external_attr>>16):raise RuntimeError('Unsafe archive path/type')
            archive.extractall(runtime)
    servers=list(runtime.rglob('llama-server.exe'))
    if len(servers)!=1:raise RuntimeError('Expected one official portable server')
    report={'status':'artifacts_verified_not_benchmarked','model':cfg['model'],'revision':cfg['revision'],
            'weight_bytes':cfg['weight_bytes'],'weight_license':'Apache-2.0 from official model metadata; standard license cached',
            'runtime_license':'MIT, exact release license cached','runtime_tag':cfg['runtime_tag'],'cuda_runtime':cfg['cuda_runtime'],
            'artifact_count':len(completed),'server_path':str(servers[0]),'gpu_workload_started':False,'listener_started':False,
            'permanent_credentials_created':False,'checked_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}
    (out/'safe-summary.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)

if __name__=='__main__':main()
