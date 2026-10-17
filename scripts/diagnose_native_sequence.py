"""Fixed six-case multi-image sanity; generated colors only, no real video."""
from pathlib import Path
import sys,json,time,hashlib,traceback,psutil,argparse
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--vision-batch-tokens',type=int,choices=[512,2048],default=512);args=parser.parse_args()
    from gguf_candidate.runtime import NativeServer,DeviceMeter
    from cashreview.video import Sample
    from cashreview.offline import deny_network
    from PIL import Image,ImageDraw
    for p in psutil.process_iter():
        try:
            if p.name().lower()=='llama-server.exe' and Path(p.exe()).is_relative_to(ROOT/'.private/llama-cuda124-b11712'):raise RuntimeError('Owned native inference remains active')
        except (psutil.Error,OSError):pass
    out=ROOT/('.private/gguf-sequence-diagnostic-2048' if args.vision_batch_tokens==2048 else '.private/gguf-sequence-diagnostic');out.mkdir(exist_ok=True)
    if (out/'safe-summary.json').exists():raise RuntimeError('Fixed sequence diagnostic already completed')
    cases=[(4,None),(4,2),(8,None),(8,0),(8,4),(8,7)]
    (out/'registration.json').write_text(json.dumps({'scope':'generated color geometry only','cases':cases,
        'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'vision_batch_tokens':args.vision_batch_tokens,'bank_data_read':False,'tune_opened':False,'holdout_opened':False},indent=2))
    meter=DeviceMeter();meter.start();server=NativeServer(out/'runtime',vision_batch_tokens=args.vision_batch_tokens);tick=time.monotonic()
    try:
        server.start();load=time.monotonic()-tick;deny_network([server.port])
        gray=Image.new('RGB',(384,384),(127,127,127));red=gray.copy();ImageDraw.Draw(red).rectangle((60,120,309,219),fill=(255,0,0))
        schema={'type':'object','additionalProperties':False,'properties':{'red_region':{'type':'boolean'}},'required':['red_region']}
        checks={};timings={};input_tokens={}
        for count,position in cases:
            name=f'images_{count}_'+('gray' if position is None else f'red_position_{position}')
            frames=[Sample(float(i),red.copy() if i==position else gray.copy()) for i in range(count)]
            text,m=server.complete(frames,'Is any red region visible in any supplied image? Return JSON with red_region true or false.',schema,32,time.monotonic()+90)
            (out/(name+'.synthetic.json')).write_text(json.dumps({'synthetic_response':text},ensure_ascii=False),encoding='utf-8')
            try:checks[name]=json.loads(text)=={'red_region':position is not None}
            except (ValueError,TypeError):checks[name]=False
            timings[name]=m['generation_sec']
            input_tokens[name]=m.get('input_tokens')
        report={'scope':'synthetic sequence only; no bank-video quality result','cases':len(cases),'checks':checks,'passed':all(checks.values()),
                'model_load_sec':load,'generation_sec_by_case':timings,'input_tokens_by_case':input_tokens,'vision_batch_tokens':args.vision_batch_tokens,**meter.stop(),'bank_data_read':False,'tune_opened':False,'holdout_opened':False}
        (out/'safe-summary.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
    finally:meter.stop();server.close()
if __name__=='__main__':
    try:main()
    except Exception as error:
        r={'status':'failed','error_type':type(error).__name__,'source_locations':[{'file':Path(f.filename).name,'line':f.lineno} for f in traceback.extract_tb(error.__traceback__)],'raw_content_emitted':False}
        out=ROOT/'.private/gguf-sequence-diagnostic';out.mkdir(exist_ok=True);(out/'technical-failure-safe-summary.json').write_text(json.dumps(r,indent=2));print(json.dumps(r));sys.exit(1)
