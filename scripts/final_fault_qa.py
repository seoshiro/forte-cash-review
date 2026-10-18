"""Generated-only short deadline, in-flight crash recovery and owned cleanup."""
from pathlib import Path
import json,socket,sys,time
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from cashreview.supervision import atomic_json
from cashreview.technical_diagnostics import safe_exception
from scripts.final_access import OwnedChild,wait_health
OUT=ROOT/'.private/final-fault-qa-02'


def main():
    import httpx,psutil
    OUT.mkdir(exist_ok=False);server=None;phase='startup';clean=False
    try:
        with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
        url='http://127.0.0.1:'+str(port);headers={'X-API-Key':'temporary-loopback-fault-only'}
        def start(budget):
            child=OwnedChild([sys.executable,str(ROOT/'scripts/serve_final_fault_fixture.py'),'--directory',str(OUT),'--port',str(port),'--budget',str(budget)])
            try:wait_health(url,expected='synthetic_test');return child
            except BaseException:child.close();raise
        def upload(client):
            with (OUT/'fixtures/safe.mov').open('rb') as stream:response=client.post(url+'/api/v1/analyze',headers=headers,files={'file':('generated.mov',stream,'video/quicktime')})
            assert response.status_code==200;return response.json()['job_id']
        def poll(client,job):
            deadline=time.monotonic()+15
            while time.monotonic()<deadline:
                response=client.get(url+'/api/v1/jobs/'+job,headers=headers);assert response.status_code==200;value=response.json()
                if value['status']!='processing':return value
                time.sleep(.1)
            raise TimeoutError('Fixture completion')
        server=start(2);phase='deadline_kill'
        with httpx.Client(timeout=10,trust_env=False,follow_redirects=False) as client:
            started=time.monotonic();job=upload(client);assert poll(client,job)=={'job_id':job,'status':'failed'};deadline_wall=time.monotonic()-started
            workers=[p for p in psutil.Process(server.proc.pid).children(recursive=True) if 'cashreview.worker' in p.cmdline()]
            assert deadline_wall<10 and not workers
            server.close();server=None;server=start(45);phase='inflight_crash_recovery';job=upload(client);folder=OUT/'service/jobs'/job;until=time.monotonic()+8
            while not (folder/'worker.pid').exists():
                if time.monotonic()>until:raise TimeoutError('Fixture worker start')
                time.sleep(.05)
            worker=psutil.Process(int((folder/'worker.pid').read_text()));identity=(worker.pid,worker.create_time())
            server.close();server=None;server=start(45)
            assert client.get(url+'/api/v1/jobs/'+job,headers=headers).json()=={'job_id':job,'status':'failed'}
            try:alive=abs(psutil.Process(identity[0]).create_time()-identity[1])<.01
            except psutil.NoSuchProcess:alive=False
            assert not alive
        server.close();server=None;clean=True
        report={'status':'PASS','scope':'Generated-only loopback fault mechanics; no model quality or real-video runtime claim','configured_fault_deadline_sec':2,
            'configured_fixture_delay_sec':10,'observed_deadline_to_failed_sec':deadline_wall,'deadline_worker_tree_reaped':True,'inflight_crash_recovered_failed':True,
            'orphan_fixture_worker_gone':True,'owned_fixture_processes_stopped':True,'bank_data_used':False,'real_inference_changed':False,'raw_results_or_keys_emitted':False}
        atomic_json(OUT/'safe-summary.json',report);print(json.dumps(report))
    except Exception as error:
        atomic_json(OUT/'failure-safe-summary.json',{'status':'failed','phase':phase,'diagnostic':safe_exception(error,ROOT),'private_content_emitted':False});raise
    finally:
        if server:server.close()
        atomic_json(OUT/'cleanup-safe-summary.json',{'owned_server_stopped':clean or server is not None,'bank_data_used':False})


if __name__=='__main__':
    try:main()
    except Exception:raise SystemExit(1)
