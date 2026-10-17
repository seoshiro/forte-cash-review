"""Continue frozen native control after an explicitly recorded synthetic repair."""
from pathlib import Path
import sys,json,time,hashlib,traceback,psutil
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
def main():
    from scripts.validate_native import source_digests
    from scripts.evaluate_gate import run_phase,rank
    out=ROOT/'.private/gguf-control';registration=json.loads((out/'registration.json').read_text())
    if source_digests()!=registration['source_digests']:raise RuntimeError('Frozen native model/pipeline changed; control not started')
    original=json.loads((out/'synthetic-safe-summary.json').read_text());shape=ROOT/'.private/gguf-shape-diagnostic/safe-summary.json';repair=json.loads(shape.read_text())
    config_sha=hashlib.sha256((ROOT/'config/gguf-artifacts.json').read_bytes()).hexdigest()
    if not repair.get('passed') or repair.get('artifact_config_sha256')!=config_sha or not original['checks']['empty_domain_negative']:raise RuntimeError('Native positive/negative preflight not satisfied')
    if (out/'train').exists() or (out/'train-safe-summary.json').exists():raise RuntimeError('Native TRAIN phase already started; no duplicate run')
    for p in psutil.process_iter():
        try:
            if p.name().lower()=='llama-server.exe' and Path(p.exe()).resolve().is_relative_to((ROOT/'.private/llama-cuda124-b11712').resolve()):raise RuntimeError('Another owned native model remains active')
        except (psutil.Error,OSError):pass
    supplemental={'reason':'First visual test asked rectangle for a square; retained failure and one synthetic-only unambiguous shape comparison before any real control',
                  'prior_failed_summary_retained':True,'shape_summary_sha256':hashlib.sha256(shape.read_bytes()).hexdigest(),
                  'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'original_registration_sha256':hashlib.sha256((out/'registration.json').read_bytes()).hexdigest(),'train_runs_before_continuation':0}
    (out/'accepted-synthetic-repair.json').write_text(json.dumps(supplemental,indent=2))
    cfg=registration['protocol'];engine=None
    try:
        from gguf_candidate.engine import GGUFEngine
        from cashreview.offline import deny_network
        start=time.monotonic();engine=GGUFEngine(out/'control-runtime');load=time.monotonic()-start;deny_network([engine.server.port])
        rows=json.loads((ROOT/'.private/dataset/manifest.json').read_text(encoding='utf-8'));index={r['sha256']:r for r in rows if r['split']=='train' and not r['error']}
        selected=[index[s] for s in registration['source_sha256']]
        (out/'status.json').write_text(json.dumps({'stage':'fixed_train_control_after_synthetic_repair','train_started':True,'tune_started':False,'holdout_opened':False}))
        train=run_phase(engine,'train',selected,out,cfg,load)
        if train['passed_control']:
            if source_digests()!=registration['source_digests']:raise RuntimeError('Frozen source changed; TUNE not started')
            (out/'accepted-frozen-registration.json').write_text(json.dumps(registration,indent=2))
            (out/'status.json').write_text(json.dumps({'stage':'single_frozen_tune','train_started':True,'tune_started':True,'holdout_opened':False}))
            tune=sorted([r for r in rows if r['split']=='tune' and not r['error']],key=lambda r:rank(cfg['selection']['seed'],'tune-order',r['sha256']))
            run_phase(engine,'tune',tune,out,cfg,load)
        (out/'status.json').write_text(json.dumps({'stage':'complete','train_started':True,'train_passed_control':train['passed_control'],'tune_started':(out/'tune-safe-summary.json').exists(),'holdout_opened':False}))
    finally:
        if engine:engine.close()
if __name__=='__main__':
    try:main()
    except Exception as error:
        out=ROOT/'.private/gguf-control';out.mkdir(exist_ok=True)
        r={'status':'failed','error_type':type(error).__name__,'source_locations':[{'file':Path(f.filename).name,'line':f.lineno} for f in traceback.extract_tb(error.__traceback__)],'raw_content_emitted':False}
        (out/'control-failure-safe-summary.json').write_text(json.dumps(r,indent=2));print(json.dumps(r));sys.exit(1)
