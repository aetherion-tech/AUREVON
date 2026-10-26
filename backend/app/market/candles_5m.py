"""Session-aligned live candles and Pine's session HLC3-volume VWAP."""

from dataclasses import dataclass, replace
from datetime import date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation

from app.broker.kite_auth import IST
from app.market.warmup import SessionCalendar


@dataclass(frozen=True)
class MarketCandle:
    time: datetime
    end: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal | None
    oi: Decimal | None
    partial: bool
    vwap: Decimal | None = None
    vwap_partial: bool = False


def number(value: object, *, positive: bool = False) -> Decimal:
    try:
        result = Decimal(str(value))
        if not result.is_finite() or result < 0 or (positive and result == 0):
            raise ValueError
        return result
    except (InvalidOperation, ValueError):
        raise ValueError("Invalid candle price, volume, or open interest") from None


class CandleBuilder:
    """One instrument per instance; no fabricated bars for empty intervals.

    Futures volume uses deltas of the daily cumulative counter. The first
    observation only establishes its baseline. Cross-boundary deltas are assigned
    to the bucket receiving the tick; these are sampled-feed approximations.
    The first bucket and any bucket affected by a detected gap are partial.
    """

    def __init__(
        self,
        minutes: int = 5,
        *,
        futures: bool = True,
        calendar: SessionCalendar | None = None,
    ) -> None:
        if minutes not in (1, 5):
            raise ValueError("Only one-minute and five-minute candles are supported")
        self.calendar = calendar
        self.minutes = minutes
        self.futures = futures
        self.current: MarketCandle | None = None
        self.last_time: datetime | None = None
        self.day: date | None = None
        self.cumulative: Decimal | None = None
        self.weighted = Decimal(0)
        self.total_volume = Decimal(0)
        self.vwap_partial = True
        self._next_partial = True
        self._closed_until: datetime | None = None

    def mark_gap(self) -> None:
        self._next_partial = True
        self.vwap_partial = True
        if self.current is not None:
            self.current = replace(self.current, partial=True)

    def _finish(self) -> MarketCandle:
        assert self.current is not None
        candle = self.current
        if self.futures and candle.volume is not None:
            self.weighted += (
                (candle.high + candle.low + candle.close) / 3
            ) * candle.volume
            self.total_volume += candle.volume
        result = replace(
            candle,
            vwap=self.weighted / self.total_volume if self.total_volume else None,
            vwap_partial=self.vwap_partial,
        )
        self.current = None
        self._closed_until = candle.end
        return result

    def import_completed(
        self,
        candle: MarketCandle,
        *,
        session_open: datetime,
        session_close: datetime,
        cutoff: datetime,
    ) -> MarketCandle:
        """Import direct bar volume, never a cumulative tick counter.

        Append only into an idle builder. Rebuild from source for repeated imports
        or corrections; do not mix history into an active live interval.
        """
        stamps = (candle.time, candle.end, session_open, session_close, cutoff)
        if any(t.tzinfo is None or t.utcoffset() is None for t in stamps):
            raise ValueError("Historical candle/session times must include a timezone")
        start, end, opening, closing, finish = (t.astimezone(IST) for t in stamps)
        step = timedelta(minutes=self.minutes)
        if (
            self.current is not None
            or opening.date() != closing.date()
            or not opening <= start < end <= closing
            or end > finish
            or end - start != step
            or (start - opening) % step != timedelta(0)
            or (self._closed_until is not None and start < self._closed_until)
        ):
            raise ValueError("Expected ordered completed candles in an idle session")
        prices = [
            number(value, positive=True)
            for value in (candle.open, candle.high, candle.low, candle.close)
        ]
        op, high, low, close = prices
        if low > min(op, close) or high < max(op, close) or high < low:
            raise ValueError("Invalid historical OHLC")
        volume = number(candle.volume) if self.futures else None
        oi = number(candle.oi) if self.futures and candle.oi is not None else None
        # All validation precedes mutation.
        if self.day != start.date():
            self.day = start.date()
            self.weighted = Decimal(0)
            self.total_volume = Decimal(0)
            self.vwap_partial = start != opening
        elif self._closed_until != start:
            self.vwap_partial = True
        self.vwap_partial = self.vwap_partial or candle.partial
        self.current = replace(
            candle,
            time=start,
            end=end,
            open=op,
            high=high,
            low=low,
            close=close,
            volume=volume,
            oi=oi,
        )
        result = self._finish()
        self.last_time = end
        # History cannot prove the exchange counter at the live boundary.
        self.cumulative = None
        self._next_partial = True
        return result

    def on_tick(
        self,
        price: object,
        ts: datetime,
        *,
        cumulative_volume: object = None,
        oi: object = None,
    ) -> list[MarketCandle]:
        if ts.tzinfo is None:
            raise ValueError("Candle timestamp must include a timezone")
        local = ts.astimezone(IST)
        price_value = number(price, positive=True)
        volume = number(cumulative_volume) if self.futures else None
        interest = number(oi) if oi is not None and self.futures else None
        if self.last_time is not None and local < self.last_time:
            return []
        if self._closed_until is not None and local < self._closed_until:
            return []
        if self.calendar is not None:
            session = next(
                (s for s in self.calendar.sessions if s.opening <= local < s.closing),
                None,
            )
            if session is None:
                return []
        elif local.weekday() >= 5 or not time(9, 15) <= local.time() < time(15, 30):
            return []
        out: list[MarketCandle] = []
        new_day = self.day != local.date()
        if new_day:
            if self.current is not None:
                out.append(self._finish())
            self.day = local.date()
            self.cumulative = None
            self.weighted = Decimal(0)
            self.total_volume = Decimal(0)
            self.vwap_partial = True
            self._next_partial = True
        opening = local.replace(
            minute=(local.minute // self.minutes) * self.minutes,
            second=0,
            microsecond=0,
        )
        if self.current is not None and opening > self.current.time:
            previous_end = self.current.end
            if opening > previous_end:
                self.mark_gap()
            out.append(self._finish())
        delta: Decimal | None = None
        if self.futures:
            assert volume is not None
            if self.cumulative is None:
                delta = Decimal(0)
                self.mark_gap()
            elif volume < self.cumulative:
                self.mark_gap()
                delta = Decimal(0)
            else:
                delta = volume - self.cumulative
            self.cumulative = volume
        if self.current is None:
            self.current = MarketCandle(
                opening,
                opening + timedelta(minutes=self.minutes),
                price_value,
                price_value,
                price_value,
                price_value,
                delta,
                interest,
                self._next_partial,
            )
            self._next_partial = False
        else:
            current = self.current
            self.current = replace(
                current,
                high=max(current.high, price_value),
                low=min(current.low, price_value),
                close=price_value,
                volume=(
                    current.volume + delta
                    if current.volume is not None and delta is not None
                    else None
                ),
                oi=interest,
            )
        self.last_time = local
        return out

    def advance(self, now: datetime) -> list[MarketCandle]:
        """Finalize elapsed intervals; never emit an unfinished candle.

        This clock-based close cannot prove feed completeness. If the last tick
        is over five seconds before the boundary, mark the bar partial.
        """
        if now.tzinfo is None:
            raise ValueError("Clock must include a timezone")
        if self.current is None or now < self.current.end:
            return []
        if self.last_time is None or self.current.end - self.last_time > timedelta(
            seconds=5
        ):
            self.mark_gap()
        return [self._finish()]
