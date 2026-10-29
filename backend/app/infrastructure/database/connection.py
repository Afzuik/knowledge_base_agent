"""Connection factory. Importing this module does not create a database."""
from sqlalchemy import create_engine, event
from app.config import settings


def build_engine(config=None):
    config = config or settings
    config.data_dir.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{config.database_path}",
        connect_args={"check_same_thread": False, "timeout": 10})

    @event.listens_for(engine, "connect")
    def configure(dbapi, _record):
        dbapi.execute("PRAGMA foreign_keys=ON")
        dbapi.execute("PRAGMA busy_timeout=10000")

    return engine
