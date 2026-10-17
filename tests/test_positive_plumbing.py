"""Controlled positive branch: actual synthetic MOV/JPEG, fixed fake features."""
from pathlib import Path
from fractions import Fraction
from io import BytesIO
import time,json,base64,hashlib
import av,numpy as np
from PIL import Image
from fastapi.testclient import TestClient
from cashreview.api import create_app
from cashreview.video import sample,inspect,open_local_mov
from cashreview.supervision import atomic_json
from xclip_candidate.experimental import ExperimentalEngine,BinaryResearchResult
from cashreview.schemas import Done


def variable_pts_mov(path):
    with av.open(str(path),'w',format='mov') as container:
        stream=container.add_stream('libx264',rate=30);stream.width=320;stream.height=240;stream.pix_fmt='yuv420p'
        stream.time_base=Fraction(1,1000);stream.codec_context.time_base=Fraction(1,1000)
        stream.options={'crf':'20','preset':'ultrafast','bf':'0'}
        for index in range(90):
            value=np.zeros((240,320,3),dtype=np.uint8);value[:]=[32,64,96]
            value[80:150,10+index*2:40+index*2]=[220,170,40]
            frame=av.VideoFrame.from_ndarray(value,format='rgb24');frame.pts=index*40+(index%5)*3;frame.time_base=Fraction(1,1000)
            for packet in stream.encode(frame):container.mux(packet)
        for packet in stream.encode():container.mux(packet)


def test_controlled_positive_upload_uses_actual_pts_and_source_jpegs(tmp_path,monkeypatch):
    import cashreview.api as api
    import xclip_candidate.features as features
    key='temporary-positive-plumbing-only';other='temporary-positive-other-owner'
    source=tmp_path/'abstract-vfr.mov';variable_pts_mov(source);content=source.read_bytes()
    before=hashlib.sha256(content).hexdigest();private=tmp_path/'service'
    monkeypatch.setenv('CASH_MODE','xclip_experimental');monkeypatch.setenv('CASH_ENGINE','xclip_experimental')
    monkeypatch.setenv('CASH_PRIVATE',str(private));monkeypatch.setenv('CASH_API_KEY',key+','+other)
    positive=np.eye(1,512,0,dtype=np.float32)[0];negative=np.eye(1,512,1,dtype=np.float32)[0]
    # This is a plumbing fixture. It makes no learned-model or event-quality claim.
    monkeypatch.setattr(features,'extract',lambda *args:{'ordered':np.stack([negative,positive,negative]),'times':np.array([.5,1.137,2.5])})
    engine=ExperimentalEngine.__new__(ExperimentalEngine);engine.started=time.monotonic();engine.cfg={}
    engine.positive=positive;engine.negative=negative;engine.encoder=None;engine.check=lambda:None
    class Process:
        pid=2147483647;returncode=0
        async def wait(self):return 0
    async def spawn(*args,**kwargs):
        folder=Path(args[-1]);value=engine.analyze(folder/'input.mov',folder.name)
        atomic_json(folder/'experimental-result.json',value);return Process()
    monkeypatch.setattr(api.asyncio,'create_subprocess_exec',spawn)
    headers={'X-API-Key':key}
    with TestClient(create_app()) as client:
        for h in [{},{'X-API-Key':'wrong-temporary-value'}]:
            assert client.post('/api/experimental/xclip/analyze',headers=h,files={'file':('safe.mov',content)}).status_code==401
        response=client.post('/api/experimental/xclip/analyze',headers=headers,files={'file':('renamed-safe.mov',content)})
        assert response.status_code==200 and set(response.json())=={'job_id'};job=response.json()['job_id']
        until=time.monotonic()+3
        while True:
            value=client.get('/api/experimental/xclip/jobs/'+job,headers=headers).json()
            if value['status']!='processing':break
            assert time.monotonic()<until;time.sleep(.01)
        result=BinaryResearchResult.model_validate(value)
        assert result.binary_decision=='violation' and 1<=len(result.candidate_frames)<=3
        assert result.event_type_status=='unverified' and result.rule_application_status=='not_assessed' and not result.release_eligible
        with open_local_mov(source) as container:
            stream=container.streams.video[0];origin=float(stream.start_time*stream.time_base) if stream.start_time is not None else 0
            actual_pts=[float(frame.pts*frame.time_base)-origin for frame in container.decode(stream)]
        assert len(set(round(b-a,6) for a,b in zip(actual_pts,actual_pts[1:])))>1
        assert result.candidate_timecode_sec!=1.137
        for evidence in result.candidate_frames:
            assert any(abs(evidence.timestamp_sec-t)<1e-6 for t in actual_pts)
            source_frame=sample(source,[evidence.timestamp_sec],768)[0]
            buffer=BytesIO();source_frame.image.save(buffer,'JPEG',quality=90)
            assert buffer.getvalue()==base64.b64decode(evidence.image_base64,validate=True)
            with Image.open(BytesIO(buffer.getvalue())) as image:assert image.format=='JPEG' and image.size==(320,240)
        assert client.get('/api/experimental/xclip/jobs/'+job).status_code==401
        assert client.get('/api/experimental/xclip/jobs/'+job,headers={'X-API-Key':other}).status_code==404
        assert client.get('/api/experimental/xclip/jobs/'+'f'*32,headers=headers).status_code==404
        assert client.get('/api/v1/jobs/'+job,headers=headers).status_code==503
        assert hashlib.sha256((private/'jobs'/job/'input.mov').read_bytes()).hexdigest()==before
        assert hashlib.sha256(source.read_bytes()).hexdigest()==before
    out=Path(__file__).resolve().parents[1]/'.private/xclip-positive-plumbing';out.mkdir(exist_ok=True)
    atomic_json(out/'safe-summary.json',{'status':'passed','split':'synthetic','generated_media_only':True,
        'controlled_fixed_features':True,'learned_model_run':False,'positive_result_completed':True,
        'actual_source_jpegs_verified':len(result.candidate_frames),'variable_pts_verified':True,
        'auth_owner_isolation_and_research_schema_passed':True,'official_contract_blocked':True,
        'source_unchanged':True,'detection_or_evidence_relevance_claim':False})


def test_official_positive_contract_with_actual_synthetic_worker(tmp_path,monkeypatch):
    source=tmp_path/'generated-official-vfr.mov';variable_pts_mov(source);content=source.read_bytes()
    digest=hashlib.sha256(content).hexdigest();key='temporary-official-positive-only'
    monkeypatch.setenv('CASH_MODE','synthetic_test');monkeypatch.setenv('CASH_ENGINE','baseline')
    monkeypatch.setenv('CASH_PRIVATE',str(tmp_path/'official-service'))
    monkeypatch.setenv('CASH_API_KEY',key+',temporary-official-other-owner');monkeypatch.setenv('CASH_TEST_HASHES',digest)
    monkeypatch.delenv('CASH_TEST_DELAY_SEC',raising=False);headers={'X-API-Key':key}
    with TestClient(create_app()) as client:
        for h in [{},{'X-API-Key':'invalid-temporary-key'}]:
            assert client.post('/api/v1/analyze',headers=h,files={'file':('safe.mov',content)}).status_code==401
        response=client.post('/api/v1/analyze',headers=headers,files={'file':('arbitrary-synthetic-name.mov',content)})
        assert response.status_code==200 and set(response.json())=={'job_id'};job=response.json()['job_id']
        until=time.monotonic()+10
        while True:
            response=client.get('/api/v1/jobs/'+job,headers=headers);assert response.status_code==200;value=response.json()
            if value['status']!='processing':break
            assert time.monotonic()<until;time.sleep(.02)
        result=Done.model_validate(value)
        assert result.verdict=='violation' and len(result.violations)==1
        assert set(value)=={'job_id','status','verdict','violations'}
        points=sample(source,[.5,1.,1.5],320);evidence=result.violations[0].evidence_frames
        assert len(evidence)==3 and result.violations[0].timecode_sec==points[1].sec
        for returned,actual in zip(evidence,points):
            buffer=BytesIO();actual.image.save(buffer,'JPEG')
            assert returned.timestamp_sec==actual.sec and base64.b64decode(returned.image_base64,validate=True)==buffer.getvalue()
        assert client.get('/api/v1/jobs/'+job).status_code==401
        assert client.get('/api/v1/jobs/'+job,headers={'X-API-Key':'invalid-temporary-key'}).status_code==401
        assert client.get('/api/v1/jobs/'+job,headers={'X-API-Key':'temporary-official-other-owner'}).status_code==404
        assert client.get('/api/v1/jobs/'+'f'*32,headers=headers).status_code==404
    assert hashlib.sha256(source.read_bytes()).hexdigest()==digest
    out=Path(__file__).resolve().parents[1]/'.private/xclip-positive-plumbing';out.mkdir(exist_ok=True)
    atomic_json(out/'official-safe-summary.json',{'status':'passed','split':'synthetic','generated_media_only':True,
        'actual_synthetic_worker_subprocess':True,'learned_model_run':False,'official_positive_contract_validated':True,
        'actual_source_jpegs_verified':3,'source_pts_and_event_time_verified':True,'auth_and_owner_isolation_passed':True,
        'source_unchanged':True,'bank_detection_or_evidence_relevance_claim':False})
