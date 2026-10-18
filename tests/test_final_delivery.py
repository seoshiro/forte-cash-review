import copy,time
import pytest
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.responses import JSONResponse
from starlette.testclient import TestClient
from cashreview.final_delivery import FinalOrigin,validate_session


def record(now=100.):return {'purpose':'jury-experimental-prototype','jury':'a'*64,'operator':'b'*64,'other_owner':'c'*64,'issued_unix':now-1,'expires_unix':now+60}


def test_session_enforces_expiry_distinct_keys_and_24h_maximum():
    good=record();assert validate_session(good,100.)==good
    for key,value in [('expires_unix',100.),('expires_unix',100.+24*3600),('expires_unix',float('inf')),('issued_unix',101.),('operator','a'*64),('purpose','permanent')]:
        bad=copy.deepcopy(good);bad[key]=value
        with pytest.raises(ValueError):validate_session(bad,100.)


def test_live_jury_revocation_does_not_change_operator_or_result(tmp_path):
    clock=[100.]
    async def reply(request):return JSONResponse({'job_id':'a'*32,'status':'failed'})
    app=FinalOrigin(Starlette(routes=[Route('/api/experimental/xclip/jobs/{job}',reply)]),record(),tmp_path,lambda:clock[0])
    with TestClient(app) as client:
        path='/api/v1/jobs/'+'a'*32;jury={'X-API-Key':'a'*64};operator={'X-API-Key':'b'*64}
        assert client.get(path,headers=jury).json()['status']=='failed'
        (tmp_path/'revoke-jury.request').touch()
        assert client.get(path,headers=jury).status_code==401
        assert client.get(path,headers=operator).status_code==200
        assert client.get('/healthz').json()['jury_key_revoked'] is True
        clock[0]=160.
        assert client.get(path,headers=operator).status_code==503


def test_final_ui_discloses_available_experimental_api_without_changing_frozen_page(tmp_path):
    app=FinalOrigin(Starlette(),record(),tmp_path,lambda:100.)
    with TestClient(app) as client:
        response=client.get('/')
        assert response.status_code==200 and 'Экспериментальный API доступен' in response.text
        assert 'Конкурсный API в этом режиме отключён' not in response.text
        assert response.headers['Cache-Control']=='no-store' and "frame-ancestors 'none'" in response.headers['Content-Security-Policy']
        stylesheet=client.get('/static/style.css');assert stylesheet.status_code==200 and stylesheet.headers['content-type'].startswith('text/css')
        assert client.get('/static/app.js').status_code==404
