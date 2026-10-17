"""Exactly18 preregistered text-only calls. No rendering audit or raw persistence."""
from pathlib import Path
import sys,json,time,datetime,hashlib
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from cashreview.supervision import supervise,await_start_gate,ControlSummary,atomic_json,write_progress
from xclip_candidate.experimental import sha
from scripts.qwen_text_discrimination import bounded_json,SyntheticClient
OUT=ROOT/'.private/qwen-decomposition'
FILES=['config/qwen-decomposition-protocol.json','hybrid_candidate/decomposition.py','scripts/qwen_decomposition.py','tests/test_decomposition.py',
    'hybrid_candidate/discrimination.py','scripts/qwen_text_discrimination.py','hybrid_candidate/action_controls.py',
    'scripts/qwen_action_probe.py','gguf_candidate/runtime.py','scripts/hybrid_experiment.py',
    'config/gguf-artifacts.json','cashreview/supervision.py','requirements-patched-lock.txt']


def expected_digest(cfg):
    from hybrid_candidate.decomposition import expected
    values=[expected(action,case,cfg) for action in cfg['actions'] for case in cfg['cells']]
    return hashlib.sha256(json.dumps(values,sort_keys=True,separators=(',',':')).encode('ascii')).hexdigest()


def verify(record):
    from scripts.hybrid_experiment import native_identity
    if {name:sha(ROOT/name) for name in FILES}!=record['code_sha256']:raise ValueError('Decomposition source changed')
    if native_identity()!=record['native_artifact_sha256']:raise ValueError('Native identity changed')
    if expected_digest(json.loads((ROOT/FILES[0]).read_text()))!=record['expected_answer_sha256']:raise ValueError('Independent expected answers changed')


def register():
    from scripts.hybrid_experiment import native_identity
    cfg=json.loads((ROOT/FILES[0]).read_text());OUT.mkdir(exist_ok=True)
    if len(cfg['actions'])*len(cfg['cells'])!=18:raise ValueError('Frozen count mismatch')
    record={'protocol_id':cfg['protocol_id'],'registered_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'code_sha256':{name:sha(ROOT/name) for name in FILES},'native_artifact_sha256':native_identity(),
        'expected_answer_sha256':expected_digest(cfg),'calls_allowed':18,'wall_cap_sec':240,'runs_allowed':1}
    with (OUT/'registration.json').open('x') as stream:json.dump(record,stream,indent=2)
    print(json.dumps({'registered':True,'registration_sha256':sha(OUT/'registration.json'),'expected_answer_sha256':record['expected_answer_sha256'],'model_started':False}))


class TextOnlyClient(SyntheticClient):
    def request(self,method,path,**kwargs):
        if (method,path) not in {('GET','/health'),('POST','/v1/chat/completions')}:raise ValueError('Non-text-control endpoint rejected')
        if path=='/v1/chat/completions' and self.generation_calls>=18:raise ValueError('Frozen18-call limit')
        return super().request(method,path,**kwargs)


def record_cell():
    return {'attempted':0,'completed':0,'correct':0,'valid_format':0,'stop':0,'truncated':0,'technical_errors':0,
        'field_correct':0,'fact_invalid_format':0,'field_correct_by_name':{'first_inside':0,'last_inside':0,'all_inside':0},
        'fact_histogram':{format(i,'03b'):0 for i in range(8)},'label_histogram':{'ALPHA':0,'BETA':0,'GAMMA':0,'INVALID':0},
        'confusion_rows_exit_enter_stay_cols_exit_enter_stay_invalid':[[0]*4 for _ in range(3)],
        'input_tokens_sum':0,'output_tokens_sum':0,'usage_missing':0,'latency_sec_sum':0.,'latency_sec_max':0.}


def execute(server,action,case,cfg,deadline,row,prompt_hashes):
    from hybrid_candidate.decomposition import body,score
    from hybrid_candidate.discrimination import extract_response
    request=body(action,case,cfg);row['attempted']+=1;tick=time.monotonic()
    stop=min(deadline,tick+cfg['inference']['per_request_sec'])
    prompt_hashes.add(hashlib.sha256(json.dumps(request['messages'],sort_keys=True).encode('utf-8')).hexdigest())
    value=bounded_json(server,'POST','/v1/chat/completions',stop,request)
    text,finish,usage=extract_response(value);result=score(text,finish,action,case,cfg)
    elapsed=time.monotonic()-tick
    if time.monotonic()>=stop:raise TimeoutError('Late parsed decomposition response')
    row['completed']+=1
    for key in ['correct','valid_format','stop','truncated','field_correct']:row[key]+=int(result[key])
    for key,match in result['field_matches'].items():row['field_correct_by_name'][key]+=match
    if case['family']=='facts':
        if result['fact_code'] is not None:row['fact_histogram'][result['fact_code']]+=1
        else:row['fact_invalid_format']+=1
    else:
        row['label_histogram'][result['label'] or 'INVALID']+=1
        row['confusion_rows_exit_enter_stay_cols_exit_enter_stay_invalid'][cfg['actions'].index(action)][cfg['actions'].index(result['semantic']) if result['semantic'] else 3]+=1
    if all(type(usage[k]) is int and usage[k]>=0 for k in usage):
        row['input_tokens_sum']+=usage['prompt_tokens'];row['output_tokens_sum']+=usage['completion_tokens']
    else:row['usage_missing']+=1
    row['latency_sec_sum']+=elapsed;row['latency_sec_max']=max(row['latency_sec_max'],elapsed)
    return result


def revoke(summary,error_type):
    summary.update(status='failed',technical_error_type=error_type,semantic_status='NOT_ASSESSED_TECHNICAL_FAILURE',compound_quality_assertion_passed=False)
    if 'cell_semantic_status' in summary:summary['cell_semantic_status']={key:'NOT_ASSESSED_TECHNICAL_FAILURE' for key in summary['cell_semantic_status']}


def worker():
    run,deadline=await_start_gate();tick=time.monotonic();server=None;meter=None;cells={};summary={};active=None
    report=ControlSummary(status='failed',completed_cases=0,passed_cases=0,total_cases=1,failure='exception')
    try:
        from gguf_candidate.runtime import NativeServer,DeviceMeter
        from scripts.qwen_action_probe import start_native
        from hybrid_candidate.discrimination import paired
        cfg=json.loads((ROOT/FILES[0]).read_text());registration=json.loads((OUT/'registration.json').read_text());verify(registration)
        cells={case['id']:record_cell() for case in cfg['cells']};results={};hashes=set()
        meter=DeviceMeter();meter.start();server=NativeServer(run/'native',image_max_tokens=1024);server.client=TextOnlyClient(server.client,server.base)
        load=start_native(server,cfg,deadline);ready=time.monotonic()
        for action_index,action in enumerate(cfg['actions']):
            order=cfg['cells'][action_index:]+cfg['cells'][:action_index]
            for case in order:
                active=case['id'];results[(active,action)]=execute(server,action,case,cfg,deadline,cells[active],hashes);active=None
                atomic_json(run/'aggregate-progress-safe-summary.json',{'split':'synthetic','cells':cells,'raw_responses_saved':False})
                write_progress(run,'synthetic_text',0,0,1)
        if time.monotonic()>=deadline:raise TimeoutError('Decomposition tail deadline')
        contrasts={'definition_order':paired(results,[('direct_d0_l0','direct_d1_l0'),('direct_d0_l1','direct_d1_l1')]),
            'allowed_list_order':paired(results,[('direct_d0_l0','direct_d0_l1'),('direct_d1_l0','direct_d1_l1')])}
        duration=time.monotonic()-ready;verify(registration)
        passed=all(row['correct']==3 and row['valid_format']==3 and row['stop']==3 for row in cells.values())
        statuses={name:'assessed_synthetic_only' if row['valid_format']==3 and row['stop']==3 else 'NOT_ASSESSED_FORMAT_OR_TRUNCATION' for name,row in cells.items()}
        summary={'split':'synthetic','status':'completed','protocol_id':cfg['protocol_id'],'cells':cells,'paired_contrasts':contrasts,
            'cell_semantic_status':statuses,'semantic_status':'assessed_synthetic_only' if all(x=='assessed_synthetic_only' for x in statuses.values()) else 'PARTIAL_FORMAT_OR_TRUNCATION',
            'compound_quality_assertion_passed':passed,'calls_completed':sum(row['completed'] for row in cells.values()),'generation_calls_attempted':server.client.generation_calls,
            'unique_request_message_hash_count':len(hashes),'native_load_sec':load,'text_phase_sec':duration,
            'raw_responses_prompts_or_logs_saved':False,'bank_notes_train_tune_holdout_or_images_read':False,
            'binding_uses_ground_truth_not_model_facts':True,'rendering_audit_repeated':False,
            'monitor_scope':'One compound assertion, not calls','server_defaults_independently_identified':False,'root_cause_or_bank_quality_established':False}
        report=ControlSummary(status='completed',completed_cases=1,passed_cases=int(passed),total_cases=1)
    except Exception as error:
        if active in cells:cells[active]['technical_errors']+=1
        summary={'split':'synthetic','cells':cells,'real_calls_completed':sum(row['completed'] for row in cells.values()),'raw_private_content_emitted':False}
        revoke(summary,type(error).__name__)
    finally:
        before=None;after=None;requested=False;clean=False
        if server:
            before=server.process.poll() if server.process else None;requested=server.process is not None and before is None
            try:server.close();after=server.process.wait(timeout=3) if server.process else None;clean=server.process is None or after is not None
            except Exception:
                revoke(summary,'NativeCleanupError');report=ControlSummary(status='failed',completed_cases=0,passed_cases=0,total_cases=1,failure='exception')
            if before is not None:
                revoke(summary,'NativeExitedBeforeCleanup');report=ControlSummary(status='failed',completed_cases=0,passed_cases=0,total_cases=1,failure='server_exit' if before else 'exception',server_exit_code=before)
        if meter:
            try:summary.update(meter.stop())
            except Exception:
                revoke(summary,'MeterCleanupError');report=ControlSummary(status='failed',completed_cases=0,passed_cases=0,total_cases=1,failure='exception')
        summary.update(native_exit_before_cleanup=before,native_exit_after_cleanup=after,native_shutdown_requested=requested,native_cleanup_complete=clean,worker_elapsed_including_cleanup_sec=time.monotonic()-tick)
    atomic_json(run/'decomposition-safe-summary.json',summary);atomic_json(run/'worker-safe-summary.json',report.model_dump())
    if report.status!='completed':raise SystemExit(1)


if __name__=='__main__':
    try:
        action=sys.argv[1]
        if action=='register':register()
        elif action=='worker':worker()
        elif action=='run':
            terminal=supervise([sys.executable,str(Path(__file__).resolve()),'worker'],OUT/'run',240,1,str(ROOT));print(json.dumps({'technical_monitor':terminal}))
            if terminal['status']=='completed':
                summary=json.loads((OUT/'run/decomposition-safe-summary.json').read_text());summary['technical_monitor_validated']=True
                atomic_json(OUT/'safe-summary.json',summary);print(json.dumps(summary))
            else:raise SystemExit(1)
        else:raise ValueError('Unknown action')
    except Exception as error:print(json.dumps({'status':'not_started_or_failed','technical_error_type':type(error).__name__,'raw_private_content_emitted':False}));sys.exit(1)
