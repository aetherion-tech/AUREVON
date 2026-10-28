"""Bounded, full-depth option quotes; separate from spot/futures recovery state."""

from datetime import UTC, datetime
from decimal import Decimal
from threading import RLock
from typing import Any

from pydantic import ValidationError

from app.strategy.models import DepthLevel, OptionContract, OptionQuote


class OptionQuoteBook:
    def __init__(self, capacity: int = 200) -> None:
        if not 1 <= capacity <= 200:
            raise ValueError("option capacity must be 1–200")
        self.capacity = capacity
        self.lock = RLock()
        self.candidates: dict[int, OptionContract] = {}
        self.traded: dict[int, OptionContract] = {}
        self.quotes: dict[int, OptionQuote] = {}
        self.invalid = 0
        self.subscription_error = False

    @property
    def tokens(self) -> list[int]:
        with self.lock:
            return sorted(self.candidates.keys() | self.traded.keys())

    def configure(
        self,
        candidates: list[OptionContract],
        traded: list[OptionContract] | None = None,
    ) -> None:
        with self.lock:
            pinned = self.traded if traded is None else {c.token: c for c in traded}
            selected = {c.token: c for c in candidates}
            if len(selected) != len(candidates) or (
                traded is not None and len(pinned) != len(traded)
            ):
                raise ValueError("duplicate option subscription")
            if any(
                token in selected and selected[token] != c
                for token, c in pinned.items()
            ):
                raise ValueError("candidate/traded token identity collision")
            desired = selected | pinned
            if len(desired) > self.capacity:
                raise ValueError("option subscription capacity exceeded")
            prior = self.candidates | self.traded
            if any(prior[t] != desired[t] for t in prior.keys() & desired.keys()):
                raise ValueError("option identity changed; worker restart required")
            self.quotes = {
                t: q
                for t, q in self.quotes.items()
                if t in desired and prior.get(t) == desired[t]
            }
            self.candidates, self.traded = selected, dict(pinned)

    def invalidate(self) -> None:
        with self.lock:
            self.quotes.clear()

    def accept(self, tick: dict[str, Any], received: datetime) -> bool:
        with self.lock:
            token = tick.get("instrument_token")
            if type(token) is not int:
                return False
            contract = (self.candidates | self.traded).get(token)
            if contract is None:
                return False
            try:
                stamp = tick["exchange_timestamp"]
                if not isinstance(stamp, datetime) or received.utcoffset() is None:
                    raise ValueError("invalid option time")
                # Kite SDK uses datetime.fromtimestamp: a naive SDK value is
                # system-local, exactly like the core ticker normalization.
                stamp = stamp.astimezone(UTC)
                if stamp > received or (
                    token in self.quotes
                    and (
                        stamp < self.quotes[token].exchange_at
                        or received < self.quotes[token].received_at
                    )
                ):
                    raise ValueError("future/out-of-order option tick")
                depth = tick["depth"]

                def levels(side: str) -> tuple[DepthLevel, ...]:
                    return tuple(
                        DepthLevel(
                            price=Decimal(str(row["price"])), quantity=row["quantity"]
                        )
                        for row in depth[side][:5]
                        if Decimal(str(row["price"])) > 0 and row["quantity"] > 0
                    )

                quote = OptionQuote(
                    contract=contract,
                    exchange_at=stamp,
                    received_at=received,
                    bids=levels("buy"),
                    asks=levels("sell"),
                    open_interest=tick["oi"],
                )
                self.quotes[token] = quote
                return True
            except (KeyError, TypeError, ValueError, ValidationError, ArithmeticError):
                # A malformed new update must not leave an older quote looking valid.
                self.quotes.pop(token, None)
                self.invalid += 1
                return False

    def snapshot(self) -> dict[int, OptionQuote]:
        with self.lock:
            return dict(self.quotes) if not self.subscription_error else {}
