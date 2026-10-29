"""Transactional replay paper lifecycle. Each broker action is a separate commit.

The SQLite writer lock covers the entire paper book and ledger. No external side
effect occurs inside the transaction: PaperBroker is deterministic and pure.
MarketService integration is deliberately disabled pending reference gates.
"""

import re
from collections.abc import Callable
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import TypeVar

from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.broker.paper_broker import PaperBroker
from app.db.models import PaperExecutionBook
from app.execution.models import (
    FillSettings,
    LedgerEntry,
    MarketPrice,
    OrderStatus,
    PaperBook,
    Position,
    PositionStatus,
    Readiness,
    Rejection,
    RiskSettings,
    Side,
    Transition,
)
from app.market.warmup import SessionCalendar, local_time
from app.strategy.models import CapitalSnapshot, TradePlan
from app.wallet.contracts import MAX_MONEY, money
from app.wallet.projections import ReconciliationError, synchronize, verify

T = TypeVar("T")
ACTIVE = {
    PositionStatus.ENTERING,
    PositionStatus.OPEN,
    PositionStatus.CLOSING,
    PositionStatus.UNWINDING,
}


class PaperExecution:
    def __init__(
        self,
        engine: Engine,
        calendar: SessionCalendar,
        fills: FillSettings | None = None,
        risk: RiskSettings | None = None,
        user_id: str = "local",
    ) -> None:
        if engine.dialect.name != "sqlite":
            raise ValueError(
                "paper book currently requires SQLite writer serialization"
            )
        self.engine, self.calendar = engine, calendar
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,32}", user_id):
            raise ValueError("bounded wallet user identity required")
        self.user_id = user_id
        self.account_id = "PAPER" if user_id == "local" else "PAPER:" + user_id
        self.fills, self.risk = fills or FillSettings(), risk or RiskSettings()
        self.broker = PaperBroker(self.fills)
        self._mutate(lambda b, revision: None)

    def _mutate(self, action: Callable[[PaperBook, int], T]) -> T:
        from pydantic import ValidationError

        from app.market.renko_builder import IST
        from app.wallet.reconciliation import alert

        try:
            return self._transaction(action)
        except (ValidationError, ReconciliationError):
            alert(self.engine, self.account_id, datetime.now(IST))
            raise

    def _transaction(self, action: Callable[[PaperBook, int], T]) -> T:
        with self.engine.connect() as conn:
            conn.exec_driver_sql("BEGIN IMMEDIATE")
            with Session(bind=conn) as db:
                try:
                    row = db.get(PaperExecutionBook, self.account_id)
                    book = (
                        PaperBook.model_validate_json(row.payload)
                        if row
                        else PaperBook(
                            fill_settings=self.fills, risk_settings=self.risk
                        )
                    )
                    if (
                        book.fill_settings != self.fills
                        or book.risk_settings != self.risk
                    ):
                        raise ValueError(
                            "persisted settings differ; explicit migration required"
                        )
                    revision = row.revision if row else 0
                    previous_rejects = set(book.rejects)
                    previous_positions = set(book.positions)
                    if book.projected:
                        verify(db, book, self.account_id, self.user_id, revision)
                    else:
                        from app.db.models import WalletAccount

                        if db.get(WalletAccount, self.account_id) is not None:
                            raise ReconciliationError("unexpected wallet projection")
                        self._set(book, projected=True)
                    result = action(book, revision)
                    from hashlib import sha256

                    from app.api.decision_store import retain
                    from app.db.models import DashboardAlert

                    for key in book.rejects.keys() - previous_rejects:
                        reject = book.rejects[key]
                        retain(
                            db,
                            self.account_id,
                            "risk:" + key,
                            reject.signal_id,
                            reject.at,
                            "RISK_REJECT",
                            False,
                            list(reject.reasons),
                        )
                        identity = sha256(
                            (self.account_id + ":risk:" + key).encode()
                        ).hexdigest()[:32]
                        db.add(
                            DashboardAlert(
                                id=identity,
                                source_key="risk:" + identity,
                                level="warning",
                                code="risk_reject",
                                at=reject.at.isoformat(),
                                acknowledged_at=None,
                            )
                        )
                    for key in book.positions.keys() - previous_positions:
                        position = book.positions[key]
                        retain(
                            db,
                            self.account_id,
                            "admission:" + position.decision_id,
                            position.plan.signal.signal_id,
                            position.plan.planned_at,
                            "PAPER_ADMISSION",
                            True,
                            ["accepted"],
                            key,
                        )
                    payload = PaperBook.model_validate_json(
                        book.model_dump_json()
                    ).model_dump_json()
                    if row is None:
                        db.add(
                            PaperExecutionBook(
                                id=self.account_id, revision=1, payload=payload
                            )
                        )
                    elif row.payload != payload:
                        row.payload, row.revision = payload, revision + 1
                    if row is None or row.revision != revision:
                        validated = PaperBook.model_validate_json(payload)
                        synchronize(
                            db,
                            validated,
                            self.account_id,
                            self.user_id,
                            row.revision if row else 1,
                        )
                    db.flush()
                    conn.commit()
                    return result
                except BaseException:
                    conn.rollback()
                    raise

    @staticmethod
    def _set(book: PaperBook, **values: object) -> None:
        # Mutations exist only within a serialized transaction; validation before
        # commit prevents bypassing the public immutable contracts.
        for key, value in values.items():
            object.__setattr__(book, key, value)

    def snapshot(self) -> PaperBook:
        return self._mutate(lambda b, r: b.model_copy(deep=True))

    def capital(self, at: datetime) -> CapitalSnapshot:
        return self._mutate(
            lambda b, r: CapitalSnapshot(
                at=at,
                free_capital=max(Decimal(0), b.balance - b.reserved),
                source="PAPER_WALLET",
                revision=str(r),
            )
        )

    def _ledger(
        self, b: PaperBook, key: str, kind: str, amount: Decimal, at: datetime
    ) -> None:
        at = local_time(at)
        money(amount)
        if b.ledger and at < b.ledger[-1].at:
            raise ValueError("wallet ledger clock regression")
        if any(e.key == key for e in b.ledger):
            raise ValueError("duplicate ledger booking")
        self._set(
            b,
            ledger=b.ledger
            + (
                LedgerEntry(
                    key=key,
                    at=at,
                    kind=kind,
                    amount=amount,
                    balance=b.balance,
                    reserved=b.reserved,
                ),
            ),
        )

    def deposit(self, key: str, amount: Decimal, at: datetime) -> None:
        local_time(at)
        if not key or len(key) > 160 or money(amount) <= 0:
            raise ValueError("positive exact paise deposit required")

        def apply(b: PaperBook, revision: int) -> None:
            prior = next((e for e in b.ledger if e.key == "deposit:" + key), None)
            if prior:
                if prior.amount != amount:
                    raise ValueError("deposit idempotency conflict")
                return
            money(b.balance + amount)
            self._set(b, balance=b.balance + amount)
            self._ledger(b, "deposit:" + key, "DEPOSIT", amount, at)

        self._mutate(apply)

    def _roll(self, b: PaperBook, at: datetime) -> None:
        day = at.date()
        if not self.calendar.first_date <= day <= self.calendar.last_date:
            raise ValueError("calendar coverage unavailable")
        session = next(
            (s for s in self.calendar.sessions if local_time(s.opening).date() == day),
            None,
        )
        if session is None or at < session.opening:
            raise ValueError("valid session required")
        if b.day and day < b.day:
            raise ValueError("session cannot move backwards")
        if b.day != day:
            if any(p.status in ACTIVE for p in b.positions.values()):
                raise ValueError("prior session position requires closure")
            self._set(
                b,
                day=day,
                day_capital=b.balance,
                day_net=Decimal(0),
                day_trades=0,
                loss_locked=False,
            )

    def rollover(self, at: datetime) -> None:
        self._mutate(lambda b, r: self._roll(b, local_time(at)))

    def enter(
        self,
        decision_id: str,
        plan: TradePlan,
        at: datetime,
        readiness: Readiness,
        prices: dict[int, MarketPrice],
    ) -> str | None:
        at = local_time(at)
        if not decision_id or len(decision_id) > 160:
            raise ValueError("bounded decision identity required")
        plan = TradePlan.model_validate_json(plan.model_dump_json())

        def apply(b: PaperBook, revision: int) -> str | None:
            prior = next(
                (
                    p
                    for p in b.positions.values()
                    if p.decision_id == decision_id
                    or p.plan.signal.signal_id == plan.signal.signal_id
                ),
                None,
            )
            if prior:
                if prior.plan != plan:
                    raise ValueError("signal/decision idempotency conflict")
                return prior.id
            if decision_id in b.rejects or any(
                r.signal_id == plan.signal.signal_id for r in b.rejects.values()
            ):
                return None
            reasons = []
            try:
                self._roll(b, at)
            except ValueError:
                reasons.append("invalid_session")
            if b.last_at is not None and at < b.last_at:
                reasons.append("clock_regression")
            if b.killed:
                reasons.append("kill_locked")
            if b.loss_locked:
                reasons.append("daily_loss_locked")
            if (
                not readiness.ready()
                or not 0 <= (at - readiness.at).total_seconds() <= 1
            ):
                reasons.append("readiness_or_event_block")
            if not self.risk.entry_start <= at.time() < self.risk.entry_end:
                reasons.append("entry_window")
            if not any(s.opening <= at < s.closing for s in self.calendar.sessions):
                reasons.append("session_closed")
            if any(p.status in ACTIVE for p in b.positions.values()):
                reasons.append("one_position")
            if b.day_trades >= self.risk.max_trades:
                reasons.append("max_trades")
            if plan.maximum_loss > b.day_capital * self.risk.max_trade_loss_pct / 100:
                reasons.append("max_trade_loss")
            if (
                plan.capital.source != "PAPER_WALLET"
                or plan.capital.revision != str(revision)
                or (
                    plan.required_margin > b.balance - b.reserved
                    and not (b.wallet_settings and b.wallet_settings.auto_topup)
                )
            ):
                reasons.append("capital_unavailable_or_changed")
            if (
                not 0
                <= (at - plan.planned_at).total_seconds()
                <= self.risk.max_plan_age_seconds
            ):
                reasons.append("stale_plan")
            if plan.catalog_loaded_at.date() != at.date() or plan.expiry < at.date():
                reasons.append("stale_contract")
            if (
                plan.signal.grade < plan.settings.min_grade
                or plan.signal.family not in plan.settings.allowed_families
                or (plan.settings.skip_high_risk and plan.signal.risk == "High")
                or (
                    plan.settings.skip_opposite_bias
                    and plan.signal.bias_direction == -plan.signal.direction
                )
            ):
                reasons.append("signal_restriction")
            for leg in (plan.short, plan.hedge):
                price = prices.get(leg.contract.token)
                if (
                    price is None
                    or price.token != leg.contract.token
                    or not self.broker.valid(price, at)
                    or abs(leg.limit_price - price.last) > price.last * Decimal(".05")
                ):
                    reasons.append("quote_quality_or_price_sanity")
            if reasons:
                b.rejects[decision_id] = Rejection(
                    decision_id=decision_id,
                    signal_id=plan.signal.signal_id,
                    at=at,
                    reasons=tuple(dict.fromkeys(reasons)),
                )
                return None
            identity = "P-T-" + plan.plan_id
            shortfall = plan.required_margin - (b.balance - b.reserved)
            if shortfall > 0:
                if b.balance + shortfall > MAX_MONEY:
                    raise ValueError("auto top-up exceeds wallet precision")
                self._set(b, balance=b.balance + shortfall)
                self._ledger(b, "auto:" + identity, "DEPOSIT", shortfall, at)
            p = Position(
                id=identity,
                decision_id=decision_id,
                plan=plan,
                transitions=(
                    Transition(at=at, state=PositionStatus.ENTERING, reason="accepted"),
                ),
            )
            b.positions[identity] = p
            self._set(
                b,
                reserved=b.reserved + plan.required_margin,
                day_trades=b.day_trades + 1,
                last_at=at,
            )
            self._ledger(b, identity + ":reserve", "RESERVE", plan.required_margin, at)
            return identity

        return self._mutate(apply)

    @staticmethod
    def _transition(
        p: Position, state: PositionStatus, at: datetime, reason: str
    ) -> Position:
        return p.model_copy(
            update={
                "status": state,
                "exit_reason": reason,
                "transitions": p.transitions
                + (Transition(at=at, state=state, reason=reason),),
            }
        )

    def _loss(self, b: PaperBook, at: datetime) -> None:
        # Unknown marks block entries; only valid marks can trigger daily MTM loss.
        unrealised = sum(
            (p.unrealised or Decimal(0)) - p.costs
            for p in b.positions.values()
            if p.status in ACTIVE
        )
        if (
            b.day_capital > 0
            and b.day_net + unrealised
            <= -b.day_capital * self.risk.daily_loss_pct / 100
        ):
            self._set(b, loss_locked=True)
            for key, p in list(b.positions.items()):
                if p.status in (PositionStatus.OPEN, PositionStatus.ENTERING):
                    b.positions[key] = self._transition(
                        p, PositionStatus.CLOSING, at, "daily_loss"
                    )

    def close(self, identity: str, at: datetime, reason: str = "manual") -> None:
        at = local_time(at)
        if reason not in {"manual", "indicator", "kill", "square_off"}:
            raise ValueError("unknown exit source")

        def apply(b: PaperBook, revision: int) -> None:
            p = b.positions[identity]
            if p.status in (PositionStatus.ENTERING, PositionStatus.OPEN):
                if b.last_at is not None and at < b.last_at:
                    raise ValueError("paper clock regression")
                self._set(b, last_at=at)
                b.positions[identity] = self._transition(
                    p, PositionStatus.CLOSING, at, reason
                )

        self._mutate(apply)

    def indicator_exit(self, indicator_trade_id: str, at: datetime) -> None:
        for p in self.snapshot().positions.values():
            if p.plan.signal.trade_id == indicator_trade_id and p.status in ACTIVE:
                self.close(p.id, at, "indicator")

    def kill(self, at: datetime) -> None:
        at = local_time(at)

        def apply(b: PaperBook, revision: int) -> None:
            if b.killed:
                return
            stamp = max(at, b.last_at) if b.last_at is not None else at
            self._set(b, killed=True, last_at=stamp)
            for key, p in list(b.positions.items()):
                if p.status in ACTIVE:
                    orders = {k: self.broker.cancel(o) for k, o in p.orders.items()}
                    p = p.model_copy(update={"orders": orders})
                    b.positions[key] = self._transition(
                        p, PositionStatus.CLOSING, stamp, "kill"
                    )

        self._mutate(apply)

    def poll_kill(self, flag: Path, at: datetime) -> bool:
        if flag.exists():
            self.kill(at)
            return True
        return False

    def _order(
        self,
        p: Position,
        label: str,
        hedge: bool,
        closing: bool,
        at: datetime,
        prices: dict[int, MarketPrice],
    ) -> Position:
        leg = p.plan.hedge if hedge else p.plan.short
        order = p.orders.get(label)
        if order is None:
            side = Side.SELL if hedge == closing else Side.BUY
            order = self.broker.place(
                p.id + ":" + label,
                leg.contract.token,
                side,
                leg.quantity,
                leg.contract.tick_size,
                at,
            )
        elif order.status == OrderStatus.PENDING:
            price = prices.get(order.token)
            if price:
                order = self.broker.process(order, price, at)
        orders = dict(p.orders)
        orders[label] = order
        return p.model_copy(update={"orders": orders})

    @staticmethod
    def _filled(p: Position, label: str) -> bool:
        return label in p.orders and p.orders[label].status == OrderStatus.FILLED

    def _settle(self, b: PaperBook, p: Position, at: datetime) -> Position:
        fills = [(o, o.fill) for o in p.orders.values() if o.fill is not None]
        gross = sum(
            (
                f.price * f.quantity * (1 if o.side == Side.SELL else -1)
                for o, f in fills
            ),
            Decimal(0),
        )
        costs = sum((f.costs for _, f in fills), Decimal(0))
        self._set(b, reserved=b.reserved - p.plan.required_margin)
        self._ledger(b, p.id + ":release", "RELEASE", -p.plan.required_margin, at)
        self._set(b, balance=b.balance + gross)
        self._ledger(b, p.id + ":gross", "REALISED_GROSS", gross, at)
        self._set(b, balance=b.balance - costs, day_net=b.day_net + gross - costs)
        self._ledger(b, p.id + ":costs", "COSTS", -costs, at)
        p = p.model_copy(
            update={
                "gross": gross,
                "costs": costs,
                "unrealised": Decimal(0),
                "mark_at": at,
            }
        )
        return self._transition(p, PositionStatus.CLOSED, at, p.exit_reason or "closed")

    def step(
        self,
        at: datetime,
        prices: dict[int, MarketPrice],
        readiness: Readiness | None = None,
        kill_flag: Path | None = None,
    ) -> None:
        """One durable action per position. Call again on later market/poll events.

        Exits continue with readiness false; invalid prices leave exits pending,
        reserve retained and entries blocked. Never fabricate a stale-price fill.
        """
        at = local_time(at)
        if kill_flag is not None:
            self.poll_kill(kill_flag, at)

        def apply(b: PaperBook, revision: int) -> None:
            if b.last_at is not None and at < b.last_at:
                raise ValueError("paper clock regression")
            self._set(b, last_at=at)
            for key, p in list(b.positions.items()):
                if p.status not in ACTIVE:
                    continue
                if (
                    at.time() >= self.risk.square_off
                    or at.date() > p.plan.planned_at.date()
                ):
                    if p.status in (PositionStatus.OPEN, PositionStatus.ENTERING):
                        p = self._transition(
                            p, PositionStatus.CLOSING, at, "square_off"
                        )
                entry_phase = p.status == PositionStatus.ENTERING
                if entry_phase:
                    if (
                        readiness is None
                        or not readiness.ready()
                        or not 0 <= (at - readiness.at).total_seconds() <= 1
                        or not self.risk.entry_start <= at.time() < self.risk.entry_end
                        or not any(
                            s.opening <= at < s.closing for s in self.calendar.sessions
                        )
                        or (at - p.plan.planned_at).total_seconds()
                        > self.risk.max_plan_age_seconds
                        or b.killed
                        or b.loss_locked
                    ):
                        p = self._transition(
                            p, PositionStatus.UNWINDING, at, "readiness_lost"
                        )
                    else:
                        label = (
                            "entry_short"
                            if self._filled(p, "entry_hedge")
                            else "entry_hedge"
                        )
                        p = self._order(
                            p, label, label == "entry_hedge", False, at, prices
                        )
                        if p.orders[label].status in (
                            OrderStatus.REJECTED,
                            OrderStatus.CANCELLED,
                        ):
                            p = self._transition(
                                p, PositionStatus.UNWINDING, at, "entry_failed"
                            )
                        elif self._filled(p, "entry_short"):
                            # Reject slippage that turns the spread into a debit or
                            # exceeds the funded plan's maximum loss.
                            short = p.orders["entry_short"].fill
                            hedge = p.orders["entry_hedge"].fill
                            assert short is not None and hedge is not None
                            if short.price - hedge.price < p.plan.credit_per_unit:
                                p = self._transition(
                                    p, PositionStatus.UNWINDING, at, "entry_slippage"
                                )
                            else:
                                p = self._transition(
                                    p, PositionStatus.OPEN, at, "entry_complete"
                                )
                elif p.status == PositionStatus.OPEN:
                    p = self._mark(p, at, prices)
                    debit = p.spread_debit
                    if debit is not None:
                        if debit >= p.plan.stop_debit_per_unit:
                            p = self._transition(
                                p, PositionStatus.CLOSING, at, "premium_stop"
                            )
                        elif (
                            p.plan.profit_capture_enabled
                            and debit <= p.plan.profit_capture_debit_per_unit
                        ):
                            p = self._transition(
                                p, PositionStatus.CLOSING, at, "premium_target"
                            )
                if not entry_phase and p.status in (
                    PositionStatus.CLOSING,
                    PositionStatus.UNWINDING,
                ):
                    orders = {
                        k: self.broker.cancel(o) if k.startswith("entry_") else o
                        for k, o in p.orders.items()
                    }
                    p = p.model_copy(update={"orders": orders})
                    short_open = self._filled(p, "entry_short") and not self._filled(
                        p, "exit_short"
                    )
                    hedge_open = self._filled(p, "entry_hedge") and not self._filled(
                        p, "exit_hedge"
                    )
                    if short_open or hedge_open:
                        label = "exit_short" if short_open else "exit_hedge"
                        existing = p.orders.get(label)
                        if existing and existing.status in (
                            OrderStatus.REJECTED,
                            OrderStatus.CANCELLED,
                        ):
                            # Retain rejected attempts with durable retry IDs.
                            archived = dict(p.orders)
                            archived[label + ":attempt:" + str(len(archived))] = (
                                existing
                            )
                            del archived[label]
                            p = p.model_copy(update={"orders": archived})
                            leg = p.plan.short if short_open else p.plan.hedge
                            order = self.broker.place(
                                p.id + ":" + label + ":" + str(len(archived)),
                                leg.contract.token,
                                Side.BUY if short_open else Side.SELL,
                                leg.quantity,
                                leg.contract.tick_size,
                                at,
                            )
                            p.orders[label] = order
                        else:
                            p = self._order(p, label, not short_open, True, at, prices)
                    else:
                        p = self._settle(b, p, at)
                if p.status in ACTIVE:
                    p = self._mark(p, at, prices)
                b.positions[key] = p
            self._loss(b, at)

        self._mutate(apply)

    def _mark(
        self, p: Position, at: datetime, prices: dict[int, MarketPrice]
    ) -> Position:
        short = prices.get(p.plan.short.contract.token)
        hedge = prices.get(p.plan.hedge.contract.token)
        if (
            short is None
            or hedge is None
            or short.token != p.plan.short.contract.token
            or hedge.token != p.plan.hedge.contract.token
            or not self.broker.valid(short, at)
            or not self.broker.valid(hedge, at)
            or abs((short.at - hedge.at).total_seconds())
            > p.plan.settings.quote_max_skew_seconds
        ):
            return p.model_copy(
                update={
                    "unrealised": None,
                    "mark_at": None,
                    "spread_debit": None,
                    "mark_prices": {},
                }
            )
        debit = (
            short.ask if short.ask is not None else short.last + self.fills.slippage
        ) - (hedge.bid if hedge.bid is not None else hedge.last - self.fills.slippage)
        cash, short_remaining, hedge_remaining = Decimal(0), 0, 0
        for o in p.orders.values():
            if o.fill is None:
                continue
            signed = o.fill.quantity * (1 if o.side == Side.BUY else -1)
            cash -= signed * o.fill.price
            if o.token == p.plan.short.contract.token:
                short_remaining -= signed
            else:
                hedge_remaining += signed
        short_price = (
            short.ask if short.ask is not None else short.last + self.fills.slippage
        )
        hedge_price = (
            hedge.bid if hedge.bid is not None else hedge.last - self.fills.slippage
        )
        gross = cash - short_remaining * short_price + hedge_remaining * hedge_price
        costs = sum((o.fill.costs for o in p.orders.values() if o.fill), Decimal(0))
        return p.model_copy(
            update={
                "unrealised": gross,
                "costs": costs,
                "spread_debit": debit if p.status == PositionStatus.OPEN else None,
                "mark_at": at,
                "mark_prices": {short.token: short, hedge.token: hedge},
            }
        )
