"""Release routing and immutable, WAL-consistent backup/restore evidence."""

import gzip
import hashlib
import json
import sqlite3
from datetime import date, datetime

import pytest
from fastapi.testclient import TestClient

from app.broker.kite_auth import IST
from app.config import BACKEND_DIR, Settings
from app.db.models import Base
from app.db.session import database_engine
from app.main import create_app
from app.market.exchange_calendar import ExchangeCalendar
from app.market.lifecycle_state import ProcessLease
from app.market.maintenance import nightly
from app.tools.backup import backup, inspect_database, restore
from app.tools.retention import compress_sealed, expired_pnl_ticks


def test_built_dashboard_routes_and_missing_assets(tmp_path):
    build = tmp_path / "dist"
    build.mkdir()
    (build / "index.html").write_text("<html>release-dashboard</html>")
    (build / "assets").mkdir()
    (build / "assets" / "app.js").write_text("// release chunk")
    app = create_app(
        Settings(
            _env_file=None,
            dashboard_frontend_dir=build,
            database_url=f"sqlite:///{(tmp_path / 'test.db').as_posix()}",
            market_lock_file=tmp_path / "owner.lock",
        )
    )
    with TestClient(app, base_url="https://testserver") as client:
        for route in ("", "history", "wallet", "settings", "live"):
            reply = client.get("/dashboard/" + route, headers={"Accept": "text/html"})
            assert reply.status_code == 200
            assert "release-dashboard" in reply.text
            assert reply.headers["cache-control"] == "no-store"
        assert (
            client.head(
                "/dashboard/settings", headers={"Accept": "text/html"}
            ).status_code
            == 200
        )
        assert client.get("/").url.path == "/dashboard/"
        assert client.get("/dashboard/assets/app.js").status_code == 200
        for route in ("assets/missing.js", ".env", "api/missing", "ws/missing"):
            assert (
                client.get(
                    "/dashboard/" + route, headers={"Accept": "text/html"}
                ).status_code
                == 404
            )
        assert (
            client.get(
                "/dashboard/unknown", headers={"Accept": "application/json"}
            ).status_code
            == 404
        )
        assert (
            client.get("/api/not-a-route", headers={"Accept": "text/html"}).status_code
            == 404
        )
        assert client.get("/api/health").json()["mode"] == "PAPER"
        assert client.get("/api/wallet").status_code == 401


def test_backup_restores_committed_wal_and_refuses_overwrite_or_tamper(tmp_path):
    source = tmp_path / "source.db"
    with sqlite3.connect(source) as db:
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("CREATE TABLE ledger (id INTEGER PRIMARY KEY, paise INTEGER)")
        db.execute("INSERT INTO ledger VALUES (1, 10001)")
        db.commit()
        saved = tmp_path / "backup.db"
        report = backup(source, saved)
        assert report["rows"] == {"ledger": 1}
        copied = tmp_path / "restore.db"
        assert restore(saved, copied)["rows"] == report["rows"]
        assert inspect_database(copied)["rows"] == report["rows"]
        with pytest.raises(FileExistsError):
            restore(saved, source)
        with sqlite3.connect(saved) as changed:
            changed.execute("UPDATE ledger SET paise=0")
        with pytest.raises(ValueError, match="manifest"):
            restore(saved, tmp_path / "bad.db")
        assert not (tmp_path / "bad.db").exists()


def test_retention_requires_seal_validates_hash_and_preserves_original(tmp_path):
    run = tmp_path / "run"
    run.mkdir()
    raw = run / "2026-10-28.jsonl"
    raw.write_bytes(b'{"sequence":0}\n')
    assert compress_sealed(tmp_path, date(2026, 10, 30), apply=True) == []
    (run / "SEALED.json").write_text(
        json.dumps({"sha256": {raw.name: hashlib.sha256(raw.read_bytes()).hexdigest()}})
    )
    assert compress_sealed(tmp_path, date(2026, 10, 30))
    assert not raw.with_suffix(".jsonl.gz").exists()
    assert compress_sealed(tmp_path, date(2026, 10, 30), apply=True)
    assert (
        gzip.decompress(raw.with_suffix(".jsonl.gz").read_bytes()) == raw.read_bytes()
    )
    assert compress_sealed(tmp_path, date(2026, 10, 30), apply=True) == []
    raw.write_bytes(b"changed")
    with pytest.raises(ValueError, match="manifest"):
        compress_sealed(tmp_path, date(2026, 10, 30), apply=True)
    assert expired_pnl_ticks(date(2026, 10, 30), date(2026, 7, 31))
    assert not expired_pnl_ticks(date(2026, 10, 30), date(2026, 8, 1))


@pytest.mark.parametrize("with_wallet", [False, True])
def test_nightly_waits_until_close_and_restores_to_separate_database(
    tmp_path, with_wallet
):
    engine = database_engine(f"sqlite:///{(tmp_path / 'source.db').as_posix()}")
    Base.metadata.create_all(engine)
    calendar = ExchangeCalendar(BACKEND_DIR / "app" / "market" / "calendars")
    if with_wallet:
        from app.wallet.service import WalletService

        WalletService(engine, calendar).initialize(
            datetime(2026, 10, 29, 10, 0, tzinfo=IST)
        )
    backups = tmp_path / "backups"
    recordings = tmp_path / "ticks"
    run = recordings / "closed"
    run.mkdir(parents=True)
    raw = run / "2026-10-27.jsonl"
    raw.write_bytes(b'{"sequence":0}\n')
    (run / "SEALED.json").write_text(
        json.dumps({"sha256": {raw.name: hashlib.sha256(raw.read_bytes()).hexdigest()}})
    )
    assert not nightly(
        engine, calendar, backups, datetime(2026, 10, 29, 15, 30, tzinfo=IST)
    )
    assert nightly(
        engine,
        calendar,
        backups,
        datetime(2026, 10, 29, 16, 0, tzinfo=IST),
        recordings=recordings,
    )
    assert raw.exists() and raw.with_suffix(".jsonl.gz").exists()
    assert not nightly(
        engine, calendar, backups, datetime(2026, 10, 29, 16, 1, tzinfo=IST)
    )
    source = backups / "2026-10-29" / "paper.db"
    assert (
        restore(source, tmp_path / "restored.db")["rows"]
        == inspect_database(source)["rows"]
    )
    engine.dispose()


def test_release_owner_lease_rejects_duplicate_and_releases_on_stop(tmp_path):
    first = ProcessLease(tmp_path / "https.lock")
    second = ProcessLease(tmp_path / "https.lock")
    first.acquire()
    try:
        with pytest.raises(RuntimeError, match="owner"):
            second.acquire()
    finally:
        first.release()
    second.acquire()
    second.release()


def test_scm_stop_requests_graceful_uvicorn_shutdown():
    import threading
    from types import SimpleNamespace
    from unittest.mock import Mock

    from app.tools.windows_service import AurevonService

    service = object.__new__(AurevonService)
    service.stopping = threading.Event()
    service.http = SimpleNamespace(should_exit=False)
    service.ReportServiceStatus = Mock()
    service.SvcStop()
    assert service.stopping.is_set()
    assert service.http.should_exit
    service.ReportServiceStatus.assert_called_once()


def test_https_runner_checks_build_tls_and_rejects_foreign_host(tmp_path, monkeypatch):
    from app.tools import serve

    backend = tmp_path / "backend"
    backend.mkdir()
    frontend = tmp_path / "frontend"
    build = frontend / "dist"
    build.mkdir(parents=True)
    tls = frontend / ".local-tls"
    tls.mkdir()
    monkeypatch.setattr(serve, "BACKEND_DIR", backend)
    with pytest.raises(ValueError, match="Build frontend"):
        serve.server()
    (build / "index.html").write_text("<html>built</html>")
    for name in ("localhost-key.pem", "localhost-cert.pem"):
        (tls / name).write_text("fixture-presence-only")
    config = Settings(
        _env_file=None,
        database_url=f"sqlite:///{(tmp_path / 'runner.db').as_posix()}",
        market_lock_file=tmp_path / "market.lock",
        dashboard_frontend_dir=build,
    )
    monkeypatch.setattr(serve, "Settings", lambda **kwargs: config)
    http = serve.server()
    assert http.config.host == "127.0.0.1" and http.config.port == 8443
    assert http.config.workers == 1 and not http.config.proxy_headers
    with TestClient(http.config.app, base_url="https://127.0.0.1:8443") as client:
        assert client.get("/api/health").status_code == 200
        assert (
            client.get("/dashboard/", headers={"Host": "evil.example"}).status_code
            == 400
        )
