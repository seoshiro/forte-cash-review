"""One generated-gray format diagnostic; never reads a bank video."""
from pathlib import Path
import sys,json,time,traceback
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))

def main():
    from scripts.oracle_diagnostic import feature_prompt,parse_features
    from panel_candidate.engine import PanelEngine
    from cashreview.video import Sample
    from cashreview.offline import deny_network
    from PIL import Image
    out=ROOT/'.private/oracle-format-diagnostic';out.mkdir(exist_ok=True)
    if (out/'safe-summary.json').exists():raise RuntimeError('single_format_diagnostic_already_completed')
    cfg=json.loads((ROOT/'config/oracle-diagnostic.json').read_text());count=len(cfg['features']);engine=None
    try:
        tick=time.monotonic();engine=PanelEngine(out/'runtime');load=time.monotonic()-tick;deny_network([engine.server.port])
        frames=[Sample(float(i),Image.new('RGB',(384,384),(127,127,127))) for i in range(4)]
        schema={'type':'object','additionalProperties':False,'properties':{'signals':{'type':'array','minItems':count,'maxItems':count,'items':{'type':'string','enum':cfg['feature_answers']}}},'required':['signals']}
        text,metric=engine.server.complete(frames,feature_prompt(cfg['features']),schema,cfg['feature_max_tokens'],time.monotonic()+cfg['max_request_sec'])
        (out/'generated-gray.response.private.txt').write_text(text,encoding='utf-8')
        data=None
        try:data=json.loads(text)
        except ValueError:pass
        parsed=False
        try:parse_features(text,count);parsed=True
        except ValueError:pass
        signals=data.get('signals') if isinstance(data,dict) else None
        report={'bank_data_read':False,'same_questions_schema_and_token_budget':True,'model_load_sec':load,**metric,'decoded_chars':len(text),
                'json_parse_ok':data is not None,'top_level_is_object':type(data) is dict,'expected_single_key':type(data) is dict and set(data)=={'signals'},
                'signals_is_array':type(signals) is list,'signals_count':len(signals) if isinstance(signals,list) else None,
                'all_answers_in_fixed_enum':isinstance(signals,list) and all(type(v) is str and v in cfg['feature_answers'] for v in signals),'strict_parse_passed':parsed,
                'token_limit_reached':metric['generated_tokens']==cfg['feature_max_tokens'],'raw_response_emitted':False}
        (out/'safe-summary.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
    finally:
        if engine:engine.close()
if __name__=='__main__':
    try:main()
    except Exception as error:
        print(json.dumps({'status':'failed','error_type':type(error).__name__,'source_locations':[{'file':Path(f.filename).name,'line':f.lineno} for f in traceback.extract_tb(error.__traceback__)],'raw_response_emitted':False}));sys.exit(1)
