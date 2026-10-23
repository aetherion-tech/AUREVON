"""Create connections only; schema changes are managed with Alembic."""

from pathlib import Path

from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import make_url


def database_engine(url: str) -> Engine:
    parsed = make_url(url)
    if parsed.get_backend_name() == "sqlite":
        if parsed.database and parsed.database != ":memory:":
            Path(parsed.database).parent.mkdir(parents=True, exist_ok=True)
        return create_engine(url, connect_args={"check_same_thread": False})
    return create_engine(url)
