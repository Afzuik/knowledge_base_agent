"""Versioned migration, applied once at startup, never during requests.

SQLite user_version records schema version without adding a fifth application table.
"""
from pathlib import Path


def migrate(engine):
    with engine.connect() as conn:
        conn.exec_driver_sql("BEGIN IMMEDIATE")
        try:
            version = conn.exec_driver_sql("PRAGMA user_version").scalar_one()
            if version not in (0, 1):
                raise RuntimeError(f"Unsupported database schema version: {version}")
            if version == 0:
                tables = conn.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").all()
                if tables:
                    raise RuntimeError("Refusing to initialize an unversioned non-empty database")
                sql = (Path(__file__).parent / "migrations/001_initial.sql").read_text()
                for statement in sql.split(";"):
                    if statement.strip():
                        conn.exec_driver_sql(statement)
                conn.exec_driver_sql("PRAGMA user_version=1")
            conn.commit()
        except Exception:
            conn.rollback()
            raise
