"""Real persisted domain projections and explicit owner-provided execution inputs."""

import json
from collections.abc import Callable
from datetime import datetime
from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from sqlalchemy import Engine, func, inspect, select
from sqlalchemy.orm import Session

from app.api.domain_contracts import (
    ActionResult,
    DataSettings,
    DecisionView,
    ExecutionControl,
    LegView,
    OrderView,
    PositionView,
    SettingsBundle,
    SettingsView,
    SignalRecord,
    WalletView,
)
from app.api.domain_storage import Commands, SettingsStore
from app.api.schemas import Page, Pagination
from app.db.models import (
    DomainDecision,
    IndicatorCheckpoint,
    IndicatorEvent,
    IndicatorResult,
    MarketCheckpoint,
    StrategyDecision,
)
from app.execution.models import MarketPrice, PaperBook, Position, Readiness, Rejection
from app.execution.service import ACTIVE, PaperExecution
from app.indicator.chart_history import digest, overlays
from app.market.persistence import encode
from app.market.renko_builder import IST
from app.market.service import MarketService
from app.strategy.models import Catalog, OptionQuote, PlanDecision, SignalInput
from app.strategy.planner import build_plan
from app.wallet.service import WalletService


def wallet_view(wallet: WalletService, b: PaperBook | None = None) -> WalletView:
    b = b if b is not None else wallet.snapshot()
    active = [p for p in b.positions.values() if p.status in ACTIVE]
    limit = b.day_capital * wallet.risk.daily_loss_pct / 100
    used = (
        max(
            Decimal(0),
            -(
                b.day_net
                + sum(
                    (
                        p.unrealised - p.costs
                        for p in active
                        if p.unrealised is not None
                    ),
                    Decimal(0),
                )
            ),
        )
        if all(p.unrealised is not None for p in active)
        else None
    )
    return WalletView(
        initialized=bool(b.ledger),
        balance=b.balance,
        free=max(Decimal(0), b.balance - b.reserved),
        reserved=b.reserved,
        auto_topup=bool(b.wallet_settings and b.wallet_settings.auto_topup),
        killed=b.killed,
        loss_locked=b.loss_locked,
        day_trades=b.day_trades,
        risk_day=b.day,
        daily_loss_limit=limit if b.day is not None and limit > 0 else None,
        daily_loss_used=used if b.day is not None and limit > 0 else None,
        daily_loss_utilisation_pct=(
            used / limit * 100
            if used is not None and b.day is not None and limit > 0
            else None
        ),
    )


def position_view(p: Position, engine: Engine | None = None) -> PositionView:
    source: dict[str, Any] = {}
    if engine is not None:
        try:
            stream, raw_index, raw_ordinal = p.plan.signal.signal_id.rsplit(":", 2)
            index, ordinal = int(raw_index), int(raw_ordinal)
            with Session(engine) as db:
                row = db.get(IndicatorResult, (stream, index))
                if row is not None and ordinal >= 0:
                    result = json.loads(row.payload)
                    event = result["events"][ordinal]
                    if (
                        event["kind"] == "ENTRY"
                        and event["trade_id"] == p.plan.signal.trade_id
                        and event["direction"] == p.plan.signal.direction
                    ):
                        explanation = next(
                            (
                                s.get("explanation", {}).get("tooltip")
                                for s in result["signals"]
                                if s["accepted"]
                                and s["type"] == event["type"]
                                and s["direction"] == event["direction"]
                            ),
                            None,
                        )
                        source = dict(
                            signal_stream=stream,
                            signal_index=index,
                            signal_explanation=explanation,
                            indicator_trade_id=event["trade_id"],
                        )
        except (ValueError, IndexError, KeyError):
            pass
    return_basis = p.gross - p.costs if p.status.value == "CLOSED" else p.unrealised
    legs = []
    for label, leg in (("entry_short", p.plan.short), ("entry_hedge", p.plan.hedge)):
        order = p.orders.get(label)
        mark = p.mark_prices.get(leg.contract.token)
        legs.append(
            LegView(
                role=leg.role,
                symbol=leg.contract.symbol,
                token=leg.contract.token,
                quantity=leg.quantity,
                entry=order.fill.price if order and order.fill else None,
                mark=mark.last if mark else None,
            )
        )
    return PositionView(
        **source,
        trade_id=p.id,
        decision_id=p.decision_id,
        state=p.status,
        created_at=p.transitions[0].at,
        mark_at=p.mark_at,
        legs=legs,
        margin=p.plan.required_margin,
        gross=p.gross,
        costs=p.costs,
        net=p.gross - p.costs,
        unrealised=p.unrealised,
        spread_debit=p.spread_debit,
        exit_reason=p.exit_reason,
        stop_debit_per_unit=p.plan.stop_debit_per_unit,
        profit_capture_debit_per_unit=p.plan.profit_capture_debit_per_unit,
        profit_capture_enabled=p.plan.profit_capture_enabled,
        margin_return_pct=(
            return_basis / p.plan.required_margin * 100
            if p.plan.required_margin > 0 and return_basis is not None
            else None
        ),
        closed_at=p.transitions[-1].at if p.status.value == "CLOSED" else None,
        orders=[
            OrderView(
                id=o.id,
                status=o.status,
                side=o.side,
                token=o.token,
                quantity=o.quantity,
                filled_at=o.fill.at if o.fill else None,
                fill_price=o.fill.price if o.fill else None,
                costs=o.fill.costs if o.fill else None,
                reason=o.reason,
                created_at=o.at,
                eligible_at=o.eligible_at,
            )
            for o in p.orders.values()
        ],
    )


class PaperRuntime:
    """Owner capability, never constructed or armed by HTTP or normal startup.

    Providers must be server-owned and point-in-time. Entry authorization defaults
    false; polling still services exits when readiness fails. UI cannot supply
    prices, clocks, contracts, wallets, readiness, or an authorization switch.
    """

    def __init__(
        self,
        wallet: WalletService,
        settings: SettingsView,
        readiness: Callable[[datetime], Readiness],
        catalog: Callable[[], Catalog],
        options: Callable[[], dict[int, OptionQuote]],
        prices: Callable[[], dict[int, MarketPrice]],
        *,
        entries_allowed: bool = False,
    ) -> None:
        if (
            wallet.fills != settings.settings.fills
            or wallet.risk != settings.settings.risk
            or wallet.snapshot().wallet_settings != settings.settings.wallet
        ):
            raise ValueError("owner wallet settings differ from selected version")
        self.wallet, self.settings = wallet, settings
        self.readiness, self.catalog, self.options, self.prices = (
            readiness,
            catalog,
            options,
            prices,
        )
        self.entries_allowed = entries_allowed

    def poll(self, at: datetime) -> None:
        self.wallet.step(at, self.prices(), self.readiness(at))


class DomainService:
    def __init__(
        self,
        engine: Engine,
        market: MarketService,
        execution: Callable[[], PaperExecution | None],
        runtime: Callable[[], PaperRuntime | None],
    ) -> None:
        self.engine, self.market = engine, market
        self.execution_provider, self.runtime_provider = execution, runtime
        self.commands = Commands(engine)
        self.published: dict[str, str] = {}
        self.publish: Callable[[Any], Any] = lambda event: None
        self.available_tables: set[str] | None = None
        data = DataSettings(
            mode=market.settings.renko_mode,
            box=Decimal(str(market.settings.renko_box)),
            anchor=Decimal(str(market.settings.renko_anchor))
            if market.settings.renko_anchor is not None
            else None,
            lookback_days=market.settings.warmup_lookback_trading_days,
        )
        from app.indicator.settings import IndicatorSettings

        self.settings = SettingsStore(
            engine,
            SettingsBundle(
                data=data, pine=IndicatorSettings(boxSize=float(data.box)).values
            ),
        )

    def execution(self) -> PaperExecution:
        service = self.execution_provider()
        if not isinstance(service, PaperExecution):
            raise HTTPException(409, detail="paper_account_unavailable")
        if service.user_id != "local":
            raise HTTPException(403)
        return service

    def wallet(self) -> WalletService:
        service = self.execution()
        if not isinstance(service, WalletService):
            raise HTTPException(409)
        return service

    def signals(
        self, stream: str, limit: int, offset: int, accepted: bool | None = None
    ) -> Page[SignalRecord]:
        statement = (
            select(IndicatorEvent, IndicatorResult.payload)
            .join(
                IndicatorResult,
                (IndicatorResult.stream == IndicatorEvent.stream)
                & (IndicatorResult.index == IndicatorEvent.index),
            )
            .where(IndicatorEvent.stream == stream, IndicatorEvent.kind == "SIGNAL")
        )
        if accepted is not None:
            statement = statement.where(
                func.json_extract(IndicatorEvent.payload, "$.accepted") == accepted
            )
        with Session(self.engine) as db:
            if db.get(IndicatorCheckpoint, stream) is None:
                raise HTTPException(
                    409 if db.get(MarketCheckpoint, stream) is not None else 404
                )
            rows = db.execute(
                statement.order_by(IndicatorEvent.index.desc(), IndicatorEvent.ordinal)
                .offset(offset)
                .limit(limit + 1)
            ).all()
            items = []
            for row, raw_result in rows[:limit]:
                candidate, result = json.loads(row.payload), json.loads(raw_result)
                explanation = candidate.get("explanation", {})
                entry_ordinal = (
                    next(
                        (
                            i
                            for i, e in enumerate(result["events"])
                            if e["kind"] == "ENTRY"
                            and e["type"] == candidate["type"]
                            and e["direction"] == candidate["direction"]
                        ),
                        None,
                    )
                    if candidate["accepted"]
                    else None
                )
                text = explanation.get("tooltip", candidate["reason"].replace("_", " "))
                items.append(
                    SignalRecord(
                        id=f"{stream}:{row.index}:candidate:{row.ordinal}",
                        stream=stream,
                        index=row.index,
                        ordinal=row.ordinal,
                        at=datetime.fromtimestamp(result["time_ms"] / 1000, IST),
                        code=candidate["type"],
                        direction=candidate["direction"],
                        grade=candidate["grade"],
                        risk=candidate["risk"]["label"],
                        accepted=candidate["accepted"],
                        reason=candidate["reason"],
                        explanation=text,
                        entry_event_ordinal=entry_ordinal,
                        signal_id=f"{stream}:{row.index}:{entry_ordinal}"
                        if entry_ordinal is not None
                        else None,
                    )
                )
            return Page(
                items=items,
                pagination=Pagination(
                    limit=limit,
                    offset=offset,
                    next_offset=offset + limit if len(rows) > limit else None,
                ),
            )

    def decisions(self, limit: int, offset: int) -> Page[DecisionView]:
        with Session(self.engine) as db:
            rows = db.scalars(
                select(DomainDecision)
                .where(DomainDecision.scope == "PAPER")
                .order_by(DomainDecision.at.desc(), DomainDecision.id)
                .offset(offset)
                .limit(limit + 1)
            ).all()
            return Page(
                items=[
                    DecisionView.model_validate_json(r.payload) for r in rows[:limit]
                ],
                pagination=Pagination(
                    limit=limit,
                    offset=offset,
                    next_offset=offset + limit if len(rows) > limit else None,
                ),
            )

    def confirm(self, identity: str) -> ActionResult:
        # Recover a committed terminal admission/reject even if the owner has
        # restarted or market/settings readiness changed after its commit.
        wallet = self.wallet()
        committed = wallet.snapshot()
        admitted = next(
            (p for p in committed.positions.values() if p.decision_id == identity), None
        )
        if admitted is not None:
            return ActionResult(
                accepted=True,
                trade_id=admitted.id,
                reason="already_admitted",
                state=admitted.status,
            )
        if identity in committed.rejects:
            return ActionResult(
                accepted=False, reason="; ".join(committed.rejects[identity].reasons)
            )
        runtime = self.runtime_provider()
        wallet = self.wallet()
        if (
            not isinstance(runtime, PaperRuntime)
            or runtime.wallet is not wallet
            or not runtime.entries_allowed
        ):
            raise HTTPException(409)
        chosen = self.settings.read()
        if chosen != runtime.settings:
            raise HTTPException(409)
        b = wallet.snapshot()
        prior = next(
            (p for p in b.positions.values() if p.decision_id == identity), None
        )
        if prior:
            return ActionResult(
                accepted=True,
                trade_id=prior.id,
                reason="already_admitted",
                state=prior.status,
            )
        with Session(self.engine) as db:
            row = db.get(StrategyDecision, identity)
            if row is None:
                raise HTTPException(404)
            if not PlanDecision.model_validate_json(row.payload).accepted:
                raise HTTPException(409)
            signal = SignalInput.model_validate_json(row.input)
            try:
                stream, index, ordinal = signal.signal_id.rsplit(":", 2)
                result = db.get(IndicatorResult, (stream, int(index)))
                if (
                    result is None
                    or SignalInput.from_indicator(
                        stream, json.loads(result.payload), int(ordinal)
                    )
                    != signal
                ):
                    raise ValueError("signal lineage unavailable")
                market = db.get(MarketCheckpoint, stream)
                checkpoint = db.get(IndicatorCheckpoint, stream)
                if market is None or checkpoint is None:
                    raise ValueError("source unavailable")
                publication = overlays(
                    db,
                    dict(
                        stream=stream,
                        revision=market.revision,
                        configuration_id=digest(market.configuration),
                    ),
                    [],
                    None,
                )
                source = publication["indicator_source"]
                if source is None or source.settings_id != digest(
                    encode(chosen.settings.pine)
                ):
                    raise ValueError("indicator settings/source unavailable")
                config = json.loads(market.configuration)
                if (
                    Decimal(str(config["box"])) != chosen.settings.data.box
                    or config.get("mode") != chosen.settings.data.mode
                    or (
                        chosen.settings.data.anchor is not None
                        and Decimal(str(config["anchor"]))
                        != chosen.settings.data.anchor
                    )
                ):
                    raise ValueError("grid rebuild required")
            except (ValueError, KeyError, IndexError, TypeError, StopIteration):
                raise HTTPException(409) from None
        now = self.market.clock()
        decision = build_plan(
            signal,
            runtime.catalog(),
            runtime.options(),
            wallet.planning_capital(now),
            now,
            wallet.calendar,
            chosen.settings.strategy,
        )
        if not decision.accepted or decision.plan is None:

            def reject(book: Any, revision: int) -> None:
                if identity not in book.rejects:
                    book.rejects[identity] = Rejection(
                        decision_id=identity,
                        signal_id=signal.signal_id,
                        at=now,
                        reasons=(decision.reason,),
                    )

            wallet._mutate(reject)
            return ActionResult(accepted=False, reason=decision.reason)
        trade = wallet.enter(
            identity, decision.plan, now, runtime.readiness(now), runtime.prices()
        )
        return ActionResult(
            accepted=trade is not None,
            trade_id=trade,
            reason="admitted_pending_fills"
            if trade
            else "; ".join(wallet.snapshot().rejects[identity].reasons),
            state=wallet.snapshot().positions[trade].status if trade else None,
        )

    def prepare(
        self, stream: str, index: int, ordinal: int, key: str | None = None
    ) -> PlanDecision:
        from app.strategy.service import decision_identity, save_decision

        if key is not None:
            with Session(self.engine) as db:
                prior = db.get(StrategyDecision, decision_identity(key))
                if prior is not None:
                    return PlanDecision.model_validate_json(prior.payload)

        runtime = self.runtime_provider()
        wallet = self.wallet()
        if runtime is None or runtime.wallet is not wallet:
            raise HTTPException(409)
        selected = self.settings.read()
        if selected != runtime.settings:
            raise HTTPException(409)
        with Session(self.engine) as db:
            row = db.get(IndicatorResult, (stream, index))
            if row is None:
                raise HTTPException(404)
            try:
                signal = SignalInput.from_indicator(
                    stream, json.loads(row.payload), ordinal
                )
            except (IndexError, ValueError, KeyError, StopIteration):
                raise HTTPException(422) from None
        now = self.market.clock()
        settings = selected.settings.strategy
        quotes = runtime.options()
        result = build_plan(
            signal,
            runtime.catalog(),
            quotes,
            wallet.planning_capital(now),
            now,
            wallet.calendar,
            settings,
        )
        return save_decision(self.engine, result, signal, settings, now, quotes, key)

    def control(self, action: str, identity: str | None, key: str) -> ExecutionControl:
        self.execution()  # Unavailable owners must not consume a legacy retry key.

        def run() -> str:
            service = self.execution()
            if action == "kill":
                service.kill(self.market.clock())
            else:
                assert identity is not None
                service.close(identity, self.market.clock())
            b = service.snapshot()
            return ExecutionControl(
                entries_locked=b.killed or b.loss_locked,
                pending_closures=sum(p.status in ACTIVE for p in b.positions.values()),
            ).model_dump_json()

        return ExecutionControl.model_validate_json(
            self.commands.run(key, action, identity or "", run)
        )

    def poll(self, at: datetime) -> None:
        runtime = self.runtime_provider()
        if runtime is not None:
            runtime.poll(at)
            if self.market.settings.pnl_tick_recording_enabled:
                from app.wallet.pnl_ticks import sample

                sample(self.engine, at)

    def rebind_wallet(self, stream: str | None = None) -> WalletService:
        """Owner-only configuration application after stopping and rebuilding.

        Not exposed as a client arming endpoint. Grid changes need a matching
        committed market/indicator publication before immutable settings change.
        It preserves balances, history, risk counters and kill/loss locks.
        """
        from app.broker.paper_broker import PaperBroker

        with self.commands.lock:
            if self.market.desired or self.market.worker is not None:
                raise ValueError("stop the managed owner before rebinding settings")
            wallet = self.wallet()
            selected = self.settings.read()
            if selected.requires_rebuild:
                stream = stream or self.market.settings.market_stream
                with Session(self.engine) as db:
                    market = db.get(MarketCheckpoint, stream)
                    if market is None:
                        raise ValueError("rebuilt stream unavailable")
                    config = json.loads(market.configuration)
                    publication = overlays(
                        db,
                        dict(
                            stream=stream,
                            revision=market.revision,
                            configuration_id=digest(market.configuration),
                        ),
                        [],
                        None,
                    )
                    source = publication["indicator_source"]
                    desired = selected.settings
                    if (
                        source is None
                        or source.settings_id != digest(encode(desired.pine))
                        or Decimal(str(config["box"])) != desired.data.box
                        or config.get("mode") != desired.data.mode
                        or (
                            desired.data.anchor is not None
                            and Decimal(str(config["anchor"])) != desired.data.anchor
                        )
                    ):
                        raise ValueError("rebuilt source/configuration mismatch")

            def apply(book: PaperBook, revision: int) -> None:
                if any(p.status in ACTIVE for p in book.positions.values()):
                    raise ValueError("close all exposure before changing assumptions")
                wallet._set(
                    book,
                    fill_settings=selected.settings.fills,
                    risk_settings=selected.settings.risk,
                    wallet_settings=selected.settings.wallet,
                )

            wallet._mutate(apply)
            wallet.fills, wallet.risk = selected.settings.fills, selected.settings.risk
            wallet.broker = PaperBroker(wallet.fills)
            data = selected.settings.data
            self.market.settings.renko_mode = data.mode
            self.market.settings.renko_box = float(data.box)
            self.market.settings.renko_anchor = (
                float(data.anchor) if data.anchor is not None else None
            )
            self.market.settings.warmup_lookback_trading_days = data.lookback_days
            if stream is not None:
                self.market.settings.market_stream = stream
            return wallet

    def entries_enabled(self, book: PaperBook | None = None) -> bool:
        runtime = self.runtime_provider()
        if runtime is None or not runtime.entries_allowed:
            return False
        if (
            self.execution_provider() is not runtime.wallet
            or self.settings.read() != runtime.settings
        ):
            return False
        now = self.market.clock()
        b = book if book is not None else runtime.wallet.snapshot()
        gate = runtime.readiness(now)
        return (
            gate.ready()
            and 0 <= (now - gate.at).total_seconds() <= 1
            and not b.killed
            and not b.loss_locked
            and not any(p.status in ACTIVE for p in b.positions.values())
            and runtime.wallet.risk.entry_start
            <= now.time()
            < runtime.wallet.risk.entry_end
            and any(
                s.opening <= now < s.closing for s in runtime.wallet.calendar.sessions
            )
        )

    def sample(self) -> dict[str, Any]:
        from app.api.domain_contracts import PnlSummary
        from app.api.live_contracts import (
            AlertData,
            PositionData,
            SignalData,
            TradeData,
        )
        from app.db.models import DashboardAlert
        from app.wallet.reporting import summary

        missing = {"indicators", "signals", "execution", "positions", "wallet", "pnl"}
        result: dict[str, Any] = {}
        if self.available_tables is None:
            # New domain migrations are applied only with the owner stopped.
            # Keep the accepted feed snapshot usable on its older schema.
            self.available_tables = set(inspect(self.engine).get_table_names())
        stream = self.market.settings.market_stream
        try:
            if (
                not {"indicator_checkpoints", "indicator_events", "indicator_results"}
                <= self.available_tables
            ):
                raise HTTPException(409)
            signals = self.signals(stream, 50, 0).items
            values = [
                SignalData(
                    id=s.id,
                    code=s.code,
                    accepted=s.accepted,
                    reason=s.reason,
                    explanation=s.explanation,
                    detail=s,
                )
                for s in signals
            ]
            result["signals"] = values
            missing.discard("signals")
            for value in reversed(values):
                self._publish("signal:" + value.id, value)
        except HTTPException as error:
            if error.status_code not in (404, 409):
                raise
        execution = self.execution_provider()
        if execution is not None:
            execution = self.execution()
            b = execution.snapshot()
            active = [
                position_view(p) for p in b.positions.values() if p.status in ACTIVE
            ]
            closed = [p for p in b.positions.values() if p.status not in ACTIVE]
            result["positions"] = active
            result["last_trade"] = (
                position_view(max(closed, key=lambda p: p.transitions[-1].at))
                if closed
                else None
            )
            missing -= {"positions", "execution"}
            for item in active:
                self._publish(
                    "position:" + item.trade_id,
                    PositionData(
                        trade_id=item.trade_id,
                        state=item.state,
                        mtm=item.unrealised,
                        detail=item,
                    ),
                )
            # Recent durable history is reloaded through REST on resync; avoid
            # flooding the finite journal with old transitions on every sample.
            recent = sorted(
                b.positions.values(), key=lambda p: p.transitions[-1].at, reverse=True
            )[:128]
            for p in recent:
                for i, transition in enumerate(p.transitions):
                    self._publish(
                        f"trade:{p.id}:{i}",
                        TradeData(trade_id=p.id, event=transition.state),
                    )
            if isinstance(execution, WalletService):
                result["wallet"] = wallet_view(execution, b)
                day = self.market.clock().date()
                result["pnl"] = PnlSummary.model_validate(summary(b, day, day))
                result["entries_enabled"] = self.entries_enabled(b)
                missing -= {"wallet", "pnl"}
        with Session(self.engine) as db:
            alerts = db.scalars(
                select(DashboardAlert)
                .order_by(DashboardAlert.at.desc(), DashboardAlert.id)
                .limit(200)
            ).all()
            for row in reversed(alerts):
                alert_value = AlertData.model_validate(
                    {k: getattr(row, k) for k in AlertData.model_fields}
                )
                self._publish("alert:" + alert_value.id, alert_value)
        result["unavailable"] = sorted(missing)
        return result

    def _publish(self, key: str, value: Any) -> None:
        encoded = value.model_dump_json()
        if self.published.get(key) != encoded:
            self.publish(value)
            self.published[key] = encoded
        while len(self.published) > 2048:
            del self.published[next(iter(self.published))]
