"""Read service-owned TLS and optional DPAPI state without modifying either."""

import ssl
from pathlib import Path


def validate_service_access(tls_dir: Path, session_file: Path) -> None:
    try:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(
            tls_dir / "localhost-cert.pem", tls_dir / "localhost-key.pem"
        )
    except (OSError, ssl.SSLError) as from_error:
        raise RuntimeError("Service cannot load the local TLS pair") from from_error
    if session_file.exists():
        import win32crypt  # type: ignore[import-untyped]

        try:
            win32crypt.CryptUnprotectData(
                session_file.read_bytes(), None, None, None, 1
            )
        except Exception as exc:
            raise RuntimeError(
                "Service cannot decrypt the saved Kite session; file preserved"
            ) from exc
