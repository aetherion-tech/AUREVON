"""Explicit opt-in Close-source Renko; no readiness or TradingView parity claim."""

import hashlib
import json
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

from app.market.candles_5m import MarketCandle
from app.market.renko_builder import IST, Brick, RenkoBuilder, WickBrick
from app.market.warmup import SessionCalendar


class FiveMinuteCloseRenko(RenkoBuilder):
    """Consume completed spot minutes; only complete five-minute closes build bricks.

    Wicks use five-minute CLOSE extrema since the last emitted brick, not minute
    high/low. Only opposite excursions greater than one box are exposed. Missing
    or partial periods are discarded and mark a sticky gap; no bars are filled.
    History and live callers use the same input method and versioned checkpoint.
    """

    def __init__(
        self, box: float | str, anchor: float | str, calendar: SessionCalendar
    ) -> None:
        super().__init__(box, anchor)
        self.calendar = calendar
        self.bucket: datetime | None = None
        self.minute_end: datetime | None = None
        self.minute_count = 0
        self.close: Decimal | None = None
        self.complete = True
        self.gap_detected = False
        self.excursion_high: Decimal | None = None
        self.excursion_low: Decimal | None = None

    def configuration(self) -> dict[str, Any]:
        calendar = [
            self.calendar.first_date.isoformat(),
            self.calendar.last_date.isoformat(),
            [
                (s.opening.isoformat(), s.closing.isoformat())
                for s in self.calendar.sessions
            ],
        ]
        return dict(
            version=2,
            mode="five_minute_close",
            source_minutes=5,
            wicks="close_excursion",
            box=str(self.box.normalize()),
            anchor=str(self.anchor.normalize()),
            calendar_sha256=hashlib.sha256(json.dumps(calendar).encode()).hexdigest(),
        )

    def on_price(self, price: Decimal | float | str, ts: datetime) -> list[Brick]:
        raise ValueError("Five-minute Renko requires completed minute candles")

    def on_candle(self, candle: MarketCandle) -> list[Brick]:
        # Validation or construction failure cannot partially advance a caller.
        working = self.clone()
        output = working._on_candle(candle)
        self.__dict__.update(working.__dict__)
        return output

    def clone(self) -> "FiveMinuteCloseRenko":
        # SessionCalendar and its session tuple are frozen. Copy mutable state,
        # not hundreds of immutable annual sessions for every tick/minute.
        return deepcopy(self, {id(self.calendar): self.calendar})

    def _on_candle(self, candle: MarketCandle) -> list[Brick]:
        if candle.time.utcoffset() is None or candle.end.utcoffset() is None:
            raise ValueError("Aware minute timestamps required")
        start, end = candle.time.astimezone(IST), candle.end.astimezone(IST)
        prices = (candle.open, candle.high, candle.low, candle.close)
        if (
            end - start != timedelta(minutes=1)
            or start.second
            or start.microsecond
            or type(candle.partial) is not bool
            or any(
                not isinstance(p, Decimal) or not p.is_finite() or p <= 0
                for p in prices
            )
            or not candle.low
            <= min(candle.open, candle.close)
            <= max(candle.open, candle.close)
            <= candle.high
        ):
            raise ValueError("Invalid completed spot minute")
        session = next(
            (
                s
                for s in self.calendar.sessions
                if s.opening <= start < end <= s.closing
            ),
            None,
        )
        if session is None:
            raise ValueError("Minute outside supplied exchange session calendar")
        if self.minute_end is not None:
            if start < self.minute_end:
                raise ValueError("Duplicate or backward minute")
            if start != self.minute_end and not (
                start == session.opening
                and any(s.closing == self.minute_end for s in self.calendar.sessions)
                and not any(
                    self.minute_end < s.opening < start for s in self.calendar.sessions
                )
            ):
                self.gap_detected = True
                self.complete = False
        bucket = session.opening + (
            (start - session.opening) // timedelta(minutes=5)
        ) * timedelta(minutes=5)
        if bucket != self.bucket:
            if self.bucket is not None:
                self.gap_detected = True
            self.bucket, self.minute_count, self.complete = bucket, 0, start == bucket
            if not self.complete:
                self.gap_detected = True
        self.minute_count += 1
        self.complete = self.complete and not candle.partial
        if candle.partial:
            self.gap_detected = True
        self.minute_end, self.close = end, candle.close
        if end != bucket + timedelta(minutes=5):
            return []
        valid = self.complete and self.minute_count == 5
        price = candle.close
        self.bucket, self.minute_count, self.close = None, 0, None
        self.complete = True
        if not valid:
            self.gap_detected = True
            return []
        return self._close(price, end)

    def _close(self, price: Decimal, end: datetime) -> list[Brick]:
        self.excursion_high = max(self.excursion_high or price, price)
        self.excursion_low = min(self.excursion_low or price, price)
        bodies = super().on_price(price, end)
        if self.last is not None and self.last.close <= 0:
            raise ValueError("Anchor grid must produce a positive Renko seed")
        output: list[Brick] = []
        for i, body in enumerate(bodies):
            high, low = body.high, body.low
            if i == 0:
                if body.direction == -1 and self.excursion_high > body.open + self.box:
                    high = self.excursion_high
                if body.direction == 1 and self.excursion_low < body.open - self.box:
                    low = self.excursion_low
            output.append(
                WickBrick(
                    body.index,
                    body.open,
                    body.close,
                    body.direction,
                    body.ts,
                    wick_high=high,
                    wick_low=low,
                )
            )
        if output:
            self.last = output[-1]
            self.excursion_high = self.excursion_low = price
        return output

    def snapshot(self) -> dict[str, Any]:
        return dict(
            configuration=self.configuration(),
            last=asdict(self.last) if self.last is not None else None,
            last_timestamp=self.last_timestamp,
            next_index=self.index,
            bucket=self.bucket,
            minute_end=self.minute_end,
            minute_count=self.minute_count,
            close=self.close,
            complete=self.complete,
            gap_detected=self.gap_detected,
            excursion_high=self.excursion_high,
            excursion_low=self.excursion_low,
        )

    def restore_snapshot(self, data: dict[str, Any]) -> None:
        """Restore only a matching, structurally consistent checkpoint atomically."""
        from app.market.persistence import brick_from

        working = FiveMinuteCloseRenko(str(self.box), str(self.anchor), self.calendar)
        if (
            set(data) != set(working.snapshot())
            or data["configuration"] != working.configuration()
        ):
            raise ValueError("Five-minute checkpoint configuration mismatch")
        for name in ("complete", "gap_detected"):
            if type(data[name]) is not bool:
                raise ValueError("Invalid checkpoint flag")
            setattr(working, name, data[name])
        for name in ("next_index", "minute_count"):
            if type(data[name]) is not int or data[name] < 0:
                raise ValueError("Invalid checkpoint count")
        working.index, working.minute_count = data["next_index"], data["minute_count"]
        if working.minute_count > 4:
            raise ValueError("Unfinished period has too many minutes")
        for name in ("last_timestamp", "bucket", "minute_end"):
            value = (
                datetime.fromisoformat(data[name]) if data[name] is not None else None
            )
            if value is not None and value.utcoffset() is None:
                raise ValueError("Naive checkpoint timestamp")
            setattr(working, name, value)
        for name in ("close", "excursion_high", "excursion_low"):
            try:
                number = Decimal(data[name]) if data[name] is not None else None
            except InvalidOperation:
                raise ValueError("Invalid checkpoint price") from None
            if number is not None and (not number.is_finite() or number <= 0):
                raise ValueError("Invalid checkpoint price")
            setattr(working, name, number)
        try:
            working.last = (
                brick_from(data["last"]) if data["last"] is not None else None
            )
        except InvalidOperation:
            raise ValueError("Invalid checkpoint brick price") from None
        if (
            (working.last is None) != (working.last_timestamp is None)
            or (working.last is None and working.index != 0)
            or (working.last is not None and working.last.index != working.index - 1)
            or (working.bucket is None) != (working.minute_count == 0)
            or (working.bucket is None) != (working.close is None)
        ):
            raise ValueError("Inconsistent checkpoint state")
        if working.bucket is not None:
            session = next(
                (
                    s
                    for s in working.calendar.sessions
                    if s.opening <= working.bucket < s.closing
                ),
                None,
            )
            if session is None or (working.bucket - session.opening) % timedelta(
                minutes=5
            ):
                raise ValueError("Unaligned checkpoint period")
            if (
                working.minute_end is None
                or not working.bucket
                < working.minute_end
                < working.bucket + timedelta(minutes=5)
                or (
                    working.complete
                    and working.minute_end
                    != working.bucket + timedelta(minutes=working.minute_count)
                )
            ):
                raise ValueError("Invalid unfinished period")
        for name in ("minute_end", "last_timestamp"):
            stamp = getattr(working, name)
            if stamp is not None:
                session = next(
                    (
                        s
                        for s in working.calendar.sessions
                        if s.opening < stamp <= s.closing
                    ),
                    None,
                )
                duration = timedelta(minutes=5 if name == "last_timestamp" else 1)
                if session is None or (stamp - session.opening) % duration:
                    raise ValueError("Unaligned checkpoint source timestamp")
        if not working.complete and not working.gap_detected:
            raise ValueError("Incomplete period cannot clear gap evidence")
        if working.last is not None:
            if (
                working.excursion_high is None
                or working.excursion_low is None
                or working.excursion_low > working.excursion_high
                or working.minute_end is None
                or working.last_timestamp is None
                or working.last_timestamp > working.minute_end
                or working.last.ts > working.last_timestamp
            ):
                raise ValueError("Invalid Renko seed/extrema")
            b = working.last
            if (
                type(b.index) is not int
                or type(b.direction) is not int
                or not b.open.is_finite()
                or not b.close.is_finite()
                or min(b.open, b.close) <= 0
                or (b.open - working.anchor) % working.box
                or (b.index == -1 and (b.open != b.close or b.direction != 0))
                or (
                    b.index >= 0
                    and (
                        abs(b.close - b.open) != working.box
                        or b.direction != (1 if b.close > b.open else -1)
                    )
                )
            ):
                raise ValueError("Invalid checkpoint brick geometry")
        elif working.excursion_high is not None or working.excursion_low is not None:
            raise ValueError("Extrema without Renko seed")
        self.__dict__.update(working.__dict__)
