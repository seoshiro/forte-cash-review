from io import BytesIO
import json,hashlib,time,base64
import pytest
from PIL import Image
from fastapi.testclient import TestClient
from cashreview.api import create_app
KEY='temporary-review-test-only';OTHER='temporary-review-other-owner'
HEADERS={'X-API-Key':KEY};JOB='a'*32
def seed(private,context='limited',done=True):
    folder=private/'jobs'/JOB;folder.mkdir(parents=True,exist_ok=True)
    (folder/'meta.json').write_text(json.dumps({'owner':hashlib.sha256(KEY.encode()).hexdigest(),'created':time.time()}))
    if not done:return folder
    buffer=BytesIO();Image.new('RGB',(32,32),'green').save(buffer,'JPEG')
    result={'job_id':JOB,'status':'done','verdict':'violation','violations':[{'type':'Искусственный тест',
       'timecode_sec':1.,'description':'Синтетическая проверка API, не банковское событие.',
       'evidence_frames':[{'timestamp_sec':1.,'image_base64':base64.b64encode(buffer.getvalue()).decode()}]}]}
    (folder/'result.json').write_text(json.dumps(result,ensure_ascii=False),encoding='utf-8')
    (folder/'detail.json').write_text(json.dumps({'duration_sec':3.,'events':[{'context':{'status':context,'result':'Синтетический контекст','limitation':'Тест'}}]}),encoding='utf-8')
    return folder

@pytest.fixture
def setup(monkeypatch,tmp_path):
    monkeypatch.setenv('CASH_PRIVATE',str(tmp_path));monkeypatch.setenv('CASH_API_KEY',KEY+','+OTHER)
    return tmp_path

def test_decision_persists_and_does_not_change_competition_result(setup):
    folder=seed(setup);original=(folder/'result.json').read_bytes()
    with TestClient(create_app()) as client:
        baseline=client.get('/api/v1/jobs/'+JOB,headers=HEADERS).json()
        for decision in ['confirmed','rejected','insufficient_data']:
            response=client.put(f'/api/ui/jobs/{JOB}/reviews/0',headers=HEADERS,json={'decision':decision,'note':'Тестовая заметка'})
            assert response.status_code==200 and response.json()['reviews']['0']['decision']==decision
            assert client.get('/api/v1/jobs/'+JOB,headers=HEADERS).json()==baseline
            assert (folder/'result.json').read_bytes()==original
        assert set(baseline)=={'job_id','status','verdict','violations'}
    with TestClient(create_app()) as client:
        state=client.get(f'/api/ui/jobs/{JOB}/reviews',headers=HEADERS).json()
        assert state['reviews']['0']['decision']=='insufficient_data'
        assert state['reviews']['0']['note']=='Тестовая заметка'
    assert json.loads((folder/'reviews.json').read_text(encoding='utf-8'))['training_use'] is False

def test_no_notification_or_decision_before_analysis_and_context_finish(setup):
    with TestClient(create_app()) as client:
        seed(setup,done=False)
        state=client.get(f'/api/ui/jobs/{JOB}/reviews',headers=HEADERS).json()
        assert not state['ready'] and state['notification'] is None
        assert client.put(f'/api/ui/jobs/{JOB}/reviews/0',headers=HEADERS,json={'decision':'confirmed'}).status_code==409
        seed(setup,context='pending')
        (setup/'jobs'/JOB/'detail.json').unlink()
        state=client.get(f'/api/ui/jobs/{JOB}/reviews',headers=HEADERS).json()
        assert not state['ready'] and state['notification'] is None
        seed(setup,context='pending')
        state=client.get(f'/api/ui/jobs/{JOB}/reviews',headers=HEADERS).json()
        assert not state['ready'] and state['notification'] is None
        assert client.put(f'/api/ui/jobs/{JOB}/reviews/0',headers=HEADERS,json={'decision':'confirmed'}).status_code==409
        seed(setup,context='limited')
        state=client.get(f'/api/ui/jobs/{JOB}/reviews',headers=HEADERS).json()
        assert state['ready'] and state['contexts'][0]['status']=='limited'
        assert state['notification']['unreviewed_count']==1

def test_decisions_are_owner_isolated_and_bound_to_original_prediction(setup):
    folder=seed(setup)
    with TestClient(create_app()) as client:
        assert client.get(f'/api/ui/jobs/{JOB}/reviews',headers={'X-API-Key':OTHER}).status_code==404
        assert client.put(f'/api/ui/jobs/{JOB}/reviews/0',headers={'X-API-Key':OTHER},json={'decision':'confirmed'}).status_code==404
        assert client.put(f'/api/ui/jobs/{JOB}/reviews/9',headers=HEADERS,json={'decision':'confirmed'}).status_code==404
        assert client.put(f'/api/ui/jobs/{JOB}/reviews/0',headers=HEADERS,json={'decision':'no_violation'}).status_code==422
        assert client.put(f'/api/ui/jobs/{JOB}/reviews/0',headers=HEADERS,json={'decision':'confirmed'}).status_code==200
        (folder/'result.json').write_text((folder/'result.json').read_text(encoding='utf-8')+' ',encoding='utf-8')
        assert client.get(f'/api/ui/jobs/{JOB}/reviews',headers=HEADERS).status_code==409
