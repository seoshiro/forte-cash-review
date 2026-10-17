"""Replace only the short-lived supervisor, preserving its running GPU child.

The original 40-minute whole-TUNE timeout is shorter than measured completion
time. No evaluator is terminated, restarted or duplicated. Frozen model code,
config, runtime, completed answers and inputs remain unchanged.
"""
from pathlib import Path
import os,sys,json,time,hashlib,subprocess,psutil
ROOT=Path(__file__).resolve().parents[1];os.chdir(ROOT)
out=ROOT/'.private/structured'
def exact(pid,script):
    process=psutil.Process(pid)
    if Path(process.cwd()).resolve()!=ROOT or not any(Path(x).name==script for x in process.cmdline()[1:]):raise RuntimeError('Owned process identity mismatch')
    return process
def stage(name,**extra):
    (out/'status.json').write_text(json.dumps({'stage':name,'updated_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'supervisor_pid':os.getpid(),**extra}),encoding='utf-8')
def main():
    supervisor=exact(8068,'run_structured_validation.py');evaluator=exact(5188,'evaluate.py')
    if 8068 not in {p.pid for p in evaluator.parents()}:raise RuntimeError('Evaluator is not a child of the verified old supervisor')
    state=json.loads((out/'status.json').read_text())
    if state['stage']!='structured_tune_uniform':raise RuntimeError('Unexpected current stage; no process stopped')
    runs=sorted((ROOT/'.private/experiments').glob('*-uniform-tune'));run=runs[-1]
    frozen=json.loads((run/'frozen-source-digests.json').read_text())
    if any(hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=value for name,value in frozen.items()):raise RuntimeError('Frozen evaluator source changed; no process stopped')
    identity=evaluator.create_time()
    # Deliberately terminate ONLY this verified supervisor, never kill_tree.
    # Windows venv launcher/evaluator children retain their independent handles.
    supervisor.terminate();supervisor.wait(timeout=5)
    same=evaluator.is_running() and evaluator.create_time()==identity
    record={'updated_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'old_supervisor_pid':8068,
            'new_supervisor_pid':os.getpid(),'preserved_gpu_evaluator_pid':5188,
            'same_gpu_process_alive':same,'evaluator_terminated_or_restarted':False,
            'source_digest_mismatches':0,'original_stage_started_utc':state['updated_utc'],
            'reason':'preserve useful evaluation beyond original 2400-second whole-stage timeout'}
    (out/'supervisor-handoff-safe-summary.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
    print(json.dumps(record),flush=True)
    if not same:raise RuntimeError('Evaluator did not remain alive; no replacement GPU workload started')
    stage('structured_tune_uniform',stage_started_utc=state['updated_utc'],evaluation_pid=5188,supervisor_mode='preserve_existing_evaluator')
    evaluator.wait()
    summary=json.loads((run/'safe-summary.json').read_text())
    if summary['completed']+summary['failed']!=summary['requested']:raise RuntimeError('TUNE aggregate is incomplete')
    (out/'tune-uniform.safe-summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps(summary),flush=True)
    stage('structured_train_uniform')
    with (out/'train-uniform.stdout.log').open('w') as stdout,(out/'train-uniform.stderr.log').open('w') as stderr:
        process=subprocess.Popen([sys.executable,'scripts/evaluate.py','--split','train','--strategy','uniform'],cwd=ROOT,stdout=stdout,stderr=stderr,creationflags=0x08000000)
        if process.wait()!=0:raise RuntimeError('TRAIN evaluator failed')
    subprocess.run([sys.executable,'scripts/claims.py'],cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=True)
    stage('uniform_complete_holdout_closed')
if __name__=='__main__':
    try:main()
    except Exception as error:
        print(json.dumps({'status':'supervisor_blocked','error_type':type(error).__name__}),flush=True)
        # An existing evaluator is never killed by this error path.
        sys.exit(1)
