"""Current-workflow dependency wait, then one native experiment. No raw log reads."""
from pathlib import Path
import os,sys,json,time,subprocess,psutil
ROOT=Path(__file__).resolve().parents[1]
def main():
    out=ROOT/'.private/gguf-control';out.mkdir(exist_ok=True);status=out/'supervisor-safe-summary.json'
    def save(stage,**extra):
        record={'stage':stage,'updated_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'holdout_opened':False,**extra}
        status.write_text(json.dumps(record,indent=2));return record
    save('waiting_for_verified_artifacts');deadline=time.monotonic()+1800
    ready=ROOT/'.private/gguf-preflight/safe-summary.json'
    while not ready.is_file():
        active=False
        for process in psutil.process_iter():
            try:
                if any(Path(a).name=='prepare_gguf.py' for a in process.cmdline()[1:]):active=True
            except psutil.Error:pass
        if not active:save('artifact_preparation_stopped_without_verified_summary');return
        if time.monotonic()>deadline:save('artifact_wait_budget_exhausted');return
        time.sleep(2)
    if json.loads(ready.read_text()).get('status')!='artifacts_verified_not_benchmarked':save('artifact_summary_not_ready');return
    python=ROOT/'.venv-patched/Scripts/python.exe'
    with (out/'run.stdout.log').open('w') as stdout,(out/'run.stderr.log').open('w') as stderr:
        process=subprocess.Popen([str(python),str(ROOT/'scripts/validate_native.py'),'--train-control','--run-tune-if-passed'],cwd=ROOT,stdout=stdout,stderr=stderr,creationflags=subprocess.CREATE_NO_WINDOW)
    save('native_synthetic_then_conditional_train_tune',child_pid=process.pid)
    process.wait();save('native_child_finished',exit_code=process.returncode)
if __name__=='__main__':main()
