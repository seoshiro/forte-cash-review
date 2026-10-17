"""Official SHA-pinned portable fallback; no model, listener or OS installation."""
from pathlib import Path
import hashlib,json,subprocess,sys,zipfile,httpx
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.resume_downloads import fetch

release=json.loads((ROOT/'.private/llamacpp-release.json').read_text())
if release['tag']!='b11669':raise RuntimeError('Review a new runtime release explicitly')
assets=[a for a in release['assets'] if a['name']=='llama-b11669-bin-win-vulkan-x64.zip']
if len(assets)!=1:raise RuntimeError('Official runtime asset unavailable')
a=assets[0];digest=a['digest'].removeprefix('sha256:')
if digest!='2c07574e7bde71321cb785282b20cc821e951132149eeceeea32ddebdbf0598e':raise RuntimeError('Runtime checksum changed')
archive=ROOT/'.private/bootstrap'/a['name']
fetch(a['url'],archive,a['size'],digest)
target=ROOT/'.runtime/llamacpp-b11669';target.mkdir(parents=True,exist_ok=True)
with zipfile.ZipFile(archive) as z:
    for entry in z.infolist():
        p=(target/entry.filename).resolve()
        if not p.is_relative_to(target.resolve()):raise RuntimeError('Unsafe archive member')
    z.extractall(target)
executables=list(target.rglob('llama-server.exe'))
if len(executables)!=1:raise RuntimeError('Portable runtime executable not unique')
exe=executables[0];out=ROOT/'.private/portable-runtime';out.mkdir(parents=True,exist_ok=True)
checks={}
for name,args in [('version',['--version']),('devices',['--list-devices']),('help',['--help'])]:
    try:
        r=subprocess.run([str(exe),*args],cwd=exe.parent,capture_output=True,text=True,timeout=30,encoding='utf-8',errors='replace')
        (out/(name+'.txt')).write_text(r.stdout+r.stderr,encoding='utf-8');checks[name+'_returncode']=r.returncode
    except subprocess.TimeoutExpired:
        checks[name+'_timeout']=True
        break
help_text=(out/'help.txt').read_text() if (out/'help.txt').exists() else ''
checks.update({x.lstrip('-').replace('-','_')+'_flag':x in help_text for x in ['--mmproj','--offline','--host','--api-key','--n-gpu-layers']})
record={'release':release['tag'],'archive_bytes':a['size'],'archive_sha256':digest,'source':a['url'],'code_license':'MIT','checks':checks,'model_loaded':False,'listener_started':False,'os_installation':False}
(out/'safe-summary.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
print(json.dumps(record))
