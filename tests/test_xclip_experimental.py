"""Code/synthetic tests only; no real features, models or bank media loaded."""
from pathlib import Path
from io import BytesIO
import json,base64,time,hashlib,importlib.metadata as metadata
import numpy as np
import pytest
from PIL import Image
from fastapi.testclient import TestClient
from xclip_candidate.experimental import BinaryResearchResult,load_prototypes,sha,FROZEN_INPUTS,ROOT
from xclip_candidate.evaluate import score_video
from cashreview.api import create_app
KEY='temporary-experimental-contract-only';HEADERS={'X-API-Key':KEY};JOB='c'*32


def result(job=JOB):
    data=BytesIO();Image.new('RGB',(8,8),'gray').save(data,'JPEG')
    return BinaryResearchResult(job_id=job,binary_decision='violation',decision_margin=.2,duration_sec=2.,elapsed_engine_sec=.1,
        candidate_timecode_sec=1.,candidate_frames=[{'timestamp_sec':1.,'image_base64':base64.b64encode(data.getvalue()).decode('ascii')}]).model_dump()


def setup(tmp_path,monkeypatch):
    private=tmp_path/'service';monkeypatch.setenv('CASH_PRIVATE',str(private));monkeypatch.setenv('CASH_MODE','xclip_experimental')
    monkeypatch.setenv('CASH_ENGINE','xclip_experimental');monkeypatch.setenv('CASH_API_KEY',KEY+',temporary-other-owner')
    return private


def seed(private,payload):
    folder=private/'jobs'/JOB;folder.mkdir(parents=True)
    (private/'.api-store-contract.json').write_text(json.dumps({'contract':'xclip-experimental-v1'}))
    (folder/'meta.json').write_text(json.dumps({'owner':hashlib.sha256(KEY.encode()).hexdigest(),'created':time.time()}))
    (folder/'experimental-result.json').write_text(json.dumps(payload));return folder


def test_binary_positive_never_implies_verified_type_or_rule():
    value=result();assert value['event_type_status']=='unverified' and value['rule_application_status']=='not_assessed'
    assert value['release_eligible'] is False and 'violations' not in value and 'verdict' not in value
    for change in [{'event_type_status':'verified'},{'release_eligible':True},{'binary_decision':'no_violation'},
        {'candidate_timecode_sec':1.5},{'candidate_frames':[]}]:
        with pytest.raises(ValueError):BinaryResearchResult.model_validate({**value,**change})


def test_experimental_routes_are_authenticated_isolated_and_contract_fails_closed(tmp_path,monkeypatch):
    private=setup(tmp_path,monkeypatch);seed(private,result())
    with TestClient(create_app()) as client:
        assert client.get('/healthz').json()['mode']=='xclip_experimental'
        assert client.get('/api/experimental/xclip/jobs/'+JOB).status_code==401
        data=client.get('/api/experimental/xclip/jobs/'+JOB,headers=HEADERS).json()
        assert data['binary_decision']=='violation' and data['event_type_status']=='unverified'
        assert client.get('/api/experimental/xclip/jobs/'+JOB,headers={'X-API-Key':'temporary-other-owner'}).status_code==404
        assert client.get('/api/experimental/xclip/jobs/'+'f'*32,headers=HEADERS).status_code==404
        assert client.post('/api/v1/analyze',headers=HEADERS).status_code==503
        assert client.get('/api/v1/jobs/'+JOB,headers=HEADERS).status_code==503
        assert client.get('/api/ui/jobs/'+JOB+'/detail',headers=HEADERS).status_code==503


def test_invalid_experimental_result_fails_not_negative(tmp_path,monkeypatch):
    private=setup(tmp_path,monkeypatch);seed(private,{**result(),'event_type_status':'verified'})
    with TestClient(create_app()) as client:
        assert client.get('/api/experimental/xclip/jobs/'+JOB,headers=HEADERS).json()=={'job_id':JOB,'status':'failed'}


def test_experimental_upload_polls_separate_result_and_filters_credentials(tmp_path,monkeypatch):
    import cashreview.api as api
    private=setup(tmp_path,monkeypatch);captured={}
    class Process:
        pid=2147483647;returncode=0
        async def wait(self):return 0
    async def spawn(*args,**kwargs):
        captured.update(kwargs['env']);folder=Path(args[-1]);(folder/'experimental-result.json').write_text(json.dumps(result(folder.name)))
        return Process()
    monkeypatch.setattr(api.asyncio,'create_subprocess_exec',spawn)
    monkeypatch.setenv('OPENAI_API_KEY','temporary-never-forward')
    with TestClient(create_app()) as client:
        response=client.post('/api/experimental/xclip/analyze',headers=HEADERS,files={'file':('renamed-synthetic.mov',b'fake transport bytes; no model run')})
        assert response.status_code==200 and set(response.json())=={'job_id'}
        job=response.json()['job_id'];deadline=time.monotonic()+3
        while time.monotonic()<deadline:
            data=client.get('/api/experimental/xclip/jobs/'+job,headers=HEADERS).json()
            if data['status']!='processing':break
            time.sleep(.01)
        assert data['status']=='done' and data['event_type_status']=='unverified'
        assert 'CASH_API_KEY' not in captured and 'OPENAI_API_KEY' not in captured
        assert float(captured['CASH_WORKER_DEADLINE_MONOTONIC'])>time.monotonic()
        assert not (private/'jobs'/job/'result.json').exists()


def test_binary_engine_cannot_be_enabled_through_normal_mode(tmp_path,monkeypatch):
    setup(tmp_path,monkeypatch);monkeypatch.setenv('CASH_MODE','model')
    with pytest.raises(RuntimeError):create_app()


def test_normal_service_does_not_expose_experimental_routes(tmp_path,monkeypatch):
    setup(tmp_path,monkeypatch);monkeypatch.setenv('CASH_MODE','synthetic_test');monkeypatch.setenv('CASH_ENGINE','baseline')
    with TestClient(create_app()) as client:
        assert client.get('/api/experimental/xclip/jobs/'+JOB,headers=HEADERS).status_code==404


def test_store_contract_cannot_be_switched_or_corrupt_other_mode_jobs(tmp_path,monkeypatch):
    private=setup(tmp_path,monkeypatch);folder=seed(private,result());before=(folder/'experimental-result.json').read_bytes()
    monkeypatch.setenv('CASH_MODE','synthetic_test');monkeypatch.setenv('CASH_ENGINE','baseline')
    with pytest.raises(RuntimeError,match='different API contract'):
        with TestClient(create_app()):pass
    assert (folder/'experimental-result.json').read_bytes()==before and not (folder/'failed').exists()


def synthetic_pack(tmp_path,monkeypatch):
    import xclip_candidate.experimental as experimental
    root=tmp_path/'source';root.mkdir();monkeypatch.setattr(experimental,'ROOT',root)
    for name in FROZEN_INPUTS:
        path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('synthetic public source')
    directory=root/experimental.MODEL_DIRECTORY;directory.mkdir(parents=True)
    for name in experimental.MODEL_FILES:(directory/name).write_text('synthetic artifact')
    pack=tmp_path/'pack';pack.mkdir()
    positive=np.zeros(512,dtype=np.float32);positive[0]=1;negative=np.zeros(512,dtype=np.float32);negative[1]=1
    np.savez_compressed(pack/'prototypes.npz',positive=positive,negative=negative)
    record={'schema_version':2,'arm':'ordered','pooling':'max','threshold':0.0,'release_eligible':False,'prototype_sha256':sha(pack/'prototypes.npz'),
        'encoder_artifact_sha256':experimental.encoder_artifacts(),
        'frozen_code_sha256':{name:sha(root/name) for name in FROZEN_INPUTS},'versions':{name:metadata.version(name) for name in ['torch','transformers','numpy','av']}}
    (pack/'prototypes.json').write_text(json.dumps(record));return pack,directory,positive,negative


def test_content_only_score_and_private_pack_integrity(tmp_path,monkeypatch):
    pack,directory,positive,negative=synthetic_pack(tmp_path,monkeypatch)
    features=np.stack([negative,positive]);times=np.array([1.,2.]);score,sec=score_video(features,times,positive,negative,'max')
    assert score==1 and sec==2
    p,n=load_prototypes(pack)
    assert np.array_equal(p,positive) and np.array_equal(n,negative)
    with (pack/'prototypes.npz').open('ab') as stream:stream.write(b'changed')
    with pytest.raises(ValueError):load_prototypes(pack)


@pytest.mark.parametrize('name',['config.json','preprocessor_config.json','provenance.json','model.safetensors'])
def test_mutable_encoder_inputs_cannot_change_upload_embeddings_silently(tmp_path,monkeypatch,name):
    pack,directory,_,_=synthetic_pack(tmp_path,monkeypatch);(directory/name).write_text('changed')
    with pytest.raises(ValueError,match='encoder artifacts changed'):load_prototypes(pack)


def test_added_alternate_processor_config_is_rejected(tmp_path,monkeypatch):
    pack,directory,_,_=synthetic_pack(tmp_path,monkeypatch);(directory/'processor_config.json').write_text('{}')
    with pytest.raises(ValueError,match='artifact inventory'):load_prototypes(pack)
