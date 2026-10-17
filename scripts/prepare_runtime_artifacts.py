"""Download-only verified official runtime artifacts. No installation or GPU.

May run while the frozen model evaluation continues; the active environment,
model weights, inputs, security settings, credentials and listeners stay intact.
"""
from pathlib import Path
import json,sys,urllib.request,hashlib,zipfile,time
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.download_chunks import fetch
extras_only='--extras-only' in sys.argv
out=ROOT/('.private/quantization-preflight' if extras_only else '.private/runtime-upgrade');out.mkdir(exist_ok=True)
config=json.loads((ROOT/'config/runtime-upgrade.json').read_text())
for artifact in ([] if extras_only else config['artifacts']):
    target=out/artifact['filename']
    fetch(artifact['url'],target,artifact['bytes'],artifact['sha256'],progress=out/(target.name+'.progress.json'))
    print(json.dumps({'verified_artifact':artifact['filename'],'bytes':artifact['bytes']}),flush=True)
for name,version in [('bitsandbytes','0.50.2'),('accelerate','1.15.0')]:
    with urllib.request.urlopen('https://pypi.org/pypi/'+name+'/'+version+'/json',timeout=25) as response:metadata=json.load(response)
    wheels=[r for r in metadata['urls'] if r['filename'].endswith('.whl') and ('win_amd64' in r['filename'] or r['filename'].endswith('py3-none-any.whl'))]
    if len(wheels)!=1:raise RuntimeError('Expected exactly one compatible official wheel')
    artifact=wheels[0];target=out/artifact['filename']
    if not target.is_file():
        with urllib.request.urlopen(artifact['url'],timeout=60) as response:raw=response.read(100_000_000)
        if len(raw)!=artifact['size'] or hashlib.sha256(raw).hexdigest()!=artifact['digests']['sha256']:raise RuntimeError('Official wheel digest mismatch')
        target.write_bytes(raw)
    if hashlib.sha256(target.read_bytes()).hexdigest()!=artifact['digests']['sha256']:raise RuntimeError('Cached wheel digest mismatch')
    with zipfile.ZipFile(target) as archive:
        dlls=[p for p in archive.namelist() if p.endswith('.dll') and ('cuda128' in p or 'cuda130' in p)]
        license_files=[p for p in archive.namelist() if p.upper().endswith(('/LICENSE','/LICENSE.TXT','/LICENSE.MD'))]
        for index,path in enumerate(license_files):(out/(name+'-license-'+str(index)+'.txt')).write_bytes(archive.read(path))
    record={'name':name,'version':version,'sha256':artifact['digests']['sha256'],'bytes':artifact['size'],
            'requires_dist':metadata['info']['requires_dist'],'license_expression':metadata['info'].get('license_expression'),
            'license_metadata':metadata['info'].get('license'),'license_files':license_files,'matching_cuda_dlls':dlls,
            'advisories':metadata.get('vulnerabilities',[]),'installed':False}
    (out/(name+'-preflight.json')).write_text(json.dumps(record,indent=2),encoding='utf-8')
    print(json.dumps({k:record[k] for k in ['name','version','bytes','license_expression','license_metadata','license_files','matching_cuda_dlls','installed']}),flush=True)
(out/'artifact-preparation-safe-summary.json').write_text(json.dumps({'status':'verified_downloads_only','environment_modified':False,'gpu_workload_started':False,'updated_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())},indent=2),encoding='utf-8')
