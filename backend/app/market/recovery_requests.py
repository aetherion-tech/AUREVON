"""Bounded retries for read-only historical recovery; no session mutation."""

from collections.abc import Callable
from datetime import datetime
from time import sleep
from typing import Any

import httpx

from app.broker.kite_auth import AuthError
from app.config import Settings
from app.market.historical import HistoricalClient


class RecoveryRequestError(RuntimeError):
    def __init__(self, message: str, attempts: int, status_code: int) -> None:
        super().__init__(message)
        self.attempts = attempts
        self.status_code = status_code


class RecoveryHistoryClient:
    """Retry transport failures, HTTP 429 and service failures only.

    Maximum attempts includes the first call. Each retry still passes through
    the existing historical request pacer. Invalid data, request/auth errors and
    persistence conflicts are never retried. Run blocking calls off the event loop.
    """

    def __init__(
        self,
        auth: HistoricalClient,
        settings: Settings,
        *,
        sleeper: Callable[[float], None] | None = None,
    ) -> None:
        self.auth = auth
        self.settings = settings
        self.sleeper = sleeper or sleep
        self.retries = 0

    def historical_data(
        self,
        instrument_token: int,
        interval: str,
        start: datetime,
        end: datetime,
        *,
        oi: bool = False,
    ) -> dict[str, Any]:
        for attempt in range(1, self.settings.recovery_max_attempts + 1):
            failure: AuthError
            try:
                return self.auth.historical_data(
                    instrument_token, interval, start, end, oi=oi
                )
            except AuthError as error:
                if not error.retryable:
                    raise
                failure = error
            except httpx.TransportError:
                failure = AuthError(
                    "Historical network request failed.", 502, retryable=True
                )
            if attempt == self.settings.recovery_max_attempts:
                raise RecoveryRequestError(
                    "Historical recovery attempts exhausted; state unchanged.",
                    attempt,
                    failure.status_code,
                ) from None
            delay = min(
                self.settings.recovery_backoff_seconds * 2 ** (attempt - 1),
                self.settings.recovery_backoff_max_seconds,
            )
            if failure.retry_after_seconds is not None:
                if (
                    failure.retry_after_seconds
                    > self.settings.recovery_backoff_max_seconds
                ):
                    raise RecoveryRequestError(
                        "Historical retry delay exceeds policy; retry later.",
                        attempt,
                        failure.status_code,
                    ) from None
                delay = max(delay, failure.retry_after_seconds)
            self.sleeper(delay)
            self.retries += 1
        raise AssertionError("Validated recovery attempts must be positive")
