"""Isolated synthetic browser acceptance only; never reads the project's .env."""

import ipaddress
import os
import subprocess
import sys
import tempfile
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

frontend = Path(__file__).resolve().parents[1]
backend = frontend.parent / "backend"
sys.path.insert(0, str(backend))

with tempfile.TemporaryDirectory(prefix="aurevon-browser-") as folder:
    root = Path(folder)
    # Guard even the module-level default app against loading real state/secrets.
    os.environ.update(
        DATABASE_URL=f"sqlite:///{(root / 'test.db').as_posix()}",
        KITE_API_KEY="",
        KITE_API_SECRET="",
        MARKET_SERVICE_ENABLED="false",
        MARKET_LOCK_FILE=str(root / "owner.lock"),
        KITE_SESSION_FILE=str(root / "kite.bin"),
    )
    os.chdir(frontend)
    import uvicorn
    from argon2 import PasswordHasher

    from app.config import Settings
    from app.db.models import Base
    from app.market.exchange_calendar import ExchangeCalendar
    from app.wallet.service import WalletService

    # main also constructs a module-level default app. Disable dotenv there too.
    Settings.model_config["env_file"] = None
    from app.main import create_app

    settings = Settings(
        _env_file=None,
        database_url=os.environ["DATABASE_URL"],
        market_lock_file=root / "owner.lock",
        kite_session_file=root / "kite.bin",
        market_record_dir=root / "ticks",
        log_level="ERROR",
        market_service_enabled=False,
        wallet_reconciliation_enabled=False,
        development_replay_enabled=False,
        kite_api_key="",
        kite_api_secret="",
        dashboard_password_hash=PasswordHasher().hash("browser-fixture-only"),
        dashboard_origins=["https://127.0.0.1:5174"],
        market_stream="browser-live",
        renko_anchor=23900,
    )
    app = create_app(settings)
    Base.metadata.create_all(app.state.database_engine)
    from live_fixture import seed_chart

    seed_chart(app.state.database_engine, settings.market_stream)
    wallet = WalletService(
        app.state.database_engine, ExchangeCalendar(settings.market_calendar_dir)
    )
    wallet.initialize(datetime.now(timezone.utc))
    app.state.paper_execution = wallet
    server = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=18765, log_level="warning")
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(timezone.utc) - timedelta(minutes=1))
        .not_valid_after(datetime.now(timezone.utc) + timedelta(days=1))
        .add_extension(
            x509.SubjectAlternativeName(
                [
                    x509.DNSName("localhost"),
                    x509.IPAddress(ipaddress.ip_address("127.0.0.1")),
                ]
            ),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )
    key_path, cert_path = root / "key.pem", root / "cert.pem"
    key_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    env = dict(
        os.environ,
        LOCAL_TLS_KEY=str(key_path),
        LOCAL_TLS_CERT=str(cert_path),
        LOCAL_API_TARGET="http://127.0.0.1:18765",
        LOCAL_UI_PORT="5174",
    )
    try:
        subprocess.run(["npm.cmd", "run", "dev"], cwd=frontend, env=env, check=True)
    finally:
        server.should_exit = True
        thread.join(timeout=10)
