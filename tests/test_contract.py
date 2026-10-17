from pathlib import Path
import sys, time, hashlib, json, asyncio
import httpx
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from cashreview.api import create_app
from cashreview.schemas import Done
from scripts.synthetic import generate


def setup_app(tmp_path,monkeypatch):
    fixtures=[generate(tmp_path/'negative.mov'),generate(tmp_path/'positive.mov',positive=True)]
    hashes=[hashlib.file_digest(p.open('rb'),'sha256').hexdigest() for p in fixtures]
    monkeypatch.setenv('CASH_API_KEY','temporary-test-a,temporary-test-b')
    monkeypatch.setenv('CASH_PRIVATE',str(tmp_path/'private'))
    monkeypatch.setenv('CASH_MODE','synthetic_test')
    monkeypatch.setenv('CASH_TEST_HASHES',','.join(hashes))
    return create_app(),fixtures


def poll(c,j,h):
    deadline=time.monotonic()+30
    while time.monotonic()<deadline:
        r=c.get('/api/v1/jobs/'+j,headers=h); assert r.status_code==200
        data=r.json()
        if data['status']!='processing': return data
        time.sleep(.05)
    raise AssertionError('Synthetic processing timeout')


def test_auth_and_validation(tmp_path,monkeypatch):
    app,files=setup_app(tmp_path,monkeypatch)
    with TestClient(app) as c:
        h={'X-API-Key':'temporary-test-a'}
        assert c.post('/api/v1/analyze').status_code==401
        assert c.post('/api/v1/analyze',headers={'X-API-Key':'wrong'}).status_code==401
        assert c.get('/api/v1/jobs/'+'0'*32).status_code==401
        assert c.get('/api/v1/jobs/'+'0'*32,headers=h).status_code==404
        assert c.get('/api/v1/jobs/..',headers=h).status_code in (404,307)
        assert c.post('/api/v1/analyze',headers=h,files={'file':('bad.mp4',b'a')}).status_code==415
        assert c.post('/api/v1/analyze',headers=h,files={'file':('empty.mov',b'')}).status_code==400
        assert c.get('/.private/dataset/manifest.json',headers=h).status_code==404
        assert c.get('/static/../config/rules.json',headers=h).status_code==404
        assert c.get('/').headers['content-security-policy'].startswith("default-src 'self'")


def test_real_async_fixture_and_isolation(tmp_path,monkeypatch):
    app,files=setup_app(tmp_path,monkeypatch);h={'X-API-Key':'temporary-test-a'}
    with TestClient(app) as c:
        for i,p in enumerate(files):
            r=c.post('/api/v1/analyze',headers=h,files={'file':('arbitrary-renamed.mov',p.read_bytes(),'video/quicktime')});assert r.status_code==200
            j=r.json()['job_id']
            assert c.post('/api/v1/analyze',headers=h,files={'file':('other.mov',b'x')}).status_code==429
            assert c.get('/api/v1/jobs/'+j,headers={'X-API-Key':'temporary-test-b'}).status_code==404
            data=poll(c,j,h); assert data['status']=='done'
            validated=Done.model_validate(data)
            assert validated.verdict==('violation' if i else 'no_violation')
            assert len(data['violations'])==i
            if i:
                assert len(data['violations'][0]['evidence_frames'])==3
                assert all(0<=f['timestamp_sec']<3 for f in data['violations'][0]['evidence_frames'])
            assert c.get('/api/ui/jobs/'+j+'/detail',headers=h).status_code==200
        r=c.post('/api/v1/analyze',headers=h,files={'file':('broken.mov',b'not a movie')})
        assert poll(c,r.json()['job_id'],h)['status']=='failed'


def test_restart_marks_interrupted_failed(tmp_path,monkeypatch):
    app,files=setup_app(tmp_path,monkeypatch);folder=tmp_path/'private/jobs'/('a'*32);folder.mkdir()
    (folder/'meta.json').write_text(json.dumps({'owner':hashlib.sha256(b'temporary-test-a').hexdigest(),'created':time.time()}))
    with TestClient(app) as c:
        result=c.get('/api/v1/jobs/'+'a'*32,headers={'X-API-Key':'temporary-test-a'}).json()
        assert result['status']=='failed'


def test_slow_upload_consumes_processing_deadline(tmp_path,monkeypatch):
    monkeypatch.setenv('CASH_JOB_BUDGET_SEC','0.05')
    app,files=setup_app(tmp_path,monkeypatch)
    boundary='synthetic-boundary'
    def body():
        yield ('--'+boundary+'\r\nContent-Disposition: form-data; name="file"; filename="safe.mov"\r\nContent-Type: video/quicktime\r\n\r\n').encode()
        time.sleep(.1)
        yield files[0].read_bytes()
        yield ('\r\n--'+boundary+'--\r\n').encode()
    with TestClient(app) as c:
        h={'X-API-Key':'temporary-test-a','Content-Type':'multipart/form-data; boundary='+boundary}
        r=c.post('/api/v1/analyze',headers=h,content=body())
        assert r.status_code in (200,408)
        if r.status_code==200:assert poll(c,r.json()['job_id'],{'X-API-Key':'temporary-test-a'})['status']=='failed'


def test_stalled_upload_releases_capacity(tmp_path,monkeypatch):
    monkeypatch.setenv('CASH_JOB_BUDGET_SEC','0.05')
    app,_=setup_app(tmp_path,monkeypatch)
    async def check():
        async def stalled():
            yield b'--safe\r\nContent-Disposition: form-data; name="file"; filename="safe.mov"\r\n\r\n'
            await asyncio.sleep(.3)
            yield b'not completed'
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as c:
                h={'X-API-Key':'temporary-test-a','Content-Type':'multipart/form-data; boundary=safe'}
                r=await c.post('/api/v1/analyze',headers=h,content=stalled())
                assert r.status_code==408
                # A fresh invalid upload reaches validation, instead of busy.
                r=await c.post('/api/v1/analyze',headers={'X-API-Key':'temporary-test-a'},files={'file':('bad.mp4',b'x')})
                assert r.status_code==415
    asyncio.run(check())
