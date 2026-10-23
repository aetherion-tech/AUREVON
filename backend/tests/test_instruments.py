"""Daily catalog tests use synthetic instruments and never contact Kite."""

import csv
import hashlib
import io
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.orm import Session

from alembic import command
from app.broker.instruments import InstrumentError, Instruments, parse_instruments
from app.broker.kite_auth import IST, AuthError, KiteAuth
from app.config import BACKEND_DIR, Settings
from app.db.models import Base, Instrument, InstrumentSnapshot
from app.db.session import database_engine
from app.main import create_app

COLUMNS = [
    "instrument_token",
    "exchange_token",
    "tradingsymbol",
    "name",
    "last_price",
    "expiry",
    "strike",
    "tick_size",
    "lot_size",
    "instrument_type",
    "segment",
    "exchange",
]


def fake_csv(exchange: str) -> str:
    today = datetime.now(IST).date()
    near = (today + timedelta(days=2)).isoformat()
    far = (today + timedelta(days=9)).isoformat()
    expired = (today - timedelta(days=1)).isoformat()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(COLUMNS)
    if exchange == "NSE":
        writer.writerow(
            [111, 1, "NIFTY 50", "NIFTY 50", 0, "", 0, 0, 0, "EQ", "INDICES", "NSE"]
        )
    else:
        writer.writerows(
            [
                [
                    201,
                    1,
                    "NIFTYNEARFUT",
                    "NIFTY",
                    0,
                    near,
                    0,
                    ".05",
                    40,
                    "FUT",
                    "NFO-FUT",
                    "NFO",
                ],
                [
                    202,
                    2,
                    "NIFTYFARFUT",
                    "NIFTY",
                    0,
                    far,
                    0,
                    ".05",
                    40,
                    "FUT",
                    "NFO-FUT",
                    "NFO",
                ],
                [
                    203,
                    3,
                    "NIFTYEXPIREDFUT",
                    "NIFTY",
                    0,
                    expired,
                    0,
                    ".05",
                    40,
                    "FUT",
                    "NFO-FUT",
                    "NFO",
                ],
                [
                    301,
                    4,
                    "NIFTYNEARCE",
                    "NIFTY",
                    0,
                    near,
                    25000,
                    ".05",
                    40,
                    "CE",
                    "NFO-OPT",
                    "NFO",
                ],
                [
                    302,
                    5,
                    "NIFTYNEARPE",
                    "NIFTY",
                    0,
                    near,
                    25000,
                    ".05",
                    40,
                    "PE",
                    "NFO-OPT",
                    "NFO",
                ],
                [
                    303,
                    6,
                    "NIFTYFARCE",
                    "NIFTY",
                    0,
                    far,
                    25100,
                    ".05",
                    45,
                    "CE",
                    "NFO-OPT",
                    "NFO",
                ],
                [
                    304,
                    7,
                    "NIFTYOLDCE",
                    "NIFTY",
                    0,
                    expired,
                    25000,
                    ".05",
                    40,
                    "CE",
                    "NFO-OPT",
                    "NFO",
                ],
                [
                    401,
                    8,
                    "BANKNIFTYCE",
                    "BANKNIFTY",
                    0,
                    near,
                    50000,
                    ".05",
                    20,
                    "CE",
                    "NFO-OPT",
                    "NFO",
                ],
            ]
        )
    return output.getvalue()


def make_service(tmp_path: Path, handler):
    settings = Settings(
        _env_file=None,
        kite_api_key=SecretStr("instrument-test-key"),
        kite_api_secret=SecretStr("instrument-test-secret"),
        kite_session_file=tmp_path / "session.bin",
        database_url=f"sqlite:///{(tmp_path / 'test.db').as_posix()}",
    )
    auth = KiteAuth(
        settings,
        httpx.Client(
            base_url="https://api.kite.trade", transport=httpx.MockTransport(handler)
        ),
    )
    auth._save(
        {
            "access_token": "instrument-test-token",
            "user_id": "TEST",
            "api_key_hash": hashlib.sha256(b"instrument-test-key").hexdigest(),
            "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
        }
    )
    engine = database_engine(settings.database_url)
    Base.metadata.create_all(engine)
    return settings, auth, Instruments(engine, auth)


def test_refresh_and_nifty_routes_use_daily_cache(tmp_path: Path) -> None:
    calls = []

    def broker(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        assert (
            request.headers["Authorization"]
            == "token instrument-test-key:instrument-test-token"
        )
        return httpx.Response(200, text=fake_csv(request.url.path.rsplit("/", 1)[1]))

    settings, auth, service = make_service(tmp_path, broker)
    try:
        with TestClient(create_app(settings, auth)) as client:
            assert client.get("/api/market/nifty").status_code == 409
            response = client.post("/api/market/instruments/refresh")
            assert response.status_code == 200
            assert response.json()["ready"] is True
            assert response.json()["exchanges"]["NFO"]["count"] == 8
            assert client.post("/api/market/instruments/refresh").status_code == 200
            assert calls == ["/instruments/NSE", "/instruments/NFO"]
            nifty = client.get("/api/market/nifty").json()
            assert nifty["spot"]["instrument_token"] == 111
            assert nifty["future"]["tradingsymbol"] == "NIFTYNEARFUT"
            assert len(nifty["options"]) == 2
            assert {o["name"] for o in nifty["options"]} == {"NIFTY"}
            far = nifty["option_expiries"][1]
            selected = client.get("/api/market/nifty", params={"expiry": far}).json()
            assert selected["options"][0]["lot_size"] == 45
            assert client.get("/api/market/nifty?expiry=2000-01-01").status_code == 404
            assert client.get("/api/market/nifty?expiry=invalid").status_code == 422
    finally:
        service.engine.dispose()


def test_bad_refresh_preserves_previous_snapshot(tmp_path: Path) -> None:
    fail = False

    def broker(request: httpx.Request) -> httpx.Response:
        exchange = request.url.path.rsplit("/", 1)[1]
        return httpx.Response(
            200, text="bad CSV" if fail and exchange == "NFO" else fake_csv(exchange)
        )

    _, auth, service = make_service(tmp_path, broker)
    try:
        service.refresh()
        with Session(service.engine) as db, db.begin():
            for snapshot in db.scalars(select(InstrumentSnapshot)):
                snapshot.loaded_at = datetime.now(UTC) - timedelta(days=1)
        fail = True
        with pytest.raises(InstrumentError, match="invalid instrument CSV"):
            service.refresh()
        with Session(service.engine) as db:
            assert db.get(Instrument, ("NSE", "NIFTY 50")) is not None
            assert db.get(Instrument, ("NFO", "NIFTYNEARFUT")) is not None
        assert service.status()["ready"] is False
    finally:
        auth.close()
        service.engine.dispose()


@pytest.mark.parametrize("text", ["", "<html>failure</html>", ",".join(COLUMNS)])
def test_invalid_or_empty_csv_is_rejected(text: str) -> None:
    with pytest.raises(InstrumentError):
        parse_instruments(text, "NSE")


def test_duplicate_and_nonfinite_rows_rejected() -> None:
    text = fake_csv("NSE")
    with pytest.raises(InstrumentError):
        parse_instruments(text + text.splitlines()[1] + "\n", "NSE")
    with pytest.raises(InstrumentError):
        parse_instruments(fake_csv("NFO").replace("25000", "NaN"), "NFO")


def test_download_requires_login_and_preserves_session_on_timeout(
    tmp_path: Path,
) -> None:
    def broker(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("instrument-test-token", request=request)

    settings, auth, service = make_service(tmp_path, broker)
    try:
        with pytest.raises(AuthError, match="download failed"):
            auth.download_instruments("NSE")
        assert settings.kite_session_file.exists()
        settings.kite_session_file.unlink()
        with pytest.raises(AuthError, match="Log in"):
            auth.download_instruments("NSE")
    finally:
        auth.close()
        service.engine.dispose()


def test_migration_matches_models_and_can_run_twice(
    tmp_path: Path, monkeypatch
) -> None:
    url = f"sqlite:///{(tmp_path / 'migration.db').as_posix()}"
    monkeypatch.setenv("DATABASE_URL", url)
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    command.upgrade(config, "head")
    command.upgrade(config, "head")
    engine = database_engine(url)
    try:
        with engine.connect() as connection:
            assert (
                compare_metadata(MigrationContext.configure(connection), Base.metadata)
                == []
            )
    finally:
        engine.dispose()
