"""Owned, revocable day-bounded jury delivery. No secrets or raw logs on stdout."""
from pathlib import Path
from datetime import datetime,timezone
import argparse,hashlib,json,os,re,secrets,socket,subprocess,sys,threading,time
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from cashreview.supervision import atomic_json,OwnedWindowsJob
from cashreview.technical_diagnostics import safe_exception
from scripts.research_access import clean_env,identities
OUT=ROOT/'.private/final-access';LOCAL='http://127.0.0.1:8771'


class OwnedChild:
    def __init__(self,command,directory=ROOT,pipe=False):
        self.job=OwnedWindowsJob();self.proc=None
        try:
            self.proc=subprocess.Popen(command,cwd=directory,env=clean_env(),stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE if pipe else subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
            self.job.assign(self.proc)
        except BaseException:self.close();raise
    def close(self):
        self.job.close()
        if self.proc is not None:
            if self.proc.poll() is None:self.proc.terminate()
            self.proc.wait(timeout=5)


def wait_health(url,timeout=45,expected='xclip_experimental'):
    import httpx
    deadline=time.monotonic()+timeout
    with httpx.Client(timeout=5,trust_env=False,follow_redirects=False) as client:
        while time.monotonic()<deadline:
            try:
                response=client.get(url+'/healthz')
                if response.status_code==200 and response.json().get('mode')==expected:return
            except (httpx.HTTPError,ValueError):pass
            time.sleep(.2)
    raise TimeoutError('Origin readiness')


def start_tunnel(directory,local):
    directory=Path(directory);cfg=json.loads((ROOT/'config/cloudflared-artifact.json').read_text());binary=ROOT/'.runtime/cloudflared/cloudflared.exe'
    if hashlib.sha256(binary.read_bytes()).hexdigest()!=cfg['sha256']:raise ValueError('Pinned connector mismatch')
    config=directory/'empty-cloudflared-config.json';config.write_text('{}');no_cert=directory/'no-account-cert.pem'
    if no_cert.exists() or no_cert.is_symlink():raise ValueError('No-account certificate must not exist')
    child=OwnedChild([str(binary),'tunnel','--config',str(config),'--no-autoupdate','--origincert',str(no_cert),
        '--metrics','127.0.0.1:0','--management-diagnostics=false','--loglevel','info','--label','terenoi-expiring-prototype','--url',local],directory,True)
    found=[]
    def discard():
        while True:
            line=child.proc.stderr.readline(16384)
            if not line:break
            for value in re.findall(rb'https://[a-z0-9-]+\.trycloudflare\.com',line):
                if not found:found.append(value.decode('ascii'))
    reader=threading.Thread(target=discard,daemon=True);reader.start();deadline=time.monotonic()+90
    try:
        while not found:
            if child.proc.poll() is not None or time.monotonic()>deadline:raise RuntimeError('Quick Tunnel unavailable')
            time.sleep(.2)
        return child,found[0],reader
    except BaseException:child.close();reader.join(timeout=2);raise


def active_supervisor():
    import psutil
    path=OUT/'supervisor-identity.json'
    if not path.exists():return False
    try:
        item=json.loads(path.read_text());proc=psutil.Process(item['pid'])
        return abs(proc.create_time()-item['created'])<.01 and str(Path(__file__).resolve()) in proc.cmdline()
    except (psutil.Error,OSError,ValueError,KeyError):return False


def provision():
    from cashreview.local_secrets import save
    from cashreview.final_delivery import validate_session
    # Human-authorized one-day temporary jury access. Never create a permanent key.
    now=time.time();expiry=datetime(2026,10,18,18,59,59,tzinfo=timezone.utc).timestamp()
    if datetime.now(timezone.utc).date()!=datetime(2026,10,18).date():raise ValueError('This authorization is for the specified evaluation day only')
    record=validate_session({'purpose':'jury-experimental-prototype','issued_unix':now,'expires_unix':expiry,
        **{key:secrets.token_urlsafe(48) for key in ['jury','operator','other_owner']}})
    OUT.mkdir(exist_ok=True);save(OUT/'credentials.dpapi',record)
    pythonw=Path(sys.executable).with_name('pythonw.exe')
    if not pythonw.exists():pythonw=Path(sys.executable)
    (OUT/'Open-Jury-Access.cmd').write_text('@echo off\r\n"'+str(pythonw)+'" "'+str(ROOT/'scripts/show_final_key.py')+'"\r\n',encoding='utf-8')
    for filename,action in [('Restart-Origin.cmd','restart-origin'),('Revoke-Jury-Key.cmd','revoke-jury'),('Stop-All-Access.cmd','stop')]:
        (OUT/filename).write_text('@echo off\r\n"'+sys.executable+'" "'+str(Path(__file__).resolve())+'" '+action+'\r\n',encoding='utf-8')
    report={'status':'provisioned','jury_key_created':True,'separate_operator_and_owner_test_keys':True,'permanent_key_created':False,
        'user_scoped_dpapi':True,'expires_utc':'2026-10-18 18:59:59 UTC','expires_astana':'2026-10-18 23:59:59 UTC+5','secrets_emitted':False,'new_cloudflare_grants':False}
    atomic_json(OUT/'provision-safe-summary.json',report);print(json.dumps(report))


def start():
    from cashreview.local_secrets import load
    from cashreview.final_delivery import validate_session
    validate_session(load(OUT/'credentials.dpapi'))
    if active_supervisor():raise RuntimeError('Owned final supervisor already active')
    if (OUT/'revoke-all.request').exists():raise RuntimeError('Access explicitly revoked; cannot silently restore')
    (OUT/'stop.request').unlink(missing_ok=True)
    process=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'supervisor'],cwd=ROOT,env=clean_env(),stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
    atomic_json(OUT/'launcher-identity.json',identities(process));print(json.dumps({'status':'starting','new_keys_created':False,'secrets_emitted':False}))


def security_check(url,record):
    import httpx
    headers={'X-API-Key':record['operator']};unknown='/api/v1/jobs/'+'0'*32
    with httpx.Client(timeout=12,trust_env=False,follow_redirects=False) as client:
        assert client.get(url+'/').status_code==200
        for auth in [{},{'X-API-Key':'incorrect'},[('X-API-Key',record['operator']),('X-API-Key',record['jury'])]]:
            assert client.get(url+unknown,headers=auth).status_code==401
            assert client.post(url+'/api/v1/analyze',headers=auth).status_code==401
        for name in ['jury','operator','other_owner']:
            assert client.post(url+'/api/v1/analyze',headers={'X-API-Key':record[name]}).status_code==422
        assert client.get(url+unknown,headers=headers).status_code==404
        for path in ['/.git/HEAD','/.private/credentials.dpapi','/.private/final-service/jobs','/input.mov','/result.json','/raw','/docs','/openapi.json','/static/app.js']:
            assert client.get(url+path,headers=headers).status_code==404


def supervisor():
    import psutil
    from filelock import FileLock
    from cashreview.local_secrets import load
    from cashreview.final_delivery import validate_session
    origin=None;tunnel=None;reader=None;phase='startup';cleanup=True;record=None
    with FileLock(str(OUT/'supervisor.lock'),timeout=0):
        atomic_json(OUT/'supervisor-identity.json',{'pid':os.getpid(),'created':psutil.Process().create_time()})
        try:
            record=validate_session(load(OUT/'credentials.dpapi'));expiry=record['expires_unix']
            with socket.socket() as probe:probe.bind(('127.0.0.1',8771))
            def spawn_origin():
                child=OwnedChild([sys.executable,str(ROOT/'scripts/serve_final_delivery.py'),'--directory',str(OUT)])
                try:
                    wait_health(LOCAL)
                    if child.proc.poll() is not None:raise RuntimeError('Owned origin exited during readiness')
                    atomic_json(OUT/'origin-identity.json',identities(child.proc));return child
                except BaseException:child.close();raise
            phase='local_security_preflight';origin=spawn_origin();security_check(LOCAL,record)
            phase='public_connector';tunnel,url,reader=start_tunnel(OUT,LOCAL);wait_health(url);security_check(url,record)
            atomic_json(OUT/'connector-identity.json',identities(tunnel.proc))
            atomic_json(OUT/'endpoint.json',{'url':url,'purpose':'jury-experimental-prototype','active_expected':True,'expires_unix':expiry})
            atomic_json(OUT/'safe-summary.json',{'status':'READY','canonical_url':url,'expires_utc':'2026-10-18 18:59:59 UTC','expires_astana':'2026-10-18 23:59:59 UTC+5',
                'local_and_public_auth_paths_passed':True,'prototype':True,'semantic_contract_complete':False,'release_eligible':False,'permanent_key_created':False,
                'native_baseline_unchanged':True,'new_persistent_cloudflare_grants':False,'os_settings_changed':False,'secret_or_raw_logs_emitted':False})
            phase='serving';automatic_restarts=0
            while time.time()<expiry and not (OUT/'stop.request').exists() and not (OUT/'revoke-all.request').exists():
                if tunnel.proc.poll() is not None:raise RuntimeError('Owned connector exited; public URL must be rechecked after restart')
                request=OUT/'restart-origin.request';requested=request.exists();exited=origin.proc.poll() is not None
                if requested or exited:
                    if exited and not requested:
                        automatic_restarts+=1
                        if automatic_restarts>2:raise RuntimeError('Bounded origin restart limit exceeded')
                    token=json.loads(request.read_text())['request_id'] if requested else 'automatic'
                    origin.close();origin=None;origin=spawn_origin();wait_health(url)
                    atomic_json(OUT/'restart-safe-summary.json',{'status':'PASS','request_id':token,'same_public_url':True,'checked_utc':time.strftime('%Y-%m-%d %H:%M:%S UTC',time.gmtime())})
                    request.unlink(missing_ok=True)
                atomic_json(OUT/'availability-safe-summary.json',{'status':'running','checked_utc':time.strftime('%Y-%m-%d %H:%M:%S UTC',time.gmtime()),'origin_alive':True,'connector_alive':True,'release_eligible':False})
                time.sleep(1)
        except Exception as error:atomic_json(OUT/'failure-safe-summary.json',{'status':'failed','phase':phase,'diagnostic':safe_exception(error,ROOT),'private_content_emitted':False})
        finally:
            for child in [origin,tunnel]:
                if child:
                    try:child.close()
                    except Exception:cleanup=False
            if reader:reader.join(timeout=2)
            if cleanup and record is not None:
                try:
                    from cashreview.session_cleanup import purge_final_uploads
                    purged=purge_final_uploads(ROOT)
                    atomic_json(OUT/'upload-cleanup-safe-summary.json',{'status':'PASS' if not purged['blocked'] else 'partial',**purged,'original_dataset_untouched':True})
                except Exception as error:
                    atomic_json(OUT/'upload-cleanup-safe-summary.json',{'status':'blocked','diagnostic':safe_exception(error,ROOT),'original_dataset_untouched':True})
            if (OUT/'endpoint.json').exists():
                item=json.loads((OUT/'endpoint.json').read_text());item['active_expected']=False;atomic_json(OUT/'endpoint.json',item)
            atomic_json(OUT/'stopped-safe-summary.json',{'status':'stopped','owned_cleanup_confirmed':cleanup})
            if (OUT/'safe-summary.json').exists():
                item=json.loads((OUT/'safe-summary.json').read_text());item['status']='STOPPED';atomic_json(OUT/'safe-summary.json',item)


def restart_origin():
    if not active_supervisor():raise RuntimeError('No active owned supervisor; use start to recreate tunnel and recheck its new URL')
    token=secrets.token_hex(8);atomic_json(OUT/'restart-origin.request',{'request_id':token});deadline=time.monotonic()+55
    while time.monotonic()<deadline:
        path=OUT/'restart-safe-summary.json'
        if path.exists():
            item=json.loads(path.read_text())
            if item.get('request_id')==token and item.get('status')=='PASS':print(json.dumps({'status':'PASS','same_public_url':True,'no_new_key':True}));return
        time.sleep(.2)
    raise TimeoutError('Origin restart completion unconfirmed; inspect safe status before retry')


def status():
    result={'supervisor_active':active_supervisor()}
    for name in ['safe-summary.json','availability-safe-summary.json','failure-safe-summary.json']:
        if (OUT/name).exists():result[name]=json.loads((OUT/name).read_text())
    print(json.dumps(result))


def revoke_jury():
    (OUT/'revoke-jury.request').touch();print(json.dumps({'status':'jury_key_revoked','takes_effect_on_next_request':True,'secret_emitted':False}))


def stop():
    (OUT/'stop.request').touch();print(json.dumps({'status':'owned_access_stop_requested'}))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['provision','start','supervisor','status','restart-origin','revoke-jury','stop']);args=parser.parse_args()
    try:globals()[args.action.replace('-','_')]()
    except Exception as error:print(json.dumps({'status':'failed','diagnostic':safe_exception(error,ROOT),'private_content_emitted':False}));raise SystemExit(1)
