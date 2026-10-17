"""Current local CPU-ASR workflow; no transcript/log reads or network inference."""
from pathlib import Path
import sys,json,time,subprocess,psutil
ROOT=Path(__file__).resolve().parents[1]
def main():
    out=ROOT/'.private/clarifications';status=out/'asr-supervisor-safe-summary.json';deadline=time.monotonic()+3600
    def save(stage,**kw):status.write_text(json.dumps({'stage':stage,'gpu_workload':False,**kw},indent=2))
    save('waiting_for_audited_cpu_asr')
    ready=out/'asr-preparation-safe-summary.json'
    while True:
        active=False
        for p in psutil.process_iter():
            try:
                if any(Path(a).name=='prepare_clarification_asr.py' for a in p.cmdline()[1:]):active=True
            except psutil.Error:pass
        if ready.exists() and json.loads(ready.read_text()).get('status')=='ready_for_local_cpu_transcription':break
        if not active:save('preparation_stopped_without_ready_report');return
        if time.monotonic()>deadline:save('preparation_wait_budget_exhausted');return
        time.sleep(2)
    if json.loads(ready.read_text()).get('status')!='ready_for_local_cpu_transcription':save('cpu_preparation_failed');return
    if (out/'transcript.json').exists():save('existing_private_transcript_preserved');return
    with (out/'transcribe.stdout.log').open('w') as stdout,(out/'transcribe.stderr.log').open('w') as stderr:
        p=subprocess.Popen([str(ROOT/'.venv-asr/Scripts/python.exe'),str(ROOT/'scripts/transcribe_clarification.py')],cwd=ROOT,stdout=stdout,stderr=stderr,creationflags=subprocess.CREATE_NO_WINDOW)
    save('local_cpu_transcription',child_pid=p.pid);p.wait();save('transcription_child_finished',exit_code=p.returncode)
if __name__=='__main__':main()
