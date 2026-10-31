"""Traditional, close-source Renko, following SPEC section 9."""

from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_FLOOR, Decimal
from typing import Literal
from zoneinfo import ZoneInfo

import structlog

IST = ZoneInfo("Asia/Kolkata")
log = structlog.get_logger(__name__)


@dataclass(frozen=True)
class Brick:
    index: int
    open: Decimal
    close: Decimal
    direction: int
    ts: datetime
    volume: Decimal = Decimal(0)

    @property
    def high(self) -> Decimal:
        return max(self.open, self.close)

    @property
    def low(self) -> Decimal:
        return min(self.open, self.close)


@dataclass(frozen=True, kw_only=True)
class WickBrick(Brick):
    """Observed Renko OHLC; separate from the legacy body-only constructor.

    Explicit extrema are immutable input evidence, never inferred from a body.
    Keeping this subclass separate preserves legacy payload/retry identities.
    """

    wick_high: Decimal
    wick_low: Decimal

    def __post_init__(self) -> None:
        prices = (self.open, self.close, self.wick_high, self.wick_low)
        if any(not p.is_finite() or p <= 0 for p in prices) or not (
            self.wick_low
            <= min(self.open, self.close)
            <= max(self.open, self.close)
            <= self.wick_high
        ):
            raise ValueError("Invalid Renko wick OHLC")

    @property
    def high(self) -> Decimal:
        return self.wick_high

    @property
    def low(self) -> Decimal:
        return self.wick_low


class RenkoBuilder:
    """Feed completed minute closes or ticks, as selected by the caller.

    Decimal prices keep inclusive boundaries exact. The first sample seeds the
    grid without emitting a brick. State continues across session boundaries.
    Minute-close mode ignores equal/older timestamps. Tick mode preserves equal-time
    samples in caller-supplied order; one input can emit many bricks.
    Replay the original input file with identical settings to restore state.
    """

    def __init__(
        self,
        box: Decimal | float | str = 50,
        anchor: Decimal | float | str = 0,
        mode: Literal["minute_close", "tick"] = "minute_close",
    ) -> None:
        self.box = Decimal(str(box))
        self.anchor = Decimal(str(anchor))
        if not self.box.is_finite() or self.box <= 0:
            raise ValueError("box must be finite and positive")
        if not self.anchor.is_finite():
            raise ValueError("anchor must be finite")
        if mode not in ("minute_close", "tick"):
            raise ValueError("invalid Renko mode")
        self.mode = mode
        self.last: Brick | None = None
        self.last_timestamp: datetime | None = None
        self.index = 0

    def on_price(self, price: Decimal | float | str, ts: datetime) -> list[Brick]:
        value = Decimal(str(price))
        if not value.is_finite() or value <= 0:
            raise ValueError("price must be finite and positive")
        if ts.tzinfo is None or ts.utcoffset() is None:
            raise ValueError("timestamp must include a timezone")
        ts = ts.astimezone(IST)
        if self.last_timestamp is not None and (
            ts < self.last_timestamp
            or (ts == self.last_timestamp and self.mode != "tick")
        ):
            log.warning("renko_sample_ignored", timestamp=ts.isoformat())
            return []
        self.last_timestamp = ts
        if self.last is None:
            steps = ((value - self.anchor) / self.box).to_integral_value(
                rounding=ROUND_FLOOR
            )
            base = self.anchor + steps * self.box
            self.last = Brick(-1, base, base, 0, ts)
            return []
        out: list[Brick] = []
        while True:
            last = self.last
            up = (last.close if last.direction >= 0 else last.open) + self.box
            down = (last.close if last.direction <= 0 else last.open) - self.box
            if value >= up:
                opening, closing, direction = up - self.box, up, 1
            elif value <= down:
                opening, closing, direction = down + self.box, down, -1
            else:
                return out
            self.last = Brick(self.index, opening, closing, direction, ts)
            self.index += 1
            out.append(self.last)
