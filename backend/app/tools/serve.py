"""Single-owner local HTTPS production server; Ctrl+C drains application work."""

from pathlib import Path

import uvicorn
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.config import BACKEND_DIR, Settings
from app.market.lifecycle_state import ProcessLease


def server() -> uvicorn.Server:
    root = BACKEND_DIR.parent
    tls = root / "frontend" / ".local-tls"
    build = root / "frontend" / "dist"
    for path in (
        tls / "localhost-key.pem",
        tls / "localhost-cert.pem",
        build / "index.html",
    ):
        if not path.is_file():
            raise ValueError("Build frontend and configure local TLS before serving")
    from app.main import create_app

    settings = Settings(dashboard_frontend_dir=build)
    application = create_app(settings)
    application.add_middleware(
        TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"]
    )
    return uvicorn.Server(
        uvicorn.Config(
            application,
            host="127.0.0.1",
            port=8443,
            workers=1,
            ssl_keyfile=str(tls / "localhost-key.pem"),
            ssl_certfile=str(tls / "localhost-cert.pem"),
            access_log=False,
            proxy_headers=False,
        )
    )


def main() -> None:
    owner = ProcessLease(Path(BACKEND_DIR / "data" / "https-server.lock"))
    owner.acquire()
    try:
        server().run()
    finally:
        owner.release()


if __name__ == "__main__":
    main()
