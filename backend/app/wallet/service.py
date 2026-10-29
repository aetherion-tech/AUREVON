"""Wallet operations share the execution transaction and retain all history."""

import base64
import csv
import hashlib
import io
import json
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import Engine, select, tuple_
from sqlalchemy.orm import Session

from app.db.models import PaperTradeSummary, WalletAccount
from app.execution.models import FillSettings, PaperBook, Position, RiskSettings
from app.execution.service import ACTIVE, PaperExecution
from app.market.warmup import SessionCalendar, local_time
from app.strategy.models import CapitalSnapshot
from app.wallet.contracts import MAX_MONEY, WalletSettings, money
from app.wallet.reporting import HistoryQuery, Period, bounds, summary


def history_display(p: Position) -> dict[str, Any]:
    def fill(label: str) -> str | None:
        order = p.orders.get(label)
        return str(order.fill.price) if order and order.fill else None

    return dict(
        created_at=p.transitions[0].at.isoformat(),
        quantity=p.plan.short.quantity,
        short_entry=fill("entry_short"),
        hedge_entry=fill("entry_hedge"),
        short_exit=fill("exit_short"),
        hedge_exit=fill("exit_hedge"),
        duration_seconds=int(
            (p.transitions[-1].at - p.transitions[0].at).total_seconds()
        ),
        signal_id=p.plan.signal.signal_id,
    )


class WalletService(PaperExecution):
    def __init__(
        self,
        engine: Engine,
        calendar: SessionCalendar,
        fills: FillSettings | None = None,
        risk: RiskSettings | None = None,
        user_id: str = "local",
        settings: WalletSettings | None = None,
    ) -> None:
        super().__init__(engine, calendar, fills, risk, user_id)
        settings = settings or WalletSettings()

        def configure(b: PaperBook, revision: int) -> None:
            if b.wallet_settings is not None and b.wallet_settings != settings:
                raise ValueError("persisted wallet settings differ")
            self._set(b, wallet_settings=settings)

        self._mutate(configure)

    def initialize(self, at: datetime) -> None:
        at = local_time(at)

        def apply(b: PaperBook, revision: int) -> None:
            if any(e.kind == "INITIAL" for e in b.ledger):
                return
            if b.ledger or b.positions:
                raise ValueError("existing wallet cannot be initialized again")
            assert b.wallet_settings is not None
            amount = money(b.wallet_settings.initial_capital)
            self._set(b, balance=amount)
            self._ledger(b, "initial", "INITIAL", amount, at)

        self._mutate(apply)

    def withdraw(self, key: str, amount: Decimal, at: datetime) -> None:
        at = local_time(at)
        if not key or len(key) > 160 or money(amount) <= 0:
            raise ValueError("positive exact paise withdrawal required")

        def apply(b: PaperBook, revision: int) -> None:
            prior = next((e for e in b.ledger if e.key == "withdraw:" + key), None)
            if prior:
                if prior.amount != -amount:
                    raise ValueError("withdrawal idempotency conflict")
                return
            if amount > b.balance - b.reserved:
                raise ValueError("withdrawal exceeds free balance")
            self._set(b, balance=b.balance - amount)
            self._ledger(b, "withdraw:" + key, "WITHDRAW", -amount, at)

        self._mutate(apply)

    def reset(self, key: str, target: Decimal, at: datetime) -> None:
        at = local_time(at)
        if not key or len(key) > 160 or money(target) < 0:
            raise ValueError("nonnegative exact reset baseline required")

        def apply(b: PaperBook, revision: int) -> None:
            prior = next((e for e in b.ledger if e.key == "reset:" + key), None)
            if prior:
                if prior.balance != target:
                    raise ValueError("reset idempotency conflict")
                return
            if b.reserved or any(p.status in ACTIVE for p in b.positions.values()):
                raise ValueError("cannot reset while a position or reservation exists")
            delta = target - b.balance
            self._set(b, balance=target)
            self._ledger(b, "reset:" + key, "RESET", delta, at)
            # Risk locks and counters deliberately survive wallet reset.

        self._mutate(apply)

    def planning_capital(self, at: datetime) -> CapitalSnapshot:
        """Auto-top-up funding ceiling, distinct from actual capital()/balance.

        This is a PAPER funding promise for BE-10 sizing only. Admission still
        enforces all risk limits against actual session capital before depositing.
        """
        return self._mutate(
            lambda b, r: CapitalSnapshot(
                at=at,
                free_capital=(
                    MAX_MONEY - b.reserved
                    if b.wallet_settings and b.wallet_settings.auto_topup
                    else max(Decimal(0), b.balance - b.reserved)
                ),
                source="PAPER_WALLET",
                revision=str(r),
            )
        )

    def period(self, kind: Period, at: datetime) -> dict[str, Any]:
        at = local_time(at)
        if kind not in {"daily", "weekly", "monthly", "all"}:
            raise ValueError("unknown period")

        def report(b: PaperBook, revision: int) -> dict[str, Any]:
            first = min((e.at.date() for e in b.ledger), default=at.date())
            start, end = bounds(kind, at.date(), first)
            return summary(b, start, min(end, at.date()))

        return self._mutate(report)

    def history(self, query: HistoryQuery | None = None) -> dict[str, Any]:
        query = query or HistoryQuery()
        revision, positions = self._mutate(lambda b, r: (r, dict(b.positions)))
        fingerprint = hashlib.sha256(
            (
                self.account_id
                + query.model_copy(update={"cursor": None}).model_dump_json()
            ).encode()
        ).hexdigest()
        after: tuple[str, str] | None = None
        after_net = Decimal(0)
        if query.cursor:
            try:
                cursor = json.loads(base64.urlsafe_b64decode(query.cursor.encode()))
                if cursor["revision"] != revision or cursor["query"] != fingerprint:
                    raise ValueError("history changed or cursor filters differ")
                after = cursor["at"], cursor["id"]
                if not all(isinstance(v, str) for v in after):
                    raise ValueError("invalid cursor")
                if query.sort == "net":
                    after_net = Decimal(cursor["value"])
                    if not after_net.is_finite():
                        raise ValueError("invalid net cursor")
            except (KeyError, TypeError, ValueError, InvalidOperation) as error:
                raise ValueError("invalid or stale history cursor") from error
        with self.engine.connect() as connection, Session(bind=connection) as db:
            connection.exec_driver_sql("BEGIN")
            account = db.get(WalletAccount, self.account_id)
            if account is None or account.revision != revision:
                raise ValueError("history changed; reload first page")
            statement = select(PaperTradeSummary).where(
                PaperTradeSummary.account_id == self.account_id
            )
            for name in ("family", "direction", "grade", "result"):
                value = getattr(query, name)
                if value is not None:
                    statement = statement.where(
                        getattr(PaperTradeSummary, name) == value
                    )
            if query.start is not None:
                statement = statement.where(
                    PaperTradeSummary.day >= query.start.isoformat()
                )
            if query.end is not None:
                statement = statement.where(
                    PaperTradeSummary.day <= query.end.isoformat()
                )
            if after is not None and query.sort == "closed_at":
                key = tuple_(PaperTradeSummary.closed_at, PaperTradeSummary.trade_id)
                statement = statement.where(
                    key > after if query.order == "asc" else key < after
                )
            if query.sort == "net":
                candidates = db.scalars(statement.limit(10001)).all()
                if len(candidates) > 10000:
                    raise ValueError("net sort exceeds 10000 trades; narrow dates")
                found = sorted(
                    candidates,
                    key=lambda r: (
                        Decimal(json.loads(r.payload)["net"]),
                        r.closed_at,
                        r.trade_id,
                    ),
                    reverse=query.order == "desc",
                )
                if after is not None:
                    boundary = (after_net, *after)
                    found = [
                        r
                        for r in found
                        if (
                            (
                                Decimal(json.loads(r.payload)["net"]),
                                r.closed_at,
                                r.trade_id,
                            )
                            > boundary
                            if query.order == "asc"
                            else (
                                Decimal(json.loads(r.payload)["net"]),
                                r.closed_at,
                                r.trade_id,
                            )
                            < boundary
                        )
                    ]
                found = found[: query.limit + 1]
            else:
                columns = (PaperTradeSummary.closed_at, PaperTradeSummary.trade_id)
                found = list(
                    db.scalars(
                        statement.order_by(
                            *(
                                c.asc() if query.order == "asc" else c.desc()
                                for c in columns
                            )
                        ).limit(query.limit + 1)
                    ).all()
                )
            selected = found[: query.limit]
            cursor_text = None
            if len(found) > query.limit:
                last = selected[-1]
                cursor_text = base64.urlsafe_b64encode(
                    json.dumps(
                        dict(
                            revision=revision,
                            query=fingerprint,
                            at=last.closed_at,
                            id=last.trade_id,
                            value=json.loads(last.payload)["net"],
                        )
                    ).encode()
                ).decode()
            return dict(
                items=[
                    {**json.loads(r.payload), **history_display(positions[r.trade_id])}
                    for r in selected
                ],
                next_cursor=cursor_text,
                revision=revision,
                mode="PAPER",
            )

    def detail(self, trade_id: str) -> dict[str, Any]:
        book = self.snapshot()
        if trade_id not in book.positions:
            raise KeyError(trade_id)
        return book.positions[trade_id].model_dump(mode="json")

    def export_csv(self, query: HistoryQuery | None = None) -> str:
        query = query or HistoryQuery()
        if query.cursor is not None:
            raise ValueError("export starts at first page")
        records: list[dict[str, Any]] = []
        while True:
            page = self.history(query)
            records.extend(page["items"])
            if len(records) > 10000:
                raise ValueError("export exceeds 10000 trades; narrow dates")
            if page["next_cursor"] is None:
                break
            query = query.model_copy(update={"cursor": page["next_cursor"]})
        fields = [
            "trade_id",
            "closed_at",
            "family",
            "direction",
            "grade",
            "result",
            "gross",
            "costs",
            "net",
            "margin",
            "margin_return_pct",
            "capital_return_pct",
            "short_symbol",
            "hedge_symbol",
            "reason",
        ]
        output = io.StringIO(newline="")
        writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for record in records:
            row = {k: record[k] for k in fields}
            for field in ("short_symbol", "hedge_symbol", "reason"):
                if isinstance(row[field], str) and row[field].lstrip().startswith(
                    ("=", "+", "-", "@")
                ):
                    row[field] = "'" + row[field]
            writer.writerow(row)
        return output.getvalue()
