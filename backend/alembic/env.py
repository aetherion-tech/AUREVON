"""Use the same database setting as the application, without logging secrets."""

from alembic import context
from app.config import Settings
from app.db.models import Base
from app.db.session import database_engine

engine = database_engine(Settings().database_url)
try:
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=Base.metadata)
        with context.begin_transaction():
            context.run_migrations()
finally:
    engine.dispose()
