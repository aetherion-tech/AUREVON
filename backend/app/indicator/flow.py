"""Completed futures-bar flow; no developing bar or continuous-contract substitution."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from math import isfinite
from typing import Any

from app.indicator.settings import IndicatorSettings
from app.market.renko_builder import IST
from app.market.warmup import SessionCalendar


@dataclass(frozen=True)
class FlowBar:
    start: datetime
    end: datetime
    high: float
    low: float
    close: float
    volume: float
    oi: float | None


def percent(now: float | None, before: float | None) -> float | None:
    return (
        (now - before) / before * 100
        if now is not None and before is not None and before > 0
        else None
    )


def buildup(px: float | None, oi: float | None, settings: IndicatorSettings) -> int:
    if px is None or oi is None:
        return 0
    if abs(px) < settings["pxMinPct"] or abs(oi) < settings["oiMinPct"]:
        return 0
    return (
        2
        if px > 0 and oi > 0
        else 1
        if px > 0 and oi < 0
        else -2
        if px < 0 and oi > 0
        else -1
    )


class FuturesFlow:
    """Caller supplies one exact contract and exchange-aligned completed bars.

    Missing OI is never replaced by zero/price. With useOI false, bW/bD are
    neutral while VWAP, price and volume remain usable, as in the original Pine.
    Prior-day references must be supplied from a verified completed daily bar.
    """

    def __init__(
        self,
        contract: str,
        settings: IndicatorSettings | None = None,
        calendar: SessionCalendar | None = None,
    ) -> None:
        if not contract:
            raise ValueError("exact futures contract required")
        self.contract = contract
        self.settings = settings or IndicatorSettings()
        self.calendar = calendar
        self.bars: list[FlowBar] = []
        self.day: str | None = None
        self.pv = 0.0
        self.volume = 0.0

    def update(
        self,
        bar: FlowBar,
        at: datetime,
        contract: str,
        previous_close: float | None = None,
        previous_oi: float | None = None,
    ) -> dict[str, Any]:
        if any(
            t.tzinfo is None or t.utcoffset() is None for t in (bar.start, bar.end, at)
        ):
            raise ValueError("aware flow timestamps required")
        if contract != self.contract or not bar.start < bar.end <= at:
            raise ValueError("contract mismatch or incomplete flow bar")
        if self.bars and bar.start < self.bars[-1].end:
            raise ValueError("duplicate/out-of-order flow bar")
        day = bar.start.astimezone(IST).date().isoformat()
        if self.bars and day == self.day and bar.start != self.bars[-1].end:
            raise ValueError("missing completed flow bar; rebuild required")
        if self.calendar is not None:
            session = next(
                (
                    s
                    for s in self.calendar.sessions
                    if s.opening <= bar.start < s.closing
                ),
                None,
            )
            tf = self.settings["flowTf"]
            if session is None or not tf.isdigit() or int(tf) < 1:
                raise ValueError("flow session/timeframe unavailable")
            duration = timedelta(minutes=int(tf))
            if (bar.start - session.opening) % duration != timedelta(
                0
            ) or bar.end != min(bar.start + duration, session.closing):
                raise ValueError("flow bar is not exchange/timeframe aligned")
        values = (bar.high, bar.low, bar.close, bar.volume)
        if (
            not all(isfinite(v) for v in values)
            or bar.volume < 0
            or not 0 < bar.low <= bar.close <= bar.high
            or (bar.oi is not None and (not isfinite(bar.oi) or bar.oi < 0))
        ):
            raise ValueError("invalid futures values")
        s = self.settings
        if day != self.day:
            self.pv = self.volume = 0.0
        self.pv += (bar.high + bar.low + bar.close) / 3 * bar.volume
        self.volume += bar.volume
        vwap = self.pv / self.volume if self.volume else None
        previous = (
            self.bars[-s["flowBars"]] if len(self.bars) >= s["flowBars"] else None
        )
        px = percent(bar.close, previous.close if previous else None)
        oi = percent(bar.oi, previous.oi if previous else None) if s["useOI"] else None
        day_px = percent(bar.close, previous_close)
        day_oi = percent(bar.oi, previous_oi) if s["useOI"] else None
        # Pine volume[1] / sma(volume, 20)[1], not current-bar volume/SMA.
        vol_ratio = None
        if len(self.bars) >= 20:
            avg = sum(b.volume for b in self.bars[-20:]) / 20
            vol_ratio = self.bars[-1].volume / avg if avg else None
        enabled = s["flowOn"]
        bw = buildup(px, oi, s) if enabled else 0
        bd = buildup(day_px, day_oi, s) if enabled else 0
        vs = (
            (1 if bar.close > vwap else -1 if bar.close < vwap else 0)
            if enabled and vwap is not None
            else 0
        )
        spike = vol_ratio is not None and vol_ratio >= s["volMult"]
        vol = (
            (1 if px > 0 else -1 if px < 0 else 0)
            if enabled and spike and px is not None
            else 0
        )
        ds = (
            (1 if day_px > 0.1 else -1 if day_px < -0.1 else 0)
            if enabled and day_px is not None
            else 0
        )
        self.bars.append(bar)
        self.bars = self.bars[-max(20, s["flowBars"]) :]
        self.day = day
        return {
            "flow_ok": enabled,
            "window_build": bw,
            "day_build": bd,
            "vwap": vwap,
            "vwap_side": vs,
            "volume_ratio": vol_ratio,
            "volume_spike": spike,
            "price_pct": px,
            "oi_pct": oi,
            "day_price_pct": day_px,
            "day_oi_pct": day_oi,
            "score": bw + vs + vol + ds,
            "completed_at": bar.end.isoformat(),
        }
