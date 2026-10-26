"""Fake HTTP, fake sleeps and session sentinels for bounded historical retries."""

from unittest.mock import Mock

import httpx
import pytest
from test_recovery import END, START

from app.broker.kite_auth import AuthError, KiteAuth
from app.config import Settings
from app.market.recovery_requests import RecoveryHistoryClient, RecoveryRequestError


def test_exponential_backoff_is_capped_and_success_is_returned_once():
    auth, sleeps = Mock(spec=KiteAuth), []
    auth.historical_data.side_effect = [
        AuthError("rate limit", 429, retryable=True),
        httpx.ReadTimeout("private URL"),
        AuthError("service", 502, retryable=True),
        {"candles": []},
    ]
    settings = Settings(
        _env_file=None, recovery_backoff_seconds=2, recovery_backoff_max_seconds=3
    )
    client = RecoveryHistoryClient(auth, settings, sleeper=sleeps.append)
    assert client.historical_data(222, "5minute", START, END, oi=True) == {
        "candles": []
    }
    assert sleeps == [2, 3, 3]
    assert client.retries == 3
    assert auth.historical_data.call_count == 4
    assert all(
        call.kwargs["oi"] is True for call in auth.historical_data.call_args_list
    )


@pytest.mark.parametrize("attempts", [1, 3])
def test_exhaustion_has_no_final_sleep_or_private_error_details(attempts):
    auth, sleeps = Mock(spec=KiteAuth), []
    auth.historical_data.side_effect = httpx.ConnectError("private URL and token")
    client = RecoveryHistoryClient(
        auth,
        Settings(_env_file=None, recovery_max_attempts=attempts),
        sleeper=sleeps.append,
    )
    with pytest.raises(RecoveryRequestError, match="exhausted") as error:
        client.historical_data(111, "minute", START, END)
    assert auth.historical_data.call_count == attempts
    assert len(sleeps) == attempts - 1
    assert error.value.attempts == attempts
    assert "private" not in str(error.value)


@pytest.mark.parametrize(
    "failure",
    [
        AuthError("login", 401),
        AuthError("bad input", 400),
        AuthError("malformed body", 502),
        ValueError("invalid candle"),
    ],
)
def test_nontransient_failures_are_not_retried(failure):
    auth, sleeps = Mock(spec=KiteAuth), []
    auth.historical_data.side_effect = failure
    client = RecoveryHistoryClient(
        auth, Settings(_env_file=None), sleeper=sleeps.append
    )
    with pytest.raises(type(failure)):
        client.historical_data(111, "minute", START, END)
    assert auth.historical_data.call_count == 1
    assert sleeps == []


@pytest.mark.parametrize("delay,expected", [(5, [5]), (31, [])])
def test_numeric_retry_after_is_observed_or_fails_without_early_retry(delay, expected):
    auth, sleeps = Mock(spec=KiteAuth), []
    auth.historical_data.side_effect = [
        AuthError("limit", 429, retryable=True, retry_after_seconds=delay),
        {"candles": []},
    ]
    client = RecoveryHistoryClient(
        auth, Settings(_env_file=None), sleeper=sleeps.append
    )
    if delay > 30:
        with pytest.raises(RecoveryRequestError, match="exceeds policy"):
            client.historical_data(111, "minute", START, END)
        assert auth.historical_data.call_count == 1
    else:
        assert client.historical_data(111, "minute", START, END) == {"candles": []}
    assert sleeps == expected


@pytest.mark.parametrize(
    "status,body,retryable,expected_code",
    [
        (429, "plain rate limit", True, 429),
        (503, "plain unavailable", True, 502),
        (500, {"status": "error"}, True, 502),
        (400, {"status": "error", "error_type": "InputException"}, False, 502),
        (403, {"status": "error", "error_type": "TokenException"}, False, 401),
        (200, "invalid JSON", False, 502),
    ],
)
def test_http_classification_preserves_the_saved_session(
    tmp_path, status, body, retryable, expected_code
):
    session = tmp_path / "session.bin"
    session.write_bytes(b"encrypted-fixture")

    def handler(request):
        kwargs = {"json": body} if isinstance(body, dict) else {"text": body}
        return httpx.Response(status, headers={"Retry-After": "5"}, **kwargs)

    auth = KiteAuth(
        Settings(_env_file=None, kite_session_file=session),
        httpx.Client(
            base_url="https://api.kite.trade", transport=httpx.MockTransport(handler)
        ),
    )
    try:
        with pytest.raises(AuthError) as error:
            auth._request("GET", "/instruments/historical/111/minute", token="private")
        assert error.value.retryable is retryable
        assert error.value.status_code == expected_code
        assert session.read_bytes() == b"encrypted-fixture"
        assert "private" not in str(error.value)
    finally:
        auth.close()
