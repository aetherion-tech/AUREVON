"""Operations schema migration preserves existing durable financial evidence."""

from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from alembic import command


def test_operations_upgrade_and_downgrade_preserve_ledger(tmp_path, monkeypatch):
    url = f"sqlite:///{(tmp_path / 'migration.db').as_posix()}"
    monkeypatch.setenv("DATABASE_URL", url)
    config = Config("alembic.ini")
    command.upgrade(config, "0011_domain_api")
    engine = create_engine(url)
    with engine.begin() as connection:
        connection.execute(
            text("CREATE TABLE retained_evidence (amount TEXT NOT NULL)")
        )
        connection.execute(text("INSERT INTO retained_evidence VALUES ('100000.01')"))
    command.upgrade(config, "0012_operations")
    assert {"pnl_ticks", "shadow_receipts"} <= set(inspect(engine).get_table_names())
    with engine.connect() as connection:
        assert (
            connection.execute(
                text("SELECT amount FROM retained_evidence")
            ).scalar_one()
            == "100000.01"
        )
    command.downgrade(config, "0011_domain_api")
    assert not (
        {"pnl_ticks", "shadow_receipts"} & set(inspect(engine).get_table_names())
    )
    with engine.connect() as connection:
        assert (
            connection.execute(
                text("SELECT amount FROM retained_evidence")
            ).scalar_one()
            == "100000.01"
        )
    engine.dispose()
