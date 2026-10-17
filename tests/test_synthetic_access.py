from fastapi.testclient import TestClient
from cashreview.local_secrets import save
from scripts.serve_synthetic_access import create_origin


def test_synthetic_origin_only_exposes_own_app_and_authenticates_all_api(tmp_path,monkeypatch):
    for name in ['CASH_MODE','CASH_ENGINE','CASH_PRIVATE','CASH_API_KEY','CASH_JOB_BUDGET_SEC','CASH_TEST_HASHES','CASH_TEST_DELAY_SEC',
        'HF_HUB_OFFLINE','TRANSFORMERS_OFFLINE','HF_HUB_DISABLE_TELEMETRY','DO_NOT_TRACK']:
        monkeypatch.setenv(name,'temporary-unit-test')
    save(tmp_path/'credentials.dpapi',{'purpose':'synthetic-infrastructure-only','primary':'temporary-unit-primary-only','other_owner':'temporary-unit-other-only'})
    app=create_origin(tmp_path,'synthetic-unit-session')
    with TestClient(app) as client:
        assert client.get('/healthz').json()=={'mode':'synthetic_test','purpose':'infrastructure_only','session':'synthetic-unit-session'}
        assert client.get('/').status_code==200
        assert 'temporary-unit-primary-only' not in client.get('/').text
        for path in ['/api/v1/analyze','/api/v1/jobs/'+'0'*32,'/api/ui/jobs/'+'0'*32+'/detail','/api/arbitrary']:
            assert client.get(path).status_code==401
            assert client.get(path,headers={'X-API-Key':'incorrect'}).status_code==401
        headers={'X-API-Key':'temporary-unit-primary-only'}
        assert client.get('/api/v1/jobs/'+'0'*32,headers=headers).status_code==404
        for path in ['/.git/HEAD','/.private/credentials.dpapi','/.env','/openapi.json','/docs','/api/experimental/xclip/analyze']:
            assert client.get(path,headers=headers).status_code==404
