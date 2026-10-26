from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from threading import Event
from unittest.mock import patch

import httpx
import pytest

from app.broker.kite_auth import AuthError, KiteAuth
from app.broker.request_limits import (
    RecoveryBusyError,
    RequestCoordinator,
    single_recovery,
)
from app.config import Settings
from app.market.recovery import recover_missing_history


class FakeTime:
    def __init__(self):
        self.now = 100.0

    def clock(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


def test_mixed_clients_share_pacing_and_catalog_cooldown():
    timer = FakeTime()
    limiter = RequestCoordinator(clock=timer.clock, sleeper=timer.sleep)
    starts = []

    def handler(request):
        starts.append(timer.now)
        if request.url.path == "/instruments/NSE":
            return httpx.Response(429, headers={"Retry-After": "5"})
        return httpx.Response(200, json={"status": "success", "data": {}})

    settings = Settings(_env_file=None, kite_api_key="fake", kite_api_secret="fake")
    with (
        httpx.Client(
            base_url="https://api.kite.trade", transport=httpx.MockTransport(handler)
        ) as client,
        patch("app.broker.kite_auth.managed_rest", limiter),
    ):
        first, second = KiteAuth(settings, client), KiteAuth(settings, client)
        with patch.object(first, "_load", return_value={"access_token": "private"}):
            first.historical_data(1, "minute", datetime.now(), datetime.now())
            with pytest.raises(AuthError):
                first.download_instruments("NSE")
        second._request("GET", "/user/profile")
        second._request("POST", "/session/token")
    assert starts == pytest.approx([100, 100.4, 105.4, 105.8])


def test_concurrent_requests_and_failure_spacing():
    timer = FakeTime()
    limiter = RequestCoordinator(clock=timer.clock, sleeper=timer.sleep)
    starts = []

    def call():
        return limiter.call(lambda: starts.append(timer.now))

    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda _: call(), range(8)))
    assert starts == pytest.approx([100 + i * 0.4 for i in range(8)])
    with pytest.raises(ValueError):
        limiter.call(lambda: (_ for _ in ()).throw(ValueError()))
    call()
    assert starts[-1] == pytest.approx(103.6)


def test_recovery_overlap_and_release_after_failure():
    entered, release = Event(), Event()

    @single_recovery
    def active():
        entered.set()
        assert release.wait(5)
        raise ValueError("failed")

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(active)
        try:
            assert entered.wait(5)
            with pytest.raises(RecoveryBusyError):
                recover_missing_history()
        finally:
            release.set()
        with pytest.raises(ValueError, match="failed"):
            future.result()
    with pytest.raises(TypeError):
        recover_missing_history()
