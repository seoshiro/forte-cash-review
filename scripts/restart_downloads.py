"""Restart only this project's active artifact pipeline, preserving partial bytes."""
from pathlib import Path
import psutil,subprocess,sys,json,time,shutil
root=Path(__file__).resolve().parents[1];out=root/'.private/vlm-pipeline'
state=json.loads((out/'status.json').read_text())
if state['stage'] not in ['download_preparation','blocked_download']:raise RuntimeError('Pipeline already past artifact preparation; do not interrupt')
names={'run_vlm_experiment.py','resume_downloads.py'};targets=[]
for p in psutil.process_iter():
    try:
        if p.name().lower()=='python.exe' and Path(p.cwd()).resolve()==root and any(Path(x).name in names for x in p.cmdline()[1:]):targets.append(p)
    except (psutil.Error,OSError,ValueError):pass
for p in sorted(targets,key=lambda p:p.create_time()):
    try:p.terminate()
    except psutil.NoSuchProcess:pass
_,alive=psutil.wait_procs(targets,timeout=5)
if alive:raise RuntimeError('Old artifact processes still active; no new writer started')
stamp=time.strftime('%Y%m%dT%H%M%SZ',time.gmtime());archive=out/'previous'/stamp;archive.mkdir(parents=True,exist_ok=True)
for p in out.glob('*.log'):shutil.copy2(p,archive/p.name)
shutil.copy2(out/'status.json',archive/'status.json')
with (out/'runner.stdout.log').open('w') as stdout,(out/'runner.stderr.log').open('w') as stderr:
    p=subprocess.Popen([sys.executable,'scripts/run_vlm_experiment.py'],cwd=root,stdout=stdout,stderr=stderr,creationflags=subprocess.CREATE_NO_WINDOW)
print(json.dumps({'stopped_project_download_processes':len(targets),'resumed_pipeline_pid':p.pid,'partials_preserved':True,'no_other_project_processes_targeted':True}))
