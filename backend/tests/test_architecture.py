"""Structural checks only: do not implement or claim business behavior."""

import ast
import importlib
import pkgutil
from pathlib import Path
from types import SimpleNamespace

import pytest

import app
from app.config import settings


APP_DIR = Path(app.__file__).parent


@pytest.mark.parametrize("layer,forbidden", [
    ("application", ("app.api", "app.main")),
    ("intelligence", ("app.api", "app.application", "app.main")),
    ("infrastructure", ("app.api", "app.application", "app.intelligence", "app.main")),
])
def test_layers_do_not_import_upper_layers(layer, forbidden):
    for path in (APP_DIR / layer).rglob("*.py"):
        module = "app." + ".".join(path.relative_to(APP_DIR).with_suffix("").parts)
        package = module if path.name == "__init__.py" else module.rsplit(".", 1)[0]
        if path.name == "__init__.py":
            package = module.removesuffix(".__init__")
        for node in ast.walk(ast.parse(path.read_text())):
            dependencies = []
            if isinstance(node, ast.Import):
                dependencies = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                base = node.module or ""
                if node.level:
                    base = importlib.util.resolve_name("." * node.level + base, package)
                dependencies = [base, *(base + "." + alias.name for alias in node.names)]
            for dependency in dependencies:
                assert not any(dependency == p or dependency.startswith(p + ".") for p in forbidden), (
                    f"{path}: forbidden upward dependency {dependency}"
                )


def test_old_module_layout_is_removed():
    for relative in ["services", "rag", "api/routes", "database.py", "models.py", "schemas.py"]:
        assert not (APP_DIR / relative).exists(), relative


def test_all_modules_import_without_creating_database(tmp_path, monkeypatch):
    import app.infrastructure.database.connection as connection

    fake = SimpleNamespace(data_dir=tmp_path, database_path=tmp_path / "test.sqlite3")
    monkeypatch.setattr(connection, "settings", fake)
    for module in pkgutil.walk_packages(app.__path__, prefix="app."):
        importlib.import_module(module.name)
    assert not fake.database_path.exists()
    assert settings.project_root == APP_DIR.parents[1]


def test_relocated_connection_factory_uses_configured_path(tmp_path, monkeypatch):
    from sqlalchemy import text
    import app.infrastructure.database.connection as connection

    path = tmp_path / "store" / "test.sqlite3"
    monkeypatch.setattr(connection, "settings", SimpleNamespace(
        data_dir=path.parent, database_path=path,
    ))
    engine = connection.build_engine()
    try:
        with engine.connect() as session:
            assert session.execute(text("SELECT 1")).scalar_one() == 1
            assert session.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).all() == []
        assert path.is_file()
    finally:
        engine.dispose()


def test_api_exposes_ingestion_not_qa():
    from app.main import create_app
    paths = create_app().openapi()['paths']
    assert '/api/notebooks' in paths
    assert '/api/notebooks/{notebook_id}/sources/{source_id}/chunks' in paths
    assert '/api/chat' not in paths and '/api/notes' not in paths
