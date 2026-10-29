"""Versioned migrations; preserve v1 data, back it up before upgrading to v2."""
from pathlib import Path
from uuid import uuid4
import sqlite3


def migrate(engine):
    with engine.connect() as conn:
        version = conn.exec_driver_sql('PRAGMA user_version').scalar_one()
        conn.rollback()
        if version not in (0,1,2):
            raise RuntimeError(f'Unsupported database schema version: {version}')
        if version == 1:
            database = Path(engine.url.database)
            backup = database.with_name(database.name + '.v1-backup-' + uuid4().hex[:8])
            with sqlite3.connect(database) as src, sqlite3.connect(backup) as dest:
                src.backup(dest)
        conn.exec_driver_sql('BEGIN IMMEDIATE')
        try:
            if version == 0:
                tables = conn.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").all()
                if tables: raise RuntimeError('Refusing to initialize an unversioned non-empty database')
            for number, filename in [(1,'001_initial.sql'),(2,'002_research.sql')]:
                if version < number:
                    sql = (Path(__file__).parent / 'migrations' / filename).read_text()
                    for statement in sql.split(';'):
                        if statement.strip(): conn.exec_driver_sql(statement)
                    conn.exec_driver_sql(f'PRAGMA user_version={number}')
            conn.commit()
        except Exception:
            conn.rollback()
            raise
