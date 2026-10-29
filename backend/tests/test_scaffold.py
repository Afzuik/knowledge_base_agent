from fastapi.testclient import TestClient
from app.config import settings
from app.application.identity import get_local_owner_id
from app.main import create_app


def test_health_distinguishes_ingestion_from_qa(client, config):
    response = client.get('/api/health')
    assert response.status_code == 200
    body = response.json()
    assert body['stage'] == 'research' and body['ingestion_ready'] is True
    assert body['qa_ready'] is False and body['business_ready'] is False
    assert body['max_upload_bytes'] == config.max_upload_bytes
    assert body['model_services']['llm']['configured'] is False



def test_no_unscoped_qa_or_notes_routes(client):
    for path in ['chat', 'notes']:
        assert client.get(f'/api/{path}').status_code == 404


def test_paths_do_not_depend_on_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert settings.vector_dir != settings.project_root / 'chroma_db'
    assert settings.uploads_dir != settings.project_root / 'docs'


def test_local_identity():
    assert get_local_owner_id() == 'local-demo'


def test_missing_frontend_is_explicit(client):
    response = client.get('/')
    assert response.status_code == 503
    assert response.json()['health_url'] == '/api/health'


def test_static_frontend(config):
    config.frontend_dist.mkdir(parents=True)
    (config.frontend_dist / 'index.html').write_text('<div id="root"></div>')
    (config.frontend_dist / 'assets').mkdir()
    (config.frontend_dist / 'assets' / 'test.js').write_text('/* test */')
    with TestClient(create_app(config, run_worker=False)) as c:
        assert c.get('/').text == '<div id="root"></div>'
        assert c.get('/assets/test.js').status_code == 200
        assert c.get('/api/nonexistent').status_code == 404
