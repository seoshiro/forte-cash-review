"""One frozen synthetic-only semantic control, conditional images, aggregate output."""
from pathlib import Path
import sys,json,time,datetime,hashlib
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from cashreview.supervision import supervise,await_start_gate,ControlSummary,atomic_json,write_progress
from xclip_candidate.experimental import sha
OUT=ROOT/'.private/qwen-text-discrimination'
FILES=['config/qwen-text-discrimination.json','hybrid_candidate/discrimination.py','scripts/qwen_text_discrimination.py',
    'hybrid_candidate/action_controls.py','hybrid_candidate/template_audit.py','hybrid_candidate/template_source.py',
    'scripts/audit_qwen_metadata.py','scripts/qwen_action_probe.py','gguf_candidate/runtime.py','scripts/hybrid_experiment.py',
    'config/gguf-artifacts.json','cashreview/supervision.py','requirements-patched-lock.txt',
    'tests/test_action_oracle_independent.py','tests/test_discrimination.py']


def verify(record):
    from scripts.hybrid_experiment import native_identity
    if {name:sha(ROOT/name) for name in FILES}!=record['code_sha256']:raise ValueError('Frozen control code changed')
    if native_identity()!=record['native_artifact_sha256']:raise ValueError('Frozen native identity changed')


def register():
    from scripts.hybrid_experiment import native_identity
    cfg=json.loads((ROOT/FILES[0]).read_text());OUT.mkdir(exist_ok=True)
    record={'protocol_id':cfg['protocol_id'],'registered_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'code_sha256':{name:sha(ROOT/name) for name in FILES},'native_artifact_sha256':native_identity(),
        'text_calls':36,'conditional_image_calls':18,'monitor_compound_assertions':1,'runs_allowed':1}
    with (OUT/'registration.json').open('x') as stream:json.dump(record,stream,indent=2)
    print(json.dumps({'registered':True,'registration_sha256':sha(OUT/'registration.json'),'model_started':False}))


class SyntheticClient:
    def __init__(self,client,base):self.client=client;self.base=base;self.generation_calls=0
    def request(self,method,path,**kwargs):
        if (method,path) not in {('GET','/health'),('GET','/props'),('POST','/apply-template'),('POST','/v1/chat/completions')}:
            raise ValueError('Non-control endpoint')
        if path=='/v1/chat/completions':
            if self.generation_calls>=54:raise ValueError('Frozen call limit')
            self.generation_calls+=1
        return self.client.request(method,self.base+path,**kwargs)
    def get(self,url,**kwargs):
        if not url.startswith(self.base):raise ValueError('Non-loopback URL')
        return self.request('GET',url.removeprefix(self.base),**kwargs)
    def close(self):self.client.close()


def bounded_json(server,method,path,deadline,body=None):
    remaining=deadline-time.monotonic()
    if remaining<=0:raise TimeoutError('Control deadline exhausted')
    response=server.client.request(method,path,timeout=remaining,**({'json':body} if body is not None else {}))
    if response.status_code!=200 or len(response.content)>128*1024:raise RuntimeError('Control HTTP response rejected')
    value=response.json()
    if not isinstance(value,dict):raise ValueError('Control response object required')
    if time.monotonic()>=deadline:raise TimeoutError('Late control response')
    return value


def cell_record():
    return {'attempted':0,'completed':0,'correct':0,'recognized_correct':0,'valid_format':0,'stop':0,'truncated':0,'technical_errors':0,
        'input_render_verified':0,'token_histogram':{'ALPHA':0,'BETA':0,'GAMMA':0,'INVALID':0},
        'confusion_rows_exit_enter_stay_cols_exit_enter_stay_invalid':[[0]*4 for _ in range(3)],
        'input_tokens_sum':0,'output_tokens_sum':0,'usage_missing':0,'latency_sec_sum':0.,'latency_sec_max':0.}


def mark_technical_failure(summary,error_type):
    summary.update(status='failed',technical_error_type=error_type,semantic_assertion='NOT_ASSESSED',
        compound_quality_assertion_passed=False,text_gate_passed=None,image_gate_passed=None,
        text_semantics_status='NOT_ASSESSED_TECHNICAL_FAILURE',image_semantics_status='NOT_ASSESSED_TECHNICAL_FAILURE')


def execute(server,case,action,cfg,phase_deadline,renderer,props,row,prompt_hashes):
    from hybrid_candidate.discrimination import request_body,score,extract_response,assert_input_present
    from hybrid_candidate.template_audit import expected_prompt,digest_text
    row['attempted']+=1;tick=time.monotonic()
    cap=cfg['inference']['image_request_sec' if case['family']=='images' else 'text_request_sec']
    deadline=min(phase_deadline,tick+cap);body=request_body(action,case,cfg)
    actual=bounded_json(server,'POST','/apply-template',deadline,{'messages':body['messages'],'add_generation_prompt':True})
    expected=expected_prompt(renderer,body['messages'],props,True)
    if actual.get('prompt')!=expected:raise ValueError('Input rendering mismatch')
    assert_input_present(actual['prompt'],body['messages'],props['media_marker'])
    row['input_render_verified']+=1;prompt_hashes.add(digest_text(expected))
    raw=bounded_json(server,'POST','/v1/chat/completions',deadline,body)
    text,finish,usage=extract_response(raw);result=score(text,finish,action,case,cfg)
    elapsed=time.monotonic()-tick
    if time.monotonic()>=deadline:raise TimeoutError('Late parsed control response')
    # Only fixed aggregates survive this function; raw is not logged or saved.
    for key in ['correct','recognized_correct','valid_format','stop','truncated']:row[key]+=int(result[key])
    row['completed']+=1;row['token_histogram'][result['label'] or 'INVALID']+=1
    row['confusion_rows_exit_enter_stay_cols_exit_enter_stay_invalid'][cfg['actions'].index(action)][cfg['actions'].index(result['semantic']) if result['semantic'] else 3]+=1
    if all(type(usage[k]) is int and usage[k]>=0 for k in usage):
        row['input_tokens_sum']+=usage['prompt_tokens'];row['output_tokens_sum']+=usage['completion_tokens']
    else:row['usage_missing']+=1
    row['latency_sec_sum']+=elapsed;row['latency_sec_max']=max(row['latency_sec_max'],elapsed)
    return result


def worker():
    run,deadline=await_start_gate();tick=time.monotonic();server=None;meter=None;summary={};cells={};results={};phase='setup';active=None
    report=ControlSummary(status='failed',completed_cases=0,passed_cases=0,total_cases=1,failure='exception')
    try:
        from gguf_candidate.runtime import NativeServer,DeviceMeter
        from scripts.qwen_action_probe import start_native
        from scripts.audit_qwen_metadata import header
        from hybrid_candidate.template_audit import compile_expected
        from hybrid_candidate.template_source import lexer_source
        from hybrid_candidate.discrimination import image_cells,paired
        cfg=json.loads((ROOT/FILES[0]).read_text());registration=json.loads((OUT/'registration.json').read_text());verify(registration)
        if len(cfg['text_cells'])*len(cfg['actions'])!=36:raise ValueError('Frozen text count')
        meter=DeviceMeter();meter.start();server=NativeServer(run/'native',image_max_tokens=1024)
        server.client=SyntheticClient(server.client,server.base)
        load=start_native(server,cfg,deadline);ready=time.monotonic()
        props=bounded_json(server,'GET','/props',min(deadline,ready+8))
        template=header(ROOT/'models/qwen3vl-4b-gguf/Qwen3VL-4B-Instruct-Q4_K_M.gguf')['metadata']['tokenizer.chat_template']
        if props.get('chat_template')!=lexer_source(template) or props.get('modalities',{}).get('vision') is not True:raise ValueError('Unexpected native template or modality')
        renderer=compile_expected(template);phase='text';text_deadline=min(deadline,ready+cfg['budget']['text_phase_sec_from_ready']);hashes=set()
        cells={case['id']:cell_record() for case in cfg['text_cells']}
        for action_index,action in enumerate(cfg['actions']):
            # A fixed cyclic cell order prevents one mode always following another.
            order=cfg['text_cells'][action_index:]+cfg['text_cells'][:action_index]
            for case in order:
                active=case['id'];results[(active,action)]=execute(server,case,action,cfg,text_deadline,renderer,props,cells[active],hashes)
                active=None
                atomic_json(run/'aggregate-progress-safe-summary.json',{'split':'synthetic','phase':phase,'cells':cells,'raw_responses_saved':False})
                write_progress(run,'synthetic_text',0,0,1)
        text_elapsed=time.monotonic()-ready
        text_pass=all(row['correct']==3 and row['valid_format']==3 and row['stop']==3 for row in cells.values())
        truncated=sum(row['truncated'] for row in cells.values())
        contrasts={'schema':paired(results,[('read_json','read_schema'),('geom0_json','geom0_schema'),('geom1_json','geom1_schema')]),
            'enum_order':paired(results,[('geom0_schema','geom0_schema_rotated')]),
            'prompt_order':paired(results,[('geom0_bare','geom0_bare_reordered'),('geom0_json','geom0_json_reordered')]),
            'label_mapping':paired(results,[('geom0_'+mode,'geom1_'+mode) for mode in ['bare','json','schema']])}
        if time.monotonic()>=text_deadline:raise TimeoutError('Text phase tail deadline')
        image_run=False;image_pass=None;image_count=0;image_elapsed=None;phase='images_not_run_due_to_text_gate'
        if text_pass:
            if time.monotonic()>=text_deadline:raise TimeoutError('Text gate transition deadline')
            image_run=True;phase='images';image_tick=time.monotonic();image_deadline=min(deadline,image_tick+cfg['budget']['image_phase_sec_from_text_gate'])
            visual=image_cells(cfg)
            for case in visual:cells[case['id']]=cell_record()
            for action in cfg['actions']:
                for case in visual:
                    active=case['id'];execute(server,case,action,cfg,image_deadline,renderer,props,cells[active],hashes);image_count+=1
                    active=None
                    atomic_json(run/'aggregate-progress-safe-summary.json',{'split':'synthetic','phase':phase,'cells':cells,'raw_responses_saved':False})
                    write_progress(run,'synthetic_visual',0,0,1)
            if time.monotonic()>=image_deadline:raise TimeoutError('Image phase tail deadline')
            image_pass=all(cells[case['id']]['correct']==3 and cells[case['id']]['valid_format']==3 and cells[case['id']]['stop']==3 for case in visual)
            image_elapsed=time.monotonic()-image_tick
            if time.monotonic()>=image_deadline:raise TimeoutError('Image gate tail deadline')
        verify(registration)
        compound=text_pass and image_pass is True
        image_truncated=sum(row['truncated'] for name,row in cells.items() if name.startswith('image'))
        summary={'split':'synthetic','status':'completed','protocol_id':cfg['protocol_id'],'cells':cells,'paired_contrasts':contrasts,
            'text_calls_completed':36,'text_calls_correct':sum(cells[c['id']]['correct'] for c in cfg['text_cells']),
            'text_gate_passed':text_pass,'text_semantics_status':'NOT_ASSESSED_TRUNCATION' if truncated else 'assessed_synthetic_only',
            'image_calls_completed':image_count,'images_run':image_run,'image_gate_passed':image_pass,
            'image_semantics_status':('NOT_ASSESSED_TRUNCATION' if image_truncated else 'assessed_synthetic_only') if image_run else 'NOT_RUN_TEXT_GATE',
            'images_not_run_due_to_text_gate':not image_run,'compound_quality_assertion_passed':compound,
            'unique_rendered_prompt_hash_count':len(hashes),'generation_calls_attempted':server.client.generation_calls,
            'native_load_sec':load,'text_phase_sec':text_elapsed,'image_phase_sec':image_elapsed,
            'monitor_counts_scope':'One compound assertion, not calls. Calls are the sum of cells.completed.',
            'raw_responses_or_prompts_or_logs_saved':False,'bank_notes_train_tune_holdout_read':False,
            'cause_capacity_or_bank_quality_identified':False}
        report=ControlSummary(status='completed',completed_cases=1,passed_cases=int(compound),total_cases=1)
    except Exception as error:
        if active in cells:cells[active]['technical_errors']+=1
        summary={'split':'synthetic','status':'failed','phase':phase,'cells':cells,'semantic_assertion':'NOT_ASSESSED',
            'technical_error_type':type(error).__name__,'raw_private_content_emitted':False,
            'real_calls_completed':sum(row['completed'] for row in cells.values()),'bank_notes_train_tune_holdout_read':False}
        mark_technical_failure(summary,type(error).__name__)
    finally:
        before=None;after=None;requested=False;clean=False
        if server:
            before=server.process.poll() if server.process else None;requested=server.process is not None and before is None
            try:server.close();after=server.process.wait(timeout=3) if server.process else None;clean=server.process is None or after is not None
            except Exception:
                mark_technical_failure(summary,'NativeCleanupError')
                report=ControlSummary(status='failed',completed_cases=0,passed_cases=0,total_cases=1,failure='exception')
            if before is not None:
                mark_technical_failure(summary,'NativeExitedBeforeCleanup')
                report=ControlSummary(status='failed',completed_cases=0,passed_cases=0,total_cases=1,failure='server_exit' if before else 'exception',server_exit_code=before)
        if meter:
            try:summary.update(meter.stop())
            except Exception:
                mark_technical_failure(summary,'MeterCleanupError')
                report=ControlSummary(status='failed',completed_cases=0,passed_cases=0,total_cases=1,failure='exception')
        summary.update(native_exit_before_cleanup=before,native_exit_after_cleanup=after,native_shutdown_requested=requested,native_cleanup_complete=clean,
            worker_elapsed_including_cleanup_sec=time.monotonic()-tick)
    atomic_json(run/'discrimination-safe-summary.json',summary);atomic_json(run/'worker-safe-summary.json',report.model_dump())
    if report.status!='completed':raise SystemExit(1)


if __name__=='__main__':
    try:
        action=sys.argv[1]
        if action=='register':register()
        elif action=='worker':worker()
        elif action=='run':
            terminal=supervise([sys.executable,str(Path(__file__).resolve()),'worker'],OUT/'run',480,1,str(ROOT))
            print(json.dumps({'technical_monitor':terminal}))
            if terminal['status']=='completed':
                summary=json.loads((OUT/'run/discrimination-safe-summary.json').read_text());summary['technical_monitor_validated']=True
                atomic_json(OUT/'safe-summary.json',summary);print(json.dumps(summary))
            else:raise SystemExit(1)
        else:raise ValueError('Unknown action')
    except Exception as error:
        print(json.dumps({'status':'not_started_or_failed','technical_error_type':type(error).__name__,'raw_private_content_emitted':False}));sys.exit(1)
