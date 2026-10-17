"""Resumable, bounded local VLM experiment. No real-video content in stdout.

Starts artifact preparation only when explicitly called and writes all local
outputs to .private. No credentials or public exposure are configured here.
"""
from pathlib import Path
import sys,os,subprocess,json,concurrent.futures,time
ROOT=Path(__file__).resolve().parents[1];os.chdir(ROOT);out=ROOT/'.private/vlm-pipeline';out.mkdir(parents=True,exist_ok=True)
def stage(name,**kwargs):
    (out/'status.json').write_text(json.dumps({'stage':name,'updated_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),**kwargs}),encoding='utf-8')
def run(args,log,timeout):
    with (out/(log+'.stdout.log')).open('w') as stdout,(out/(log+'.stderr.log')).open('w') as stderr:
        return subprocess.run([sys.executable,*args],stdout=stdout,stderr=stderr,cwd=ROOT,timeout=timeout).returncode
try:
    stage('download_preparation')
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        futures={name:pool.submit(run,['scripts/resume_downloads.py',name],name+'-download',3800) for name in ['qwen','cuda']}
        codes={name:f.result() for name,f in futures.items()}
    if any(codes.values()):stage('blocked_download',returncodes=codes);sys.exit(2)
    stage('technical_benchmark')
    if run(['scripts/benchmark.py'],'benchmark',600):stage('blocked_benchmark');sys.exit(2)
    bench=json.loads((ROOT/'.private/benchmark/safe-summary.json').read_text())
    if bench['json_success_count']!=bench['sample_count']:stage('blocked_model_output_contract');sys.exit(2)
    if bench['inference_sec_max']>35:stage('budget_review_required',observed_inference_sec_max=bench['inference_sec_max']);sys.exit(2)
    stage('tuning_uniform')
    if run(['scripts/evaluate.py','--split','tune','--strategy','uniform'],'tune-uniform',3600):stage('blocked_uniform');sys.exit(2)
    stage('tuning_coarse_refine')
    if run(['scripts/evaluate.py','--split','tune','--strategy','coarse_refine'],'tune-refine',3600):stage('blocked_refine');sys.exit(2)
    run(['scripts/claims.py'],'claim-ledger',60);stage('tuning_complete_holdout_closed')
except Exception as e:stage('failed',error_type=type(e).__name__);sys.exit(1)
