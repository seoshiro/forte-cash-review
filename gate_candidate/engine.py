"""Short local decision first; bounded detail generation only for positives."""
from pathlib import Path
import json,time
from budget_candidate.engine import BudgetEngine,ROOT
from cashreview.observations import ObservationError

def gate_prompt(rules):
    # Identical decision wording/schema to the generated-gray diagnostic.
    return ('Decide whether these images directly show a possible violation satisfying ALL visible conditions of any listed rule, with no applicable exclusion. '
            'The rules are possible checks, not facts. Missing compliance evidence is not evidence of a violation. If ambiguous or not visible, answer false. '
            'Do not identify faces or infer hidden records. Rules: '+json.dumps(rules,ensure_ascii=False)+
            '\nReturn only JSON with visible_violation (true or false). Do not generate events or explanations.')

def parse_gate(text):
    try:
        value=json.loads(text)
        if type(value) is not dict or set(value)!={'visible_violation'} or type(value['visible_violation']) is not bool:raise ValueError()
        return value['visible_violation']
    except (ValueError,TypeError):raise ObservationError('invalid_observable_gate') from None

class GatedEngine(BudgetEngine):
    def __init__(self,precision='bf16'):
        super().__init__(precision)
        self.gate_protocol=json.loads((ROOT/'config/gate-protocol.json').read_text())
        self.gate_calls=[]

    def decide(self,frames,deadline):
        from lmformatenforcer import JsonSchemaParser
        from lmformatenforcer.tokenenforcer import TokenEnforcer
        rules=[{k:r[k] for k in self.config['model_registry_fields']} for r in self.registry['rules'] if r['enabled']]
        content=[]
        for i,f in enumerate(frames):content.extend([{'type':'text','text':f'F{i}: {f.sec:.6f} seconds:'},{'type':'image','image':f.image}])
        content.append({'type':'text','text':gate_prompt(rules)})
        inputs=self.processor.apply_chat_template([{'role':'user','content':content}],tokenize=True,add_generation_prompt=True,return_dict=True,return_tensors='pt').to('cuda')
        schema={'type':'object','additionalProperties':False,'properties':{'visible_violation':{'type':'boolean'}},'required':['visible_violation']}
        enforcer=TokenEnforcer(self.tokenizer_data,JsonSchemaParser(schema))
        remaining=deadline-time.monotonic()
        if remaining<=0:raise TimeoutError('Analysis budget exhausted')
        tick=time.monotonic()
        with self.torch.inference_mode():
            generated=self.model.generate(**inputs,max_new_tokens=self.gate_protocol['decision']['max_new_tokens'],do_sample=False,max_time=remaining,
                prefix_allowed_tokens_fn=lambda _batch,seq:enforcer.get_allowed_tokens(seq.tolist()).allowed_tokens)
        text=self.processor.batch_decode(generated[:,inputs.input_ids.shape[1]:],skip_special_tokens=True,clean_up_tokenization_spaces=False)[0]
        metric={'stage':'observable_gate','frames':len(frames),'input_tokens':int(inputs.input_ids.shape[1]),
                'generated_tokens':int(generated.shape[1]-inputs.input_ids.shape[1]),'generation_sec':time.monotonic()-tick}
        del inputs,generated;self.torch.cuda.empty_cache()
        self.telemetry.append(metric)
        decision=parse_gate(text)
        self.gate_calls.append({'frames':len(frames),'visible_violation':decision})
        return decision

    def observe(self,frames,max_events,token_limit,deadline):
        if not self.decide(frames,deadline):
            return {'events':[],'limitation':'Оценена только выборка кадров.'}
        return super().observe(frames,max_events,token_limit,deadline)

    def analyze(self,path,job_id,private,strategy=None):
        self.gate_calls=[]
        payload=super().analyze(path,job_id,private,strategy)
        private=Path(private)
        detail=json.loads((private/'detail.json').read_text(encoding='utf-8'))
        detail['limitations'].append('Отрицательный gate относится к просмотренным кадрам и не доказывает отсутствие события во всём видео.')
        (private/'detail.json').write_text(json.dumps(detail,ensure_ascii=False),encoding='utf-8')
        metrics=json.loads((private/'metrics.json').read_text())
        metrics.update(engine_family='two_stage_gate',gate_calls=self.gate_calls)
        (private/'metrics.json').write_text(json.dumps(metrics,indent=2))
        return payload
