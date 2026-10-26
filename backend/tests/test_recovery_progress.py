"""Progress and failure evidence use the established recovery source fixture."""

from unittest.mock import patch

import httpx
import pytest
import test_recovery as recovery_sources
from sqlalchemy.exc import OperationalError
from test_recovery import (
    CALENDAR,
    END,
    IDENTITY,
    SETTINGS,
    START,
    broker,
    snapshot,
)

from app.broker.kite_auth import AuthError, KiteAuth
from app.market.persistence import PersistenceError
from app.market.recovery import recover_missing_history
from app.market.recovery_progress import RecoveryProgress

# Reuse the fixture's original source prices/catalog/checkpoint without rewriting it.


@pytest.fixture
def engine(tmp_path):
    yield from recovery_sources.engine.__wrapped__(tmp_path)


def run(database, auth, progress, **kwargs):
    return recover_missing_history(
        auth,
        database,
        SETTINGS,
        "test",
        111,
        222,
        IDENTITY,
        CALENDAR,
        END,
        progress=progress,
        **kwargs,
    )


def test_progress_tracks_real_ranges_and_committed_source_times(engine):
    progress = RecoveryProgress()
    observed = []
    auth = broker()
    original = auth.historical_data.side_effect

    def request(*args, **kwargs):
        observed.append(progress.snapshot())
        return original(*args, **kwargs)

    auth.historical_data.side_effect = request
    result = run(engine, auth, progress)
    actual = progress.snapshot()
    assert actual["phase"] == "complete"
    assert actual["completed_ranges"] == actual["total_ranges"] == 2
    assert actual["failure_reason"] is None
    assert actual["quality_pending"] is True  # Recovery does not clear entry gaps.
    assert actual["entries_enabled"] is False
    assert actual["last_successful_source_time"] == {
        "111": END.isoformat(),
        "222": END.isoformat(),
    }
    assert all(row["phase"] == "downloading" for row in observed)
    assert observed[0]["completed_ranges"] == 0 and observed[1]["completed_ranges"] == 1
    assert result.imported
    run(engine, broker(), progress)
    assert progress.snapshot()["total_ranges"] == 0


def test_failure_preserves_committed_watermarks_and_rolls_back(engine):
    progress = RecoveryProgress()
    progress.committed({111: START}, quality_pending=True)
    before = snapshot(engine)
    with patch.object(
        engine.dialect,
        "do_commit",
        side_effect=OperationalError("", {}, Exception("private token")),
    ):
        with pytest.raises(PersistenceError):
            run(engine, broker(), progress)
    assert snapshot(engine) == before
    row = progress.snapshot()
    assert row["phase"] == "failed" and row["failure_reason"] == "persistence_failed"
    assert row["last_successful_source_time"] == {"111": START.isoformat()}
    assert "private" not in str(row)


def test_expired_session_is_not_retried_or_written(engine, tmp_path):
    progress = RecoveryProgress()
    session = tmp_path / "encrypted.bin"
    session.write_bytes(b"session-sentinel")
    settings = SETTINGS.model_copy(update={"kite_session_file": session})
    # Dummy keys; the real broker reader finds no valid session.
    from pydantic import SecretStr

    settings = settings.model_copy(
        update={
            "kite_api_key": SecretStr("fixture"),
            "kite_api_secret": SecretStr("fixture"),
        }
    )

    def unexpected(request):
        raise AssertionError("Expired session must not send HTTP")

    before = snapshot(engine)
    with httpx.Client(
        base_url="https://api.kite.trade", transport=httpx.MockTransport(unexpected)
    ) as client:
        auth = KiteAuth(settings, client)
        with patch.object(auth, "_load", return_value=None) as load:
            with pytest.raises(AuthError) as error:
                recover_missing_history(
                    auth,
                    engine,
                    settings,
                    "test",
                    111,
                    222,
                    IDENTITY,
                    CALENDAR,
                    END,
                    progress=progress,
                )
            assert error.value.status_code == 401
            assert load.call_count == 1
    assert snapshot(engine) == before
    assert session.read_bytes() == b"session-sentinel"
    assert progress.snapshot()["failure_reason"] == "authentication_required"
    assert progress.snapshot()["last_successful_source_time"] == {}
