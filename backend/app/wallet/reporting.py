"""Pure ledger-derived capital bases and fill-derived trade returns."""

from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Literal

from pydantic import Field, model_validator

from app.execution.models import PaperBook, PositionStatus
from app.strategy.models import Frozen

Period = Literal["daily", "weekly", "monthly", "all"]


def percent(net: Decimal, capital: Decimal) -> str | None:
    return (
        str((net / capital * 100).quantize(Decimal(".000001"))) if capital > 0 else None
    )


def bounds(kind: Period, day: date, first: date) -> tuple[date, date]:
    if kind == "daily":
        return day, day
    if kind == "weekly":
        start = day - timedelta(days=day.weekday())
        return start, start + timedelta(days=6)
    if kind == "monthly":
        start = day.replace(day=1)
        return start, (
            (start.replace(day=28) + timedelta(days=4)).replace(day=1)
            - timedelta(days=1)
        )
    return first, day


def opening_capital(book: PaperBook, start: date) -> Decimal:
    prior = [e for e in book.ledger if e.at.date() < start]
    if prior:
        return prior[-1].balance
    # Creating a wallet establishes its first baseline; later deposits are flows.
    initial = next((e for e in book.ledger if e.kind == "INITIAL"), None)
    if initial is not None and initial.at.date() == start:
        return initial.balance
    return Decimal(0)


def trades(book: PaperBook) -> list[dict[str, Any]]:
    result = []
    ledger = {e.key: e for e in book.ledger}
    for p in book.positions.values():
        if p.status != PositionStatus.CLOSED:
            continue
        at = p.transitions[-1].at
        capital = ledger[p.id + ":reserve"].balance
        net = p.gross - p.costs
        result.append(
            dict(
                trade_id=p.id,
                closed_at=at.isoformat(),
                day=at.date().isoformat(),
                family=p.plan.signal.family,
                direction=p.plan.signal.direction,
                grade=p.plan.signal.grade,
                result="WIN" if net > 0 else "LOSS" if net < 0 else "FLAT",
                gross=str(p.gross),
                costs=str(p.costs),
                net=str(net),
                margin=str(p.plan.required_margin),
                entry_capital=str(capital),
                margin_return_pct=percent(net, p.plan.required_margin),
                capital_return_pct=percent(net, capital),
                reason=p.exit_reason,
                short_symbol=p.plan.short.contract.symbol,
                hedge_symbol=p.plan.hedge.contract.symbol,
            )
        )
    return sorted(result, key=lambda t: (t["closed_at"], t["trade_id"]))


def summary(book: PaperBook, start: date, end: date) -> dict[str, Any]:
    if end < start:
        raise ValueError("ordered period required")
    selected = [
        t for t in trades(book) if start.isoformat() <= t["day"] <= end.isoformat()
    ]
    gross = sum((Decimal(t["gross"]) for t in selected), Decimal(0))
    costs = sum((Decimal(t["costs"]) for t in selected), Decimal(0))
    capital = opening_capital(book, start)
    flows = sum(
        (
            e.amount
            for e in book.ledger
            if start <= e.at.date() <= end
            and e.kind in {"DEPOSIT", "WITHDRAW", "RESET"}
        ),
        Decimal(0),
    )
    families = {
        f: str(
            sum((Decimal(t["net"]) for t in selected if t["family"] == f), Decimal(0))
        )
        for f in ("CO", "DIV", "OT")
    }
    return dict(
        start=start.isoformat(),
        end=end.isoformat(),
        starting_capital=str(capital),
        trades=len(selected),
        wins=sum(t["result"] == "WIN" for t in selected),
        gross=str(gross),
        costs=str(costs),
        net=str(gross - costs),
        external_flows=str(flows),
        capital_return_pct=percent(gross - costs, capital),
        by_family_net=families,
        basis="CLOSED_TRADES_NET_OF_ESTIMATED_COSTS",
    )


class HistoryQuery(Frozen):
    mode: Literal["PAPER"] = "PAPER"
    start: date | None = None
    end: date | None = None
    family: Literal["CO", "DIV", "OT"] | None = None
    direction: Literal[-1, 1] | None = None
    grade: int | None = Field(default=None, ge=1, le=3, strict=True)
    result: Literal["WIN", "LOSS", "FLAT"] | None = None
    limit: int = Field(default=50, ge=1, le=100, strict=True)
    cursor: str | None = Field(default=None, max_length=2000)
    sort: Literal["closed_at", "net"] = "closed_at"
    order: Literal["asc", "desc"] = "asc"

    @model_validator(mode="after")
    def dates(self) -> "HistoryQuery":
        if self.start is not None and self.end is not None and self.end < self.start:
            raise ValueError("ordered history dates required")
        return self
