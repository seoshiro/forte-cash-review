import copy
import pytest
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient
from cashreview.research_delivery import ResearchOrigin,validate_credentials


def test_expiring_gateway_allows_only_research_assets_and_authenticated_api():
    async def reply(request):return JSONResponse({'fixture':True})
    app=Starlette(routes=[Route('/',reply),Route('/static/research.js',reply),Route('/api/experimental/xclip/jobs/{job}',reply),Route('/api/v1/analyze',reply,methods=['POST'])])
    clock=[100.];client=TestClient(ResearchOrigin(app,['test-primary','test-other'],200.,lambda:clock[0]))
    assert client.get('/').status_code==200 and client.get('/healthz').json()['release_eligible'] is False
    job='/api/experimental/xclip/jobs/'+'a'*32
    for headers in [{},{'X-API-Key':'wrong'},[('X-API-Key','test-primary'),('X-API-Key','test-other')]]:
        assert client.get(job,headers=headers).status_code==401
    assert client.get(job,headers={'X-API-Key':'test-primary'}).status_code==200
    assert client.get('/static/app.js').status_code==404
    assert client.get('/api/ui/jobs/'+'a'*32+'/detail',headers={'X-API-Key':'test-primary'}).status_code==404
    assert client.get('/.private/jobs/result.json').status_code==404
    clock[0]=200.
    assert client.get('/').status_code==503 and client.get(job,headers={'X-API-Key':'test-primary'}).status_code==503


def test_credentials_require_distinct_strong_keys_purpose_and_bounded_expiry():
    good={'purpose':'research-prototype-only','primary':'a'*48,'other_owner':'b'*48,'expires_unix':200.}
    assert validate_credentials(good,100.)==good
    for key,value in [('purpose','jury'),('primary','temporary-local-demo-only'),('other_owner','a'*48),('expires_unix',100.),('expires_unix',100.+8*3600+1)]:
        changed=copy.deepcopy(good);changed[key]=value
        with pytest.raises(ValueError):validate_credentials(changed,100.)
