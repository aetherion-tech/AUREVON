"""Read-only catalog/quotes and durable nonexecuting preview decisions."""

from datetime import UTC, datetime
from typing import Literal, cast
from uuid import uuid4

from pydantic import ValidationError
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.db.models import Instrument, InstrumentSnapshot, StrategyDecision
from app.market.renko_builder import IST
from app.market.warmup import SessionCalendar
from app.strategy.models import (
    CapitalSnapshot,
    Catalog,
    OptionContract,
    OptionQuote,
    PlanDecision,
    SignalInput,
    StrategySettings,
)
from app.strategy.planner import PlanRejected, build_plan


def load_catalog(engine: Engine, at: datetime) -> Catalog:
    try:
        return _load_catalog(engine, at)
    except ValidationError:
        raise PlanRejected("invalid_option_catalog") from None


def _load_catalog(engine: Engine, at: datetime) -> Catalog:
    with Session(engine) as db:
        source = db.get(InstrumentSnapshot, "NFO")
        if source is None:
            raise PlanRejected("catalog_unavailable")
        stamp = source.loaded_at
        stamp = stamp.replace(tzinfo=UTC) if stamp.tzinfo is None else stamp
        if stamp.astimezone(IST).date() != at.astimezone(IST).date() or stamp > at:
            raise PlanRejected("stale_catalog")
        rows = db.scalars(
            select(Instrument).where(
                Instrument.exchange == "NFO",
                Instrument.name == "NIFTY",
                Instrument.segment == "NFO-OPT",
                Instrument.instrument_type.in_(["CE", "PE"]),
                Instrument.expiry >= at.astimezone(IST).date(),
            )
        ).all()
        return Catalog(
            loaded_at=stamp,
            contracts=tuple(
                OptionContract(
                    token=r.instrument_token,
                    symbol=r.tradingsymbol,
                    expiry=r.expiry,
                    strike=r.strike,
                    option_type=cast(Literal["CE", "PE"], r.instrument_type),
                    lot_size=r.lot_size,
                    tick_size=r.tick_size,
                )
                for r in rows
                if r.expiry is not None
            ),
        )


def save_decision(
    engine: Engine,
    result: PlanDecision,
    signal: SignalInput,
    settings: StrategySettings,
    at: datetime,
    quotes: dict[int, OptionQuote] | None = None,
) -> PlanDecision:
    identity = uuid4().hex
    decision = result.model_copy(update={"decision_id": identity})
    with Session(engine) as db, db.begin():
        db.add(
            StrategyDecision(
                id=identity,
                signal_id=signal.signal_id,
                at=at.isoformat(),
                payload=decision.model_dump_json(),
                input=signal.model_dump_json(),
                settings=settings.model_dump_json(),
                quotes="["
                + ",".join(q.model_dump_json() for q in (quotes or {}).values())
                + "]",
            )
        )
    return decision


def preview(
    engine: Engine,
    signal: SignalInput,
    catalog: Catalog,
    quotes: dict[int, OptionQuote],
    capital: CapitalSnapshot | None,
    at: datetime,
    calendar: SessionCalendar,
    settings: StrategySettings | None = None,
) -> PlanDecision:
    settings = settings or StrategySettings()
    return save_decision(
        engine,
        build_plan(signal, catalog, quotes, capital, at, calendar, settings),
        signal,
        settings,
        at,
        quotes,
    )
