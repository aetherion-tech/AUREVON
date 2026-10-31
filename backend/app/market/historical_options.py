"""Offline, actual-price-only option input for isolated historical replay.

Provider provenance is a declaration, not independent verification. This adapter
never opens the operator database, downloads prices or manufactures a quote.
"""

import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from app.api.schemas import IST, ISTTimestamp
from app.strategy.models import Catalog, Frozen, OptionQuote


class HistoricalOptions(Frozen):
    version: Literal[1] = 1
    price_basis: Literal["ACTUAL_RECORDED_DEPTH"]
    provider: str = Field(min_length=1, max_length=160)
    source_reference: str = Field(min_length=1, max_length=500)
    catalogs: tuple[Catalog, ...] = Field(min_length=1)
    quotes: tuple[OptionQuote, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def chronological(self) -> "HistoricalOptions":
        times = [c.loaded_at for c in self.catalogs]
        if times != sorted(set(times)):
            raise ValueError("catalog snapshots must be strictly chronological")
        previous: dict[tuple[str, object], OptionQuote] = {}
        last_received: datetime | None = None
        for quote in self.quotes:
            if quote.exchange_at > quote.received_at:
                raise ValueError("quote received before exchange event")
            if last_received is not None and quote.received_at < last_received:
                raise ValueError("quotes must follow historical availability order")
            last_received = quote.received_at
            catalog = self.catalog_at(quote.received_at)
            if catalog is None or quote.contract not in catalog.contracts:
                raise ValueError("quote lacks matching historical contract snapshot")
            if quote.exchange_at.date() > quote.contract.expiry:
                raise ValueError("quote is after contract expiry")
            key = (quote.contract.symbol, quote.contract.expiry)
            prior = previous.get(key)
            if prior is not None and quote.exchange_at <= prior.exchange_at:
                raise ValueError("duplicate or out-of-order contract quote")
            if any(
                level.price % quote.contract.tick_size
                for level in (*quote.bids, *quote.asks)
            ):
                raise ValueError("historical quote is off contract tick grid")
            previous[key] = quote
        return self

    def catalog_at(self, at: datetime) -> Catalog | None:
        if at.utcoffset() is None:
            raise ValueError("historical clock requires timezone")
        return next((c for c in reversed(self.catalogs) if c.loaded_at <= at), None)

    def quotes_at(
        self, at: datetime, *, max_age_seconds: int = 5
    ) -> dict[int, OptionQuote]:
        """Only already-received, fresh, exact-identity quotes; never future depth."""
        if type(max_age_seconds) is not int or not 1 <= max_age_seconds <= 60:
            raise ValueError("quote age must be 1-60 seconds")
        catalog = self.catalog_at(at)
        if catalog is None:
            return {}
        at = at.astimezone(IST)
        result: dict[int, OptionQuote] = {}
        for quote in self.quotes:
            if quote.received_at > at:
                break
            if (
                quote.contract in catalog.contracts
                and quote.contract.expiry >= at.date()
                and timedelta(0)
                <= at - quote.exchange_at
                <= timedelta(seconds=max_age_seconds)
            ):
                result[quote.contract.token] = quote
        return result


class CoverageRequest(Frozen):
    start: ISTTimestamp
    end: ISTTimestamp

    @model_validator(mode="after")
    def ordered(self) -> "CoverageRequest":
        if self.start > self.end:
            raise ValueError("start must not exceed end")
        return self


def load_options(
    path: Path, *, max_bytes: int = 50_000_000
) -> tuple[HistoricalOptions, str]:
    """Hash and validate the same bounded bytes, without modifying source data."""
    if type(max_bytes) is not int or max_bytes <= 0:
        raise ValueError("positive byte limit required")
    with path.open("rb") as source:
        raw = source.read(max_bytes + 1)
    if len(raw) > max_bytes:
        raise ValueError("historical option bundle exceeds byte limit")
    return HistoricalOptions.model_validate_json(raw), hashlib.sha256(raw).hexdigest()


def coverage(bundle: HistoricalOptions, request: CoverageRequest) -> dict[str, object]:
    quotes = [q for q in bundle.quotes if request.start <= q.received_at <= request.end]
    blockers = []
    if bundle.catalog_at(request.start) is None:
        blockers.append("historical_contract_snapshot_missing_at_start")
    if not quotes:
        blockers.append("historical_option_quotes_missing_in_range")
    # Presence is not complete-session coverage or executable strategy readiness.
    return {
        "status": "BLOCKED" if blockers else "INPUT_PRESENT_NOT_EXECUTION_READY",
        "provider": bundle.provider,
        "source_reference": bundle.source_reference,
        "provenance_independently_verified": False,
        "quotes_in_range": len(quotes),
        "contracts_in_range": len({q.contract.symbol for q in quotes}),
        "blockers": blockers,
        "paper_trading_ready": False,
        "option_pnl": None,
        "estimated_price_fallback": False,
    }
