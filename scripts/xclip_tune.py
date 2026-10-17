"""One immutable TUNE assessment. Private responses never reach tool stdout."""
from pathlib import Path
import os,sys,json,time,hashlib,argparse,csv,datetime,importlib.metadata as metadata
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from cashreview.supervision import atomic_json,supervise,await_start_gate,ControlSummary
OUT=ROOT/'.private/xclip-tune-control'
FILES=['config/xclip-tune-protocol.json','scripts/xclip_tune.py','tests/test_xclip_tune.py',
    'config/xclip-protocol.json','config/xclip-artifacts.json','xclip_candidate/features.py','xclip_candidate/evaluate.py',
    'xclip_candidate/experimental.py','cashreview/video.py','cashreview/offline.py','cashreview/supervision.py',
    'cashreview/research_split.py','requirements-patched-lock.txt','.private/dataset/manifest.json','.private/dataset/split.json',
    'qvt_candidate/evaluate.py','cashreview/schemas.py','cashreview/processes.py',
    '.private/xclip-experimental-v2/prototypes.json','.private/xclip-experimental-v2/prototypes.npz',
    '.private/xclip-control/registration.json','.private/xclip-control/feature-registration.json']
WORKER_FILES=[n for n in FILES if not n.startswith('.private/')]+[
    '.private/xclip-experimental-v2/prototypes.json','.private/xclip-experimental-v2/prototypes.npz']


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def prior_audit():
    names=['xclip-control','xclip-experimental-v2','xclip-hardneg-control','xclip-spatial-control','xclip-linear-control','xclip-api-synthetic-smoke']
    paths=[]
    for name in names:
        paths.extend((ROOT/'.private'/name).glob('*safe-summary.json'))
        paths.extend((ROOT/'.private'/name/'run').glob('*safe-summary.json'))
    matches=0
    for path in paths:
        record=json.loads(path.read_text())
        matches+=int(record.get('split')=='tune' or any(record.get(k) is True for k in ['tune_used','tune_run','tune_evaluated']))
    with (ROOT/'docs/claim-ledger.csv').open(encoding='utf-8') as stream:
        ledger=sum('xclip' in (r['claim']+' '+r['calculation']).lower() and r['split']=='tune' for r in csv.DictReader(stream))
    return {'status':'PASS' if not matches and not ledger else 'PRIOR_TUNE_FOUND','safe_reports_checked':len(paths),
        'prior_tune_reports_found':matches,'ledger_xclip_tune_rows':ledger,
        'scope':'Known XCLIP aggregate report locations and aggregate ledger; source/history inventory searched separately; no private per-video rows read'}


def select_rows(manifest):
    import math
    from cashreview.research_split import unique_train_contents
    unique_train_contents(manifest)  # Fail on source/group crossing; do not evaluate HOLDOUT.
    rows=sorted([r for r in manifest if r['split']=='tune'],key=lambda r:r['sha256'])
    if len(rows)!=9 or any(r.get('error') for r in rows):raise ValueError('Exactly9 valid original TUNE rows required')
    for row in rows:
        if type(row['target']) is not int or row['target'] not in (0,1):raise ValueError('Invalid TUNE target')
        if row['target'] and (row['label_sec'] is None or not math.isfinite(row['label_sec']) or not 0<=row['label_sec']<row['duration_sec']):raise ValueError('Invalid TUNE positive point')
        if not row['target'] and row['label_sec'] is not None:raise ValueError('Negative TUNE point must be absent')
    return rows


def identity(reg):
    files=WORKER_FILES if reg.get('worker_record') is True else FILES
    if {n:sha(ROOT/n) for n in files}!=reg['code_sha256']:raise ValueError('Registered candidate changed')
    if {n:metadata.version(n) for n in reg['versions']}!=reg['versions']:raise ValueError('Version changed')
    from xclip_candidate.experimental import encoder_artifacts
    if encoder_artifacts()!=reg['encoder_sha256']:raise ValueError('Encoder inventory changed')


def resource_preflight():
    import psutil,subprocess
    cfg=json.loads((ROOT/'config/xclip-tune-protocol.json').read_text())['runtime']
    available=psutil.virtual_memory().available/2**20
    used=float(subprocess.check_output(['nvidia-smi','--query-gpu=memory.used','--format=csv,noheader,nounits'],timeout=5,text=True).strip())
    if available<cfg['minimum_system_available_mib_before']:raise RuntimeError('RAM reserve insufficient')
    if used>cfg['max_device_used_mib_before']:raise RuntimeError('GPU busy; do not stop foreign processes')
    return available,used


def distribution(values):
    import numpy as np
    if not values:return {'count':0}
    a=np.asarray(values,dtype=float)
    if not np.isfinite(a).all() or np.any(a<0):raise ValueError('Invalid wall times')
    return {'count':len(values),'min':float(a.min()),'p25':float(np.percentile(a,25)),
        'median':float(np.median(a)),'p75':float(np.percentile(a,75)),'p95':float(np.percentile(a,95)),
        'max':float(a.max()),'mean':float(a.mean()),'sum':float(a.sum())}


def aggregate(rows):
    from qvt_candidate.evaluate import metrics
    done=[r for r in rows if r['status']=='done'];failed=[r for r in rows if r['status']!='done']
    m=metrics(done) if done else None
    return {'completed_results':len(done),'failed_or_refused':len(failed),'completed_metrics':m,
        'failed_positive_count':sum(r['truth']==1 for r in failed),'failed_negative_count':sum(r['truth']==0 for r in failed),
        'failure_reasons':{reason:sum((r.get('failure_reason') or 'unspecified')==reason for r in failed) for reason in sorted({r.get('failure_reason') or 'unspecified' for r in failed})},
        'not_attempted_count':sum(r['full_wall_sec'] is None for r in rows),
        'full_wall_sec_distribution':distribution([r['full_wall_sec'] for r in rows if r['full_wall_sec'] is not None]),
        'completed_wall_sec_distribution':distribution([r['full_wall_sec'] for r in done]),
        'over_300_seconds':sum(r['full_wall_sec'] is not None and r['full_wall_sec']>300 for r in rows)}


def register():
    import psutil
    OUT.mkdir(exist_ok=True)
    if (OUT/'registration.json').exists() or (OUT/'attempt.json').exists():raise RuntimeError('Existing assessment must be inspected, never repeated')
    audit=prior_audit();atomic_json(OUT/'history-safe-summary.json',audit)
    if audit['status']!='PASS':raise RuntimeError('Use existing matching TUNE result')
    from xclip_candidate.experimental import load_prototypes,encoder_artifacts,PACK_DIRECTORY
    load_prototypes(ROOT/PACK_DIRECTORY)
    cfg=json.loads((ROOT/'config/xclip-tune-protocol.json').read_text())
    if sha(ROOT/PACK_DIRECTORY/'prototypes.npz')!=cfg['candidate']['prototype_sha256']:raise ValueError('Candidate identity mismatch')
    available,used=resource_preflight()
    rows=select_rows(json.loads((ROOT/'.private/dataset/manifest.json').read_text(encoding='utf-8')))
    reg={'protocol_id':cfg['protocol_id'],'registered_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'code_sha256':{n:sha(ROOT/n) for n in FILES},'encoder_sha256':encoder_artifacts(),
        'versions':{n:metadata.version(n) for n in ['torch','transformers','numpy','av','psutil','scikit-learn']},
        'selection':rows,'available_ram_mib':available,'device_used_mib_before':used,'prior_tune_audit':audit}
    worker_record={'worker_record':True,'code_sha256':{n:sha(ROOT/n) for n in WORKER_FILES},
        'versions':reg['versions'],'encoder_sha256':reg['encoder_sha256']}
    with (OUT/'worker-identity.json').open('x',encoding='utf-8') as stream:json.dump(worker_record,stream,indent=2)
    reg['worker_identity_sha256']=sha(OUT/'worker-identity.json')
    with (OUT/'registration.json').open('x',encoding='utf-8') as stream:json.dump(reg,stream,indent=2)
    print(json.dumps({'registered':True,'registration_sha256':sha(OUT/'registration.json'),'tune_original_videos':len(rows),
        'tune_exact_unique_contents':len({r['sha256'] for r in rows}),'prior_tune_found':False,'available_ram_mib':available}))


def worker():
    run,deadline=await_start_gate();os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1',DO_NOT_TRACK='1')
    from cashreview.offline import deny_network
    deny_network()
    try:
        resource_preflight()
        import torch,psutil
        torch.set_num_threads(4);torch.cuda.reset_peak_memory_stats()
        from xclip_candidate.experimental import ExperimentalEngine,BinaryResearchResult
        info=json.loads((run.parent/'input-identity.json').read_text())
        if sha(OUT/'worker-identity.json')!=info['worker_identity_sha256']:raise ValueError('Worker identity record changed')
        reg=json.loads((OUT/'worker-identity.json').read_text());identity(reg)
        path=run.parent/'input.mov'
        if sha(path)!=info['sha256']:raise ValueError('Copied input changed')
        minimum_ram=json.loads((ROOT/'config/xclip-tune-protocol.json').read_text())['runtime']['minimum_system_available_mib_during']
        class GuardedEngine(ExperimentalEngine):
            def check(self):
                super().check()
                if psutil.virtual_memory().available/2**20<minimum_ram:raise RuntimeError('RAM margin')
        engine=GuardedEngine(deadline=deadline);result=engine.analyze(path,'0'*32)
        BinaryResearchResult.model_validate(result)
        if sha(path)!=info['sha256']:raise ValueError('Input changed during processing')
        atomic_json(run/'private-research-result.json',result,deadline=deadline)
        cfg=json.loads((ROOT/'config/xclip-tune-protocol.json').read_text())['runtime']
        def check():
            if time.monotonic()>=deadline:raise TimeoutError('TUNE case deadline')
            if psutil.virtual_memory().available/2**20<cfg['minimum_system_available_mib_during']:raise RuntimeError('RAM margin')
            if psutil.Process().memory_info().peak_wset/2**20>cfg['max_process_peak_working_set_mib']:raise RuntimeError('RSS limit')
            if torch.cuda.max_memory_reserved()/2**20>cfg['max_torch_reserved_mib']:raise RuntimeError('VRAM limit')
        check();atomic_json(run/'worker-safe-summary.json',ControlSummary(status='completed',completed_cases=1,passed_cases=1,total_cases=1).model_dump(),deadline=deadline);check()
    except Exception as error:
        (run/'private-research-result.json').unlink(missing_ok=True)
        atomic_json(run/'failure-safe-summary.json',{'status':'failed','technical_error_type':type(error).__name__})
        atomic_json(run/'worker-safe-summary.json',ControlSummary(status='failed',completed_cases=0,passed_cases=0,total_cases=1,failure='exception').model_dump())
        raise SystemExit(1)


def run():
    start=time.monotonic()
    from xclip_candidate.experimental import BinaryResearchResult
    cfg=json.loads((ROOT/'config/xclip-tune-protocol.json').read_text());reg=json.loads((OUT/'registration.json').read_text());identity(reg)
    with (OUT/'attempt.json').open('x') as stream:json.dump({'started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()},stream)
    results=[];root=OUT/'cases';root.mkdir(exist_ok=False)
    try:
        for index,row in enumerate(reg['selection']):
            tick=time.monotonic();deadline=tick+cfg['runtime']['job_budget_sec'];folder=root/f'case-{index:02d}';folder.mkdir()
            status='failed';prediction=None;error_sec=None;abort=False;reason='driver_exception'
            try:
                import shutil
                resource_preflight()
                if sha(OUT/'worker-identity.json')!=reg['worker_identity_sha256']:raise ValueError('Worker identity changed')
                if sha(row['path'])!=row['sha256']:raise ValueError('Original source identity changed')
                shutil.copyfile(row['path'],folder/'input.mov')
                atomic_json(folder/'input-identity.json',{'sha256':row['sha256'],'worker_identity_sha256':reg['worker_identity_sha256']},deadline=deadline)
                remaining=deadline-time.monotonic()
                if remaining<=0:raise TimeoutError('Copy deadline')
                terminal=supervise([sys.executable,str(Path(__file__).resolve()),'worker'],folder/'worker',remaining,1,str(ROOT))
                if not terminal['cleanup_complete']:abort=True;reason='cleanup_unconfirmed';raise RuntimeError('Cleanup unconfirmed')
                if not terminal['quality_gate_passed']:reason='worker_failed';raise RuntimeError('Case failed')
                result=BinaryResearchResult.model_validate_json((folder/'worker/private-research-result.json').read_text())
                prediction=int(result.binary_decision=='violation')
                error_sec=abs(result.candidate_timecode_sec-row['label_sec']) if prediction and row['target'] else None
                if sha(row['path'])!=row['sha256']:raise ValueError('Original source changed')
                status='done'
            except Exception:status='failed';prediction=None;error_sec=None
            record={'status':status,'truth':row['target'],'prediction':prediction,'error_sec':error_sec,'failure_reason':None if status=='done' else reason}
            atomic_json(folder/'private-evaluation.json',record)
            record['full_wall_sec']=time.monotonic()-tick
            if record['full_wall_sec']>cfg['runtime']['full_wall_limit_sec']:record.update(status='failed',prediction=None,error_sec=None,failure_reason='full_wall_limit')
            results.append(record);atomic_json(OUT/'private-evaluation-results.json',results)
            print(json.dumps({'completed_attempts':len(results),'total_attempts':9,'per_video_results_emitted':False}),flush=True)
            if abort:
                for pending in reg['selection'][index+1:]:results.append({'status':'refused','truth':pending['target'],
                    'prediction':None,'error_sec':None,'failure_reason':'cleanup_unconfirmed','full_wall_sec':None})
                atomic_json(OUT/'private-evaluation-results.json',results);break
        identity(reg)
        summary={'status':'completed','protocol_id':cfg['protocol_id'],'split':'tune','evaluation_original_videos':len(results),
            'attempted_original_videos':sum(r['full_wall_sec'] is not None for r in results),**aggregate(results),
            'total_assessment_wall_sec':time.monotonic()-start,'cold_worker_per_video':True,'candidate_and_sources_unchanged':True,
            'threshold_or_model_changed':False,'holdout_used':False,'type_rule_or_evidence_validated':False,'final_test':False,
            'official_score':False,'per_video_outputs_emitted':False,'release_eligible':False,'registration_sha256':sha(OUT/'registration.json'),
            'timing_scope':'Local cold process including copy/integrity/model/decode/score/JPEG/schema/cleanup; not HTTP upload or public latency'}
        atomic_json(OUT/'safe-summary.json',summary);print(json.dumps(summary),flush=True)
    except Exception as error:
        failure={'status':'failed','technical_error_type':type(error).__name__,'attempted_videos':len(results),**aggregate(results),
            'holdout_used':False,'per_video_outputs_emitted':False,'repeat_authorized':False}
        atomic_json(OUT/'safe-summary.json',failure);print(json.dumps(failure));raise SystemExit(1)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['audit','register','run','worker']);a=p.parse_args()
    try:
        if a.action=='audit':print(json.dumps(prior_audit()))
        elif a.action=='register':register()
        elif a.action=='worker':worker()
        else:run()
    except Exception as error:print(json.dumps({'rejected_or_failed':True,'technical_error_type':type(error).__name__,'raw_private_content_emitted':False}));sys.exit(1)
