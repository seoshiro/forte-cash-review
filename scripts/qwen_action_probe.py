"""Fresh synthetic-only discriminating probe; no raw model text or logs saved."""
from pathlib import Path
from io import BytesIO
import sys,os,time,json,base64,subprocess,datetime
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from cashreview.supervision import supervise,await_start_gate,ControlSummary,atomic_json,write_progress
from xclip_candidate.experimental import sha
OUT=ROOT/'.private/qwen-action-probe'
FILES=['config/qwen-action-probe.json','hybrid_candidate/action_controls.py','scripts/qwen_action_probe.py',
    'gguf_candidate/runtime.py','scripts/hybrid_experiment.py','config/gguf-artifacts.json','cashreview/supervision.py','requirements-patched-lock.txt']


def verify(registration):
    from scripts.hybrid_experiment import native_identity
    if {name:sha(ROOT/name) for name in FILES}!=registration['code_sha256']:raise ValueError('Probe source changed')
    if native_identity()!=registration['native_artifact_sha256']:raise ValueError('Native artifact changed')


def register():
    from scripts.hybrid_experiment import native_identity
    OUT.mkdir(exist_ok=True)
    if (OUT/'registration.json').exists():raise RuntimeError('No probe registration overwrite')
    record={'protocol_id':'QWEN-ACTION-CONTROL-01','registered_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'code_sha256':{name:sha(ROOT/name) for name in FILES},'native_artifact_sha256':native_identity(),
        'bank_media_or_private_responses_read':False}
    with (OUT/'registration.json').open('x') as stream:json.dump(record,stream,indent=2)
    print(json.dumps({'registered':True,'registration_sha256':sha(OUT/'registration.json'),'model_started':False}))


def start_native(server,cfg,deadline):
    c=cfg['inference']
    args=[str(server.exe),'--offline','--model',str(server.models['text']),'--mmproj',str(server.models['projector']),
        '--device','CUDA0','--mmproj-device','CUDA0','--gpu-layers','all','--fit','off','--ctx-size',str(c['ctx_size']),
        '--parallel','1','--threads','4','--batch-size','512','--ubatch-size','128',
        '--image-min-tokens',str(c['image_min_tokens']),'--image-max-tokens',str(c['image_max_tokens']),
        '--mtmd-batch-max-tokens','512','--host','127.0.0.1','--port',str(server.port),'--no-webui','--no-agent','--no-ui-mcp-proxy',
        '--cors-origins','http://127.0.0.1','--no-cors-credentials','--api-key','temporary-local-native-test-only','--log-disable']
    env={k:v for k,v in os.environ.items() if not k.startswith(('LLAMA_','MTMD_','HF_')) and k not in ['CASH_API_KEY','OPENAI_API_KEY','ANTHROPIC_API_KEY']}
    env['PATH']=str(server.exe.parent)+os.pathsep+env.get('PATH','');tick=time.monotonic()
    server.process=subprocess.Popen(args,cwd=server.exe.parent,env=env,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
    limit=min(deadline,tick+cfg['budget']['startup_sec'])
    while time.monotonic()<limit:
        if server.process.poll() is not None:raise RuntimeError('Native startup exited')
        try:
            if server.client.get(server.base+'/health',timeout=min(1.,max(.001,limit-time.monotonic()))).status_code==200:
                if time.monotonic()>=limit:raise TimeoutError('Late native readiness')
                return time.monotonic()-tick
        except Exception:pass
        time.sleep(.1)
    raise TimeoutError('Bounded native readiness failed')


def request(server,images,prompt,constrained,cfg,deadline):
    from hybrid_candidate.action_controls import schema,parse
    content=[]
    for index,image in enumerate(images):
        buffer=BytesIO();image.save(buffer,'JPEG',quality=cfg['inference']['jpeg_quality'])
        content.extend([{'type':'text','text':'F'+str(index)+':'},{'type':'image_url','image_url':{'url':'data:image/jpeg;base64,'+base64.b64encode(buffer.getvalue()).decode('ascii')}}])
    content.append({'type':'text','text':prompt});c=cfg['inference']
    body={'messages':[{'role':'user','content':content}],'temperature':c['temperature'],'seed':c['seed'],'max_tokens':c['max_tokens'],
        'cache_prompt':False,'stream':False,'n':1}
    if constrained:body['response_format']={'type':'json_schema','json_schema':{'schema':schema()}}
    remaining=min(c['per_request_sec'],deadline-time.monotonic())
    if remaining<=0:raise TimeoutError('Probe deadline')
    tick=time.monotonic();call_deadline=tick+remaining
    response=server.client.post(server.base+'/v1/chat/completions',json=body,timeout=remaining)
    if response.status_code!=200:raise RuntimeError('Native inference HTTP failure')
    value=response.json();choice=value['choices'][0];action=parse(choice.get('message',{}).get('content'));usage=value.get('usage',{})
    if time.monotonic()>=call_deadline:raise TimeoutError('Late native response')
    return action,choice.get('finish_reason'),{'input_tokens':usage.get('prompt_tokens'),'output_tokens':usage.get('completion_tokens'),'sec':time.monotonic()-tick}


def worker():
    run,deadline=await_start_gate();start=time.monotonic();server=None;completed=0;passed=0;report=None;cells={};summary={}
    try:
        from gguf_candidate.runtime import NativeServer
        from hybrid_candidate.action_controls import frames,montage,short_prompt,long_prompt,text_positions
        cfg=json.loads((ROOT/'config/qwen-action-probe.json').read_text());registration=json.loads((OUT/'registration.json').read_text());verify(registration)
        for cell in cfg['cells']:cells[cell]={'completed':0,'correct':0,'valid_json':0,'unknown':0,'truncated':0,'transport_errors':0,'stop_finish':0,'other_finish':0,'input_tokens':[],'output_tokens':[],'latency_sec':[]}
        server=NativeServer(run/'native',image_max_tokens=cfg['inference']['image_max_tokens']);load=start_native(server,cfg,deadline)
        for expected in cfg['cases']:
            images=frames(expected,cfg)
            for cell in cfg['cells']:
                if time.monotonic()>=deadline:raise TimeoutError('Probe total deadline')
                row=cells[cell];is_text=cell.startswith(('T_','TC_'));use_montage=cell.startswith('PC_')
                supplied=[] if is_text else [montage(images)] if use_montage else images
                prompt=text_positions(expected,cfg) if is_text else long_prompt() if cell.startswith('LC_') else short_prompt()
                try:
                    action,finish,technical=request(server,supplied,prompt,not cell.endswith('_plain'),cfg,deadline)
                    row['valid_json']+=int(action is not None);row['correct']+=int(action==expected and finish=='stop');row['unknown']+=int(action=='unknown')
                    row['truncated']+=int(finish=='length');row['stop_finish']+=int(finish=='stop');row['other_finish']+=int(finish not in ['length','stop'])
                    for name in ['input_tokens','output_tokens']:
                        if type(technical[name]) is int:row[name].append(technical[name])
                    row['latency_sec'].append(technical['sec']);passed+=int(action==expected and finish=='stop')
                except Exception:
                    row['transport_errors']+=1
                    if server.process.poll() is not None:raise RuntimeError('Native exited during probe')
                row['completed']+=1;completed+=1
                atomic_json(run/'cells-safe-summary.json',{'split':'synthetic','cells':cells,'raw_responses_or_logs_saved':False})
                write_progress(run,'synthetic_visual',completed,passed,18)
        verify(registration)
        summary={'status':'completed','split':'synthetic','protocol_id':cfg['protocol_id'],'cells':cells,'completed':completed,'exact_correct_total':passed,
            'native_load_sec':load,'elapsed_sec':time.monotonic()-start,'bank_media_or_private_responses_read':False,
            'raw_responses_or_logs_saved':False,'dataset_quality_claim':False,'not_identified':cfg['not_identified']}
        report=ControlSummary(status='completed',completed_cases=completed,passed_cases=passed,total_cases=18)
    except Exception as error:
        summary={'status':'failed','split':'synthetic','completed':completed,'cells':cells,
            'technical_error_type':type(error).__name__,'raw_private_content_emitted':False}
        report=ControlSummary(status='failed',completed_cases=completed,passed_cases=passed,total_cases=18,failure='exception')
    finally:
        before=None;after=None;requested=False;clean=False
        if server:
            before=server.process.poll() if server.process else None;requested=server.process is not None and before is None
            try:
                server.close()
                after=server.process.wait(timeout=3) if server.process else None;clean=server.process is None or after is not None
            except Exception:
                report=ControlSummary(status='failed',completed_cases=completed,passed_cases=passed,total_cases=18,failure='exception')
                summary.update(status='failed',technical_error_type='NativeCleanupError')
            if before is not None:
                report=ControlSummary(status='failed',completed_cases=completed,passed_cases=passed,total_cases=18,
                    failure='server_exit' if before else 'exception',server_exit_code=before)
                summary.update(status='failed',technical_error_type='NativeExitedBeforeRequestedShutdown')
        summary.update(native_exit_before_cleanup=before,native_exit_after_cleanup=after,native_shutdown_requested=requested,native_cleanup_complete=clean,
            elapsed_including_native_cleanup_sec=time.monotonic()-start)
    atomic_json(run/'probe-safe-summary.json',summary)
    atomic_json(run/'worker-safe-summary.json',report.model_dump())
    if report.status!='completed':raise SystemExit(1)


if __name__=='__main__':
    try:
        action=sys.argv[1]
        if action=='register':register()
        elif action=='worker':worker()
        elif action=='run':
            cfg=json.loads((ROOT/'config/qwen-action-probe.json').read_text())
            report=supervise([sys.executable,str(Path(__file__).resolve()),'worker'],OUT/'run',cfg['budget']['wall_sec'],18,str(ROOT))
            print(json.dumps({'technical_monitor':report}),flush=True)
            # Control correctness is separate from technical completion.
            if report['status']=='completed':
                summary=json.loads((OUT/'run/probe-safe-summary.json').read_text());summary['technical_monitor_validated']=True
                atomic_json(OUT/'safe-summary.json',summary);print(json.dumps(summary),flush=True)
            else:raise SystemExit(1)
        else:raise ValueError('Unknown probe action')
    except Exception as error:print(json.dumps({'status':'not_started_or_failed','technical_error_type':type(error).__name__,'raw_private_content_emitted':False}));sys.exit(1)
