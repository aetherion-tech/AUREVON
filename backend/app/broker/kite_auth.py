"""Kite authentication only. This module cannot place orders."""

import hashlib
import json
import secrets
from datetime import UTC, datetime, timedelta
from threading import RLock
from time import monotonic, sleep
from typing import Any
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

import httpx
import structlog
from pydantic import BaseModel

from app.config import Settings

log = structlog.get_logger("aurevon")
IST = ZoneInfo("Asia/Kolkata")


class AuthError(Exception):
    """Only fixed, safe messages from this exception reach the browser."""

    def __init__(self, message: str, status_code: int = 400) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class KiteStatus(BaseModel):
    configured: bool
    authenticated: bool = False
    user_id: str | None = None
    expires_at: datetime | None = None
    message: str


def session_expiry(now: datetime) -> datetime:
    """Use the next 06:00 IST boundary, including logins before 06:00."""
    local = now.astimezone(IST)
    boundary = local.replace(hour=6, minute=0, second=0, microsecond=0)
    if local >= boundary:
        boundary += timedelta(days=1)
    return boundary.astimezone(UTC)


class KiteAuth:
    def __init__(self, settings: Settings, client: httpx.Client | None = None) -> None:
        self.settings = settings
        self.client = client or httpx.Client(
            base_url="https://api.kite.trade", timeout=10.0
        )
        self.lock = RLock()
        self.pending: dict[str, datetime] = {}
        self._historical_next = 0.0

    def historical_data(
        self,
        instrument_token: int,
        interval: str,
        start: datetime,
        end: datetime,
        *,
        oi: bool = False,
    ) -> dict[str, Any]:
        """Read-only historical request, serialized at 2.5 requests per second."""
        if instrument_token <= 0 or interval not in {"minute", "5minute"}:
            raise ValueError("Expected a positive token and minute/5minute interval")
        with self.lock:
            session = self._load() if self.settings.kite_configured else None
            if session is None:
                raise AuthError("Log in to Kite before downloading prices.", 401)
            sleep(max(0.0, self._historical_next - monotonic()))
            self._historical_next = monotonic() + 0.4
            return self._request(
                "GET",
                f"/instruments/historical/{instrument_token}/{interval}",
                token=session["access_token"],
                params={
                    "from": start.astimezone(IST).strftime("%Y-%m-%d %H:%M:%S"),
                    "to": end.astimezone(IST).strftime("%Y-%m-%d %H:%M:%S"),
                    "continuous": "0",
                    "oi": "1" if oi else "0",
                },
            )

    def close(self) -> None:
        self.client.close()

    def create_ticker(self) -> Any:
        """Create a market-data-only SDK socket without returning credentials."""
        from kiteconnect import KiteTicker  # type: ignore[import-untyped]

        with self.lock:
            session = self._load() if self.settings.kite_configured else None
            if session is None:
                raise AuthError("Log in to Kite before starting the price feed.", 401)
            return KiteTicker(
                self.settings.kite_api_key.get_secret_value().strip(),
                session["access_token"],
                reconnect=True,
                reconnect_max_delay=30,
                reconnect_max_tries=50,
                debug=False,
            )

    def download_instruments(self, exchange: str) -> str:
        """Download a read-only CSV without exposing the access token to callers."""
        if exchange not in {"NSE", "NFO"}:
            raise ValueError("Only NSE and NFO instrument downloads are supported")
        with self.lock:
            session = self._load() if self.settings.kite_configured else None
            if session is None:
                raise AuthError("Log in to Kite before downloading instruments.", 401)
            key = self.settings.kite_api_key.get_secret_value().strip()
            try:
                response = self.client.get(
                    f"/instruments/{exchange}",
                    headers={
                        "X-Kite-Version": "3",
                        "Authorization": f"token {key}:{session['access_token']}",
                    },
                    timeout=60.0,
                )
            except httpx.HTTPError:
                log.warning("instrument_download_failed", exchange=exchange)
                raise AuthError("Instrument download failed. Check connectivity.", 502)
            if response.status_code == 403:
                # A permission failure is not always a revoked token; preserve it.
                raise AuthError(
                    "Kite denied instrument access. Check login and app.", 403
                )
            if response.is_error:
                raise AuthError("Kite could not provide the instrument list.", 502)
            return response.text

    def begin_login(self) -> tuple[str, str]:
        if not self.settings.kite_configured:
            raise AuthError("Add Kite credentials to backend/.env first.", 503)
        now = datetime.now(UTC)
        state = secrets.token_urlsafe(32)
        with self.lock:
            self.pending = {k: v for k, v in self.pending.items() if v > now}
            if len(self.pending) >= 100:
                raise AuthError("Too many login attempts. Try again later.", 429)
            self.pending[state] = now + timedelta(minutes=10)
        query = urlencode(
            {
                "v": "3",
                "api_key": self.settings.kite_api_key.get_secret_value().strip(),
                "redirect_params": urlencode({"state": state}),
            }
        )
        log.info("kite_login_started")
        return f"https://kite.zerodha.com/connect/login?{query}", state

    def finish_login(
        self, state: str, cookie: str, request_token: str, status: str
    ) -> None:
        with self.lock:
            deadline = self.pending.get(state)
            if (
                not state
                or not cookie
                or not secrets.compare_digest(state, cookie)
                or deadline is None
                or deadline <= datetime.now(UTC)
            ):
                raise AuthError("Login expired or invalid. Start login again.")
            del self.pending[state]  # Each login attempt can be used only once.
        if status != "success" or not request_token:
            raise AuthError("Kite login was cancelled or failed. Start login again.")
        key = self.settings.kite_api_key.get_secret_value().strip()
        secret = self.settings.kite_api_secret.get_secret_value().strip()
        checksum = hashlib.sha256(f"{key}{request_token}{secret}".encode()).hexdigest()
        data = self._request(
            "POST",
            "/session/token",
            data={"api_key": key, "request_token": request_token, "checksum": checksum},
        )
        token = data.get("access_token")
        user_id = data.get("user_id")
        if not isinstance(token, str) or not token or not isinstance(user_id, str):
            raise AuthError("Kite returned an incomplete session. Log in again.", 502)
        session = {
            "access_token": token,
            "user_id": user_id,
            "api_key_hash": hashlib.sha256(key.encode()).hexdigest(),
            "expires_at": session_expiry(datetime.now(UTC)).isoformat(),
        }
        with self.lock:
            self._save(session)
        log.info("kite_login_succeeded")

    def status(self) -> KiteStatus:
        if not self.settings.kite_configured:
            return KiteStatus(configured=False, message="Add Kite credentials to .env.")
        with self.lock:
            session = self._load()
            if session is None:
                return KiteStatus(configured=True, message="Daily Kite login required.")
            token = session["access_token"]
            try:
                self._request("GET", "/user/profile", token=token)
            except AuthError as error:
                if error.status_code == 401:
                    self.settings.kite_session_file.unlink(missing_ok=True)
                    log.info("kite_session_invalidated")
                    return KiteStatus(
                        configured=True, message="Kite login required again."
                    )
                raise
            return KiteStatus(
                configured=True,
                authenticated=True,
                user_id=session["user_id"],
                expires_at=datetime.fromisoformat(session["expires_at"]),
                message="Kite session verified. Application remains in PAPER mode.",
            )

    def _request(
        self,
        method: str,
        path: str,
        *,
        token: str = "",
        data: dict[str, str] | None = None,
        params: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        headers = {"X-Kite-Version": "3"}
        if token:
            key = self.settings.kite_api_key.get_secret_value().strip()
            headers["Authorization"] = f"token {key}:{token}"
        try:
            response = self.client.request(
                method, path, headers=headers, data=data, params=params
            )
            payload = response.json()
        except (httpx.HTTPError, ValueError):
            log.warning("kite_connection_failed")
            raise AuthError("Cannot reach Kite. Check your connection and retry.", 502)
        if not isinstance(payload, dict):
            raise AuthError("Kite returned an unexpected response.", 502)
        if response.is_error or payload.get("status") != "success":
            log.warning("kite_request_rejected", status_code=response.status_code)
            if response.status_code == 429:
                raise AuthError("Kite rate limit reached. Retry later.", 429)
            if payload.get("error_type") == "TokenException" and token:
                raise AuthError("Kite session is no longer valid.", 401)
            raise AuthError(
                "Kite rejected the request. Check your app and log in again.", 502
            )
        result = payload.get("data")
        if not isinstance(result, dict):
            raise AuthError("Kite returned an unexpected response.", 502)
        return result

    def _save(self, session: dict[str, str]) -> None:
        # DPAPI ties encryption to this Windows user; no extra key in .env.
        import win32crypt  # type: ignore[import-untyped]

        try:
            encrypted = win32crypt.CryptProtectData(
                json.dumps(session).encode(),
                "AUREVON Kite session",
                None,
                None,
                None,
                1,
            )
            path = self.settings.kite_session_file
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix(".tmp")
            temporary.write_bytes(encrypted)
            temporary.replace(path)
        except Exception:
            log.error("kite_session_save_failed")
            raise AuthError("Could not save the encrypted Kite session locally.", 500)

    def _load(self) -> dict[str, str] | None:
        import win32crypt

        path = self.settings.kite_session_file
        if not path.exists():
            return None
        try:
            _, plaintext = win32crypt.CryptUnprotectData(
                path.read_bytes(), None, None, None, 1
            )
            session = json.loads(plaintext)
            key = self.settings.kite_api_key.get_secret_value().strip()
            if (
                not isinstance(session, dict)
                or not all(
                    isinstance(session.get(k), str)
                    for k in ("access_token", "user_id", "api_key_hash", "expires_at")
                )
                or session["api_key_hash"] != hashlib.sha256(key.encode()).hexdigest()
                or datetime.fromisoformat(session["expires_at"]) <= datetime.now(UTC)
            ):
                raise ValueError("Expired or mismatched session")
            return {k: str(v) for k, v in session.items()}
        except Exception:
            log.warning("kite_session_unavailable")
            path.unlink(missing_ok=True)
            return None
