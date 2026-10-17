"""Private TRAIN-only end-to-end model API QA. Never print semantic results/evidence.

Starts a dedicated loopback test server with an intentionally non-production,
temporary test value. Stops only its own process tree. No public relay or keys.
"""
from pathlib import Path
from io import BytesIO
import argparse,base64,hashlib,json,os,socket,subprocess,sys,time,statistics
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from cashreview.video import sample,inspect
from cashreview.schemas import Done


def verify_frames(path,result):
    checked=0;duration=inspect(path)['duration_sec']
    for event in result['violations']:
        if not 0<=event['timecode_sec']<=duration:raise ValueError('Event timestamp outside source')
        for e in event['evidence_frames']:
            t=e['timestamp_sec']
            if not 0<=t<=duration:raise ValueError('Evidence timestamp outside source')
            frame=sample(path,[max(0,t-.0006)],960)[0]
            if abs(frame.sec-t)>.001:raise ValueError('Evidence PTS mismatch')
            b=BytesIO();frame.image.save(b,'JPEG',quality=85)
            if b.getvalue()!=base64.b64decode(e['image_base64'],validate=True):raise ValueError('Evidence pixels differ from timestamped source frame')
            checked+=1
    return checked


def main():
    import httpx,psutil
    p=argparse.ArgumentParser();p.add_argument('--strategy',choices=['uniform','coarse_refine'],default='uniform')
    p.add_argument('--engine',choices=['baseline','budget'],default='baseline')
    p.add_argument('--precision',choices=['bf16','nf4'],default='bf16');a=p.parse_args()
    os.chdir(ROOT);status=json.loads((ROOT/'.private/vlm-pipeline/status.json').read_text())
    if status['stage'] in ['download_preparation','technical_benchmark','tuning_uniform','tuning_coarse_refine']:raise RuntimeError('Wait for active artifact/GPU pipeline first')
    structured=ROOT/'.private/structured/status.json'
    if structured.exists() and json.loads(structured.read_text())['stage'] in ['structured_technical_benchmark','structured_tune_uniform','structured_train_uniform','latency_profile','budget_technical_benchmark']:
        raise RuntimeError('Wait for active structured TRAIN/TUNE pipeline first')
    weights=ROOT/'models/qwen3-vl-2b/model.safetensors';provenance=json.loads((ROOT/'models/provenance.json').read_text())
    with weights.open('rb') as f:verified=hashlib.file_digest(f,'sha256').hexdigest()==provenance['weights_sha256']
    if not verified:raise RuntimeError('Official model checksum mismatch')
    rows=[r for r in json.loads((ROOT/'.private/dataset/manifest.json').read_text(encoding='utf-8')) if r['split']=='train' and not r['error']]
    chosen=[next(r for r in rows if r['target']==v) for v in [0,1]]
    longest=max(rows,key=lambda r:r['duration_sec'])
    if not any(r['sha256']==longest['sha256'] for r in chosen):chosen.append(longest)
    cases=[(r,'unseen-input.mov') for r in chosen]+[(chosen[1],'different-arbitrary-name.mov')]
    out=ROOT/'.private/model-api-qa'/time.strftime('%Y%m%dT%H%M%SZ',time.gmtime());out.mkdir(parents=True)
    (out/'frozen-config.json').write_bytes((ROOT/'config/experiment.json').read_bytes())
    if a.engine=='budget':(out/'frozen-budget-protocol.json').write_bytes((ROOT/'config/budget-protocol.json').read_bytes())
    with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
    base=f'http://127.0.0.1:{port}';key='temporary-loopback-model-qa-only';other='temporary-loopback-other-owner'
    env=os.environ.copy();env.update(CASH_API_KEY=key+','+other,CASH_PRIVATE=str(out/'server-private'),CASH_STRATEGY=a.strategy,CASH_ENGINE=a.engine,CASH_PRECISION=a.precision)
    proc=None;latencies=[];failed=0;evidence=0;vram=[];truth=[];guesses=[];timing=[];completed=[];unchanged=True;checks={}
    try:
        with (out/'server.stdout.log').open('w') as stdout,(out/'server.stderr.log').open('w') as stderr:
            proc=subprocess.Popen([sys.executable,'scripts/serve.py','--port',str(port)],cwd=ROOT,env=env,stdout=stdout,stderr=stderr,creationflags=subprocess.CREATE_NO_WINDOW)
        with httpx.Client(timeout=30,trust_env=False) as c:
            deadline=time.monotonic()+30
            while True:
                try:
                    h=c.get(base+'/healthz');assert h.json()['mode']=='model';break
                except (httpx.HTTPError,AssertionError):
                    if proc.poll() is not None or time.monotonic()>deadline:raise RuntimeError('Dedicated local model server failed')
                    time.sleep(.2)
            headers={'X-API-Key':key}
            checks['missing_key_rejected']=c.get(base+'/api/v1/jobs/'+'0'*32).status_code==401
            checks['wrong_key_rejected']=c.post(base+'/api/v1/analyze',headers={'X-API-Key':'wrong'}).status_code==401
            checks['unknown_job_rejected']=c.get(base+'/api/v1/jobs/'+'0'*32,headers=headers).status_code==404
            for i,(r,name) in enumerate(cases):
                path=Path(r['path'])
                with path.open('rb') as f:before=hashlib.file_digest(f,'sha256').hexdigest()
                start=time.monotonic()
                with path.open('rb') as f:response=c.post(base+'/api/v1/analyze',headers=headers,files={'file':(name,f,'video/quicktime')})
                response.raise_for_status();job=response.json()['job_id']
                checks['foreign_owner_isolated']=checks.get('foreign_owner_isolated',True) and c.get(base+'/api/v1/jobs/'+job,headers={'X-API-Key':other}).status_code==404
                while True:
                    response=c.get(base+'/api/v1/jobs/'+job,headers=headers);response.raise_for_status();result=response.json()
                    if result['status']!='processing':break
                    if time.monotonic()-start>=300:raise TimeoutError('End-to-end job budget exceeded')
                    time.sleep(.2)
                latencies.append(time.monotonic()-start)
                with path.open('rb') as f:unchanged &= before==hashlib.file_digest(f,'sha256').hexdigest()
                (out/f'private-result-{i}.json').write_text(json.dumps(result,ensure_ascii=False),encoding='utf-8')
                if result['status']=='failed':failed+=1;completed.append(None);continue
                Done.model_validate(result);evidence+=verify_frames(path,result)
                completed.append({k:v for k,v in result.items() if k!='job_id'})
                guess=int(result['verdict']=='violation');truth.append(r['target']);guesses.append(guess)
                if guess and r['target']:timing.append(min(abs(v['timecode_sec']-r['label_sec']) for v in result['violations']))
                m=out/'server-private/jobs'/job/'metrics.json'
                if m.exists():vram.append(json.loads(m.read_text())['vram_peak_mib'])
            checks['renamed_content_invariance']=completed[1] is not None and completed[1]==completed[-1]
            checks['source_hashes_unchanged']=bool(unchanged)
        from sklearn.metrics import confusion_matrix
        summary={'scope':'TRAIN smoke test including renamed repeat; not generalization evaluation','strategy':a.strategy,'cases':len(cases),'completed':len(truth),'failed':failed,'checks':checks,'evidence_frames_verified_against_original':evidence,'latency_upload_to_status_mean_sec':statistics.mean(latencies),'latency_upload_to_status_max_sec':max(latencies),'over_300_sec':sum(t>300 for t in latencies),'vram_allocated_peak_mib':max(vram) if vram else None,'train_smoke_confusion_matrix_tn_fp_fn_tp':confusion_matrix(truth,guesses,labels=[0,1]).tolist(),'matched_positive_timing_count':len(timing),'timestamp_mae_sec':statistics.mean(timing) if timing else None,'holdout_opened':False,'public_access_tested':False,'physical_network_disconnect_tested':False,'official_score':False}
        summary.update(engine=a.engine,precision=a.precision,
                       strategy='bounded_refine' if a.engine=='budget' else a.strategy,
                       status='PASS' if not failed and all(checks.values()) and max(latencies)<300 else 'FAIL',
                       meets_240_sec_target=not failed and max(latencies)<=240,
                       queue_policy='single admitted job; overlapping upload receives 429, no hidden waiting queue',
                       protocol_id=json.loads((ROOT/'config/budget-protocol.json').read_text())['protocol_id'] if a.engine=='budget' else None)
        (out/'safe-summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');print(json.dumps(summary))
    finally:
        if proc:
            try:targets=psutil.Process(proc.pid).children(recursive=True)+[psutil.Process(proc.pid)]
            except psutil.NoSuchProcess:targets=[]
            for child in targets:
                try:child.terminate()
                except psutil.NoSuchProcess:pass
            _,alive=psutil.wait_procs(targets,timeout=5)
            for child in alive:child.kill()


if __name__=='__main__':
    try:main()
    except Exception as error:
        import traceback
        print(json.dumps({'status':'FAIL','technical_error_type':type(error).__name__,
              'source_locations':[{'file':Path(f.filename).name,'line':f.lineno,'function':f.name} for f in traceback.extract_tb(error.__traceback__)],
              'raw_model_results_emitted':False}));sys.exit(1)
