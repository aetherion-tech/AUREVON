"""Optional exact mark observations; never a ledger or financial action source."""

import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import Engine, delete, func, select
from sqlalchemy.orm import Session

from app.db.models import PaperExecutionBook, PnlTick
from app.execution.models import PaperBook
from app.execution.service import ACTIVE


def utc_stamp(at: datetime) -> str:
    if at.utcoffset() is None:
        raise ValueError("Aware sample time required")
    return at.astimezone(timezone.utc).isoformat(timespec="microseconds")


def sample(engine: Engine, at: datetime) -> int:
    stamp = utc_stamp(at)
    with engine.connect() as connection:
        connection.exec_driver_sql("BEGIN IMMEDIATE")
        with Session(bind=connection) as db:
            count = 0
            for row in db.scalars(select(PaperExecutionBook)):
                book = PaperBook.model_validate_json(row.payload)
                active = [p for p in book.positions.values() if p.status in ACTIVE]
                marks = [p.unrealised for p in active]
                unrealised = (
                    str(
                        sum((value for value in marks if value is not None), Decimal(0))
                    )
                    if all(value is not None for value in marks)
                    else None
                )
                payload = json.dumps(
                    {
                        "revision": row.revision,
                        "day_net": str(book.day_net),
                        "unrealised": unrealised,
                        "active_positions": len(active),
                        "basis": "PAPER_MARK_OBSERVATION",
                    },
                    sort_keys=True,
                )
                existing = db.get(PnlTick, (row.id, stamp))
                if existing is not None:
                    if existing.payload != payload:
                        raise ValueError("Changed P&L sample under the same timestamp")
                    continue
                db.add(PnlTick(account_id=row.id, at=stamp, payload=payload))
                count += 1
            db.flush()
            connection.commit()
            return count


def prune(engine: Engine, at: datetime) -> int:
    cutoff = utc_stamp(at - timedelta(days=90))
    with Session(engine) as db, db.begin():
        count = (
            db.scalar(
                select(func.count()).select_from(PnlTick).where(PnlTick.at < cutoff)
            )
            or 0
        )
        db.execute(delete(PnlTick).where(PnlTick.at < cutoff))
        return count
