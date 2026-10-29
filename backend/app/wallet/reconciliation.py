"""Fail-closed audit with durable alerts; scheduled by the existing owner loop."""

import hashlib
from datetime import datetime, time

from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.db.models import DashboardAlert, PaperExecutionBook, WalletReconciliationRun
from app.execution.models import PaperBook
from app.market.warmup import local_time
from app.wallet.projections import verify


def alert(engine: Engine, account: str, at: datetime) -> None:
    identity = hashlib.sha256((account + at.date().isoformat()).encode()).hexdigest()[
        :32
    ]
    with Session(engine) as db, db.begin():
        if db.get(DashboardAlert, identity) is None:
            db.add(
                DashboardAlert(
                    id=identity,
                    source_key="wallet:" + account,
                    level="critical",
                    code="paper_wallet_reconciliation_failed",
                    at=at.isoformat(),
                    acknowledged_at=None,
                )
            )


class WalletReconciler:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def poll(self, at: datetime, *, force: bool = False) -> dict[str, str]:
        at = local_time(at)
        if not force and at.time() < time(15, 35):
            return {}
        outcomes: dict[str, str] = {}
        with self.engine.connect() as conn:
            conn.exec_driver_sql("BEGIN IMMEDIATE")
            with Session(bind=conn) as db:
                for row in db.scalars(select(PaperExecutionBook)).all():
                    key = (row.id, at.date().isoformat(), row.revision)
                    prior = db.get(WalletReconciliationRun, key)
                    if not force and prior is not None and prior.status == "PASS":
                        continue
                    try:
                        book = PaperBook.model_validate_json(row.payload)
                        if not book.projected:
                            raise ValueError("wallet projection bootstrap required")
                        user = (
                            "local"
                            if row.id == "PAPER"
                            else row.id.removeprefix("PAPER:")
                        )
                        verify(db, book, row.id, user, row.revision)
                        status = "PASS"
                    except ValueError:
                        status = "FAIL"
                    db.merge(
                        WalletReconciliationRun(
                            account_id=row.id,
                            day=key[1],
                            revision=row.revision,
                            at=at.isoformat(),
                            status=status,
                        )
                    )
                    outcomes[row.id] = status
                db.flush()
                conn.commit()
        for account, status in outcomes.items():
            if status == "FAIL":
                alert(self.engine, account, at)
        return outcomes
