"""Separate final positive-JPEG plumbing harness. Generated hash-allowlisted media only; not model quality."""
from pathlib import Path
import sys,os,json,time,secrets,socket,subprocess,threading,re,hashlib,argparse
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from cashreview.supervision import supervise,await_start_gate,atomic_json,ControlSummary
from cashreview.processes import kill_tree
OUT=ROOT/'.private/final-positive-harness'


def clean_environment():
    env=os.environ.copy()
    for key in list(env):
        if key.startswith(('CASH_','TUNNEL_','CLOUDFLARE_','CF_')) or key in ['HF_TOKEN','HUGGING_FACE_HUB_TOKEN','OPENAI_API_KEY','ANTHROPIC_API_KEY','GH_TOKEN','GITHUB_TOKEN']:
            env.pop(key,None)
    return env


def worker():
    run,deadline=await_start_gate();server=None;tunnel=None;complete=False;reader=None;start=time.monotonic();phase='artifact_verification'
    try:
        import httpx,base64
        from cashreview.local_secrets import save,load
        from cashreview.schemas import Done
        from cashreview.video import sample
        from io import BytesIO
        cfg=json.loads((ROOT/'config/cloudflared-artifact.json').read_text());binary=ROOT/'.runtime/cloudflared/cloudflared.exe'
        if hashlib.sha256(binary.read_bytes()).hexdigest()!=cfg['sha256']:raise ValueError('Pinned connector mismatch')
        phase='local_secret_storage';path=OUT/'credentials.dpapi'
        if not path.exists():save(path,{'purpose':'synthetic-infrastructure-only','primary':secrets.token_urlsafe(32),'other_owner':secrets.token_urlsafe(32)})
        keys=load(path)
        if keys['purpose']!='synthetic-infrastructure-only':raise ValueError('Secret purpose mismatch')
        with socket.socket() as probe:probe.bind(('127.0.0.1',0));port=probe.getsockname()[1]
        session=secrets.token_hex(8);local='http://127.0.0.1:'+str(port)
        env=clean_environment()
        command=[sys.executable,str(ROOT/'scripts/serve_synthetic_access.py'),'--directory',str(OUT),'--port',str(port),
            '--session',session,'--test-delay-sec','10']
        phase='synthetic_origin_start';server=subprocess.Popen(command,cwd=ROOT,env=env,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
        def check():
            if time.monotonic()>=deadline:raise TimeoutError('Synthetic HTTPS budget')
            if server.poll() is not None:raise RuntimeError('Owned origin exited')
        with httpx.Client(timeout=10,trust_env=False,follow_redirects=False) as client:
            for attempt in range(60):
                check()
                try:
                    health=client.get(local+'/healthz')
                    if health.status_code==200 and health.json().get('session')==session:break
                except httpx.HTTPError:pass
                time.sleep(.25)
            else:raise TimeoutError('Origin readiness')
            phase='local_auth_preflight'
            # Test auth locally before any public forwarding.
            empty='/api/v1/jobs/'+'0'*32
            assert client.get(local+empty).status_code==401
            assert client.post(local+'/api/v1/analyze',headers={'X-API-Key':'incorrect'}).status_code==401
            assert client.get(local+empty,headers={'X-API-Key':keys['primary']}).status_code==404
        empty_config=OUT/'empty-cloudflared-config.json';empty_config.write_text('{}')
        url_box=[];log_count=[0]
        no_cert=OUT/'no-account-cert.pem'
        if no_cert.exists() or no_cert.is_symlink():raise RuntimeError('Explicit no-account certificate path must not exist')
        tunnel_command=[str(binary),'tunnel','--config',str(empty_config),'--no-autoupdate','--origincert',str(no_cert),
            '--metrics','127.0.0.1:0','--management-diagnostics=false','--loglevel','info','--label','terenoi-synthetic-pilot','--url',local]
        phase='quick_tunnel_start'
        tunnel=subprocess.Popen(tunnel_command,cwd=OUT,env=env,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,creationflags=subprocess.CREATE_NO_WINDOW)
        def consume():
            while True:
                line=tunnel.stderr.readline(16384)
                if not line:break
                log_count[0]+=1
                for value in re.findall(rb'https://[a-z0-9-]+\.trycloudflare\.com',line):
                    if not url_box:url_box.append(value.decode('ascii'))
        reader=threading.Thread(target=consume,daemon=True);reader.start()
        ready_by=min(deadline,time.monotonic()+90)
        while not url_box:
            check()
            if tunnel.poll() is not None or time.monotonic()>ready_by:raise RuntimeError('Quick Tunnel unavailable')
            time.sleep(.2)
        url=url_box[0];atomic_json(OUT/'endpoint.json',{'url':url,'session':session,'purpose':'synthetic_infrastructure_only','active_expected':True})
        headers={'X-API-Key':keys['primary']};other={'X-API-Key':keys['other_owner']}
        latencies=[];jpeg_checks=0;completed=0
        phase='public_https_health'
        with httpx.Client(timeout=15,trust_env=False,follow_redirects=False) as client:
            for attempt in range(30):
                check()
                try:
                    response=client.get(url+'/healthz')
                    if response.status_code==200 and response.json().get('session')==session:break
                except (httpx.HTTPError,ValueError):pass
                time.sleep(.5)
            else:raise TimeoutError('Public health readiness')
            phase='public_auth_and_paths';assert client.get(url+'/').status_code==200
            for auth in [{},{'X-API-Key':'incorrect'}]:
                assert client.get(url+empty,headers=auth).status_code==401
                assert client.post(url+'/api/v1/analyze',headers=auth).status_code==401
            assert client.get(url+empty,headers=headers).status_code==404
            for path in ['/.git/HEAD','/.private/credentials.dpapi','/.env','/input.mov','/result.json','/raw','/docs','/openapi.json','/api/experimental/xclip/analyze']:
                assert client.get(url+path,headers=headers).status_code==404
            def poll(job):
                until=min(deadline,time.monotonic()+60)
                while time.monotonic()<until:
                    check();response=client.get(url+'/api/v1/jobs/'+job,headers=headers);assert response.status_code==200
                    value=response.json()
                    if value['status']!='processing':return value
                    time.sleep(.2)
                raise TimeoutError('Synthetic public job')
            phase='public_synthetic_jobs'
            for name,positive in [('safe.mov',False),('positive.mov',True)]:
                tick=time.monotonic();media=OUT/'fixtures'/name
                with media.open('rb') as stream:response=client.post(url+'/api/v1/analyze',headers=headers,files={'file':(name,stream,'video/quicktime')})
                assert response.status_code==200;job=response.json()['job_id']
                if positive:
                    with media.open('rb') as stream:busy=client.post(url+'/api/v1/analyze',headers=headers,files={'file':('second.mov',stream,'video/quicktime')})
                    assert busy.status_code==429 and busy.headers.get('Retry-After')
                value=Done.model_validate(poll(job));assert value.verdict==('violation' if positive else 'no_violation')
                assert client.get(url+'/api/v1/jobs/'+job,headers=other).status_code==404
                for raw_path in ['/jobs/'+job+'/input.mov','/.private/service/jobs/'+job+'/result.json','/api/v1/jobs/'+job+'/input.mov']:
                    assert client.get(url+raw_path,headers=headers).status_code==404
                assert client.get(url+'/api/ui/jobs/'+job+'/detail').status_code==401
                assert client.get(url+'/api/ui/jobs/'+job+'/detail',headers=other).status_code==404
                assert client.get(url+'/api/ui/jobs/'+job+'/detail',headers=headers).status_code==200
                for event in value.violations:
                    for frame in event.evidence_frames:
                        actual=sample(media,[frame.timestamp_sec],320);assert len(actual)==1 and abs(actual[0].sec-frame.timestamp_sec)<1e-6
                        buffer=BytesIO();actual[0].image.save(buffer,'JPEG')
                        assert buffer.getvalue()==base64.b64decode(frame.image_base64,validate=True);jpeg_checks+=1
                latencies.append(time.monotonic()-tick);completed+=1
            phase='public_corrupt_input';bad=client.post(url+'/api/v1/analyze',headers=headers,files={'file':('corrupt.mov',b'not-a-movie','video/quicktime')})
            assert bad.status_code==200 and poll(bad.json()['job_id'])['status']=='failed'
        atomic_json(OUT/'infrastructure-safe-summary.json',{'status':'checks_passed_pending_cleanup','purpose':'synthetic_infrastructure_only','bank_data_used':False,
            'local_auth_before_tunnel_passed':True,'public_https_health_passed':True,'public_missing_wrong_key_rejected':True,
            'cross_owner_job_detail_hidden':True,'private_path_and_non_allowlisted_routes_blocked':True,'busy_429_observed':True,
            'corrupt_input_failed_without_negative_verdict':True,'strict_synthetic_results_completed':completed,'source_jpeg_checks':jpeg_checks,
            'synthetic_delay_sec':10,'public_synthetic_upload_wall_mean_sec':sum(latencies)/len(latencies),'public_synthetic_upload_wall_max_sec':max(latencies),
            'elapsed_sec_before_cleanup':time.monotonic()-start,'dpapi_user_scoped_secret_storage':True,'secret_values_emitted':False,
            'jury_key_created':False,'new_cloudflare_account_credentials_created':False,'paid_resources_or_trials':False,
            'os_firewall_warp_dns_or_service_changed':False,'raw_connector_logs_collected':False,'connector_log_lines_discarded':log_count[0],
            'production_or_model_quality_claim':False})
        complete=True
    except Exception as error:
        atomic_json(OUT/'infrastructure-safe-summary.json',{'status':'failed','phase':phase,'technical_error_type':type(error).__name__,
            'connector_exit_code':tunnel.poll() if tunnel is not None else None,
            'raw_exception_or_secret_emitted':False,'bank_data_used':False,'production_claim':False})
    finally:
        cleanup=True
        for proc in [tunnel,server]:
            if proc is not None and proc.poll() is None:
                cleanup=bool(kill_tree(proc.pid)) and cleanup
                try:proc.wait(timeout=3)
                except subprocess.TimeoutExpired:cleanup=False
        if reader:reader.join(timeout=2)
        atomic_json(OUT/'process-cleanup-safe-summary.json',{'owned_origin_and_connector_stopped':cleanup,'bank_data_used':False})
        if not cleanup:complete=False
        atomic_json(run/'worker-safe-summary.json',ControlSummary(status='completed' if complete else 'failed',completed_cases=1 if complete else 0,
            passed_cases=1 if complete else 0,total_cases=1,failure='none' if complete else 'exception').model_dump())
    if not complete:raise SystemExit(1)


def main():
    OUT.mkdir(exist_ok=True)
    report=supervise([sys.executable,str(Path(__file__).resolve()),'worker'],OUT/'run',240,1,str(ROOT))
    rollback=False;endpoint=OUT/'endpoint.json'
    if endpoint.exists():
        import httpx
        value=json.loads(endpoint.read_text());url=value['url']
        with httpx.Client(timeout=5,trust_env=False,follow_redirects=False) as client:
            for attempt in range(10):
                try:r=client.get(url+'/healthz');live=r.status_code==200 and r.json().get('session')==value['session']
                except (httpx.HTTPError,ValueError):live=False
                if not live:rollback=True;break
                time.sleep(.5)
        value['active_expected']=False;atomic_json(endpoint,value)
    atomic_json(OUT/'rollback-safe-summary.json',{'owned_cleanup_confirmed':report['cleanup_complete'],'public_origin_no_longer_responds':rollback,'purpose':'synthetic_infrastructure_only'})
    inner_path=OUT/'infrastructure-safe-summary.json'
    inner=json.loads(inner_path.read_text()) if inner_path.exists() else {'phase':'missing_worker_report'}
    passed=report['quality_gate_passed'] and report['cleanup_complete'] and rollback and inner.get('status')=='checks_passed_pending_cleanup'
    authoritative={**inner,'status':'PASS' if passed else 'failed','owned_cleanup_confirmed':report['cleanup_complete'],
        'public_rollback_observed':rollback,'technical_monitor_validated':report['quality_gate_passed']}
    atomic_json(OUT/'safe-summary.json',authoritative)
    print(json.dumps({'technical_monitor':report,'public_rollback_observed':rollback,'overall_status':authoritative['status']}),flush=True)
    print(json.dumps(authoritative),flush=True)
    if not passed:raise SystemExit(1)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['run','worker']);a=p.parse_args()
    try:worker() if a.action=='worker' else main()
    except Exception as error:print(json.dumps({'status':'failed','technical_error_type':type(error).__name__,'secret_values_emitted':False}));sys.exit(1)
