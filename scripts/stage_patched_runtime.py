"""Prepare an isolated patched runtime only after the active pipeline stops.

Default is read-only. --prepare downloads official hash-pinned wheels and creates
.venv-patched; it never modifies .venv, weights, source data or OS/driver settings.
No key, tunnel or listener is created.
"""
from pathlib import Path
import argparse,json,sys,os,subprocess,ctypes,urllib.parse,re,time
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.download_chunks import fetch

p=argparse.ArgumentParser();p.add_argument('--prepare',action='store_true');a=p.parse_args()
cfg=json.loads((ROOT/'config/runtime-upgrade.json').read_text())
target=(ROOT/cfg['environment']).resolve()
if target.parent!=ROOT.resolve() or target.name!='.venv-patched':raise RuntimeError('Unexpected isolated environment target')
if not a.prepare:
    print(json.dumps({'mode':'read_only_plan','target':str(target),'torch':cfg['torch'],'torchvision':cfg['torchvision'],'active_environment_modified':False,'downloads_started':False}));sys.exit(0)
state=json.loads((ROOT/'.private/vlm-pipeline/status.json').read_text())
if state['stage'] in ['download_preparation','technical_benchmark','tuning_uniform','tuning_coarse_refine']:raise RuntimeError('Active pipeline must finish before staging another runtime')
structured=ROOT/'.private/structured/status.json'
if structured.exists() and json.loads(structured.read_text())['stage'] in ['structured_technical_benchmark','structured_tune_uniform','structured_train_uniform','latency_profile','budget_technical_benchmark']:
    raise RuntimeError('Active structured evaluation must finish before staging another runtime')
import psutil
for process in psutil.process_iter():
    try:
        if Path(process.cwd()).resolve()==ROOT and any(Path(x).name in {'benchmark.py','evaluate.py','diagnose_synthetic_structure.py','qa_model_api.py','profile_baseline_stages.py','benchmark_budget.py'} for x in process.cmdline()[1:]):
            raise RuntimeError('Owned model workload is active; no environment prepared')
    except (psutil.Error,OSError,ValueError):pass
driver=ctypes.WinDLL('nvcuda.dll');version=ctypes.c_int()
if driver.cuDriverGetVersion(ctypes.byref(version))!=0 or version.value<cfg['minimum_driver_api']:raise RuntimeError('Current driver API does not support this runtime; no OS changes performed')
out=ROOT/'.private/runtime-upgrade';out.mkdir(parents=True,exist_ok=True);wheels=[]
for artifact in cfg['artifacts']:
    host=urllib.parse.urlsplit(artifact['url']).hostname
    if host not in ['download.pytorch.org','download-r2.pytorch.org'] or not re.fullmatch('[0-9a-f]{64}',artifact['sha256']):raise RuntimeError('Unverified artifact configuration')
    path=out/artifact['filename']
    if path.resolve().parent!=out.resolve():raise RuntimeError('Unexpected wheel path')
    fetch(artifact['url'],path,artifact['bytes'],artifact['sha256'],progress=out/(path.name+'.progress.json'))
    wheels.append(path)
uv=Path(r'C:\Users\gokusen\AppData\Local\Microsoft\WinGet\Packages\astral-sh.uv_Microsoft.Winget.Source_8wekyb3d8bbwe\uv.exe')
env=os.environ.copy();env.update(UV_CACHE_DIR=str(ROOT/'.cache'),UV_HTTP_TIMEOUT='600')
with (out/'install.log').open('w') as log:
    if not target.exists():subprocess.run([str(uv),'venv','--python',sys._base_executable,str(target)],cwd=ROOT,env=env,stdout=log,stderr=log,check=True)
    if not (target/'pyvenv.cfg').is_file():raise RuntimeError('Existing target is not a venv; left untouched')
    python=target/'Scripts/python.exe'
    subprocess.run([str(uv),'pip','install','--python',str(python),'-r',str(ROOT/'requirements.txt'),*[str(w) for w in wheels],'--no-progress'],cwd=ROOT,env=env,stdout=log,stderr=log,check=True)
record={'status':'isolated_environment_prepared_not_validated','torch':cfg['torch'],'torchvision':cfg['torchvision'],'target':str(target),'active_environment_modified':False,'model_weights_reused':True,'checked_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}
(out/'safe-summary.json').write_text(json.dumps(record,indent=2),encoding='utf-8');print(json.dumps(record))
