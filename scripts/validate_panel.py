"""Registered panel4 controls, then identical seeded TRAIN and conditional TUNE."""
from pathlib import Path
import sys,json,time,hashlib,traceback,psutil
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def sources():
    from scripts.validate_native import source_digests
    return {**source_digests(),**{str(p.relative_to(ROOT)):sha(p) for p in [*list((ROOT/'panel_candidate').glob('*.py')),Path(__file__),ROOT/'config/panel-protocol.json']}}
def main():
    from panel_candidate.engine import PanelEngine,CANVAS,PIXEL_LIMIT,panel_image
    from gguf_candidate.runtime import DeviceMeter
    from cashreview.video import Sample
    from cashreview.offline import deny_network
    from PIL import Image,ImageDraw
    from scripts.evaluate_gate import run_phase,rank
    for p in psutil.process_iter():
        try:
            if p.name().lower()=='llama-server.exe' and Path(p.exe()).is_relative_to(ROOT/'.private/llama-cuda124-b11712'):raise RuntimeError('Owned native inference active; panel not started')
        except (psutil.Error,OSError):pass
    out=ROOT/'.private/panel-control';out.mkdir(exist_ok=True)
    if (out/'registration.json').exists():raise RuntimeError('Panel experiment already registered; no duplicate run')
    cfg=json.loads((ROOT/'config/panel-protocol.json').read_text());prior=ROOT/'.private/gate-control/registration.json';selection=json.loads(prior.read_text())
    frozen=sources();registration={'protocol':cfg,'source_sha256':selection['source_sha256'],'prior_selection_sha256':sha(prior),
                                 'frozen_source_digests':frozen,'registered_before_panel_inference':True}
    (out/'registration.json').write_text(json.dumps(registration,indent=2))
    def status(stage,**extra):(out/'status.json').write_text(json.dumps({'stage':stage,'holdout_opened':False,**extra}))
    status('model_loading',train_started=False,tune_started=False)
    gray=Image.new('RGB',(384,384),(127,127,127));red=gray.copy();ImageDraw.Draw(red).rectangle((60,120,309,219),fill=(255,0,0))
    small=gray.copy();ImageDraw.Draw(small).rectangle((180,180,203,191),fill=(255,0,0))
    meter=DeviceMeter();meter.start();engine=None;tick=time.monotonic()
    try:
        engine=PanelEngine(out/'runtime');load=time.monotonic()-tick;deny_network([engine.server.port])
        schema={'type':'object','additionalProperties':False,'properties':{'red_region':{'type':'boolean'}},'required':['red_region']}
        checks={};times={};tokens={}
        for name,position,positive in [('negative',None,red),('large_first',0,red),('large_middle_1',1,red),('large_middle_2',2,red),('large_last',3,red),
                                       ('small_first',0,small),('small_middle',2,small),('small_last',3,small)]:
            frames=[Sample(float(i),positive.copy() if i==position else gray.copy()) for i in range(4)]
            image,positions=panel_image(frames)
            image.save(out/(name+'.synthetic.png'))
            text,m=engine.server.complete(frames,'Is any red region visible in any supplied image? Return JSON with red_region true or false.',schema,32,time.monotonic()+90)
            try:checks[name]=json.loads(text)=={'red_region':position is not None}
            except (ValueError,TypeError):checks[name]=False
            times[name]=m['generation_sec'];tokens[name]=m.get('input_tokens')
            if name=='large_last':
                primary={'scope':'generated panel geometry only','cases':5,'checks':dict(checks),'passed':all(checks.values()),'model_load_sec':load,
                         'canvas_width':CANVAS[0],'canvas_height':CANVAS[1],'pixel_limit':PIXEL_LIMIT,'original_frame_pixels_resized':False,'bank_data_read':False}
                (out/'synthetic-primary-safe-summary.json').write_text(json.dumps(primary,indent=2));print(json.dumps(primary),flush=True)
        blank=[Sample(float(i),gray.copy()) for i in range(4)];engine._initial_observation=True
        observation=engine.observe(blank,2,192,time.monotonic()+90)
        checks['domain_empty_negative']=observation['events']==[] and engine.gate_calls[-1]['visible_violation'] is False
        report={'protocol_id':cfg['protocol_id'],'scope':'generated panels only; not bank-video quality','cases':len(checks),'checks':checks,'passed':all(checks.values()),
                'model_load_sec':load,'generation_sec_by_case':times,'input_tokens_by_case':tokens,'canvas_width':CANVAS[0],'canvas_height':CANVAS[1],
                'canvas_pixels':CANVAS[0]*CANVAS[1],'pixel_limit':PIXEL_LIMIT,'source_frames_per_panel':4,'source_frame_max_side':384,
                'source_pixels_resized':False,'source_pixels_cropped':False,**meter.stop(),'bank_data_read':False,'tune_started':False,'holdout_opened':False}
        (out/'synthetic-safe-summary.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)
        if not report['passed']:status('synthetic_control_failed',train_started=False,tune_started=False);return
        if sources()!=frozen:raise RuntimeError('Frozen panel source changed before TRAIN')
        status('fixed_train_control',train_started=True,tune_started=False)
        rows=json.loads((ROOT/'.private/dataset/manifest.json').read_text(encoding='utf-8'));index={r['sha256']:r for r in rows if r['split']=='train' and not r['error']}
        selected=[index[s] for s in registration['source_sha256']]
        train=run_phase(engine,'train',selected,out,cfg,load)
        if train['passed_control']:
            if sources()!=frozen:raise RuntimeError('Frozen panel source changed; TUNE not started')
            (out/'accepted-frozen-registration.json').write_text(json.dumps(registration,indent=2));status('single_frozen_tune',train_started=True,tune_started=True)
            tune=sorted([r for r in rows if r['split']=='tune' and not r['error']],key=lambda r:rank(cfg['selection']['seed'],'tune-order',r['sha256']))
            run_phase(engine,'tune',tune,out,cfg,load)
        status('complete',train_started=True,train_passed_control=train['passed_control'],tune_started=(out/'tune-safe-summary.json').exists())
    finally:
        meter.stop()
        if engine:engine.close()
if __name__=='__main__':
    try:main()
    except Exception as error:
        out=ROOT/'.private/panel-control';out.mkdir(exist_ok=True)
        report={'status':'failed','error_type':type(error).__name__,'source_locations':[{'file':Path(f.filename).name,'line':f.lineno} for f in traceback.extract_tb(error.__traceback__)],'raw_content_emitted':False}
        (out/'technical-failure-safe-summary.json').write_text(json.dumps(report,indent=2));print(json.dumps(report));sys.exit(1)
