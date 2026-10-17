"""Failure-path review on generated data only, never the manual-review service."""
import asyncio,hashlib,json,time
import os
import httpx
from types import SimpleNamespace
from fastapi.testclient import TestClient
import pytest
import cashreview.api as api
from scripts.synthetic import generate
KEY='temporary-api-code-review-only';HEADERS={'X-API-Key':KEY};JOB='d'*32

def setup(tmp_path,monkeypatch,budget='295'):
    monkeypatch.setenv('CASH_PRIVATE',str(tmp_path/'private'));monkeypatch.setenv('CASH_API_KEY',KEY)
    monkeypatch.setenv('CASH_MODE','synthetic_test');monkeypatch.setenv('CASH_JOB_BUDGET_SEC',budget)
    path=generate(tmp_path/'generated.mov');monkeypatch.setenv('CASH_TEST_HASHES',hashlib.sha256(path.read_bytes()).hexdigest())
    return path,tmp_path/'private'

def seed(private,result,meta=None):
    folder=private/'jobs'/JOB;folder.mkdir(parents=True)
    (folder/'meta.json').write_text(json.dumps(meta if meta is not None else {'owner':hashlib.sha256(KEY.encode()).hexdigest(),'created':time.time()}))
    (folder/'result.json').write_text(result);return folder

@pytest.mark.parametrize('payload',['not-json',json.dumps({'job_id':'e'*32,'status':'done','verdict':'no_violation','violations':[]})])
def test_corrupt_or_mismatched_result_is_failed_not_500_or_done(tmp_path,monkeypatch,payload):
    _path,private=setup(tmp_path,monkeypatch);seed(private,payload)
    with TestClient(api.create_app(),raise_server_exceptions=False) as c:
        response=c.get('/api/v1/jobs/'+JOB,headers=HEADERS)
        assert response.status_code==200
        assert response.json()=={'job_id':JOB,'status':'failed'}

@pytest.mark.parametrize('meta',[{}, {'owner':None,'created':1}, {'owner':'a'*64,'created':10**400}])
def test_malformed_owner_metadata_is_not_an_exception_or_disclosure(tmp_path,monkeypatch,meta):
    _path,private=setup(tmp_path,monkeypatch);seed(private,'{}',meta=meta)
    with TestClient(api.create_app(),raise_server_exceptions=False) as c:
        assert c.get('/api/v1/jobs/'+JOB,headers=HEADERS).status_code==404

def test_second_api_instance_is_rejected_even_while_store_is_idle(tmp_path,monkeypatch):
    setup(tmp_path,monkeypatch)
    with TestClient(api.create_app()) as first:
        assert first.get('/healthz').status_code==200
        with pytest.raises(RuntimeError,match='single API instance'):
            with TestClient(api.create_app()):pass

class FakeProcess:
    def __init__(self):self.pid=2147483647;self.returncode=None;self.release=False
    async def wait(self):
        while not self.release:await asyncio.sleep(.01)
        self.returncode=1;return 1

def test_failed_worker_termination_is_bounded_and_blocks_new_work(tmp_path,monkeypatch):
    path,_private=setup(tmp_path,monkeypatch,budget='.05');proc=FakeProcess()
    async def spawn(*args,**kwargs):return proc
    monkeypatch.setattr(api.asyncio,'create_subprocess_exec',spawn);monkeypatch.setattr(api,'kill_tree',lambda _pid:False)
    with TestClient(api.create_app()) as c:
        try:
            job=c.post('/api/v1/analyze',headers=HEADERS,files={'file':('safe.mov',path.read_bytes())}).json()['job_id']
            deadline=time.monotonic()+3
            while time.monotonic()<deadline:
                response=c.get('/api/v1/jobs/'+job,headers=HEADERS)
                if response.json()['status']=='failed':break
                time.sleep(.02)
            assert response.json()['status']=='failed'
            assert c.post('/api/v1/analyze',headers=HEADERS,files={'file':('safe.mov',b'x')}).status_code==503
        finally:proc.release=True;time.sleep(.05)

def test_wall_clock_adjustment_cannot_extend_worker_deadline(tmp_path,monkeypatch):
    path,_private=setup(tmp_path,monkeypatch,budget='.15');jump={'active':False};proc=FakeProcess();wall=time.time
    monkeypatch.setattr(api,'time',SimpleNamespace(time=lambda:wall()-(3600 if jump['active'] else 0),monotonic=time.monotonic))
    async def spawn(*args,**kwargs):
        jump['active']=True
        async def later():await asyncio.sleep(1);proc.release=True
        asyncio.create_task(later());return proc
    def stopped(_pid):proc.release=True;return True
    monkeypatch.setattr(api.asyncio,'create_subprocess_exec',spawn);monkeypatch.setattr(api,'kill_tree',stopped)
    with TestClient(api.create_app()) as c:
        start=time.monotonic();job=c.post('/api/v1/analyze',headers=HEADERS,files={'file':('safe.mov',path.read_bytes())}).json()['job_id']
        while c.get('/api/v1/jobs/'+job,headers=HEADERS).json()['status']=='processing':time.sleep(.02)
        assert time.monotonic()-start<.8

def test_cleanup_tolerates_bad_metadata_and_preserves_active_or_unrelated_paths(tmp_path):
    from cashreview.storage import cleanup_expired
    jobs=tmp_path/'jobs';jobs.mkdir();now=time.time();old=now-7200
    for name,meta in [('1'*32,{}),('2'*32,{'owner':'a'*64,'created':old}),('3'*32,{'owner':'a'*64,'created':old}),('unrelated-folder',{'created':old})]:
        folder=jobs/name;folder.mkdir();(folder/'meta.json').write_text(json.dumps(meta));os.utime(folder,(old,old))
    outside=tmp_path/'outside';outside.mkdir();(outside/'keep.txt').write_text('Synthetic outside sentinel')
    report=cleanup_expired(jobs,{'3'*32},now)
    assert report=={'removed':2,'errors':0}
    assert (jobs/('3'*32)).exists() and (jobs/'unrelated-folder').exists() and (outside/'keep.txt').exists()

def test_body_limits_reject_declared_streamed_and_file_overflow_without_holding_slot(tmp_path,monkeypatch):
    setup(tmp_path,monkeypatch);monkeypatch.setattr(api,'MULTIPART_BYTES_LIMIT',1024);monkeypatch.setattr(api,'UPLOAD_BYTES_LIMIT',128)
    app=api.create_app()
    async def run():
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as c:
                r=await c.post('/api/v1/analyze',headers={**HEADERS,'Content-Length':'1025'},content=b'')
                assert r.status_code==413
                async def streamed():
                    yield b'--safe\r\nContent-Disposition: form-data; name="file"; filename="safe.mov"\r\n\r\n'
                    yield b'x'*2048
                    yield b'\r\n--safe--\r\n'
                r=await c.post('/api/v1/analyze',headers={**HEADERS,'Content-Type':'multipart/form-data; boundary=safe'},content=streamed())
                assert r.status_code==413
                r=await c.post('/api/v1/analyze',headers=HEADERS,files={'file':('safe.mov',b'x'*200)})
                assert r.status_code==413
                r=await c.post('/api/v1/analyze',headers=HEADERS,files={'file':('bad.mp4',b'x')})
                assert r.status_code==415
                assert list((tmp_path/'private/jobs').iterdir())==[]
    asyncio.run(run())

def test_worker_does_not_inherit_server_key_or_cloud_tokens(tmp_path,monkeypatch):
    path,_private=setup(tmp_path,monkeypatch);captured={};proc=FakeProcess();proc.release=True
    monkeypatch.setenv('OPENAI_API_KEY','temporary-do-not-send-to-worker');monkeypatch.setenv('HF_TOKEN','temporary-do-not-send-to-worker')
    async def spawn(*args,**kwargs):captured.update(kwargs['env']);return proc
    monkeypatch.setattr(api.asyncio,'create_subprocess_exec',spawn)
    with TestClient(api.create_app()) as c:
        response=c.post('/api/v1/analyze',headers=HEADERS,files={'file':('../../outside.mov',path.read_bytes())})
        assert response.status_code==200;job=response.json()['job_id']
        deadline=time.monotonic()+2
        while not captured and time.monotonic()<deadline:time.sleep(.01)
        assert not any(k in captured for k in ['CASH_API_KEY','OPENAI_API_KEY','HF_TOKEN'])
        assert captured['HF_HUB_OFFLINE']=='1' and captured['TRANSFORMERS_OFFLINE']=='1'
        assert not (tmp_path/'outside.mov').exists()
        assert hashlib.sha256((_private/'jobs'/job/'input.mov').read_bytes()).hexdigest()==hashlib.sha256(path.read_bytes()).hexdigest()

def test_startup_reaps_orphan_even_if_it_already_has_a_result(tmp_path,monkeypatch):
    from test_contract import delayed_orphan
    from cashreview.processes import kill_tree
    import psutil
    app,folder,proc,pid=delayed_orphan(tmp_path,monkeypatch)
    try:
        (folder/'result.json').write_text(json.dumps({'job_id':'b'*32,'status':'done','verdict':'no_violation','violations':[]}))
        with TestClient(app) as c:
            assert not psutil.pid_exists(pid)
            response=c.get('/api/v1/jobs/'+'b'*32,headers={'X-API-Key':'temporary-test-a'})
            assert response.json()['status']=='done'
    finally:kill_tree(proc.pid)
