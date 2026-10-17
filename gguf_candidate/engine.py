"""Same short decision/detail hypothesis, larger official quantized VLM."""
from pathlib import Path
import json,time
from budget_candidate.engine import BudgetEngine,ROOT
from cashreview.observations import ObservationError,parse_observation
from gate_candidate.engine import gate_prompt,parse_gate
from .runtime import NativeServer,DeviceMeter

class GGUFEngine(BudgetEngine):
    def __init__(self,private,vision_batch_tokens=512):
        self.protocol=json.loads((ROOT/'config/budget-protocol.json').read_text());self.config=self.protocol['candidate']
        self.registry=json.loads((ROOT/'config/rules.json').read_text(encoding='utf-8'));self.precision='Q4_K_M+F16-projector'
        self.server=self.make_server(private,vision_batch_tokens);self.server.start();self.telemetry=[];self.gate_calls=[];self.meter=DeviceMeter()
    def make_server(self,private,vision_batch_tokens):
        return NativeServer(private,vision_batch_tokens=vision_batch_tokens)
    def close(self):self.meter.stop();self.server.close()
    def reset_resources(self):self.meter.start()
    def resource_metrics(self):return self.meter.stop()
    def observe(self,frames,max_events,token_limit,deadline):
        rules=[{k:r[k] for k in self.config['model_registry_fields']} for r in self.registry['rules'] if r['enabled']];ids={r['id'] for r in rules}
        schema={'type':'object','additionalProperties':False,'properties':{'visible_violation':{'type':'boolean'}},'required':['visible_violation']}
        text,metric=self.server.complete(frames,gate_prompt(rules),schema,32,deadline);metric['stage']='observable_gate';self.telemetry.append(metric)
        decision=parse_gate(text);self.gate_calls.append({'frames':len(frames),'visible_violation':decision})
        if not decision:return {'events':[],'limitation':'Оценена только выборка кадров.'}
        properties={'r':{'type':'string','enum':sorted(ids)},'f':{'type':'string','enum':[f'F{i}' for i in range(len(frames))]},
                    'c':{'type':'number','minimum':0,'maximum':1},'v':{'type':'boolean'},
                    'x':{'type':'string','enum':['present','absent','unknown']},'o':{'type':'string','minLength':1,'maxLength':48}}
        schema={'type':'object','additionalProperties':False,'properties':{'events':{'type':'array','maxItems':max_events,'items':{
            'type':'object','additionalProperties':False,'properties':properties,'required':list(properties)}},
            'limitation':{'type':'string','maxLength':32}},'required':['events','limitation']}
        prompt=('Review this ordered visual sequence. Report only directly visible possible violations with ALL applicability conditions met and no exclusion. '
                'The registry contains possible checks, not observed facts. Missing evidence of compliance is not a violation. '
                'No faces, identity, audio, hidden records or intent. Reject normal, ambiguous and hypothetical events. '
                'Rules: '+json.dumps(rules,ensure_ascii=False)+
                '\nReturn JSON: events array (empty if no supported event), limitation (Russian <=32 characters). '
                'Event keys: r=rule ID, f=nearest supplied frame ID, c=uncalibrated confidence 0..1, '
                'v=all conditions visible, x=exclusion present/absent/unknown, o=Russian observation <=48 characters. '
                'Only include v=true, x=absent, c>=0.8. Maximum '+str(max_events)+' events. No markdown.')
        text,metric=self.server.complete(frames,prompt,schema,token_limit,deadline);metric['stage']='bounded_detail';self.telemetry.append(metric)
        try:
            data=json.loads(text)
            if type(data) is not dict or set(data)!={'events','limitation'} or type(data['events']) is not list or len(data['events'])>max_events:raise ValueError()
            if type(data['limitation']) is not str or len(data['limitation'])>32:raise ValueError()
            normalized=[]
            for e in data['events']:
                if type(e) is not dict or set(e)!=set(properties) or e['f'] not in {f'F{i}' for i in range(len(frames))}:raise ValueError()
                if type(e['v']) is not bool or e['x'] not in ['present','absent','unknown'] or type(e['o']) is not str or not 0<len(e['o'])<=48:raise ValueError()
                normalized.append({'rule_id':e['r'],'timestamp_sec':float(frames[int(e['f'][1:])].sec),'confidence':e['c'],
                                   'all_conditions_visible':e['v'] and e['x']=='absent','observation':e['o'],'limitation':''})
        except (ValueError,TypeError,KeyError,IndexError):raise ObservationError('invalid_native_detail') from None
        return parse_observation(json.dumps({'events':normalized,'limitation':data['limitation']}),ids,frames[0].sec,frames[-1].sec)
    def analyze(self,path,job_id,private,strategy=None):
        self.gate_calls=[]
        try:
            result=super().analyze(path,job_id,private,strategy)
            p=Path(private);m=json.loads((p/'metrics.json').read_text());m.update(engine_family='native_4b_gate',gate_calls=self.gate_calls)
            (p/'metrics.json').write_text(json.dumps(m,indent=2))
            return result
        finally:self.meter.stop()
