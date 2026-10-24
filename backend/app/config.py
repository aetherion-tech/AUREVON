"""Read settings from backend/.env, with environment variables taking priority."""

from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
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
    kite_api_key: SecretStr = SecretStr("")
    kite_api_secret: SecretStr = SecretStr("")
    kite_session_file: Path = BACKEND_DIR / "data" / "kite-session.bin"
    database_url: str = f"sqlite:///{(BACKEND_DIR / 'data' / 'aurevon.db').as_posix()}"

    @property
    def kite_configured(self) -> bool:
        """Presence check only; credentials are not verified with Zerodha yet."""
        return bool(
            self.kite_api_key.get_secret_value().strip()
            and self.kite_api_secret.get_secret_value().strip()
        )
