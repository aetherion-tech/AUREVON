"""Instrument identity is exchange + symbol; numeric tokens can be reused."""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text
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


class MarketCheckpoint(Base):
    __tablename__ = "market_checkpoints"

    stream: Mapped[str] = mapped_column(String(160), primary_key=True)
    revision: Mapped[int] = mapped_column(Integer)
    configuration: Mapped[str] = mapped_column(Text)
    state: Mapped[str] = mapped_column(Text)


class StoredCandle(Base):
    __tablename__ = "market_candles"

    stream: Mapped[str] = mapped_column(String(160), primary_key=True)
    token: Mapped[int] = mapped_column(Integer, primary_key=True)
    time: Mapped[str] = mapped_column(String(40), primary_key=True)
    payload: Mapped[str] = mapped_column(Text)


class StoredBrick(Base):
    __tablename__ = "renko_bricks"

    stream: Mapped[str] = mapped_column(String(160), primary_key=True)
    index: Mapped[int] = mapped_column(Integer, primary_key=True)
    payload: Mapped[str] = mapped_column(Text)


class HistoricalSpotBatch(Base):
    __tablename__ = "historical_spot_batches"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    stream: Mapped[str] = mapped_column(String(160))
    token: Mapped[int] = mapped_column(Integer)
    provenance: Mapped[str] = mapped_column(Text)


class HistoricalSpotCandle(Base):
    __tablename__ = "historical_spot_candles"

    stream: Mapped[str] = mapped_column(String(160), primary_key=True)
    token: Mapped[int] = mapped_column(Integer, primary_key=True)
    time: Mapped[str] = mapped_column(String(40), primary_key=True)
    completed_at: Mapped[str] = mapped_column(String(40))
    payload: Mapped[str] = mapped_column(Text)
    batch_id: Mapped[str] = mapped_column(ForeignKey("historical_spot_batches.id"))


class HistoricalContextBatch(Base):
    __tablename__ = "historical_context_batches"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    stream: Mapped[str] = mapped_column(String(160))
    provenance: Mapped[str] = mapped_column(Text)


class HistoricalContextCandle(Base):
    __tablename__ = "historical_context_candles"

    stream: Mapped[str] = mapped_column(String(160), primary_key=True)
    identity: Mapped[str] = mapped_column(String(160), primary_key=True)
    kind: Mapped[str] = mapped_column(String(20), primary_key=True)
    time: Mapped[str] = mapped_column(String(40), primary_key=True)
    completed_at: Mapped[str] = mapped_column(String(40))
    payload: Mapped[str] = mapped_column(Text)
    batch_id: Mapped[str] = mapped_column(ForeignKey("historical_context_batches.id"))


class MarketLifecycleState(Base):
    __tablename__ = "market_lifecycle_state"
    key: Mapped[str] = mapped_column(String(240), primary_key=True)
    payload: Mapped[str] = mapped_column(Text)


class DashboardSecurityState(Base):
    __tablename__ = "dashboard_security_state"
    key: Mapped[str] = mapped_column(String(40), primary_key=True)
    failures: Mapped[int] = mapped_column(Integer)
    locked_until: Mapped[str | None] = mapped_column(String(40), nullable=True)


class AuditEntry(Base):
    __tablename__ = "audit_log"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    at: Mapped[str] = mapped_column(String(40), index=True)
    action: Mapped[str] = mapped_column(String(200))
    actor: Mapped[str] = mapped_column(String(40))
    status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    request_id: Mapped[str] = mapped_column(String(32))


class DashboardAlert(Base):
    __tablename__ = "dashboard_alerts"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    source_key: Mapped[str] = mapped_column(String(100), index=True)
    level: Mapped[str] = mapped_column(String(20))
    code: Mapped[str] = mapped_column(String(80))
    at: Mapped[str] = mapped_column(String(40), index=True)
    acknowledged_at: Mapped[str | None] = mapped_column(String(40), nullable=True)


class IndicatorCheckpoint(Base):
    __tablename__ = "indicator_checkpoints"
    stream: Mapped[str] = mapped_column(String(160), primary_key=True)
    index: Mapped[int] = mapped_column(Integer)
    payload: Mapped[str] = mapped_column(Text)


class IndicatorResult(Base):
    __tablename__ = "indicator_results"
    stream: Mapped[str] = mapped_column(String(160), primary_key=True)
    index: Mapped[int] = mapped_column(Integer, primary_key=True)
    input: Mapped[str] = mapped_column(Text)
    payload: Mapped[str] = mapped_column(Text)


class IndicatorEvent(Base):
    __tablename__ = "indicator_events"
    stream: Mapped[str] = mapped_column(String(160), primary_key=True)
    index: Mapped[int] = mapped_column(Integer, primary_key=True)
    ordinal: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String(20))
    payload: Mapped[str] = mapped_column(Text)


class StrategyDecision(Base):
    __tablename__ = "strategy_decisions"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    signal_id: Mapped[str] = mapped_column(String(160), index=True)
    at: Mapped[str] = mapped_column(String(40))
    input: Mapped[str] = mapped_column(Text)
    settings: Mapped[str] = mapped_column(Text)
    quotes: Mapped[str] = mapped_column(Text)
    payload: Mapped[str] = mapped_column(Text)


class PaperExecutionBook(Base):
    __tablename__ = "paper_execution_books"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    revision: Mapped[int] = mapped_column(Integer)
    payload: Mapped[str] = mapped_column(Text)


class WalletAccount(Base):
    __tablename__ = "wallet_accounts"
    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(80))
    mode: Mapped[str] = mapped_column(String(10))
    revision: Mapped[int] = mapped_column(Integer)
    balance: Mapped[str] = mapped_column(String(40))
    reserved: Mapped[str] = mapped_column(String(40))
    __table_args__ = (Index("ix_wallet_scope", "user_id", "mode", unique=True),)


class WalletLedger(Base):
    __tablename__ = "wallet_ledger"
    account_id: Mapped[str] = mapped_column(String(120), primary_key=True)
    sequence: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(240))
    at: Mapped[str] = mapped_column(String(40))
    kind: Mapped[str] = mapped_column(String(30))
    payload: Mapped[str] = mapped_column(Text)
    __table_args__ = (
        Index("ix_wallet_ledger_key", "account_id", "key", unique=True),
        Index("ix_wallet_ledger_time", "account_id", "at", "sequence"),
    )


class PaperTradeSummary(Base):
    __tablename__ = "paper_trade_summaries"
    account_id: Mapped[str] = mapped_column(String(120), primary_key=True)
    trade_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    closed_at: Mapped[str] = mapped_column(String(40))
    day: Mapped[str] = mapped_column(String(10))
    family: Mapped[str] = mapped_column(String(5))
    direction: Mapped[int] = mapped_column(Integer)
    grade: Mapped[int] = mapped_column(Integer)
    result: Mapped[str] = mapped_column(String(10))
    payload: Mapped[str] = mapped_column(Text)
    __table_args__ = (
        Index("ix_paper_history_time", "account_id", "closed_at", "trade_id"),
        Index(
            "ix_paper_history_filters",
            "account_id",
            "family",
            "direction",
            "grade",
            "result",
            "day",
        ),
    )


class PaperDailyPnL(Base):
    __tablename__ = "paper_daily_pnl"
    account_id: Mapped[str] = mapped_column(String(120), primary_key=True)
    day: Mapped[str] = mapped_column(String(10), primary_key=True)
    payload: Mapped[str] = mapped_column(Text)


class WalletPeriod(Base):
    __tablename__ = "wallet_periods"
    account_id: Mapped[str] = mapped_column(String(120), primary_key=True)
    kind: Mapped[str] = mapped_column(String(10), primary_key=True)
    start: Mapped[str] = mapped_column(String(10), primary_key=True)
    payload: Mapped[str] = mapped_column(Text)


class WalletReconciliationRun(Base):
    __tablename__ = "wallet_reconciliation_runs"
    account_id: Mapped[str] = mapped_column(String(120), primary_key=True)
    day: Mapped[str] = mapped_column(String(10), primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, primary_key=True)
    at: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(5))


class DomainDecision(Base):
    __tablename__ = "domain_decisions"
    scope: Mapped[str] = mapped_column(String(120), primary_key=True)
    id: Mapped[str] = mapped_column(String(240), primary_key=True)
    at: Mapped[str] = mapped_column(String(40))
    kind: Mapped[str] = mapped_column(String(30))
    payload: Mapped[str] = mapped_column(Text)
    __table_args__ = (Index("ix_domain_decision_time", "scope", "at", "id"),)


class DashboardSettingsVersion(Base):
    __tablename__ = "dashboard_settings_versions"
    scope: Mapped[str] = mapped_column(String(120), primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, primary_key=True)
    payload: Mapped[str] = mapped_column(Text)
    command_key: Mapped[str | None] = mapped_column(String(160), nullable=True)
    __table_args__ = (
        Index("ix_settings_command", "scope", "command_key", unique=True),
    )


class DomainCommand(Base):
    __tablename__ = "domain_commands"
    scope: Mapped[str] = mapped_column(String(120), primary_key=True)
    key: Mapped[str] = mapped_column(String(160), primary_key=True)
    fingerprint: Mapped[str] = mapped_column(String(64))
    result: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[int | None] = mapped_column(Integer, nullable=True)
