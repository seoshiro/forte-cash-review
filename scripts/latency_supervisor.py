"""Preserve current TUNE, replace only its monitor and change the later queue."""
from pathlib import Path
import os,sys,json,time,hashlib,subprocess,psutil,statistics
ROOT=Path(__file__).resolve().parents[1];os.chdir(ROOT);out=ROOT/'.private/structured'
def exact(pid,script):
    process=psutil.Process(pid)
    if Path(process.cwd()).resolve()!=ROOT or not any(Path(x).name==script for x in process.cmdline()[1:]):raise RuntimeError('Owned process identity mismatch')
    return process
def stage(name,**extra):
    (out/'status.json').write_text(json.dumps({'stage':name,'updated_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'supervisor_pid':os.getpid(),**extra}),encoding='utf-8')
def run(args,label,timeout):
    with (out/(label+'.stdout.log')).open('w') as stdout,(out/(label+'.stderr.log')).open('w') as stderr:
        process=subprocess.Popen([sys.executable,*args],cwd=ROOT,stdout=stdout,stderr=stderr,creationflags=0x08000000)
        try:return process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            sys.path.insert(0,str(ROOT));from cashreview.processes import kill_tree
            clean=kill_tree(process.pid);stage('blocked_latency_stage_timeout',target=label,cleanup_confirmed=clean);raise RuntimeError('Owned latency stage exceeded technical budget') from None
def main():
    old=exact(964,'adopt_uniform_supervisor.py');evaluation=exact(5188,'evaluate.py')
    state=json.loads((out/'status.json').read_text())
    if state['stage']!='structured_tune_uniform':raise RuntimeError('TUNE stage changed; no monitor stopped')
    source=sorted((ROOT/'.private/experiments').glob('*-uniform-tune'))[-1]
    frozen=json.loads((source/'frozen-source-digests.json').read_text())
    if any(hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=value for name,value in frozen.items()):raise RuntimeError('Frozen evaluator source changed; no monitor stopped')
    identity=evaluation.create_time();old.terminate();old.wait(timeout=5)
    same=evaluation.is_running() and evaluation.create_time()==identity
    record={'updated_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'old_monitor_pid':964,
            'new_supervisor_pid':os.getpid(),'preserved_gpu_evaluator_pid':5188,'same_gpu_process_alive':same,
            'evaluator_terminated_or_restarted':False,'frozen_source_mismatches':0,'full_train_queued':False,
            'queue_after_tune':['one TRAIN technical stage profile','BUDGET-01 technical gate']}
    (out/'queue-change-safe-summary.json').write_text(json.dumps(record,indent=2),encoding='utf-8');print(json.dumps(record),flush=True)
    if not same:raise RuntimeError('Existing evaluator was not preserved; no new GPU workload started')
    stage('structured_tune_uniform',stage_started_utc=state.get('stage_started_utc',state['updated_utc']),evaluation_pid=5188,full_train_queued=False)
    evaluation.wait()
    summary=json.loads((source/'safe-summary.json').read_text())
    if summary['completed']+summary['failed']!=summary['requested']:raise RuntimeError('TUNE aggregate is incomplete')
    latencies=[json.loads(p.read_text())['elapsed_sec'] for p in source.glob('*/metrics.json')]
    import numpy as np
    summary.update(latency_percentile_scope='stored successful engine.analyze results; excludes upload, queue, process startup and model load',
                   latency_percentile_count=len(latencies),latency_p50_sec=float(np.quantile(latencies,.5)) if latencies else None,
                   latency_p90_sec=float(np.quantile(latencies,.9)) if latencies else None,latency_p95_sec=float(np.quantile(latencies,.95)) if latencies else None,
                   percentile_method='linear interpolation',full_train_skipped_due_to_sla=True)
    (out/'tune-uniform.safe-summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps(summary),flush=True)
    stage('latency_profile',tune_complete=True,full_train_queued=False)
    if run(['scripts/profile_baseline_stages.py'],'baseline-stage-profile',1200):raise RuntimeError('Technical baseline profile failed')
    stage('budget_technical_benchmark',tune_complete=True,full_train_queued=False)
    if run(['scripts/benchmark_budget.py','--precision','bf16'],'budget-technical',1200):raise RuntimeError('BUDGET-01 technical benchmark failed')
    stage('latency_technical_complete_await_api',tune_complete=True,full_train_queued=False)
if __name__=='__main__':
    try:main()
    except Exception as error:
        print(json.dumps({'status':'latency_supervisor_blocked','error_type':type(error).__name__}),flush=True)
        sys.exit(1)
