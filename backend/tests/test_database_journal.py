"""Durable file journaling and reader/writer isolation used by paper state."""

import sqlite3

import pytest

from app.db.session import database_engine


def test_file_connections_keep_full_sync_and_wal_after_pool_reconnect(tmp_path):
    engine = database_engine(f"sqlite:///{(tmp_path / 'journal.db').as_posix()}")
    try:
        for _ in range(2):
            with engine.connect() as db:
                assert db.exec_driver_sql("PRAGMA journal_mode").scalar_one() == "wal"
                assert db.exec_driver_sql("PRAGMA synchronous").scalar_one() == 2
            engine.dispose()
    finally:
        engine.dispose()


def test_reader_snapshot_survives_writer_commit_and_rollback(tmp_path):
    path = tmp_path / "journal.db"
    engine = database_engine(f"sqlite:///{path.as_posix()}")
    try:
        with engine.begin() as db:
            db.exec_driver_sql("CREATE TABLE balances (amount TEXT NOT NULL)")
            db.exec_driver_sql("INSERT INTO balances VALUES ('100.01')")
        # A real SQLite read transaction stays open while the other connection
        # commits. The reader must not block or see uncommitted/newer state.
        with sqlite3.connect(path) as reader:
            reader.execute("BEGIN")
            assert (
                reader.execute("SELECT amount FROM balances").fetchone()[0] == "100.01"
            )
            with engine.begin() as writer:
                writer.exec_driver_sql("UPDATE balances SET amount='101.02'")
            assert (
                reader.execute("SELECT amount FROM balances").fetchone()[0] == "100.01"
            )
            reader.rollback()
            assert (
                reader.execute("SELECT amount FROM balances").fetchone()[0] == "101.02"
            )
        with pytest.raises(RuntimeError, match="injected"):
            with engine.begin() as writer:
                writer.exec_driver_sql("UPDATE balances SET amount='0.00'")
                raise RuntimeError("injected rollback")
        with engine.connect() as db:
            assert (
                db.exec_driver_sql("SELECT amount FROM balances").scalar_one()
                == "101.02"
            )
    finally:
        engine.dispose()


def test_in_memory_database_keeps_shared_connection_behavior():
    engine = database_engine("sqlite:///:memory:")
    try:
        with engine.begin() as db:
            db.exec_driver_sql("CREATE TABLE test (value INTEGER)")
            db.exec_driver_sql("INSERT INTO test VALUES (7)")
        with engine.connect() as db:
            assert db.exec_driver_sql("SELECT value FROM test").scalar_one() == 7
            assert db.exec_driver_sql("PRAGMA journal_mode").scalar_one() == "memory"
    finally:
        engine.dispose()
