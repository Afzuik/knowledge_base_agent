"""SQLAlchemy connection factory; import has no filesystem/DB side effects.

Schema initialization and migrations are pending. No tables are created yet.
"""
from sqlalchemy import create_engine

from app.config import settings


def build_engine():
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    return create_engine(
        f"sqlite:///{settings.database_path}",
        connect_args={"check_same_thread": False},
    )
