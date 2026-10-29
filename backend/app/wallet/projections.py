"""Transactional indexed projections; mismatches fail closed, never auto-repair."""

import json
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Base,
    PaperDailyPnL,
    PaperTradeSummary,
    WalletAccount,
    WalletLedger,
    WalletPeriod,
)
from app.execution.models import PaperBook
from app.wallet.reporting import Period, bounds, opening_capital, summary, trades


class ReconciliationError(ValueError):
    pass


def encode(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def materialize(
    book: PaperBook, account: str, user: str, revision: int
) -> list[tuple[type[Base], list[dict[str, Any]]]]:
    days = sorted(
        {e.at.date() for e in book.ledger}
        | ({book.last_at.date()} if book.last_at else set())
    )
    first = days[0] if days else date.min
    anchors: set[tuple[Period, date]] = set()
    for day in days:
        for kind in ("daily", "weekly", "monthly", "all"):
            anchors.add((kind, bounds(kind, day, first)[0]))
    records = trades(book)
    return [
        (
            WalletAccount,
            [
                dict(
                    id=account,
                    user_id=user,
                    mode="PAPER",
                    revision=revision,
                    balance=str(book.balance),
                    reserved=str(book.reserved),
                )
            ],
        ),
        (
            WalletLedger,
            [
                dict(
                    account_id=account,
                    sequence=i,
                    key=e.key,
                    at=e.at.isoformat(),
                    kind=e.kind,
                    payload=e.model_dump_json(),
                )
                for i, e in enumerate(book.ledger)
            ],
        ),
        (
            PaperTradeSummary,
            [
                dict(
                    account_id=account,
                    **{
                        k: t[k]
                        for k in (
                            "trade_id",
                            "closed_at",
                            "day",
                            "family",
                            "direction",
                            "grade",
                            "result",
                        )
                    },
                    payload=encode(t),
                )
                for t in records
            ],
        ),
        (
            PaperDailyPnL,
            [
                dict(
                    account_id=account,
                    day=day.isoformat(),
                    payload=encode(summary(book, day, day)),
                )
                for day in days
            ],
        ),
        (
            WalletPeriod,
            [
                dict(
                    account_id=account,
                    kind=kind,
                    start=start.isoformat(),
                    payload=encode(
                        dict(starting_capital=str(opening_capital(book, start)))
                    ),
                )
                for kind, start in sorted(anchors)
            ],
        ),
    ]


def verify(
    db: Session, book: PaperBook, account: str, user: str, revision: int
) -> None:
    for model, expected in materialize(book, account, user, revision):
        column = (
            model.__table__.c.id
            if model is WalletAccount
            else model.__table__.c.account_id
        )
        actual = [
            dict(r)
            for r in db.execute(
                select(model.__table__).where(column == account)
            ).mappings()
        ]
        if sorted(map(encode, actual)) != sorted(map(encode, expected)):
            raise ReconciliationError(
                "wallet projection mismatch: " + model.__tablename__
            )


def synchronize(
    db: Session, book: PaperBook, account: str, user: str, revision: int
) -> None:
    for model, rows in materialize(book, account, user, revision):
        for row in rows:
            db.merge(model(**row))
