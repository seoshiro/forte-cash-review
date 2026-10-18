"""Native API/store integration uses generated result/JPEG only, no inference stub in service."""
import hashlib,json,time
import psutil
from starlette.testclient import TestClient
from cashreview.api import create_app
from cashreview.partial_contract import PartialV1Bridge,UNCLASSIFIED_TYPE
from cashreview.research_delivery import ResearchOrigin
from cashreview.schemas import Done
from test_partial_contract import native,JOB


def test_native_store_owner_isolation_immutable_result_and_technical_failure(tmp_path,monkeypatch):
    private=tmp_path/'store';monkeypatch.setenv('CASH_PRIVATE',str(private));monkeypatch.setenv('CASH_MODE','xclip_experimental')
    monkeypatch.setenv('CASH_ENGINE','xclip_experimental');monkeypatch.setenv('CASH_API_KEY','test-primary,test-other')
    app=ResearchOrigin(PartialV1Bridge(create_app(),True),['test-primary','test-other'],time.time()+60,partial_v1=True)
    with TestClient(app) as client:
        folder=private/'jobs'/JOB;folder.mkdir();created=time.time()
        (folder/'meta.json').write_text(json.dumps({'owner':hashlib.sha256(b'test-primary').hexdigest(),'created':created,'server_pid':psutil.Process().pid,'server_created':psutil.Process().create_time()}))
        payload=json.dumps(native(True));(folder/'experimental-result.json').write_text(payload)
        headers={'X-API-Key':'test-primary'}
        response=client.get('/api/v1/jobs/'+JOB,headers=headers);assert response.status_code==200
        result=Done.model_validate(response.json());assert result.violations[0].type==UNCLASSIFIED_TYPE
        assert client.get('/api/v1/jobs/'+JOB).status_code==401
        assert client.get('/api/v1/jobs/'+JOB,headers={'X-API-Key':'test-other'}).status_code==404
        assert (folder/'experimental-result.json').read_text()==payload and not (folder/'result.json').exists()
        (folder/'failed').write_text('synthetic technical failure')
        failure=client.get('/api/v1/jobs/'+JOB,headers=headers)
        assert failure.json()=={'job_id':JOB,'status':'failed'} and 'verdict' not in failure.json()
