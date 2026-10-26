"""Validate the daily Kite CSV, save an atomic snapshot, and resolve NIFTY."""

import csv
import io
from collections.abc import Callable
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from threading import Lock
from typing import Any

import structlog
from sqlalchemy import Engine, delete, insert, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.schemas import InstrumentView as InstrumentView
from app.broker.kite_auth import IST, KiteAuth
from app.db.models import Instrument, InstrumentSnapshot

log = structlog.get_logger("aurevon")


class InstrumentError(Exception):
    def __init__(self, message: str, status_code: int = 400) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def parse_instruments(text: str, exchange: str) -> list[dict[str, Any]]:
    reader = csv.DictReader(io.StringIO(text.lstrip("\ufeff")))
    required = set(Instrument.__table__.columns.keys())
    if not reader.fieldnames or not required.issubset(reader.fieldnames):
        raise InstrumentError("Kite returned an invalid instrument CSV.", 502)
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    try:
        for row in reader:
            symbol = row["tradingsymbol"].strip()
            if row["exchange"] != exchange or not symbol or symbol in seen:
                raise ValueError("Invalid instrument identity")
            seen.add(symbol)
            expiry = date.fromisoformat(row["expiry"]) if row["expiry"] else None
            values: dict[str, Any] = {
                "exchange": exchange,
                "tradingsymbol": symbol,
                "instrument_token": int(row["instrument_token"]),
                "name": row["name"].strip(),
                "expiry": expiry,
                "strike": Decimal(row["strike"] or "0"),
                "tick_size": Decimal(row["tick_size"]),
                "lot_size": int(row["lot_size"]),
                "instrument_type": row["instrument_type"],
                "segment": row["segment"],
            }
            if (
                values["instrument_token"] <= 0
                or values["lot_size"] < 0
                or (values["lot_size"] == 0 and values["segment"] != "INDICES")
                or not values["tick_size"].is_finite()
                or not values["strike"].is_finite()
                or values["tick_size"] < 0
                or values["strike"] < 0
                or (exchange == "NFO" and expiry is None)
            ):
                raise ValueError("Invalid instrument values")
            rows.append(values)
    except (ValueError, InvalidOperation, TypeError, AttributeError, KeyError):
        raise InstrumentError("Kite instrument CSV contains invalid rows.", 502)
    if not rows:
        raise InstrumentError("Kite returned an empty instrument list.", 502)
    return rows


class Instruments:
    def __init__(
        self,
        engine: Engine,
        auth: KiteAuth,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.clock = clock or (lambda: datetime.now(IST))
        self.engine = engine
        self.auth = auth
        self.refresh_lock = Lock()

    def status(self) -> dict[str, Any]:
        today = self.clock().astimezone(IST).date()
        try:
            with Session(self.engine) as db:
                snapshots = db.scalars(select(InstrumentSnapshot)).all()
                exchanges = {
                    item.exchange: {
                        "count": item.row_count,
                        "loaded_at": self._utc(item.loaded_at).isoformat(),
                        "current": self._utc(item.loaded_at).astimezone(IST).date()
                        == today,
                    }
                    for item in snapshots
                }
        except SQLAlchemyError:
            raise InstrumentError(
                "Database unavailable. Run uv run alembic upgrade head.", 503
            )
        return {
            "ready": all(
                exchanges.get(e, {}).get("current", False) for e in ("NSE", "NFO")
            ),
            "exchanges": exchanges,
            "message": "Refresh once each day before using instrument tokens.",
        }

    @staticmethod
    def _utc(value: datetime) -> datetime:
        # SQLite returns naive timestamps even for timezone-enabled columns.
        return (
            value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
        )

    def refresh(self) -> dict[str, Any]:
        with self.refresh_lock:
            if self.status()["ready"]:
                log.info("instruments_cache_used")
                return self.status()
            log.info("instruments_refresh_started")
            # Validate BOTH downloads before changing the last good database snapshot.
            downloads = {
                exchange: parse_instruments(
                    self.auth.download_instruments(exchange), exchange
                )
                for exchange in ("NSE", "NFO")
            }
            loaded_at = self.clock().astimezone(UTC)
            try:
                with Session(self.engine) as db, db.begin():
                    for exchange, rows in downloads.items():
                        db.execute(
                            delete(Instrument).where(Instrument.exchange == exchange)
                        )
                        db.execute(insert(Instrument), rows)
                        db.merge(
                            InstrumentSnapshot(
                                exchange=exchange,
                                loaded_at=loaded_at,
                                row_count=len(rows),
                            )
                        )
            except SQLAlchemyError:
                log.error("instruments_save_failed")
                raise InstrumentError(
                    "Could not save instruments; previous snapshot retained.", 503
                )
            log.info(
                "instruments_refresh_completed",
                counts={k: len(v) for k, v in downloads.items()},
            )
            return self.status()

    def nifty(self, expiry: date | None = None) -> dict[str, Any]:
        if not self.status()["ready"]:
            raise InstrumentError("Refresh today's instrument list first.", 409)
        today = self.clock().astimezone(IST).date()
        with Session(self.engine) as db:
            spot = db.get(Instrument, ("NSE", "NIFTY 50"))
            futures = db.scalars(
                select(Instrument)
                .where(
                    Instrument.exchange == "NFO",
                    Instrument.name == "NIFTY",
                    Instrument.instrument_type == "FUT",
                    Instrument.expiry >= today,
                )
                .order_by(Instrument.expiry, Instrument.tradingsymbol)
            ).all()
            options = db.scalars(
                select(Instrument)
                .where(
                    Instrument.exchange == "NFO",
                    Instrument.name == "NIFTY",
                    Instrument.instrument_type.in_(["CE", "PE"]),
                    Instrument.expiry >= today,
                )
                .order_by(
                    Instrument.expiry, Instrument.strike, Instrument.instrument_type
                )
            ).all()
            if spot is None or not futures or not options:
                raise InstrumentError(
                    "NIFTY spot, futures, or options missing from list.", 404
                )
            expiries = sorted({o.expiry for o in options if o.expiry is not None})
            selected = expiry or expiries[0]
            if selected not in expiries:
                raise InstrumentError("Requested option expiry is not available.", 404)
            selected_options = [
                InstrumentView.model_validate(o)
                for o in options
                if o.expiry == selected
            ]
            return {
                "as_of": today,
                "spot": InstrumentView.model_validate(spot),
                "future": InstrumentView.model_validate(futures[0]),
                "option_expiries": expiries,
                "selected_expiry": selected,
                "options": selected_options,
                "message": "Contract metadata only; prices and trading disabled.",
            }
