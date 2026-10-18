"""Authorized expiring research HTTPS access. No secrets/raw logs on stdout."""
from pathlib import Path
import argparse,hashlib,json,os,re,secrets,socket,subprocess,sys,threading,time
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from cashreview.supervision import atomic_json,OwnedWindowsJob
from cashreview.technical_diagnostics import safe_exception
OUT=ROOT/'.private/research-access-live'
PORT=8769
PARTIAL_V1=False


def configure(partial):
    global OUT,PORT,PARTIAL_V1
    PARTIAL_V1=partial
    if partial:OUT=ROOT/'.private/partial-contract-access';PORT=8770


def credentials_file():
    return ROOT/'.private/research-access-live/credentials.dpapi' if PARTIAL_V1 else OUT/'credentials.dpapi'


def clean_env():
    env=os.environ.copy()
    for key in list(env):
        if key.startswith(('CASH_','TUNNEL_','CLOUDFLARE_','CF_')) or key in ['HF_TOKEN','HUGGING_FACE_HUB_TOKEN','OPENAI_API_KEY','ANTHROPIC_API_KEY','GH_TOKEN','GITHUB_TOKEN']:env.pop(key,None)
    return env


def identities(proc):
    import psutil
    return {'pid':proc.pid,'created':psutil.Process(proc.pid).create_time()}


def start():
    if OUT.exists():raise RuntimeError('Research access has an existing owned session; inspect status first')
    OUT.mkdir()
    command=[sys.executable,str(Path(__file__).resolve()),'supervisor']+(['--partial-v1'] if PARTIAL_V1 else [])
    process=subprocess.Popen(command,cwd=ROOT,env=clean_env(),
                             stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
    atomic_json(OUT/'launcher-identity.json',identities(process))
    print(json.dumps({'status':'starting','public_ready':False,'secrets_emitted':False,'new_persistent_grants':False}),flush=True)


def supervisor():
    import httpx,psutil
    from cashreview.local_secrets import save,load
    from cashreview.research_delivery import validate_credentials
    from xclip_candidate.experimental import load_prototypes,PACK_DIRECTORY
    phase='security_preflight';server=None;tunnel=None;job=None;reader=None;ready=False;url_box=[];discarded=[0]
    atomic_json(OUT/'supervisor-identity.json',{'pid':os.getpid(),'created':psutil.Process().create_time()})
    try:
        load_prototypes(ROOT/PACK_DIRECTORY)
        cfg=json.loads((ROOT/'config/cloudflared-artifact.json').read_text());binary=ROOT/'.runtime/cloudflared/cloudflared.exe'
        if hashlib.sha256(binary.read_bytes()).hexdigest()!=cfg['sha256']:raise ValueError('Pinned connector changed')
        with socket.socket() as probe:probe.bind(('127.0.0.1',PORT))
        if PARTIAL_V1:
            keys=validate_credentials(load(credentials_file()));expires=keys['expires_unix']
        else:
            expires=time.time()+7.5*3600
            keys=validate_credentials({'purpose':'research-prototype-only','primary':secrets.token_urlsafe(48),'other_owner':secrets.token_urlsafe(48),'expires_unix':expires})
            save(credentials_file(),keys)
        env=clean_env();job=OwnedWindowsJob()
        phase='protected_origin_start'
        origin_command=[sys.executable,str(ROOT/'scripts/serve_research_delivery.py'),'--credentials-file',str(credentials_file()),'--port',str(PORT)]+(['--partial-v1'] if PARTIAL_V1 else [])
        server=subprocess.Popen(origin_command,
                                cwd=ROOT,env=env,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
        job.assign(server);atomic_json(OUT/'origin-identity.json',identities(server))
        local='http://127.0.0.1:'+str(PORT);unknown='/api/experimental/xclip/jobs/'+'0'*32
        def alive():
            if time.time()>=expires or server.poll() is not None:raise RuntimeError('Research origin unavailable or expired')
        with httpx.Client(timeout=10,trust_env=False,follow_redirects=False) as client:
            until=time.monotonic()+40
            while True:
                alive()
                try:
                    response=client.get(local+'/healthz')
                    if response.status_code==200 and response.json().get('release_eligible') is False:break
                except (httpx.HTTPError,ValueError):pass
                if time.monotonic()>until:raise TimeoutError('Origin readiness')
                time.sleep(.25)
            assert client.get(local+unknown).status_code==401
            assert client.get(local+unknown,headers={'X-API-Key':'incorrect'}).status_code==401
            assert client.get(local+unknown,headers=[('X-API-Key',keys['primary']),('X-API-Key',keys['other_owner'])]).status_code==401
            assert client.get(local+unknown,headers={'X-API-Key':keys['primary']}).status_code==404
            assert client.post(local+'/api/v1/analyze',headers={'X-API-Key':keys['primary']}).status_code==(422 if PARTIAL_V1 else 503)
            if PARTIAL_V1:
                assert client.get(local+'/api/v1/jobs/'+'0'*32,headers={'X-API-Key':keys['primary']}).status_code==404
                assert client.get(local+'/healthz').json().get('semantic_contract_complete') is False
            for path in ['/.git/HEAD','/.private/credentials.dpapi','/.env','/docs','/openapi.json','/static/app.js']:
                assert client.get(local+path,headers={'X-API-Key':keys['primary']}).status_code==404
        atomic_json(OUT/'security-preflight-safe-summary.json',{'status':'PASS','local_auth_checked_before_public_forwarding':True,'duplicate_keys_rejected':True,
                    'private_and_unapproved_routes_hidden':True,'competition_api_closed503':not PARTIAL_V1,'partial_v1_enabled':PARTIAL_V1,'semantic_contract_complete':False,'baseline_artifact_verified':True,'connector_sha256_verified':True,
                    'permanent_jury_key_created':False,'ephemeral_research_keys_dpapi_protected':True,'bank_data_used':False})
        empty=OUT/'empty-cloudflared-config.json';empty.write_text('{}');no_cert=OUT/'no-account-cert.pem'
        if no_cert.exists() or no_cert.is_symlink():raise RuntimeError('Explicit no-account certificate must not exist')
        phase='quick_tunnel_start'
        command=[str(binary),'tunnel','--config',str(empty),'--no-autoupdate','--origincert',str(no_cert),'--metrics','127.0.0.1:0',
                 '--management-diagnostics=false','--loglevel','info','--label','terenoi-research-prototype','--url',local]
        tunnel=subprocess.Popen(command,cwd=OUT,env=env,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,creationflags=subprocess.CREATE_NO_WINDOW)
        job.assign(tunnel);atomic_json(OUT/'connector-identity.json',identities(tunnel))
        def consume():
            while True:
                line=tunnel.stderr.readline(16384)
                if not line:break
                discarded[0]+=1
                for value in re.findall(rb'https://[a-z0-9-]+\.trycloudflare\.com',line):
                    if not url_box:url_box.append(value.decode('ascii'))
        reader=threading.Thread(target=consume,daemon=True);reader.start();until=time.monotonic()+90
        while not url_box:
            alive()
            if tunnel.poll() is not None or time.monotonic()>until:raise RuntimeError('Quick Tunnel unavailable')
            time.sleep(.2)
        url=url_box[0];phase='public_security_checks'
        with httpx.Client(timeout=15,trust_env=False,follow_redirects=False) as client:
            until=time.monotonic()+60
            while True:
                alive()
                try:
                    response=client.get(url+'/healthz')
                    if response.status_code==200 and response.json().get('release_eligible') is False:break
                except (httpx.HTTPError,ValueError):pass
                if time.monotonic()>until:raise TimeoutError('Public health readiness')
                time.sleep(.5)
            assert client.get(url+'/').status_code==200
            for headers in [{},{'X-API-Key':'incorrect'}]:assert client.get(url+unknown,headers=headers).status_code==401
            assert client.get(url+unknown,headers={'X-API-Key':keys['primary']}).status_code==404
            assert client.post(url+'/api/v1/analyze',headers={'X-API-Key':keys['primary']}).status_code==(422 if PARTIAL_V1 else 503)
            if PARTIAL_V1:
                assert client.get(url+'/api/v1/jobs/'+'0'*32,headers={'X-API-Key':keys['primary']}).status_code==404
                assert client.get(url+'/healthz').json().get('partial_v1_enabled') is True
            for path in ['/.git/HEAD','/.private/credentials.dpapi','/.env','/openapi.json','/static/app.js']:
                assert client.get(url+path,headers={'X-API-Key':keys['primary']}).status_code==404
        atomic_json(OUT/'endpoint.json',{'url':url,'expires_unix':expires,'purpose':'partial-v1-experimental' if PARTIAL_V1 else 'research-prototype-only','active_expected':True})
        summary={'status':'READY','url':url,'expires_utc':time.strftime('%Y-%m-%d %H:%M:%S UTC',time.gmtime(expires)),
                 'local_security_preflight_passed':True,'public_health_auth_paths_passed':True,'synthetic_full_cycle_verified':False,
                 'mode':'xclip_experimental','partial_v1_enabled':PARTIAL_V1,'semantic_contract_complete':False,'release_eligible':False,'baseline_unchanged':True,'new_persistent_grants':False,
                 'permanent_jury_key_created':False,'temporary_keys_dpapi_protected':True,'secrets_or_raw_logs_emitted':False,'bank_data_used_in_checks':False,
                 'paid_resources_used':False,'os_firewall_dns_warp_or_service_changed':False}
        atomic_json(OUT/'safe-summary.json',summary);ready=True;phase='serving'
        while time.time()<expires and not (OUT/'stop.request').exists():
            alive()
            if tunnel.poll() is not None:raise RuntimeError('Owned connector exited')
            atomic_json(OUT/'availability-safe-summary.json',{'status':'running','checked_utc':time.strftime('%Y-%m-%d %H:%M:%S UTC',time.gmtime()),'origin_process_alive':True,'connector_process_alive':True,'release_eligible':False})
            time.sleep(15)
    except Exception as error:
        atomic_json(OUT/'failure-safe-summary.json',{'status':'failed','phase':phase,'diagnostic':safe_exception(error,ROOT),'secrets_or_raw_logs_emitted':False})
    finally:
        cleanup=True
        from cashreview.processes import kill_tree
        if job:
            try:job.close()
            except Exception:cleanup=False
        for proc in [tunnel,server]:
            if proc is not None:
                try:
                    if proc.poll() is None:cleanup=bool(kill_tree(proc.pid)) and cleanup
                    proc.wait(timeout=3)
                except Exception:cleanup=False
        if reader:reader.join(timeout=2)
        endpoint=OUT/'endpoint.json'
        if endpoint.exists():
            value=json.loads(endpoint.read_text());value['active_expected']=False;atomic_json(endpoint,value)
        atomic_json(OUT/'stopped-safe-summary.json',{'status':'stopped','owned_cleanup_confirmed':cleanup,'was_public_ready':ready})
        if (OUT/'safe-summary.json').exists():
            value=json.loads((OUT/'safe-summary.json').read_text());value['status']='STOPPED';atomic_json(OUT/'safe-summary.json',value)


def verify_synthetic():
    import httpx,base64
    from cashreview.local_secrets import load
    from scripts.synthetic import generate
    from xclip_candidate.experimental import BinaryResearchResult
    from cashreview.video import sample
    from io import BytesIO
    keys=load(credentials_file());endpoint=json.loads((OUT/'endpoint.json').read_text())
    if not endpoint['active_expected'] or time.time()>=keys['expires_unix']:raise RuntimeError('Research session inactive')
    fixtures=OUT/'fixtures';fixtures.mkdir(exist_ok=True);media=generate(fixtures/'safe.mov');url=endpoint['url'];headers={'X-API-Key':keys['primary']};started=time.monotonic();jpeg_checks=0
    prefix='/api/v1' if PARTIAL_V1 else '/api/experimental/xclip'
    with httpx.Client(timeout=20,trust_env=False,follow_redirects=False) as client:
        with media.open('rb') as stream:response=client.post(url+prefix+'/analyze',headers=headers,files={'file':('safe.mov',stream,'video/quicktime')})
        assert response.status_code==200;job=response.json()['job_id'];until=time.monotonic()+290
        while time.monotonic()<until:
            response=client.get(url+prefix+'/jobs/'+job,headers=headers);assert response.status_code==200;value=response.json()
            if value['status']!='processing':break
            time.sleep(.5)
        done_elapsed=time.monotonic()-started
        if PARTIAL_V1:
            from cashreview.schemas import Done
            from cashreview.partial_contract import transport_result
            result=Done.model_validate(value)
            assert response.headers.get('X-Experimental-Mode')=='unclassified-baseline-v1'
            native=BinaryResearchResult.model_validate(client.get(url+'/api/experimental/xclip/jobs/'+job,headers=headers).json())
            assert result.model_dump()==transport_result(native)
            evidence_list=[frame for event in result.violations for frame in event.evidence_frames]
        else:result=BinaryResearchResult.model_validate(value);evidence_list=result.candidate_frames
        assert client.get(url+prefix+'/jobs/'+job,headers={'X-API-Key':keys['other_owner']}).status_code==404
        for evidence in evidence_list:
            frames=sample(media,[evidence.timestamp_sec],max_side=768);assert frames and abs(frames[0].sec-evidence.timestamp_sec)<1e-6
            buffer=BytesIO();frames[0].image.save(buffer,'JPEG',quality=90);assert buffer.getvalue()==base64.b64decode(evidence.image_base64,validate=True);jpeg_checks+=1
    report={'status':'PASS','scope':'Public upload-to-done of generated safe.mov through preserved local research model only; no bank or detector-quality claim',
            'synthetic_jobs_completed':1,'cross_owner_job_hidden':True,'schema_valid':True,'source_jpeg_checks':jpeg_checks,'public_upload_to_done_wall_sec':done_elapsed,'total_verification_wall_sec':time.monotonic()-started,
            'bank_data_used':False,'predictions_or_frames_emitted':False,'partial_v1_enabled':PARTIAL_V1,'native_binary_time_evidence_preserved':True,'semantic_contract_complete':False,'release_eligible':False,'jury_key_created':False}
    atomic_json(OUT/'synthetic-safe-summary.json',report)
    summary=json.loads((OUT/'safe-summary.json').read_text());summary['synthetic_full_cycle_verified']=True;atomic_json(OUT/'safe-summary.json',summary)
    print(json.dumps(report),flush=True)


def verify_invalid_input():
    """Generated invalid bytes only; no raw result, key or media output."""
    import httpx
    from cashreview.local_secrets import load
    keys=load(credentials_file());endpoint=json.loads((OUT/'endpoint.json').read_text())
    if not endpoint['active_expected'] or time.time()>=keys['expires_unix']:raise RuntimeError('Research session inactive')
    url=endpoint['url'];headers={'X-API-Key':keys['primary']};prefix='/api/v1' if PARTIAL_V1 else '/api/experimental/xclip';started=time.monotonic()
    with httpx.Client(timeout=20,trust_env=False,follow_redirects=False) as client:
        response=client.post(url+prefix+'/analyze',headers=headers,files={'file':('generated-invalid.mov',b'Generated invalid container; no video content.','video/quicktime')})
        assert response.status_code==200;job=response.json()['job_id'];until=time.monotonic()+290
        while time.monotonic()<until:
            response=client.get(url+prefix+'/jobs/'+job,headers=headers);assert response.status_code==200;value=response.json()
            if value.get('status')!='processing':break
            time.sleep(.5)
        assert value=={'job_id':job,'status':'failed'} and 'verdict' not in value
        assert client.get(url+prefix+'/jobs/'+job,headers={'X-API-Key':keys['other_owner']}).status_code==404
    report={'status':'PASS','scope':'Generated invalid MOV public technical-failure transport; no model-quality claim',
            'generated_invalid_jobs_failed':1,'technical_failure_not_negative_verdict':True,'cross_owner_job_hidden':True,
            'verification_wall_sec':time.monotonic()-started,'partial_v1_enabled':PARTIAL_V1,'bank_data_used':False,'predictions_or_frames_emitted':False}
    atomic_json(OUT/'invalid-input-safe-summary.json',report);print(json.dumps(report),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['start','supervisor','verify-synthetic','verify-invalid-input']);parser.add_argument('--partial-v1',action='store_true');args=parser.parse_args()
    try:configure(args.partial_v1);globals()[args.action.replace('-','_')]()
    except Exception as error:print(json.dumps({'status':'failed','diagnostic':safe_exception(error,ROOT),'secrets_emitted':False}));sys.exit(1)
