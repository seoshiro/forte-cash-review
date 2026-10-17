"""Restart only this project's synthetic-only loopback process, temporary value."""
from pathlib import Path
import psutil,subprocess,os,time,json,sys
import httpx
root=Path(__file__).resolve().parents[1];me=psutil.Process();skip={me.pid,*[p.pid for p in me.parents()]};stopped=[]
try:
    health=httpx.get('http://127.0.0.1:8765/healthz',timeout=3,trust_env=False)
    if health.status_code!=200 or health.json().get('mode')!='synthetic_test':raise RuntimeError('Refusing to replace a non-synthetic listener')
except httpx.ConnectError:pass
for p in psutil.process_iter():
    try:
        if p.pid in skip or p.name().lower()!='python.exe':continue
        if Path(p.cwd()).resolve()!=root:continue
        args=p.cmdline()
        if '--synthetic-test' not in args:continue
        if '--port' in args and args[args.index('--port')+1]!='8765':continue
        if any(x.replace('\\','/').endswith('scripts/serve.py') for x in args):stopped.append(p)
    except (psutil.Error,OSError):continue
for p in reversed(stopped):
    try:p.terminate()
    except psutil.Error:pass
psutil.wait_procs(stopped,timeout=5)
env=os.environ.copy();env['CASH_API_KEY']='temporary-local-test-only'
with (root/'.private/live/server.stdout.log').open('w') as out,(root/'.private/live/server.stderr.log').open('w') as err:
    # CREATE_NO_WINDOW is a process-local launch setting, no OS/security changes.
    p=subprocess.Popen([sys.executable,'scripts/serve.py','--synthetic-test','--port','8765'],cwd=root,env=env,stdout=out,stderr=err,creationflags=subprocess.CREATE_NO_WINDOW)
print(json.dumps({'synthetic_server_pid':p.pid,'stopped_project_processes':len(stopped)}))
