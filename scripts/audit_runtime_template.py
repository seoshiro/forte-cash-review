"""No-generation /props and /apply-template audit, generated messages only."""
from pathlib import Path
import sys,json,time,datetime
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from cashreview.supervision import supervise,await_start_gate,ControlSummary,atomic_json,write_progress
from xclip_candidate.experimental import sha
OUT=ROOT/'.private/runtime-template-audit'
FILES=['scripts/audit_runtime_template.py','hybrid_candidate/template_audit.py','scripts/audit_qwen_metadata.py',
    'scripts/qwen_action_probe.py','config/qwen-action-probe.json','hybrid_candidate/action_controls.py',
    'gguf_candidate/runtime.py','scripts/hybrid_experiment.py','config/gguf-artifacts.json','cashreview/supervision.py','requirements-patched-lock.txt']


class RestrictedClient:
    def __init__(self,client,base):self.client=client;self.base=base;self.calls=[]
    def call(self,method,url,**kwargs):
        allowed={('GET','/health'),('GET','/props'),('POST','/apply-template')}
        path=url.removeprefix(self.base)
        if not url.startswith(self.base) or (method,path) not in allowed:raise ValueError('Non-audit HTTP request rejected')
        self.calls.append((method,path))
        return self.client.request(method,url,**kwargs)
    def get(self,url,**kwargs):return self.call('GET',url,**kwargs)
    def post(self,url,**kwargs):return self.call('POST',url,**kwargs)
    def close(self):self.client.close()


def verify(registration):
    from scripts.hybrid_experiment import native_identity
    if {name:sha(ROOT/name) for name in FILES}!=registration['code_sha256']:raise ValueError('Template audit source changed')
    if native_identity()!=registration['native_artifact_sha256']:raise ValueError('Template audit native identity changed')


def register():
    from scripts.hybrid_experiment import native_identity
    OUT.mkdir(exist_ok=True)
    if (OUT/'registration.json').exists():raise RuntimeError('No audit registration overwrite')
    record={'protocol_id':'RUNTIME-TEMPLATE-01','registered_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'code_sha256':{name:sha(ROOT/name) for name in FILES},'native_artifact_sha256':native_identity(),
        'budget_sec':180,'expected_checks':7,'generation_calls_allowed':0}
    with (OUT/'registration.json').open('x') as stream:json.dump(record,stream,indent=2)
    print(json.dumps({'registered':True,'registration_sha256':sha(OUT/'registration.json'),'model_started':False}))


def bounded_json(client,method,path,deadline,body=None):
    remaining=min(10.,deadline-time.monotonic())
    if remaining<=0:raise TimeoutError('Template audit deadline')
    tick=time.monotonic();response=client.call(method,client.base+path,timeout=remaining,**({'json':body} if body is not None else {}))
    if response.status_code!=200 or len(response.content)>128*1024:raise RuntimeError('Unexpected bounded audit response')
    result=response.json()
    if time.monotonic()-tick>=remaining:raise TimeoutError('Late template response')
    return result


def worker():
    run,deadline=await_start_gate();start=time.monotonic();server=None;completed=0;passed=0;summary={};checks={};report=None
    try:
        from gguf_candidate.runtime import NativeServer
        from scripts.qwen_action_probe import start_native
        from scripts.audit_qwen_metadata import header
        from hybrid_candidate.template_audit import cases,compile_expected,expected_prompt,compare_prompt,digest_text
        registration=json.loads((OUT/'registration.json').read_text());verify(registration)
        cfg=json.loads((ROOT/'config/qwen-action-probe.json').read_text())
        template=header(ROOT/'models/qwen3vl-4b-gguf/Qwen3VL-4B-Instruct-Q4_K_M.gguf')['metadata']['tokenizer.chat_template']
        renderer=compile_expected(template)
        server=NativeServer(run/'native',image_max_tokens=1024);server.client=RestrictedClient(server.client,server.base)
        load=start_native(server,cfg,deadline);props=bounded_json(server.client,'GET','/props',deadline)
        template_equal=isinstance(props.get('chat_template'),str) and props['chat_template']==template
        props_pass=template_equal and props.get('modalities',{}).get('vision') is True
        checks['props']={'template_source_equal_gguf':template_equal,'vision_enabled':props.get('modalities',{}).get('vision') is True,
            'template_sha256':digest_text(props['chat_template']) if isinstance(props.get('chat_template'),str) else None}
        completed+=1;passed+=int(props_pass);write_progress(run,'fixture',completed,passed,7)
        for case in cases(cfg):
            body={'messages':case['messages'],'add_generation_prompt':case['generation']}
            actual=bounded_json(server.client,'POST','/apply-template',deadline,body)
            try:
                expected=expected_prompt(renderer,case['messages'],props,case['generation'])
                check=compare_prompt(actual['prompt'],expected,case,props['media_marker'])
            except Exception as error:
                check={'all_checks_passed':False,'expected_comparison_status':'NOT_ASSESSED','technical_error_type':type(error).__name__}
            checks[case['id']]=check;completed+=1;passed+=int(check['all_checks_passed']);write_progress(run,'fixture',completed,passed,7)
        verify(registration)
        summary={'status':'completed','split':'synthetic','protocol_id':'RUNTIME-TEMPLATE-01','checks':checks,'completed':completed,'passed':passed,
            'all_render_checks_passed':passed==7,'native_load_sec':load,'generation_endpoint_calls':0,
            'http_audit_calls':len(server.client.calls),'synthetic_messages_only':True,'bank_data_or_user_notes_read':False,
            'raw_props_prompts_or_logs_emitted':False,'vision_embedding_expansion_or_action_quality_validated':False,
            'limitation':'Matching rendering does not identify capacity, numerical backend correctness or action semantics.'}
        report=ControlSummary(status='completed',completed_cases=completed,passed_cases=passed,total_cases=7)
    except Exception as error:
        summary={'status':'failed','split':'synthetic','checks':checks,'completed':completed,'technical_error_type':type(error).__name__,
            'raw_private_content_emitted':False,'generation_endpoint_calls':0}
        report=ControlSummary(status='failed',completed_cases=completed,passed_cases=passed,total_cases=7,failure='exception')
    finally:
        before=None;after=None;clean=False;requested=False
        if server:
            before=server.process.poll() if server.process else None;requested=server.process is not None and before is None
            try:server.close();after=server.process.wait(timeout=3) if server.process else None;clean=server.process is None or after is not None
            except Exception:
                summary.update(status='failed',technical_error_type='NativeCleanupError')
                report=ControlSummary(status='failed',completed_cases=completed,passed_cases=passed,total_cases=7,failure='exception')
            if before is not None:
                summary.update(status='failed',technical_error_type='NativeExitedBeforeCleanup')
                report=ControlSummary(status='failed',completed_cases=completed,passed_cases=passed,total_cases=7,failure='server_exit' if before else 'exception',server_exit_code=before)
        summary.update(native_exit_before_cleanup=before,native_exit_after_cleanup=after,native_shutdown_requested=requested,native_cleanup_complete=clean,
            elapsed_including_cleanup_sec=time.monotonic()-start)
    atomic_json(run/'render-safe-summary.json',summary);atomic_json(run/'worker-safe-summary.json',report.model_dump())
    if report.status!='completed':raise SystemExit(1)


if __name__=='__main__':
    try:
        action=sys.argv[1]
        if action=='register':register()
        elif action=='worker':worker()
        elif action=='run':
            report=supervise([sys.executable,str(Path(__file__).resolve()),'worker'],OUT/'run',180,7,str(ROOT))
            print(json.dumps({'technical_monitor':report}))
            if report['status']=='completed':
                summary=json.loads((OUT/'run/render-safe-summary.json').read_text());summary['technical_monitor_validated']=True
                atomic_json(OUT/'safe-summary.json',summary);print(json.dumps(summary))
            else:raise SystemExit(1)
        else:raise ValueError('Unknown audit action')
    except Exception as error:print(json.dumps({'status':'not_started_or_failed','technical_error_type':type(error).__name__,'raw_private_content_emitted':False}));sys.exit(1)
