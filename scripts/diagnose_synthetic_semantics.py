"""One local model process; generated blank images only, no dataset reads.

Compare the same eight synthetic inputs with free text, binary decisions and
the frozen domain observation request. Never use this as a quality evaluation.
"""
from pathlib import Path
import hashlib,json,os,sys,time,traceback
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))

def ensure_idle():
    import psutil
    own_lineage={os.getpid(),*[p.pid for p in psutil.Process().parents()]}
    names={'qa_model_api.py','benchmark_budget.py','evaluate.py','evaluate_gate.py','profile_baseline_stages.py','diagnose_synthetic_semantics.py'}
    for p in psutil.process_iter():
        try:
            if p.pid not in own_lineage and Path(p.cwd()).resolve()==ROOT and any(Path(a).name in names for a in p.cmdline()[1:]):
                raise RuntimeError('Another owned model workload is active')
        except (psutil.Error,OSError,ValueError):pass

def main():
    os.chdir(ROOT);ensure_idle()
    os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1')
    from cashreview.offline import deny_network
    deny_network()
    from PIL import Image
    from cashreview.video import Sample
    from budget_candidate.engine import BudgetEngine
    out=ROOT/'.private/synthetic-semantics'/time.strftime('%Y%m%dT%H%M%SZ',time.gmtime());out.mkdir(parents=True)
    stage=lambda name:(out/'stage.json').write_text(json.dumps({'stage':name,'synthetic_only':True}))
    stage('model_loading');start=time.monotonic();engine=BudgetEngine('bf16');load=time.monotonic()-start
    torch=engine.torch;processor=engine.processor;tokenizer=processor.tokenizer
    image=Image.new('RGB',(384,384),(127,127,127));frames=[Sample(float(i),image.copy()) for i in range(8)]
    records={};mode='';remove_constraint=False;original_generate=engine.model.generate
    def audit_inputs(inputs):
        ids=inputs['input_ids'];cfg=engine.model.config;grid=inputs['image_grid_thw'];pixels=inputs['pixel_values']
        merge=processor.image_processor.merge_size
        text=tokenizer.decode(ids[0],skip_special_tokens=False)
        return {'batch_size':int(ids.shape[0]),'input_tokens':int(ids.shape[1]),
                'vision_start_count':int((ids==cfg.vision_start_token_id).sum()),
                'vision_end_count':int((ids==cfg.vision_end_token_id).sum()),
                'image_token_count':int((ids==cfg.image_token_id).sum()),
                'video_token_count':int((ids==cfg.video_token_id).sum()),
                'expected_image_tokens':int((grid.prod(-1)//(merge**2)).sum()),
                'image_grid_thw':grid.cpu().tolist(),'pixel_shape':list(pixels.shape),
                'pixel_dtype':str(pixels.dtype),'pixel_min':float(pixels.min()),'pixel_max':float(pixels.max()),
                'pixel_mean':float(pixels.float().mean()),'pixel_std':float(pixels.float().std()),
                'pixels_finite':bool(torch.isfinite(pixels).all()),
                'attention_mask_shape':list(inputs['attention_mask'].shape),
                'attention_all_one':bool((inputs['attention_mask']==1).all()),
                'assistant_generation_suffix':text.endswith('<|im_start|>assistant\n'),
                'user_message_count':text.count('<|im_start|>user\n'),
                'prior_assistant_response_count':text.count('<|im_start|>assistant\n')-1,
                'prompt_sha256':hashlib.sha256(text.encode()).hexdigest()}
    def captured_generate(**kwargs):
        before=audit_inputs(kwargs)
        if remove_constraint:kwargs.pop('prefix_allowed_tokens_fn',None)
        n=kwargs['input_ids'].shape[1];tick=time.monotonic()
        generated=original_generate(**kwargs)
        suffix=generated[:,n:];text=processor.batch_decode(suffix,skip_special_tokens=True,clean_up_tokenization_spaces=False)[0]
        records[mode]={'input_audit':before,'generated_sequences':int(generated.shape[0]),
                       'prompt_prefix_unchanged':bool(torch.equal(generated[:,:n],kwargs['input_ids'])),
                       'generated_tokens':int(suffix.shape[1]),'decode_start_index':int(n),
                       'response_contains_prompt_role_tokens':'<|im_start|>' in text,
                       'generation_sec':time.monotonic()-tick,'synthetic_response':text,
                       'constrained':bool(kwargs.get('prefix_allowed_tokens_fn'))}
        (out/(mode+'.synthetic.json')).write_text(json.dumps(records[mode],ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps({'stage':mode,'complete':True,'generation_sec':records[mode]['generation_sec'],'synthetic_only':True}),flush=True)
        return generated
    engine.model.generate=captured_generate
    def run(prompt,max_tokens,schema=None):
        from lmformatenforcer import JsonSchemaParser
        from lmformatenforcer.tokenenforcer import TokenEnforcer
        content=[]
        for i,f in enumerate(frames):content.extend([{'type':'text','text':f'F{i}: {f.sec:.6f} seconds:'},{'type':'image','image':f.image}])
        content.append({'type':'text','text':prompt})
        inputs=processor.apply_chat_template([{'role':'user','content':content}],tokenize=True,add_generation_prompt=True,return_dict=True,return_tensors='pt').to('cuda')
        kwargs={}
        if schema:
            enforcer=TokenEnforcer(engine.tokenizer_data,JsonSchemaParser(schema))
            kwargs['prefix_allowed_tokens_fn']=lambda _batch,seq:enforcer.get_allowed_tokens(seq.tolist()).allowed_tokens
        with torch.inference_mode():generated=engine.model.generate(**inputs,max_new_tokens=max_tokens,do_sample=False,max_time=90,**kwargs)
        del inputs,generated;torch.cuda.empty_cache()
    gate_only='--gate-only' in sys.argv
    if gate_only:
        mode='short_domain_gate';stage(mode)
        rules=[{k:r[k] for k in engine.config['model_registry_fields']} for r in engine.registry['rules'] if r['enabled']]
        run('Decide whether these images directly show a possible violation satisfying ALL visible conditions of any listed rule, with no applicable exclusion. '
            'The rules are possible checks, not facts. Missing compliance evidence is not evidence of a violation. If ambiguous or not visible, answer false. '
            'Do not identify faces or infer hidden records. Rules: '+json.dumps(rules,ensure_ascii=False)+
            '\nReturn only JSON with visible_violation (true or false). Do not generate events or explanations.',32,
            {'type':'object','additionalProperties':False,'properties':{'visible_violation':{'type':'boolean'}},'required':['visible_violation']})
    else:
        mode='free_description';stage(mode);run('Describe only what is visible in these images in one short sentence. Do not infer a location or activity.',64)
        mode='plain_person_yes_no';stage(mode);run('Is any person visible in these images? Answer only YES or NO.',8)
        mode='constrained_person_gate';stage(mode)
        run('Is any person visible in these images? Return JSON with person_visible set to true or false.',32,
            {'type':'object','additionalProperties':False,'properties':{'person_visible':{'type':'boolean'}},'required':['person_visible']})
        for mode,remove_constraint in [('domain_constrained',False),('domain_unconstrained',True)]:
            stage(mode)
            try:
                obs=engine.observe(frames,2,192,time.monotonic()+120)
                records[mode]['raw_events']=len(obs['events'])
                records[mode]['qualifying_events']=sum(e['all_conditions_visible'] and e['confidence']>=.8 for e in obs['events'])
                records[mode]['structure_valid']=True
            except Exception as error:
                records.setdefault(mode,{})['structure_valid']=False
                records[mode]['error_type']=type(error).__name__
    checks={}
    for name,record in records.items():
        a=record['input_audit']
        checks[name+'_input_valid']=a['batch_size']==1 and a['vision_start_count']==8 and a['vision_end_count']==8 and a['video_token_count']==0 and a['image_token_count']==a['expected_image_tokens'] and a['pixels_finite'] and a['attention_all_one'] and a['assistant_generation_suffix'] and a['user_message_count']==1 and a['prior_assistant_response_count']==0
        checks[name+'_decoding_valid']=record['prompt_prefix_unchanged'] and record['generated_sequences']==1 and not record['response_contains_prompt_role_tokens']
    if gate_only:
        try:checks['short_domain_gate_negative']=json.loads(records['short_domain_gate']['synthetic_response'])=={'visible_violation':False}
        except (ValueError,TypeError):checks['short_domain_gate_negative']=False
    else:
        checks['domain_prompt_equal']=records['domain_constrained']['input_audit']['prompt_sha256']==records['domain_unconstrained']['input_audit']['prompt_sha256']
        response=records['plain_person_yes_no']['synthetic_response'].strip().upper().rstrip('.!')
        checks['plain_person_negative']=response=='NO'
        try:checks['constrained_person_negative']=json.loads(records['constrained_person_gate']['synthetic_response'])=={'person_visible':False}
        except (ValueError,TypeError):checks['constrained_person_negative']=False
        for name in ['domain_constrained','domain_unconstrained']:checks[name+'_empty']=records[name].get('structure_valid',False) and records[name].get('raw_events')==0
    from safetensors import safe_open
    with safe_open(ROOT/'models/qwen3-vl-2b/model.safetensors',framework='pt',device='cpu') as f:weight_keys=set(f.keys())
    vision_keys=[k for k in weight_keys if 'visual.' in k]
    report={'scope':'generated uniform gray RGB images only; no media or labels read','model_load_sec':load,'runtime_torch':str(torch.__version__),
            'cases':len(records),'checks':checks,'image_count_per_case':8,'holdout_opened':False,'tune_opened':False,
            'model_class':type(engine.model).__name__,'processor_class':type(processor).__name__,
            'architectures':engine.model.config.architectures,'vision_weight_tensors':len(vision_keys),
            'total_weight_tensors':len(weight_keys),'model_technical':engine.model_technical,
            'generation_sec_by_case':{k:v['generation_sec'] for k,v in records.items()},
            'domain_event_counts':{k:{n:v.get(n) for n in ['raw_events','qualifying_events','structure_valid']} for k,v in records.items() if k.startswith('domain_')},
            'input_audit_example':next(iter(records.values()))['input_audit'],
            'interpretation':'Mechanics and synthetic sanity checks only; not real-video quality or causal proof beyond this controlled comparison.'}
    (out/'safe-summary.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    (out/'synthetic-responses.json').write_text(json.dumps({k:v['synthetic_response'] for k,v in records.items()},ensure_ascii=False,indent=2),encoding='utf-8')
    stage('complete');print(json.dumps(report),flush=True)

if __name__=='__main__':
    try:main()
    except Exception as error:
        print(json.dumps({'status':'failed','error_type':type(error).__name__,'source_locations':[{'file':Path(f.filename).name,'line':f.lineno,'function':f.name} for f in traceback.extract_tb(error.__traceback__)],'synthetic_only':True}),flush=True)
        sys.exit(1)
