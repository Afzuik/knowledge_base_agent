from fastapi.testclient import TestClient

from app.config import settings
from app.application.identity import get_local_owner_id
from app.main import create_app


def test_health_is_liveness_not_business_readiness():
    with TestClient(create_app()) as client:
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json() == {
            "status": "ok", "stage": "scaffold",
            "mode": "local-single-user", "business_ready": False,
        }


def test_pending_endpoints_do_not_claim_success():
    with TestClient(create_app()) as client:
        for path in ["notebooks", "sources", "chat", "notes"]:
            assert client.get(f"/api/{path}").status_code == 404


def test_storage_paths_are_separate_from_legacy_and_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert settings.data_dir == settings.project_root / "data"
    assert settings.vector_dir != settings.project_root / "chroma_db"
    assert settings.uploads_dir != settings.project_root / "docs"


def test_identity_is_explicitly_local_only():
    assert get_local_owner_id() == "local-demo"


def test_missing_frontend_build_is_explicit(tmp_path, monkeypatch):
    from types import SimpleNamespace
    import app.main as main

    monkeypatch.setattr(main, "settings", SimpleNamespace(frontend_dist=tmp_path))
    with TestClient(main.create_app()) as client:
        response = client.get("/")
        assert response.status_code == 503
        assert response.json()["health_url"] == "/api/health"


def test_built_frontend_and_assets_are_served(tmp_path, monkeypatch):
    from types import SimpleNamespace
    import app.main as main

    (tmp_path / "index.html").write_text('<div id="root"></div>')
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "test.js").write_text("/* test asset */")
    monkeypatch.setattr(main, "settings", SimpleNamespace(frontend_dist=tmp_path))
    with TestClient(main.create_app()) as client:
        assert client.get("/").text == '<div id="root"></div>'
        assert client.get("/assets/test.js").status_code == 200
        assert client.get("/api/nonexistent").status_code == 404
