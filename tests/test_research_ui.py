from fastapi.testclient import TestClient
from cashreview.api import create_app


def test_research_root_serves_honest_separate_ui(tmp_path, monkeypatch):
    monkeypatch.setenv('CASH_PRIVATE', str(tmp_path / 'research'))
    monkeypatch.setenv('CASH_API_KEY', 'temporary-ui-test-only')
    monkeypatch.setenv('CASH_MODE', 'xclip_experimental')
    monkeypatch.setenv('CASH_ENGINE', 'xclip_experimental')
    with TestClient(create_app()) as client:
        page = client.get('/').text
        assert '/static/research.js' in page
        assert 'Тип события и применимость правила не установлены' in page
        assert '/static/app.js' not in page
        assert client.get('/static/research.js').status_code == 200
        assert client.get('/api/v1/jobs/' + '0' * 32, headers={'X-API-Key': 'temporary-ui-test-only'}).status_code == 503


def test_normal_root_keeps_competition_ui(tmp_path, monkeypatch):
    monkeypatch.setenv('CASH_PRIVATE', str(tmp_path / 'normal'))
    monkeypatch.setenv('CASH_API_KEY', 'temporary-ui-test-only')
    monkeypatch.setenv('CASH_MODE', 'synthetic_test')
    monkeypatch.setenv('CASH_ENGINE', 'baseline')
    with TestClient(create_app()) as client:
        assert '/static/app.js' in client.get('/').text
        assert '/static/research.js' not in client.get('/').text
