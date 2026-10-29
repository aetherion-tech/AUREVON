"""Source-bound replay overlays, real API paging and independent failure fences."""

import json
from dataclasses import asdict, replace
from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from auth_helpers import authenticate, password_hash
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.orm import Session

from app.config import Settings
from app.db.models import (
    Base,
    IndicatorCheckpoint,
    IndicatorResult,
    MarketCheckpoint,
    StoredBrick,
    StoredCandle,
)
from app.indicator.chart_history import publish_chart_history
from app.indicator.persistence import IndicatorRepository
from app.indicator.settings import IndicatorSettings
from app.main import create_app
from app.market.persistence import encode
from app.market.renko_builder import IST, Brick

AT = datetime(2026, 10, 29, 10, tzinfo=IST)


@pytest.fixture
def chart(tmp_path):
    app = create_app(
        Settings(
            _env_file=None,
            database_url=f"sqlite:///{(tmp_path / 'chart.db').as_posix()}",
            dashboard_password_hash=password_hash(),
        )
    )
    engine = app.state.database_engine
    Base.metadata.create_all(engine)
    bricks = [
        Brick(i, Decimal(100 + i * 50), Decimal(150 + i * 50), 1, AT) for i in range(4)
    ]
    with Session(engine) as db, db.begin():
        db.add(
            MarketCheckpoint(
                stream="chart",
                revision=4,
                configuration=encode(
                    dict(
                        spot=111,
                        future=222,
                        box="50",
                        anchor="100",
                        mode="minute_close",
                    )
                ),
                state="{}",
            )
        )
        for b in bricks:
            db.add(
                StoredBrick(stream="chart", index=b.index, payload=encode(asdict(b)))
            )
    repository = IndicatorRepository(
        engine, "chart", IndicatorSettings(atrLen=2, rsiLen=2)
    )
    results = [repository.process(b) for b in bricks]
    client = TestClient(app, base_url="https://testserver")
    authenticate(client)
    yield client, app, bricks, results
    engine.dispose()
    app.state.market_service.auth.close()


def test_publication_and_equal_time_index_paging_include_first_brick(chart):
    client, app, bricks, results = chart
    source = publish_chart_history(app.state.database_engine, "chart")
    assert publish_chart_history(app.state.database_engine, "chart") == source
    first = client.get("/api/bricks?stream=chart&limit=2")
    assert first.status_code == 200, first.text
    body = first.json()
    assert [b["index"] for b in body["items"]] == [0, 1]
    assert [o["index"] for o in body["overlays"]] == [0, 1]
    assert body["next_after"] == 1 and body["indicators_available"]
    assert (
        body["overlay_status"] == "complete" and body["missing_overlay_indices"] == []
    )
    assert body["indicator_source"]["source_id"] == source.source_id
    assert body["indicator_source"]["reference_verified"] is False
    assert body["overlays"][0]["rsi"] is None  # warm-up isn't a fabricated zero
    assert body["overlays"][1]["supertrend"] == results[1]["supertrend"]
    assert "manifest" not in first.text and '"input"' not in first.text
    second = client.get(
        "/api/bricks",
        params=dict(
            stream="chart",
            limit=2,
            after=1,
            revision=4,
            indicator_source=source.source_id,
        ),
    ).json()
    assert [o["index"] for o in second["overlays"]] == [2, 3]
    assert second["next_after"] is None
    empty = client.get("/api/bricks?stream=chart&after=3").json()
    assert empty["overlay_status"] == "empty" and empty["overlays"] == []


def test_unpublished_missing_and_partial_are_explicit(chart):
    client, app, bricks, results = chart
    engine = app.state.database_engine
    before = client.get("/api/bricks?stream=chart").json()
    assert before["overlay_reason"] == "not_published" and before["overlays"] == []
    assert before["missing_overlay_indices"] == [0, 1, 2, 3]
    publish_chart_history(engine, "chart")
    # A market snapshot may contain a tail not yet processed by the indicator.
    with Session(engine) as db, db.begin():
        b = replace(bricks[-1], index=4, open=Decimal(300), close=Decimal(350))
        db.add(StoredBrick(stream="chart", index=4, payload=encode(asdict(b))))
    body = client.get("/api/bricks?stream=chart").json()
    assert body["overlay_status"] == "partial" and body["missing_overlay_indices"] == [
        4
    ]
    assert [o["index"] for o in body["overlays"]] == [0, 1, 2, 3]


@pytest.mark.parametrize(
    "change",
    [
        "market_revision",
        "market_configuration",
        "indicator_advanced",
        "publication_changed",
    ],
)
def test_cross_page_source_changes_require_resync(chart, change):
    client, app, bricks, results = chart
    engine = app.state.database_engine
    source = publish_chart_history(engine, "chart")
    with Session(engine) as db, db.begin():
        market = db.get(MarketCheckpoint, "chart")
        checkpoint = db.get(IndicatorCheckpoint, "chart")
        if change == "market_revision":
            market.revision += 1
        elif change == "market_configuration":
            market.configuration = market.configuration.replace(
                '"222"', '"333"'
            ).replace("222", "333")
        elif change == "indicator_advanced":
            checkpoint.index += 1
        else:
            snapshot = json.loads(checkpoint.payload)
            snapshot["chart_source"]["source_id"] = "0" * 64
            checkpoint.payload = encode(snapshot)
    response = client.get(
        "/api/bricks",
        params=dict(
            stream="chart", after=1, revision=4, indicator_source=source.source_id
        ),
    )
    assert response.status_code == 409
    if change in ("market_revision", "market_configuration"):
        first = client.get("/api/bricks?stream=chart").json()
        assert first["overlay_reason"] == "source_changed" and first["overlays"] == []


@pytest.mark.parametrize(
    "damage", ["result", "input", "brick", "missing", "settings", "manifest"]
)
def test_corrupt_published_data_never_returns_mixed_overlays(chart, damage):
    client, app, bricks, results = chart
    engine = app.state.database_engine
    publish_chart_history(engine, "chart")
    with Session(engine) as db, db.begin():
        row = db.get(IndicatorResult, ("chart", 1))
        if damage in ("result", "input"):
            setattr(row, "payload" if damage == "result" else "input", "{}")
        elif damage == "brick":
            changed = replace(bricks[1], volume=Decimal(999))
            db.get(StoredBrick, ("chart", 1)).payload = encode(asdict(changed))
        elif damage == "missing":
            db.delete(row)
        else:
            checkpoint = db.get(IndicatorCheckpoint, "chart")
            snapshot = json.loads(checkpoint.payload)
            if damage == "settings":
                snapshot["chart_source"]["settings"]["factor"] = 999
            else:
                snapshot["chart_source"]["manifest"] = []
            checkpoint.payload = encode(snapshot)
    assert client.get("/api/bricks?stream=chart").status_code == 409


@pytest.mark.parametrize(
    "damage",
    ["source_brick", "missing_prefix", "wrong_box", "wrong_settings", "unknown_stream"],
)
def test_publication_rejects_invalid_lineage_and_is_atomic(chart, damage):
    client, app, bricks, results = chart
    engine = app.state.database_engine
    with Session(engine) as db, db.begin():
        if damage == "source_brick":
            db.get(StoredBrick, ("chart", 0)).payload = encode(
                asdict(replace(bricks[0], close=Decimal(999)))
            )
        elif damage == "missing_prefix":
            db.delete(db.get(IndicatorResult, ("chart", 0)))
        elif damage == "wrong_box":
            row = db.get(MarketCheckpoint, "chart")
            config = json.loads(row.configuration)
            config["box"] = "25"
            row.configuration = encode(config)
        elif damage == "wrong_settings":
            row = db.get(IndicatorResult, ("chart", 1))
            source = json.loads(row.input)
            source["settings"]["factor"] = 8
            row.input = encode(source)
    with Session(engine) as db:
        before = db.get(IndicatorCheckpoint, "chart").payload
    with pytest.raises(ValueError):
        publish_chart_history(
            engine, "other" if damage == "unknown_stream" else "chart"
        )
    with Session(engine) as db:
        assert db.get(IndicatorCheckpoint, "chart").payload == before


def test_indicator_processing_invalidates_publication_and_republication_restores_it(
    chart,
):
    client, app, bricks, results = chart
    engine = app.state.database_engine
    old = publish_chart_history(engine, "chart")
    b = replace(
        bricks[-1],
        index=4,
        open=Decimal(300),
        close=Decimal(350),
        ts=AT + timedelta(minutes=1),
    )
    with Session(engine) as db, db.begin():
        db.add(StoredBrick(stream="chart", index=4, payload=encode(asdict(b))))
        db.get(MarketCheckpoint, "chart").revision += 1
    repository = IndicatorRepository(
        engine, "chart", IndicatorSettings(atrLen=2, rsiLen=2)
    )
    repository.process(b)
    assert (
        client.get("/api/bricks?stream=chart").json()["overlay_reason"]
        == "not_published"
    )
    assert (
        client.get(
            "/api/bricks", params=dict(stream="chart", indicator_source=old.source_id)
        ).status_code
        == 409
    )
    new = publish_chart_history(engine, "chart")
    assert new.source_id != old.source_id
    assert len(client.get("/api/bricks?stream=chart").json()["overlays"]) == 5


def test_history_auth_validation_and_bounded_queries(chart):
    client, app, bricks, results = chart
    publish_chart_history(app.state.database_engine, "chart")
    anonymous = TestClient(app, base_url="https://testserver")
    assert anonymous.get("/api/bricks?stream=chart").status_code == 401
    for params in (dict(after=-2), dict(limit=301), dict(indicator_source="bad")):
        assert (
            client.get("/api/bricks", params={"stream": "chart", **params}).status_code
            == 422
        )
    assert client.get("/api/bricks?stream=unknown").status_code == 404
    statements = []

    def capture(conn, cursor, statement, parameters, context, many):
        if statement.lstrip().upper().startswith("SELECT"):
            statements.append(statement)

    event.listen(app.state.database_engine, "before_cursor_execute", capture)
    try:
        body = client.get("/api/bricks?stream=chart&limit=1").json()
        assert len(body["items"]) == len(body["overlays"]) == 1
    finally:
        event.remove(app.state.database_engine, "before_cursor_execute", capture)
    assert (
        len(statements) == 4
    )  # market identity + brick page + indicator checkpoint + bounded result page
    assert "LIMIT" in statements[1] and " IN (" in statements[-1]


def test_candle_history_keeps_source_identity_and_remains_independent_of_renko_overlays(
    chart,
):
    client, app, bricks, results = chart
    publish_chart_history(app.state.database_engine, "chart")
    with Session(app.state.database_engine) as db, db.begin():
        for i in range(3):
            at = AT + timedelta(minutes=i)
            db.add(
                StoredCandle(
                    stream="chart",
                    token=111,
                    time=at.isoformat(),
                    payload=encode(
                        dict(
                            time=at,
                            end=at + timedelta(minutes=1),
                            open="100",
                            high="150",
                            low="100",
                            close="150",
                            volume="1",
                            oi=None,
                            vwap=None,
                            partial=False,
                            vwap_partial=True,
                        )
                    ),
                )
            )
    body = client.get("/api/candles?stream=chart&token=111&limit=2").json()
    assert len(body["items"]) == 2 and body["indicators_available"] is False
    second = client.get(
        "/api/candles",
        params=dict(stream="chart", token=111, revision=4, after=body["next_after"]),
    ).json()
    assert (
        len(second["items"]) == 1
        and second["configuration_id"] == body["configuration_id"]
    )
    assert client.get("/api/candles?stream=chart&token=999").status_code == 422


def test_real_indicator_entry_exit_markers_and_levels_are_read_only(chart):
    from app.indicator.strategy import PineEngine

    client, app, initial, results = chart
    engine = app.state.database_engine
    settings = IndicatorSettings(
        atrLen=2, rsiLen=2, evalBricks=2, minGrade="Weak and above (all)"
    )
    series = [1000, 1050, 1100, 1150, 1100, 1050, 1000, 950] * 5
    replay = PineEngine("markers", settings)
    expected = []
    with Session(engine) as db, db.begin():
        db.add(
            MarketCheckpoint(
                stream="markers",
                revision=1,
                configuration=encode(
                    dict(
                        spot=111,
                        future=222,
                        box="50",
                        anchor="1000",
                        mode="minute_close",
                    )
                ),
                state="{}",
            )
        )
        for i in range(len(series) - 1):
            opening, close = series[i], series[i + 1]
            # The repeated pattern includes a same-colour one-brick transition.
            b = Brick(
                i,
                Decimal(opening),
                Decimal(close),
                1 if close > opening else -1,
                AT + timedelta(minutes=i),
            )
            result = replay.process(b)
            expected.extend(
                (i, e["kind"], e["trade_id"], e["price"]) for e in result["events"]
            )
            db.add(StoredBrick(stream="markers", index=i, payload=encode(asdict(b))))
            db.add(
                IndicatorResult(
                    stream="markers",
                    index=i,
                    input=encode(
                        dict(brick=asdict(b), context={}, settings=settings.values)
                    ),
                    payload=encode(result),
                )
            )
        db.add(
            IndicatorCheckpoint(
                stream="markers",
                index=len(series) - 2,
                payload=encode(replay.snapshot()),
            )
        )
    source = publish_chart_history(engine, "markers")
    with Session(engine) as db:
        before = db.get(IndicatorCheckpoint, "markers").payload
    body = client.get("/api/bricks?stream=markers&limit=100").json()
    events = [
        (o["index"], e["kind"], e["trade_id"], e["price"])
        for o in body["overlays"]
        for e in o["events"]
    ]
    assert events == expected and {e[1] for e in events} >= {"ENTRY", "EXIT"}
    assert body["indicator_source"]["mode"] == "INDICATOR_REPLAY"
    assert body["overlays"][-1]["up_trigger"] == max(series[-2:]) + 50
    assert body["indicator_source"]["source_id"] == source.source_id
    with Session(engine) as db:
        assert db.get(IndicatorCheckpoint, "markers").payload == before
    assert app.state.market_service.worker is None


def test_new_settings_publication_fences_old_cursor_without_market_changes(chart):
    from app.indicator.strategy import PineEngine

    client, app, bricks, results = chart
    engine = app.state.database_engine
    old = publish_chart_history(engine, "chart")
    settings = IndicatorSettings(atrLen=3, rsiLen=3)
    replay = PineEngine("chart", settings)
    with Session(engine) as db, db.begin():
        for brick in bricks:
            row = db.get(IndicatorResult, ("chart", brick.index))
            input_data = json.loads(row.input)
            input_data["settings"] = settings.values
            row.input = encode(input_data)
            row.payload = encode(replay.process(brick))
        db.get(IndicatorCheckpoint, "chart").payload = encode(replay.snapshot())
    new = publish_chart_history(engine, "chart")
    assert new.settings_id != old.settings_id and new.source_id != old.source_id
    assert (
        client.get(
            "/api/bricks",
            params=dict(
                stream="chart", after=1, revision=4, indicator_source=old.source_id
            ),
        ).status_code
        == 409
    )
    assert (
        client.get(
            "/api/bricks",
            params=dict(
                stream="chart", after=1, revision=4, indicator_source=new.source_id
            ),
        ).status_code
        == 200
    )


def test_concurrent_market_commit_cannot_mix_page_identity_and_bricks(chart):
    from concurrent.futures import ThreadPoolExecutor

    client, app, bricks, results = chart
    engine = app.state.database_engine
    publish_chart_history(engine, "chart")
    futures = []
    fired = [False]

    def rewrite():
        with Session(engine) as db, db.begin():
            db.get(MarketCheckpoint, "chart").revision = 5
            db.get(StoredBrick, ("chart", 0)).payload = encode(
                asdict(replace(bricks[0], volume=Decimal(99)))
            )

    with ThreadPoolExecutor(max_workers=1) as pool:

        def concurrent(conn, cursor, statement, parameters, context, many):
            if "FROM renko_bricks" in statement and not fired[0]:
                fired[0] = True
                futures.append(pool.submit(rewrite))

        event.listen(engine, "before_cursor_execute", concurrent)
        try:
            response = client.get("/api/bricks?stream=chart")
            assert response.status_code == 200, response.text
            assert response.json()["revision"] == 4
            assert response.json()["items"][0]["volume"] == "0"
            futures[0].result(timeout=5)
        finally:
            event.remove(engine, "before_cursor_execute", concurrent)
    assert client.get("/api/bricks?stream=chart&revision=4").status_code == 409


def test_malformed_checkpoint_binding_returns_conflict_not_success(chart):
    client, app, bricks, results = chart
    with Session(app.state.database_engine) as db, db.begin():
        db.get(IndicatorCheckpoint, "chart").payload = encode({"chart_source": [1]})
    assert client.get("/api/bricks?stream=chart").status_code == 409


def test_future_context_cannot_be_published_as_historical_chart_data(chart):
    client, app, bricks, results = chart
    with Session(app.state.database_engine) as db, db.begin():
        row = db.get(IndicatorResult, ("chart", 0))
        source = json.loads(row.input)
        source["context"]["available_at"] = (AT + timedelta(minutes=1)).isoformat()
        row.input = encode(source)
    with pytest.raises(ValueError, match="unavailable"):
        publish_chart_history(app.state.database_engine, "chart")
