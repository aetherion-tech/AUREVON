"""Stage a venv-native SCM host; optionally repair ONLY a stopped service's path."""

import argparse
import hashlib
import shutil
import sys
from pathlib import Path


def stage_host(venv: Path, python_dll: Path, helper_dll: Path) -> Path:
    candidates = [
        venv / "Lib" / "site-packages" / "win32" / "pythonservice.exe",
        venv / "pythonservice.exe",
        venv / "Scripts" / "pythonservice.exe",
    ]
    source = next((p for p in candidates if p.is_file()), None)
    if source is None:
        raise ValueError("Installed pywin32 service host is missing")
    sources = [source, python_dll, helper_dll]
    sources.extend(sorted(python_dll.parent.glob("vcruntime140*.dll")))
    target = venv / "Scripts"
    if not target.is_dir() or not (venv / "pyvenv.cfg").is_file():
        raise ValueError("Expected a Windows virtual environment with Scripts")
    for src in sources:
        if not src.is_file():
            raise ValueError(f"Required service dependency missing: {src.name}")
        dest = target / src.name
        if dest.exists() and hashlib.sha256(dest.read_bytes()).digest() != (
            hashlib.sha256(src.read_bytes()).digest()
        ):
            raise ValueError(f"Existing service dependency differs: {dest.name}")
    for src in sources:
        dest = target / src.name
        if not dest.exists():
            shutil.copy2(src, dest)
    return target / "pythonservice.exe"


def main() -> None:
    import pywintypes  # type: ignore[import-untyped]
    import win32api  # type: ignore[import-untyped]
    import win32service  # type: ignore[import-untyped]

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--configure", action="store_true")
    args = parser.parse_args()
    manager = None
    service = None
    try:
        if args.configure:
            manager = win32service.OpenSCManager(
                None, None, win32service.SC_MANAGER_CONNECT
            )
            service = win32service.OpenService(
                manager,
                "AUREVONPaper",
                win32service.SERVICE_QUERY_STATUS | win32service.SERVICE_CHANGE_CONFIG,
            )
            if (
                win32service.QueryServiceStatus(service)[1]
                != win32service.SERVICE_STOPPED
            ):
                raise RuntimeError(
                    "Stop the service gracefully before repairing its host"
                )
        host = stage_host(
            Path(sys.prefix),
            Path(win32api.GetModuleFileName(sys.dllhandle)),
            Path(pywintypes.__file__),
        )
        if service is not None:
            win32service.ChangeServiceConfig(
                service,
                win32service.SERVICE_NO_CHANGE,
                win32service.SERVICE_NO_CHANGE,
                win32service.SERVICE_NO_CHANGE,
                f'"{host}"',
                None,
                0,
                None,
                None,
                None,
                None,
            )
        print(f"Service host staged: {host}")
        print("No service started; account, startup and recovery policy preserved.")
    finally:
        if service is not None:
            win32service.CloseServiceHandle(service)
        if manager is not None:
            win32service.CloseServiceHandle(manager)


if __name__ == "__main__":
    main()
