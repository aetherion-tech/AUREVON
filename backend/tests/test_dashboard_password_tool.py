"""Local password setup preserves config and avoids secret output in save mode."""

import pytest
from argon2 import PasswordHasher
from dotenv import dotenv_values

from app.tools import dashboard_password as tool


def test_save_mode_roundtrips_hash_preserves_other_settings_and_hides_secrets(
    tmp_path, monkeypatch, capsys
):
    path = tmp_path / ".env"
    path.write_text("# retained\nKITE_API_KEY=fixture-key\nDASHBOARD_PASSWORD_HASH=\n")
    monkeypatch.setattr(tool, "BACKEND_DIR", tmp_path)
    monkeypatch.setattr("sys.argv", ["dashboard_password", "--save"])
    password = "local-fixture-password"
    answers = iter([password, password])
    monkeypatch.setattr(tool, "getpass", lambda _: next(answers))
    tool.main()
    values = dotenv_values(path)
    assert values["KITE_API_KEY"] == "fixture-key"
    assert "# retained" in path.read_text()
    password_hash = values["DASHBOARD_PASSWORD_HASH"]
    assert PasswordHasher().verify(password_hash, password)
    output = capsys.readouterr().out
    assert password not in output and password_hash not in output
    assert "saved" in output


@pytest.mark.parametrize("confirmation", ["different-password", "short"])
def test_bad_confirmation_never_modifies_config(tmp_path, monkeypatch, confirmation):
    path = tmp_path / ".env"
    original = "KITE_API_KEY=fixture-key\n"
    path.write_text(original)
    monkeypatch.setattr(tool, "BACKEND_DIR", tmp_path)
    monkeypatch.setattr("sys.argv", ["dashboard_password", "--save"])
    answers = iter(["local-fixture-password", confirmation])
    monkeypatch.setattr(tool, "getpass", lambda _: next(answers))
    with pytest.raises(SystemExit):
        tool.main()
    assert path.read_text() == original
