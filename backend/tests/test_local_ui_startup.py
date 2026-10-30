"""Explicit zero-account setup and nontrading local startup; no operator state."""

import asyncio
import json
from datetime import datetime, timezone

import pytest
from auth_helpers import authenticate, password_hash
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.local_owner import initialize_zero_account, wait_for_maintenance
from app.config import Settings
from app.db.models import Base, PaperExecutionBook
from app.execution.models import PaperBook
from app.main import create_app
from app.tools.local_ui_setup import set_local_ui_enabled
from app.wallet.service import WalletService


def configured(tmp_path):
    return Settings(
        _env_file=None,
        local_ui_enabled=True,
        database_url=f"sqlite:///{(tmp_path / 'local.db').as_posix()}",
        dashboard_password_hash=password_hash(),
        market_lock_file=tmp_path / "market.lock",
        local_ui_maintenance_file=tmp_path / "maintenance.json",
        market_record_dir=tmp_path / "ticks",
        kite_session_file=tmp_path / "kite.bin",
    )


def test_zero_wallet_history_restart_and_no_entry_activation(tmp_path):
    settings = configured(tmp_path)
    app = create_app(settings)
    Base.metadata.create_all(app.state.database_engine)
    initialize_zero_account(app.state.domain_service, datetime.now(timezone.utc))
    initialize_zero_account(app.state.domain_service, datetime.now(timezone.utc))
    with TestClient(app, base_url="https://testserver") as client:
        authenticate(client)
        wallet = client.get("/api/wallet")
        assert wallet.status_code == 200 and wallet.json()["initialized"]
        assert wallet.json()["balance"] == "0.00"
        assert client.get("/api/trades").json()["items"] == []
        assert client.get("/api/pnl/summary").status_code == 200
        assert client.get("/api/live/snapshot").json()["entries_enabled"] is False
        assert client.get("/api/mode").json()["entries_enabled"] is False
        assert app.state.market_service.desired is False
        assert app.state.paper_runtime.entries_allowed is False
        assert (
            client.post(
                "/api/wallet/deposit",
                json={"amount": "100.01"},
                headers={"Idempotency-Key": "explicit-paper-deposit"},
            ).status_code
            == 200
        )
    restarted = create_app(settings)
    with TestClient(restarted, base_url="https://testserver") as client:
        authenticate(client)
        assert client.get("/api/wallet").json()["balance"] == "100.01"
        with Session(restarted.state.database_engine) as db:
            book = PaperBook.model_validate_json(
                db.get(PaperExecutionBook, "PAPER").payload
            )
            assert sum(entry.kind == "INITIAL" for entry in book.ledger) == 1
            assert not book.positions


def test_enable_flag_preserves_credentials_and_other_settings(tmp_path):
    path = tmp_path / ".env"
    path.write_text(
        "# retain comment\nKITE_API_SECRET=synthetic-local-only\n"
        "MARKET_SERVICE_ENABLED=false\n"
    )
    set_local_ui_enabled(path)
    set_local_ui_enabled(path)
    text = path.read_text()
    assert "KITE_API_SECRET=synthetic-local-only" in text
    assert "MARKET_SERVICE_ENABLED=false" in text
    assert text.count("LOCAL_UI_ENABLED=true") == 1


def test_interrupted_zero_account_setup_resumes_without_funding(tmp_path, monkeypatch):
    settings = configured(tmp_path)
    app = create_app(settings)
    Base.metadata.create_all(app.state.database_engine)
    original = WalletService.initialize

    def interrupted(self, at):
        raise RuntimeError("synthetic interruption before INITIAL")

    monkeypatch.setattr(WalletService, "initialize", interrupted)
    with pytest.raises(RuntimeError, match="synthetic interruption"):
        initialize_zero_account(app.state.domain_service, datetime.now(timezone.utc))
    monkeypatch.setattr(WalletService, "initialize", original)
    initialize_zero_account(app.state.domain_service, datetime.now(timezone.utc))
    with Session(app.state.database_engine) as db:
        book = PaperBook.model_validate_json(
            db.get(PaperExecutionBook, "PAPER").payload
        )
        assert book.balance == 0 and len(book.ledger) == 1
        assert book.ledger[0].kind == "INITIAL" and book.ledger[0].amount == 0
    app.state.database_engine.dispose()
    app.state.market_service.auth.close()


@pytest.mark.asyncio
async def test_maintenance_acknowledges_before_resuming(tmp_path):
    settings = configured(tmp_path)
    flag = settings.local_ui_maintenance_file
    flag.write_text(json.dumps({"nonce": "synthetic-setup"}))
    task = asyncio.create_task(wait_for_maintenance(settings))
    await asyncio.sleep(0)
    assert not task.done()
    assert (
        json.loads(flag.with_suffix(".ack.json").read_text())["nonce"]
        == "synthetic-setup"
    )
    flag.unlink()
    await asyncio.wait_for(task, timeout=2)
