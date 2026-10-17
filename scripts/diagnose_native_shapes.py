"""One bounded synthetic-only comparison; never reads media/labels/transcripts."""
from pathlib import Path
import sys,json,time,re,traceback,hashlib
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
def main():
    from scripts.diagnose_synthetic_semantics import ensure_idle
    ensure_idle()
    from gguf_candidate.runtime import NativeServer,DeviceMeter
    from cashreview.video import Sample
    from cashreview.offline import deny_network
    from PIL import Image,ImageDraw
    out=ROOT/'.private/gguf-shape-diagnostic';out.mkdir(exist_ok=True)
    if (out/'safe-summary.json').exists():raise RuntimeError('This bounded synthetic diagnostic already completed')
    registration={'scope':'synthetic geometry only','prior_positive_input_was_square':True,'new_positive_rectangle_width':250,'new_positive_rectangle_height':100,
                  'artifact_config_sha256':hashlib.sha256((ROOT/'config/gguf-artifacts.json').read_bytes()).hexdigest(),
                  'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'train_started':False,'holdout_opened':False}
    (out/'registration.json').write_text(json.dumps(registration,indent=2))
    server=NativeServer(out/'runtime');meter=DeviceMeter();meter.start();start=time.monotonic()
    try:
        server.start();load=time.monotonic()-start;deny_network([server.port])
        gray=Image.new('RGB',(384,384),(127,127,127));red=gray.copy();ImageDraw.Draw(red).rectangle((60,120,309,219),fill=(255,0,0))
        gray.save(out/'synthetic-gray.png');red.save(out/'synthetic-red-rectangle.png')
        checks={};timings={};responses={}
        for kind,image in [('gray',gray),('red',red)]:
            text,m=server.complete([Sample(0.,image)],'Describe only the visible colors and shapes in one short sentence.',None,64,time.monotonic()+90)
            responses['free_'+kind]=text;timings['free_'+kind]=m['generation_sec']
            words=text.lower();checks['free_red_color_mentioned' if kind=='red' else 'free_gray_color_mentioned']=bool(re.search(r'\bred\b',words)) if kind=='red' else bool(re.search(r'\bgr[ae]y\b',words))
            text,m=server.complete([Sample(0.,image)],'Is any red region visible? Answer only YES or NO.',None,8,time.monotonic()+60)
            responses['yes_no_'+kind]=text;timings['yes_no_'+kind]=m['generation_sec'];checks['plain_binary_'+kind]=text.strip().upper().rstrip('.!')==('YES' if kind=='red' else 'NO')
            schema={'type':'object','additionalProperties':False,'properties':{'red_region':{'type':'boolean'}},'required':['red_region']}
            text,m=server.complete([Sample(0.,image)],'Is any red region visible? Return JSON with red_region true or false.',schema,32,time.monotonic()+60)
            responses['json_'+kind]=text;timings['json_'+kind]=m['generation_sec']
            try:checks['json_binary_'+kind]=json.loads(text)=={'red_region':kind=='red'}
            except (ValueError,TypeError):checks['json_binary_'+kind]=False
        schema={'type':'object','additionalProperties':False,'properties':{'red_rectangle':{'type':'boolean'}},'required':['red_rectangle']}
        text,m=server.complete([Sample(0.,red)],'Is a red rectangle visible? Return JSON with red_rectangle true or false.',schema,32,time.monotonic()+60)
        responses['rectangle_json']=text;timings['rectangle_json']=m['generation_sec']
        try:checks['unambiguous_rectangle_positive']=json.loads(text)=={'red_rectangle':True}
        except (ValueError,TypeError):checks['unambiguous_rectangle_positive']=False
        report={'scope':'generated gray/red shapes only; no real video quality claim','cases':7,'checks':checks,'passed':all(checks.values()),
                'model_load_sec':load,'generation_sec_by_case':timings,**meter.stop(),'train_started':False,'tune_started':False,'holdout_opened':False,
                'artifact_config_sha256':registration['artifact_config_sha256'],'prior_failed_control_retained':True}
        (out/'synthetic-responses.json').write_text(json.dumps(responses,ensure_ascii=False,indent=2),encoding='utf-8')
        (out/'safe-summary.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)
    finally:meter.stop();server.close()
if __name__=='__main__':
    try:main()
    except Exception as error:
        r={'status':'failed','error_type':type(error).__name__,'source_locations':[{'file':Path(f.filename).name,'line':f.lineno} for f in traceback.extract_tb(error.__traceback__)],'raw_content_emitted':False}
        p=ROOT/'.private/gguf-shape-diagnostic';p.mkdir(exist_ok=True);(p/'technical-failure-safe-summary.json').write_text(json.dumps(r,indent=2));print(json.dumps(r));sys.exit(1)
