"""Create connections only; schema changes are managed with Alembic."""

from pathlib import Path
from sqlite3 import Connection

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.pool import StaticPool


def database_engine(url: str) -> Engine:
    parsed = make_url(url)
    if parsed.get_backend_name() == "sqlite":
        if parsed.database and parsed.database != ":memory:":
            Path(parsed.database).parent.mkdir(parents=True, exist_ok=True)
        if parsed.database in (None, "", ":memory:"):
            return create_engine(
                url, connect_args={"check_same_thread": False}, poolclass=StaticPool
            )
        engine = create_engine(url, connect_args={"check_same_thread": False})

        @event.listens_for(engine, "connect")
        def durable_wal(connection: Connection, _: object) -> None:
            # File databases are local to the paper application. Keep every commit
            # durable; NORMAL/OFF would make a cheaper but weaker benchmark.
            cursor = connection.cursor()
            try:
                mode = cursor.execute("PRAGMA journal_mode=WAL").fetchone()
                if not mode or mode[0].lower() != "wal":
                    raise RuntimeError("Local SQLite database requires WAL mode")
                cursor.execute("PRAGMA synchronous=FULL")
            finally:
                cursor.close()

        return engine
    return create_engine(url)
