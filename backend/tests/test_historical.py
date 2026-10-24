"""Historical downloads use fake HTTP and clocks only."""

from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest
from pydantic import SecretStr

from app.broker.kite_auth import AuthError, KiteAuth
from app.config import Settings
from app.market.historical import download, parse_candle, save_csv
from app.market.renko_builder import RenkoBuilder
from app.tools.replay import replay

START = datetime.fromisoformat("2026-09-01T09:15:00+05:30")


def row(ts: datetime, close: int = 24050, oi: bool = False) -> list[object]:
    values: list[object] = [ts.isoformat(), 24000, close, 23950, close, 100]
    return values + [500] if oi else values


def auth_for(tmp_path: Path, handler) -> KiteAuth:
    return KiteAuth(
        Settings(
            _env_file=None,
            kite_api_key=SecretStr("fake"),
            kite_api_secret=SecretStr("secret"),
            kite_session_file=tmp_path / "unused.bin",
        ),
        httpx.Client(
            base_url="https://api.kite.trade", transport=httpx.MockTransport(handler)
        ),
    )


def test_chunks_auth_rate_limit_and_overlap(tmp_path: Path) -> None:
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        assert request.headers["Authorization"] == "token fake:private"
        assert request.url.params["oi"] == "1"
        assert request.url.params["continuous"] == "0"
        boundary = START + timedelta(days=30)
        rows = (
            [row(START, oi=True), row(boundary, oi=True)]
            if len(calls) == 1
            else [row(boundary, oi=True), row(boundary + timedelta(minutes=5), oi=True)]
        )
        return httpx.Response(
            200, json={"status": "success", "data": {"candles": rows}}
        )

    auth = auth_for(tmp_path, handler)
    with (
        patch.object(auth, "_load", return_value={"access_token": "private"}),
        patch("app.broker.kite_auth.monotonic", return_value=100.0),
        patch("app.broker.kite_auth.sleep") as sleep,
    ):
        candles = download(
            auth, 123, START, START + timedelta(days=31), interval="5minute", oi=True
        )
    assert len(candles) == 3
    assert len(calls) == 2
    assert sleep.call_args.args[0] == pytest.approx(0.4)
    assert calls[0].url.path == "/instruments/historical/123/5minute"
    auth.close()


def test_incomplete_candles_excluded_and_csv_replays(tmp_path: Path) -> None:
    auth = auth_for(
        tmp_path,
        lambda request: httpx.Response(
            200,
            json={
                "status": "success",
                "data": {
                    "candles": [
                        row(START, 24000),
                        row(START + timedelta(minutes=1), 24100),
                    ]
                },
            },
        ),
    )
    with patch.object(auth, "_load", return_value={"access_token": "private"}):
        candles = download(
            auth,
            123,
            START,
            START + timedelta(minutes=10),
            now=START + timedelta(minutes=2),
        )
    path = tmp_path / "prices.csv"
    save_csv(path, candles, "minute")
    bricks = replay(path, RenkoBuilder(50, 24000))
    assert len(bricks) == 2
    assert bricks[-1].ts == START + timedelta(minutes=2)
    assert "candle_open_time" in path.read_text()
    auth.close()


@pytest.mark.parametrize(
    "bad",
    [
        [],
        ["bad"],
        [START.isoformat(), 1, 0, 2, 1, 0],
        [START.isoformat(), 1, 2, 1, "NaN", 0],
        ["2026-09-01T09:15:00", 1, 2, 1, 2, 0],
    ],
)
def test_invalid_candle(bad: list[object]) -> None:
    with pytest.raises(ValueError, match="invalid historical candle"):
        parse_candle(bad, oi=False)


def test_missing_login_and_rate_limit_are_safe(tmp_path: Path) -> None:
    auth = auth_for(
        tmp_path,
        lambda request: httpx.Response(
            429, json={"status": "error", "message": "private broker details"}
        ),
    )
    with patch.object(auth, "_load", return_value=None):
        with pytest.raises(AuthError) as missing:
            download(auth, 123, START, START)
        assert missing.value.status_code == 401
    with patch.object(auth, "_load", return_value={"access_token": "private"}):
        with pytest.raises(AuthError) as limited:
            download(auth, 123, START, START)
        assert limited.value.status_code == 429
        assert "private" not in str(limited.value)
    auth.close()


def test_invalid_range_and_conflicting_duplicates(tmp_path: Path) -> None:
    auth = auth_for(
        tmp_path,
        lambda request: httpx.Response(
            200,
            json={
                "status": "success",
                "data": {"candles": [row(START), row(START, 24100)]},
            },
        ),
    )
    with pytest.raises(ValueError):
        download(auth, 123, START.replace(tzinfo=None), START)
    with patch.object(auth, "_load", return_value={"access_token": "private"}):
        with pytest.raises(ValueError, match="Conflicting"):
            download(auth, 123, START, START)
    auth.close()
