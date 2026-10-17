"""Single synthetic native process; optionally one registered TRAIN control/TUNE."""
from pathlib import Path
import argparse,json,os,sys,time,hashlib,traceback
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))

def source_digests():
    from scripts.evaluate_gate import source_digests as base
    return {**base(),**{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [*list((ROOT/'gguf_candidate').glob('*.py')),ROOT/'scripts/validate_native.py',ROOT/'config/gguf-artifacts.json',ROOT/'config/gguf-protocol.json']}}

def main():
    os.chdir(ROOT);p=argparse.ArgumentParser();p.add_argument('--train-control',action='store_true');p.add_argument('--run-tune-if-passed',action='store_true');a=p.parse_args()
    from scripts.diagnose_synthetic_semantics import ensure_idle
    ensure_idle()
    cfg=json.loads((ROOT/'config/gguf-protocol.json').read_text());out=ROOT/'.private/gguf-control';out.mkdir(exist_ok=True)
    if (out/'synthetic-safe-summary.json').exists():raise RuntimeError('Native validation already completed; no repeated run')
    prior=json.loads((ROOT/'.private/gate-control/registration.json').read_text());registration={'source_sha256':prior['source_sha256'],'prior_selection_sha256':hashlib.sha256((ROOT/'.private/gate-control/registration.json').read_bytes()).hexdigest(),'protocol':cfg,'source_digests':source_digests()}
    target=out/'registration.json'
    if target.exists() and json.loads(target.read_text())!=registration:raise RuntimeError('Native registration changed')
    target.write_text(json.dumps(registration,indent=2));(out/'status.json').write_text(json.dumps({'stage':'model_loading','train_started':False,'tune_started':False,'holdout_opened':False}))
    from gguf_candidate.engine import GGUFEngine
    from gguf_candidate.runtime import DeviceMeter
    from cashreview.offline import deny_network
    from cashreview.video import Sample
    from PIL import Image,ImageDraw
    meter=DeviceMeter();meter.start();tick=time.monotonic();engine=None
    try:
        engine=GGUFEngine(out/'runtime');load=time.monotonic()-tick
        deny_network([engine.server.port])
        gray=Image.new('RGB',(384,384),(127,127,127));red=gray.copy();ImageDraw.Draw(red).rectangle((70,70,300,300),fill=(255,0,0))
        schema={'type':'object','additionalProperties':False,'properties':{'red_rectangle':{'type':'boolean'}},'required':['red_rectangle']}
        values=[];times=[];checks={}
        for index,(image,expected) in enumerate([(gray,False),(red,True),(gray,False)]):
            text,m=engine.server.complete([Sample(0.,image)],'Is a red rectangle visible? Return JSON with red_rectangle true or false.',schema,32,time.monotonic()+60)
            data=json.loads(text);checks[f'visual_binary_control_{index}']=data=={'red_rectangle':expected};values.append(data);times.append(m['generation_sec'])
        frames=[Sample(float(i),gray.copy()) for i in range(8)]
        obs=engine.observe(frames,2,192,time.monotonic()+90);checks['empty_domain_negative']=obs['events']==[] and engine.gate_calls[-1]['visible_violation'] is False
        checks['single_gate_without_detail']=len(engine.telemetry)==1
        memory=meter.stop();report={'protocol_id':cfg['protocol_id'],'scope':'generated gray/red geometry only; not bank-video quality','cases':4,'checks':checks,'passed':all(checks.values()),
                'model_load_sec':load,'single_image_generation_mean_sec':sum(times)/len(times),'single_image_generation_max_sec':max(times),
                'coarse_gate_generation_sec':engine.telemetry[-1]['generation_sec'],**memory,'torch_imported':'torch' in sys.modules,'holdout_opened':False,'tune_started':False}
        (out/'synthetic-safe-summary.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)
        if not report['passed']:return
        if a.train_control:
            if source_digests()!=registration['source_digests']:raise RuntimeError('Native source changed before TRAIN')
            from scripts.evaluate_gate import run_phase,rank
            manifest=json.loads((ROOT/'.private/dataset/manifest.json').read_text(encoding='utf-8'))
            index={r['sha256']:r for r in manifest if r['split']=='train' and not r['error']}
            selected=[index[s] for s in registration['source_sha256']]
            (out/'status.json').write_text(json.dumps({'stage':'fixed_train_control','train_started':True,'tune_started':False,'holdout_opened':False}))
            train=run_phase(engine,'train',selected,out,cfg,load)
            if a.run_tune_if_passed and train['passed_control']:
                if source_digests()!=registration['source_digests']:raise RuntimeError('Native source changed; TUNE not started')
                (out/'accepted-frozen-registration.json').write_text(json.dumps(registration,indent=2))
                (out/'status.json').write_text(json.dumps({'stage':'single_frozen_tune','train_started':True,'tune_started':True,'holdout_opened':False}))
                tune=sorted([r for r in manifest if r['split']=='tune' and not r['error']],key=lambda r:rank(cfg['selection']['seed'],'tune-order',r['sha256']))
                run_phase(engine,'tune',tune,out,cfg,load)
        (out/'status.json').write_text(json.dumps({'stage':'complete','train_started':(out/'train-safe-summary.json').exists(),'tune_started':(out/'tune-safe-summary.json').exists(),'holdout_opened':False}))
    finally:
        meter.stop()
        if engine:engine.close()

if __name__=='__main__':
    try:main()
    except Exception as error:
        report={'status':'failed','error_type':type(error).__name__,'source_locations':[{'file':Path(f.filename).name,'line':f.lineno,'function':f.name} for f in traceback.extract_tb(error.__traceback__)],'raw_content_emitted':False}
        p=ROOT/'.private/gguf-control';p.mkdir(exist_ok=True);(p/'technical-failure-safe-summary.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True);sys.exit(1)
