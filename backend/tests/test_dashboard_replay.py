"""Real production replay behind authenticated development controls."""

import asyncio
from datetime import timedelta
from threading import Event

import pytest
from auth_helpers import authenticate, password_hash
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.orm import Session
from test_tick_recording import START, tick

from app.api.replay_routes import ReplayRequest
from app.broker.kite_ticker import TickerWorker
from app.config import Settings
from app.db.models import Base, MarketCheckpoint
from app.main import create_app
from app.market.tick_recording import TickRecorder


@pytest.fixture
def recording(tmp_path):
    config = Settings(
        _env_file=None,
        dashboard_password_hash=SecretStr(password_hash()),
        database_url=f"sqlite:///{(tmp_path / 'paper.db').as_posix()}",
        market_record_dir=tmp_path / "ticks",
        development_replay_enabled=True,
    )
    recorder = TickRecorder(config.market_record_dir, 111, 222)
    source = TickerWorker(None, 111, 222, recorder=recorder)
    for minute, price in ((0, 100), (1, 130), (2, 110), (3, 140)):
        for token in source.tokens:
            at = START + timedelta(minutes=minute)
            source._accept(tick(token, at, price, 100 + minute * 10), at)
    source.advance_candles(START + timedelta(minutes=5))
    files = sorted(recorder.directory.glob("*.jsonl"))
    body = ReplayRequest(
        source_run=recorder.directory.name,
        files=[p.name for p in files],
        spot_token=111,
        future_token=222,
        box="10",
        anchor="100",
    )
    return config, files, body


def test_production_replay_does_not_touch_market_database(recording):
    config, files, body = recording
    app = create_app(config)
    Base.metadata.create_all(app.state.database_engine)
    original = [p.read_bytes() for p in files]
    # Exercise the actual production persistence path in the job executor.
    events, bricks = app.state.replay_service._execute(body)
    assert events > 0 and bricks > 0
    assert [p.read_bytes() for p in files] == original
    with Session(app.state.database_engine) as db:
        assert db.scalars(select(MarketCheckpoint)).all() == []


def test_replay_corruption_fails_safely_and_job_shutdown_joins(recording):
    config, files, body = recording
    files[0].write_text("private-invalid-recording")
    app = create_app(config)
    service = app.state.replay_service

    async def exercise():
        response = await service.start(body)
        assert response.state == "running"
        await service.close()
        assert service.task.done()
        assert service.status.state == "failed"
        assert "private" not in service.status.model_dump_json()

    asyncio.run(exercise())


def test_replay_endpoint_accepted_job_and_concurrent_feed_start_rejected(
    recording, monkeypatch
):
    config, _, body = recording
    app = create_app(config)
    Base.metadata.create_all(app.state.database_engine)
    started, release = Event(), Event()
    original = app.state.replay_service._execute

    def execute(request):
        started.set()
        assert release.wait(10)
        return original(request)

    monkeypatch.setattr(app.state.replay_service, "_execute", execute)
    with TestClient(app, base_url="https://testserver") as client:
        authenticate(client)
        try:
            response = client.post("/api/dev/replay", json=body.model_dump())
            assert response.status_code == 202, response.text
            assert started.wait(5)
            assert (
                client.post("/api/dev/replay", json=body.model_dump()).status_code
                == 409
            )
            assert client.post("/api/market/service/start").status_code == 409
            assert (
                client.get("/api/dev/replay/" + response.json()["id"]).json()["state"]
                == "running"
            )
        finally:
            release.set()
    assert app.state.replay_service.status.state == "completed"


@pytest.mark.parametrize(
    "change", ["duplicate", "traversal", "too_large", "bad_tokens"]
)
def test_replay_input_boundaries(recording, change):
    config, _, body = recording
    app = create_app(config)
    if change == "duplicate":
        body = body.model_copy(update={"files": body.files * 2})
    elif change == "traversal":
        body = body.model_copy(update={"files": ["../../.env"]})
    elif change == "too_large":
        config.development_replay_max_bytes = 1
    else:
        body = body.model_copy(update={"future_token": body.spot_token})
    from fastapi import HTTPException

    with pytest.raises(HTTPException):
        app.state.replay_service._paths(body)
