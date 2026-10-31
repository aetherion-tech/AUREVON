"""Completed spot-only display history. Never attaches a trading/feed owner."""

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.broker.kite_auth import KiteAuth
from app.config import Settings
from app.db.models import (
    HistoricalSpotCandle,
    Instrument,
    MarketCheckpoint,
    StoredBrick,
    StoredCandle,
)
from app.market.candles_5m import CandleBuilder, MarketCandle
from app.market.construction import consume_spot
from app.market.exchange_calendar import ExchangeCalendar
from app.market.five_minute_renko import FiveMinuteCloseRenko
from app.market.historical import parse_candle
from app.market.persistence import PersistenceError, brick_from, encode
from app.market.renko_builder import Brick, RenkoBuilder
from app.market.spot_history import fetch_spot_history
from app.market.warmup import HistoryRange, WarmupPlan


@dataclass(frozen=True)
class ClosedChart:
    stream: str
    as_of: datetime
    bricks: int


def load_closed_chart(
    auth: KiteAuth,
    engine: Engine,
    settings: Settings,
    exchange: ExchangeCalendar,
    at: datetime,
    *,
    fetch: bool = False,
) -> ClosedChart | None:
    """Read matching cache, or explicitly fetch completed sources and publish once.

    fetch=False performs no broker access, source writes or Renko recalculation.
    An existing incompatible/corrupt display stream is never overwritten.
    """
    if settings.renko_anchor is None or settings.renko_mode != "minute_close":
        return None
    calendar = exchange.window(
        at, days=max(90, settings.warmup_lookback_trading_days * 3)
    )
    completed = [s for s in calendar.sessions if s.closing <= at]
    count = settings.warmup_lookback_trading_days
    if len(completed) < count:
        raise PersistenceError("Calendar lacks completed display lookback")
    selected = completed[-count:]
    cutoff = selected[-1].closing
    with Session(engine) as db:
        spot = db.get(Instrument, ("NSE", "NIFTY 50"))
        if spot is None or spot.instrument_token <= 0:
            if not fetch:
                return None
            raise PersistenceError("NIFTY spot catalog required for historical chart")
        token = spot.instrument_token
    renko: RenkoBuilder
    if settings.renko_source_minutes == 5:
        renko = FiveMinuteCloseRenko(
            str(settings.renko_box),
            str(settings.renko_anchor),
            exchange.year(cutoff.year),
        )
        profile = renko.configuration()
    else:
        renko = RenkoBuilder(settings.renko_box, settings.renko_anchor)
        profile = dict(
            mode="minute_close",
            source_minutes=1,
            wicks=False,
            box=str(renko.box.normalize()),
            anchor=str(renko.anchor.normalize()),
        )
    configuration = encode(
        dict(
            **profile,
            source_kind="CLOSED_SESSION_HISTORY",
            scope="SPOT_ONLY_DISPLAY",
            spot=token,
            future=None,
            as_of=cutoff,
            lookback_sessions=count,
            first=selected[0].opening,
            entries_enabled=False,
            calendar_sessions=[(s.opening, s.closing) for s in selected],
            reference_verified=False,
        )
    )
    fingerprint = hashlib.sha256(configuration.encode()).hexdigest()[:24]
    stream = f"{settings.market_stream}:closed:{fingerprint}"
    with Session(engine) as db:
        existing = db.get(MarketCheckpoint, stream)
        if existing is not None:
            rows = db.scalars(
                select(StoredBrick)
                .where(StoredBrick.stream == stream)
                .order_by(StoredBrick.index)
            ).all()
            state = json.loads(existing.state)
            manifest = hashlib.sha256(
                encode([(r.index, r.payload) for r in rows]).encode()
            ).hexdigest()
            if (
                existing.configuration != configuration
                or not rows
                or state.get("bricks") != len(rows)
                or state.get("manifest") != manifest
                or [r.index for r in rows] != list(range(len(rows)))
            ):
                raise PersistenceError(
                    "Historical display cache changed; retain evidence"
                )
            for row in rows:
                brick = brick_from(json.loads(row.payload))
                if brick.index != row.index or brick.ts > cutoff:
                    raise PersistenceError("Invalid historical display lineage")
            return ClosedChart(stream, cutoff, len(rows))
    if not fetch:
        return None
    ranges = tuple(
        HistoryRange("minute", s.opening, s.closing - timedelta(minutes=1))
        for s in selected
    )
    plan = WarmupPlan("cold_start", cutoff, ranges, (), selected[0].opening.date())
    result = fetch_spot_history(auth, engine, stream, token, plan)
    if result.missing_minutes:
        raise PersistenceError("Historical display source has missing minutes")
    builder = CandleBuilder(1, futures=False, calendar=calendar)
    sessions = {s.opening.date(): s for s in selected}
    prices: list[MarketCandle] = []
    bricks: list[Brick] = []
    with Session(engine) as db:
        raw = db.scalars(
            select(HistoricalSpotCandle)
            .where(
                HistoricalSpotCandle.stream == stream,
                HistoricalSpotCandle.token == token,
            )
            .order_by(HistoricalSpotCandle.time)
        ).all()
        sources = [(r.time, r.completed_at, r.payload) for r in raw]
    expected = {
        s.opening + i * timedelta(minutes=1)
        for s in selected
        for i in range((s.closing - s.opening) // timedelta(minutes=1))
    }
    seen = set()
    for stamp, end, payload in sources:
        data = json.loads(payload)
        parsed = parse_candle(
            [data[k] for k in ("time", "open", "high", "low", "close", "volume")],
            oi=False,
        )
        if (
            parsed.time not in expected
            or parsed.time in seen
            or datetime.fromisoformat(stamp) != parsed.time
            or datetime.fromisoformat(end) != parsed.time + timedelta(minutes=1)
        ):
            raise PersistenceError("Historical display source grid mismatch")
        seen.add(parsed.time)
        s = sessions[parsed.time.date()]
        candle = builder.import_completed(
            MarketCandle(
                parsed.time,
                parsed.time + timedelta(minutes=1),
                parsed.open,
                parsed.high,
                parsed.low,
                parsed.close,
                None,
                None,
                False,
            ),
            session_open=s.opening,
            session_close=s.closing,
            cutoff=cutoff,
        )
        prices.append(candle)
        bricks.extend(consume_spot(renko, candle))
    if seen != expected or not bricks:
        raise PersistenceError(
            "Historical display has insufficient completed source/bricks"
        )
    payloads = [(b.index, encode(asdict(b))) for b in bricks]
    manifest = hashlib.sha256(encode(payloads).encode()).hexdigest()
    with Session(engine) as db, db.begin():
        if db.get(MarketCheckpoint, stream) is not None:
            raise PersistenceError("Historical display changed during preparation")
        if (
            db.scalar(select(StoredBrick).where(StoredBrick.stream == stream).limit(1))
            is not None
        ):
            raise PersistenceError("Historical display has orphaned output")
        db.add(
            MarketCheckpoint(
                stream=stream,
                revision=1,
                configuration=configuration,
                state=encode(
                    dict(
                        source_kind="CLOSED_SESSION_HISTORY",
                        as_of=cutoff,
                        bricks=len(bricks),
                        manifest=manifest,
                        entries_enabled=False,
                    )
                ),
            )
        )
        db.add_all(
            [StoredBrick(stream=stream, index=i, payload=p) for i, p in payloads]
        )
        db.add_all(
            [
                StoredCandle(
                    stream=stream,
                    token=token,
                    time=c.time.astimezone(UTC).isoformat(),
                    payload=encode(asdict(c)),
                )
                for c in prices
            ]
        )
    return ClosedChart(stream, cutoff, len(bricks))
