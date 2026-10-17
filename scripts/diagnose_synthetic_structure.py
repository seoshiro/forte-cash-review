"""Schema-only local VLM diagnosis using generated blank images, never real videos.

Prints only grammar/type counters and token counts, never response text or values.
"""
from pathlib import Path
import os,sys,json,re,time
from collections import Counter
os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1')
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from cashreview.offline import deny_network
deny_network()
import cashreview.engine as module
from cashreview.observations import Observation,ObservationError
from cashreview.video import Sample
from pydantic import ValidationError
from PIL import Image

report={'input':'six generated blank images','real_data_read':False};original_parse=module.decode_observation
def diagnose(text,rule_ids,frames):
    report.update(response_chars=len(text),thinking_tag_present='<think>' in text)
    match=re.search(r'\{.*\}',text,re.S)
    if match:
        try:
            data=json.loads(match[0]);report['json_syntax_valid']=True
            try:original_parse(text,rule_ids,frames);report['schema_valid']=True
            except ValidationError as error:
                report['schema_valid']=False;counter=Counter()
                allowed={'events','limitation','rule_id','timestamp_sec','confidence','all_conditions_visible','observation'}
                for e in error.errors(include_input=False):
                    path='.'.join('*' if isinstance(x,int) else x if x in allowed else '_unknown_' for x in e['loc'])
                    counter[path+':'+e['type']]+=1
                report['schema_error_counts']=dict(counter)
        except json.JSONDecodeError as error:report.update(json_syntax_valid=False,json_error_position=error.pos)
    else:report['json_object_found']=False
    return original_parse(text,rule_ids,frames)
module.decode_observation=diagnose
engine=module.LocalEngine();generate=engine.model.generate
report['parameter_bytes_by_device']={}
for parameter in engine.model.parameters():
    key=str(parameter.device)
    report['parameter_bytes_by_device'][key]=report['parameter_bytes_by_device'].get(key,0)+parameter.numel()*parameter.element_size()
print(json.dumps({'phase':'synthetic_model_loaded'}),flush=True)
def capture(**inputs):
    ids=generate(**inputs)
    report.update(input_tokens=int(inputs['input_ids'].shape[1]),generated_tokens=int(ids.shape[1]-inputs['input_ids'].shape[1]),token_limit=engine.config['max_new_tokens'])
    return ids
engine.model.generate=capture;start=time.monotonic()
try:engine.observe([Sample(float(i),Image.new('RGB',(224,224),(25,65,40))) for i in range(6)]);report['observe_valid']=True
except ObservationError as error:report.update(observe_valid=False,rejection_code=error.code)
report['elapsed_sec']=time.monotonic()-start
(ROOT/'.private/synthetic-structure-diagnostic-safe-summary.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report))
