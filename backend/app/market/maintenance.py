"""Opt-in end-of-session snapshot inside the existing leased market loop."""

import json
import sqlite3
from contextlib import closing
from datetime import datetime, time, timedelta
from pathlib import Path

from sqlalchemy import Engine, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.broker.kite_auth import IST
from app.db.models import PaperExecutionBook, WalletReconciliationRun
from app.execution.models import PaperBook
from app.execution.service import ACTIVE
from app.market.exchange_calendar import ExchangeCalendar
from app.tools.backup import backup, inspect_database
from app.wallet.reconciliation import WalletReconciler


def nightly(
    engine: Engine,
    calendar: ExchangeCalendar,
    directory: Path,
    at: datetime,
    *,
    recordings: Path | None = None,
) -> bool:
    if at.utcoffset() is None:
        raise ValueError("Maintenance requires an aware clock")
    at = at.astimezone(IST)
    session = calendar.session(at)
    if (session and at < session.closing + timedelta(minutes=10)) or (
        session is None and at.time() < time(15, 40)
    ):
        return False
    day = directory / at.date().isoformat()
    report = day / "report.json"
    if report.exists():
        return False
    with Session(engine) as db:
        for row in db.scalars(select(PaperExecutionBook)):
            book = PaperBook.model_validate_json(row.payload)
            if any(position.status in ACTIVE for position in book.positions.values()):
                raise ValueError("Session close incomplete; exposure remains")
    WalletReconciler(engine).poll(at, force=True)
    with Session(engine) as db:
        if (
            db.scalar(
                select(WalletReconciliationRun).where(
                    WalletReconciliationRun.day == at.date().isoformat(),
                    WalletReconciliationRun.status != "PASS",
                )
            )
            is not None
        ):
            raise ValueError("Ledger reconciliation failed; inspect durable alerts")
    url = make_url(str(engine.url))
    if (
        url.get_backend_name() != "sqlite"
        or not url.database
        or url.database == ":memory:"
    ):
        raise ValueError("File-backed SQLite required for local backups")
    target = day / "paper.db"
    if target.exists():
        raise ValueError("Prior snapshot lacks report; verify and archive before retry")
    result = backup(Path(url.database), target)
    # Financial HTTP mutations can commit while the owner performs the backup.
    # Certify the actual snapshot, not just the earlier live pre-check.
    with closing(
        sqlite3.connect(target.resolve().as_uri() + "?mode=ro", uri=True)
    ) as db:
        books = db.execute(
            "SELECT id, revision, payload FROM paper_execution_books"
        ).fetchall()
        for account, revision, payload in books:
            book = PaperBook.model_validate_json(payload)
            if any(position.status in ACTIVE for position in book.positions.values()):
                raise ValueError(
                    "Snapshot contains exposure; retained for investigation"
                )
            status = db.execute(
                "SELECT status FROM wallet_reconciliation_runs "
                "WHERE account_id=? AND day=? AND revision=?",
                (account, at.date().isoformat(), revision),
            ).fetchone()
            if status != ("PASS",):
                raise ValueError("Snapshot revision lacks a passing reconciliation")
    if inspect_database(target) != result:
        raise ValueError("Snapshot changed during validation")
    from app.wallet.pnl_ticks import prune

    pruned = prune(engine, at)
    from app.tools.retention import compress_sealed

    compressed = (
        compress_sealed(recordings, at.date(), apply=True) if recordings else []
    )
    with report.open("x", encoding="utf-8") as stream:
        json.dump(
            {
                "at": at.isoformat(),
                "exposure": "FLAT" if books else "NO_BOOKS",
                "backup": result,
                "pnl_samples_pruned": pruned,
                "sealed_recordings_compressed": compressed,
                "raw_recording_retention": "INDEFINITE_PRESERVED_EVIDENCE",
            },
            stream,
            indent=2,
        )
    return True
