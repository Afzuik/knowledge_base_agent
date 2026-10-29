import pytest
from fastapi.testclient import TestClient
from app.config import Settings
from app.main import create_app


@pytest.fixture
def config(tmp_path):
    return Settings(project_root=tmp_path, data_root=tmp_path / 'data', max_upload_bytes=1024 * 1024)


@pytest.fixture
def client(config):
    with TestClient(create_app(config, run_worker=False)) as c:
        yield c
