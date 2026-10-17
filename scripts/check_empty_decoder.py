"""Exercise actual candidate output grammar/tokenizer with fake CPU generation.

No model weights, bank media or CUDA context. This proves an empty answer is
available to the decoder; it does not prove the model chooses it correctly.
"""
from pathlib import Path
from types import SimpleNamespace
import os,sys,json,time
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1')
import torch
from transformers import AutoTokenizer
from budget_candidate.engine import BudgetEngine
from cashreview.structured import tokenizer_data
from cashreview.video import Sample
from PIL import Image
tokenizer=AutoTokenizer.from_pretrained(str(ROOT/'models/qwen3-vl-2b'),local_files_only=True)
data=tokenizer_data(tokenizer)
prompt=tokenizer.encode('synthetic contract check',add_special_tokens=False)
answer=tokenizer.encode('{"events":[],"limitation":""}',add_special_tokens=False)
model_eos=json.loads((ROOT/'models/qwen3-vl-2b/generation_config.json').read_text())['eos_token_id']
allowed_eos=model_eos if isinstance(model_eos,list) else [model_eos]
class Inputs(dict):
    @property
    def input_ids(self):return self['input_ids']
    def to(self,device):return self # Deliberate fake CPU-only input transport.
checks={'empty_json_tokens_allowed':True,'eos_after_empty_allowed':False}
def fake_generate(**kwargs):
    sequence=list(prompt)
    for token in answer:
        allowed=kwargs['prefix_allowed_tokens_fn'](0,torch.tensor(sequence,dtype=torch.long))
        if token not in allowed:checks['empty_json_tokens_allowed']=False;raise RuntimeError('Empty JSON token was forbidden')
        sequence.append(token)
    allowed=kwargs['prefix_allowed_tokens_fn'](0,torch.tensor(sequence,dtype=torch.long))
    checks['eos_after_empty_allowed']=any(token in allowed for token in allowed_eos)
    return torch.tensor([sequence+[tokenizer.eos_token_id]],dtype=torch.long)
engine=object.__new__(BudgetEngine)
engine.protocol=json.loads((ROOT/'config/budget-protocol.json').read_text());engine.config=engine.protocol['candidate']
engine.registry=json.loads((ROOT/'config/rules.json').read_text(encoding='utf-8'))
engine.tokenizer_data=data;engine.telemetry=[]
engine.torch=SimpleNamespace(inference_mode=torch.inference_mode,cuda=SimpleNamespace(
    memory_allocated=lambda:0,memory_reserved=lambda:0,empty_cache=lambda:None))
engine.processor=SimpleNamespace(apply_chat_template=lambda *args,**kwargs:Inputs(input_ids=torch.tensor([prompt],dtype=torch.long)),batch_decode=tokenizer.batch_decode)
engine.model=SimpleNamespace(generate=fake_generate)
observation=engine.observe([Sample(float(i),Image.new('RGB',(64,64),'green')) for i in range(2)],engine.config['max_events_coarse'],engine.config['max_new_tokens_coarse'],time.monotonic()+60)
checks['empty_observation_preserved']=observation['events']==[]
rule=next(r['id'] for r in engine.registry['rules'] if r['enabled'])
for exclusion in ['present','unknown','absent']:
    payload={'events':[{'r':rule,'f':'F1','c':.9,'v':True,'x':exclusion,'o':'Synthetic observation'}],'limitation':''}
    answer=tokenizer.encode(json.dumps(payload,separators=(',',':')),add_special_tokens=False)
    observation=engine.observe([Sample(float(i),Image.new('RGB',(64,64),'green')) for i in range(2)],2,192,time.monotonic()+60)
    checks['exclusion_'+exclusion+'_handled']=observation['events'][0]['all_conditions_visible']==(exclusion=='absent')
report={'backend':'fake CPU generation through actual candidate observe/LMFE/tokenizer',
        'checks':checks,'tokenizer_eos':tokenizer.eos_token_id,'model_eos':model_eos,
        'cuda_initialized':torch.cuda.is_initialized(),'model_weights_loaded':False,
        'real_data_read':False,'model_quality_tested':False,'status':'PASS' if all(checks.values()) and not torch.cuda.is_initialized() else 'FAIL'}
(ROOT/'.private/empty-decoder-safe-summary.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report))
raise SystemExit(report['status']!='PASS')
