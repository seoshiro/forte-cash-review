"""Sequential local format benchmark and uniform TRAIN/TUNE validation.

No credentials, public network exposure or holdout. Failures preserve technical
status and private logs. A subprocess deadline kills the full Windows tree.
"""
from pathlib import Path
import subprocess,sys,time,json,os
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));os.chdir(ROOT)
from cashreview.processes import kill_tree
out=ROOT/'.private/structured';out.mkdir(exist_ok=True)
def stage(name,**extra):
    record={'stage':name,'updated_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),**extra}
    (out/'status.json').write_text(json.dumps(record),encoding='utf-8')
    print(json.dumps(record),flush=True)
def run(args,log,timeout):
    with (out/(log+'.stdout.log')).open('w') as stdout,(out/(log+'.stderr.log')).open('w') as stderr:
        process=subprocess.Popen([sys.executable,*args],cwd=ROOT,stdout=stdout,stderr=stderr,creationflags=0x08000000)
        try:return process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:kill_tree(process.pid);raise RuntimeError('owned_stage_timeout') from None
try:
    warm=json.loads((ROOT/'.private/synthetic-structure-diagnostic-safe-summary.json').read_text())
    if not warm.get('observe_valid') or not warm.get('schema_valid'):raise RuntimeError('synthetic_schema_not_validated')
    stage('structured_technical_benchmark')
    if run(['scripts/benchmark.py'],'benchmark',650):raise RuntimeError('benchmark_failed')
    bench=json.loads((ROOT/'.private/benchmark/safe-summary.json').read_text())
    if bench['json_success_count']!=bench['sample_count'] or not bench['uniform_probe_json_valid']:raise RuntimeError('benchmark_contract_failed')
    stage('structured_tune_uniform')
    if run(['scripts/evaluate.py','--split','tune','--strategy','uniform'],'tune-uniform',2400):raise RuntimeError('tune_failed')
    stage('structured_train_uniform')
    if run(['scripts/evaluate.py','--split','train','--strategy','uniform'],'train-uniform',4800):raise RuntimeError('train_failed')
    run(['scripts/claims.py'],'claims',60)
    stage('uniform_complete_holdout_closed')
except Exception as error:
    # Only fixed errors/types. Never serialize an inference exception message.
    stage('blocked',error_type=type(error).__name__)
    sys.exit(1)
