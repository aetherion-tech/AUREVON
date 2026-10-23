"""Instrument identity is exchange + symbol; numeric tokens can be reused."""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Integer, Numeric, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Instrument(Base):
    __tablename__ = "instruments"

    exchange: Mapped[str] = mapped_column(String(10), primary_key=True)
    tradingsymbol: Mapped[str] = mapped_column(String(100), primary_key=True)
    instrument_token: Mapped[int] = mapped_column(Integer, index=True)
    name: Mapped[str] = mapped_column(String(100), index=True)
    expiry: Mapped[date | None] = mapped_column(Date, nullable=True)
    strike: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    tick_size: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    lot_size: Mapped[int] = mapped_column(Integer)
    instrument_type: Mapped[str] = mapped_column(String(10))
    segment: Mapped[str] = mapped_column(String(20))


class InstrumentSnapshot(Base):
    __tablename__ = "instrument_snapshots"

    exchange: Mapped[str] = mapped_column(String(10), primary_key=True)
    loaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    row_count: Mapped[int] = mapped_column(Integer)
