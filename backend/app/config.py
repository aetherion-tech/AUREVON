"""Read settings from backend/.env, with environment variables taking priority."""

from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    app_name: str = "AUREVON"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    renko_box: float = Field(default=50, gt=0, allow_inf_nan=False)
    renko_anchor: float | None = Field(default=None, allow_inf_nan=False)
    renko_mode: Literal["minute_close", "tick"] = "minute_close"
    # Policy inputs for the managed warm-up/recovery stages, not runtime switches.
    warmup_lookback_trading_days: int = Field(default=20, ge=1, le=250)
    recovery_max_gap_days: int = Field(default=30, ge=1, le=365)
    recovery_max_attempts: int = Field(default=5, ge=1, le=20)
    recovery_backoff_seconds: float = Field(
        default=1, gt=0, le=300, allow_inf_nan=False
    )
    recovery_backoff_max_seconds: float = Field(
        default=30, gt=0, le=300, allow_inf_nan=False
    )
    readiness_entry_delay_seconds: int = Field(default=60, ge=60, le=3600)
    market_service_enabled: bool = False
    market_poll_seconds: float = Field(default=5, ge=1, le=60)
    market_stream: str = Field(default="NIFTY-paper", min_length=1, max_length=60)
    market_calendar_dir: Path = BACKEND_DIR / "app" / "market" / "calendars"
    market_record_dir: Path = BACKEND_DIR / "data" / "ticks"
    market_lock_file: Path = BACKEND_DIR / "data" / "market-worker.lock"
    kite_api_key: SecretStr = SecretStr("")
    kite_api_secret: SecretStr = SecretStr("")
    kite_session_file: Path = BACKEND_DIR / "data" / "kite-session.bin"
    database_url: str = f"sqlite:///{(BACKEND_DIR / 'data' / 'aurevon.db').as_posix()}"

    @model_validator(mode="after")
    def validate_recovery_backoff(self) -> "Settings":
        if self.recovery_backoff_max_seconds < self.recovery_backoff_seconds:
            raise ValueError(
                "Recovery backoff maximum must be at least the initial delay"
            )
        return self

    @property
    def kite_configured(self) -> bool:
        """Presence check only; credentials are not verified with Zerodha yet."""
        return bool(
            self.kite_api_key.get_secret_value().strip()
            and self.kite_api_secret.get_secret_value().strip()
        )
