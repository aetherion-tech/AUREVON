"""Only derivative mark samples expire; exact financial records remain intact."""

import json
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import BACKEND_DIR
from app.db.models import Base, PaperExecutionBook, PnlTick, WalletLedger
from app.db.session import database_engine
from app.market.exchange_calendar import ExchangeCalendar
from app.wallet.pnl_ticks import prune, sample, utc_stamp
from app.wallet.service import WalletService


def test_samples_are_exact_idempotent_and_pruning_preserves_financial_evidence(
    tmp_path,
):
    engine = database_engine(f"sqlite:///{(tmp_path / 'ticks.db').as_posix()}")
    Base.metadata.create_all(engine)
    at = datetime(2026, 10, 30, 10, tzinfo=timezone.utc)
    wallet = WalletService(
        engine, ExchangeCalendar(BACKEND_DIR / "app/market/calendars")
    )
    wallet.initialize(at)
    assert sample(engine, at) == 1
    assert sample(engine, at) == 0
    with Session(engine) as db, db.begin():
        current = db.get(PnlTick, ("PAPER", utc_stamp(at)))
        assert json.loads(current.payload)["unrealised"] == "0"
        db.add(
            PnlTick(
                account_id="PAPER", at=utc_stamp(at - timedelta(days=90)), payload="{}"
            )
        )
        db.add(
            PnlTick(
                account_id="PAPER",
                at=utc_stamp(at - timedelta(days=90, microseconds=1)),
                payload="{}",
            )
        )
        book_before = db.get(PaperExecutionBook, "PAPER").payload
        ledger_before = db.scalar(select(func.count()).select_from(WalletLedger))
    assert prune(engine, at) == 1
    assert prune(engine, at) == 0
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(PnlTick)) == 2
        assert db.get(PaperExecutionBook, "PAPER").payload == book_before
        assert (
            db.scalar(select(func.count()).select_from(WalletLedger)) == ledger_before
        )
    with pytest.raises(ValueError, match="Aware"):
        sample(engine, at.replace(tzinfo=None))
    engine.dispose()
