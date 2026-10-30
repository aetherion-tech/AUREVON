import sys
from types import SimpleNamespace

import pytest

from app.tools.service_access import validate_service_access


def test_tls_failure_stops_before_decrypt_and_preserves_session(tmp_path):
    session = tmp_path / "session.bin"
    session.write_bytes(b"encrypted")
    with pytest.raises(RuntimeError, match="TLS pair"):
        validate_service_access(tmp_path, session)
    assert session.read_bytes() == b"encrypted"


@pytest.mark.parametrize("decrypt_ok", [True, False])
def test_dpapi_access_never_changes_session(tmp_path, monkeypatch, decrypt_ok):
    from app.tools import service_access

    session = tmp_path / "session.bin"
    session.write_bytes(b"encrypted")
    monkeypatch.setattr(
        service_access.ssl,
        "SSLContext",
        lambda *_: SimpleNamespace(load_cert_chain=lambda *_: None),
    )

    def decrypt(data, *_):
        assert data == b"encrypted"
        if not decrypt_ok:
            raise OSError("wrong identity")
        return "description", b"private plaintext"

    monkeypatch.setitem(
        sys.modules, "win32crypt", SimpleNamespace(CryptUnprotectData=decrypt)
    )
    if decrypt_ok:
        validate_service_access(tmp_path, session)
    else:
        with pytest.raises(RuntimeError, match="file preserved"):
            validate_service_access(tmp_path, session)
    assert session.read_bytes() == b"encrypted"


def test_no_saved_session_does_not_require_dpapi(tmp_path, monkeypatch):
    from app.tools import service_access

    monkeypatch.setattr(
        service_access.ssl,
        "SSLContext",
        lambda *_: SimpleNamespace(load_cert_chain=lambda *_: None),
    )
    monkeypatch.setitem(sys.modules, "win32crypt", None)
    validate_service_access(tmp_path, tmp_path / "missing.bin")
