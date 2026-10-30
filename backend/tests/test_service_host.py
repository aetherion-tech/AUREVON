from pathlib import Path
from unittest.mock import Mock

import pytest

from app.tools.service_host import stage_host


def files(tmp_path):
    venv = tmp_path / "venv"
    (venv / "Scripts").mkdir(parents=True)
    (venv / "pyvenv.cfg").write_text("home = base")
    (venv / "pythonservice.exe").write_bytes(b"host")
    base = tmp_path / "base"
    base.mkdir()
    core = base / "python312.dll"
    core.write_bytes(b"python")
    helper = base / "pywintypes312.dll"
    helper.write_bytes(b"win32")
    (base / "vcruntime140.dll").write_bytes(b"runtime")
    return venv, core, helper


def test_stage_colocates_dependencies_and_is_idempotent(tmp_path):
    venv, core, helper = files(tmp_path)
    host = stage_host(venv, core, helper)
    assert host == venv / "Scripts" / "pythonservice.exe"
    assert host.read_bytes() == b"host"
    for source in (core, helper, core.parent / "vcruntime140.dll"):
        assert (host.parent / source.name).read_bytes() == source.read_bytes()
    assert stage_host(venv, core, helper) == host
    assert (venv / "pythonservice.exe").read_bytes() == b"host"


def test_missing_dependency_rejected_before_any_copy(tmp_path):
    venv, core, helper = files(tmp_path)
    with pytest.raises(ValueError, match="missing"):
        stage_host(venv, core, helper.parent / "absent.dll")
    assert list((venv / "Scripts").iterdir()) == []


def test_different_existing_runtime_is_never_overwritten(tmp_path):
    venv, core, helper = files(tmp_path)
    dest = venv / "Scripts" / core.name
    dest.write_bytes(b"different-runtime")
    with pytest.raises(ValueError, match="differs"):
        stage_host(venv, core, helper)
    assert dest.read_bytes() == b"different-runtime"
    assert not (venv / "Scripts" / "pythonservice.exe").exists()


@pytest.mark.parametrize("running", [False, True])
def test_repair_changes_only_binary_path_and_refuses_running_service(
    monkeypatch, running
):
    import win32service

    from app.tools import service_host

    monkeypatch.setattr("sys.argv", ["service_host", "--configure"])
    monkeypatch.setattr(win32service, "OpenSCManager", Mock(return_value="manager"))
    monkeypatch.setattr(win32service, "OpenService", Mock(return_value="service"))
    monkeypatch.setattr(
        win32service, "QueryServiceStatus", Mock(return_value=(0, 4 if running else 1))
    )
    change = Mock()
    close = Mock()
    stage = Mock(return_value=Path("D:/venv/Scripts/pythonservice.exe"))
    monkeypatch.setattr(win32service, "ChangeServiceConfig", change)
    monkeypatch.setattr(win32service, "CloseServiceHandle", close)
    monkeypatch.setattr(service_host, "stage_host", stage)
    if running:
        with pytest.raises(RuntimeError, match="Stop the service"):
            service_host.main()
        stage.assert_not_called()
        change.assert_not_called()
    else:
        service_host.main()
        args = change.call_args.args
        assert args[:4] == ("service", -1, -1, -1)
        assert args[4] == '"D:\\venv\\Scripts\\pythonservice.exe"'
        assert args[5:] == (None, 0, None, None, None, None)
    assert close.call_count == 2
