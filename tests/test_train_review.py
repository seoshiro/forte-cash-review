import hashlib,json
from fastapi.testclient import TestClient
from local_review.app import create_review_app
from scripts.synthetic import generate

def fixture(tmp_path):
    path=generate(tmp_path/'safe.mov');sha=hashlib.sha256(path.read_bytes()).hexdigest()
    rows=[{'split':'train','path':str(path),'sha256':sha,'target':i%2,'label_sec':1. if i%2 else None,'duration_sec':3.} for i in range(8)]
    private=tmp_path/'private';app=create_review_app(rows,private,'temporary-synthetic-review-only','synthetic-registration-only',synthetic=True)
    return TestClient(app),private,path

def test_review_auth_range_and_selected_sources_only(tmp_path):
    client,private,path=fixture(tmp_path)
    with client as c:
        assert c.get('/api/items').status_code==403
        assert c.get('/media/1').status_code==403
        assert c.get('/?token=temporary-synthetic-review-only').status_code==200
        response=c.get('/api/items');items=response.json()['items']
        assert len(items)==8 and items[0]['label_sec'] is None
        assert all('path' not in r and 'sha256' not in r for r in items)
        assert c.get('/media/0').status_code==404 and c.get('/media/9').status_code==404
        response=c.get('/media/1',headers={'Range':'bytes=0-63'})
        assert response.status_code==206 and response.content==path.read_bytes()[:64]
        assert response.headers['cache-control']=='no-store'
        assert c.get('/assets/unknown.txt').status_code==404
        assert c.get('/healthz',headers={'Host':'external.example'}).status_code==400

def test_manual_annotations_separate_atomic_and_unverified(tmp_path):
    client,private,path=fixture(tmp_path);before=hashlib.sha256(path.read_bytes()).hexdigest()
    answers={'label_matches':'unclear','rule_or_type':'Synthetic rule proposal','visibility':'insufficient','comment':'<script>safe literal text</script>','reviewed_time_sec':None}
    with client as c:
        c.get('/?token=temporary-synthetic-review-only');headers={'Origin':'http://testserver'}
        assert c.post('/api/annotations/1',json=answers,headers={'Origin':'https://external.example'}).status_code==403
        assert c.post('/api/annotations/1',json={**answers,'official_target':1},headers=headers).status_code==422
        assert c.post('/api/annotations/1',json={**answers,'reviewed_time_sec':5.},headers=headers).status_code==422
        response=c.post('/api/annotations/1',json=answers,headers=headers)
        assert response.status_code==200 and response.json()['progress']['saved_cases']==1
        saved=json.loads((private/'annotations.json').read_text())['annotations']['1']
        assert saved['official_target']==0 and saved['official_label_sec'] is None
        assert saved['answers']==answers and saved['training_eligible'] is False
        assert saved['status']=='human_proposal_unverified'
        assert c.get('/api/items').json()['items'][0]['annotation']==answers
        assert c.post('/api/annotations/1',json={**answers,'comment':'Synthetic revision'},headers=headers).status_code==200
        assert len((private/'revisions.private.jsonl').read_text().splitlines())==2
    assert hashlib.sha256(path.read_bytes()).hexdigest()==before

def test_no_holdout_or_wrong_size_allowed(tmp_path):
    path=generate(tmp_path/'safe.mov');row={'split':'holdout','path':str(path)}
    import pytest
    with pytest.raises(ValueError):create_review_app([row]*8,tmp_path/'a','test','test',True)
    with pytest.raises(ValueError):create_review_app([],tmp_path/'b','test','test',True)
