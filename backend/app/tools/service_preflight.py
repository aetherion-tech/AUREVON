"""Read-only SCM inventory. Never starts a service or reads broker secrets."""

import argparse
import json
from datetime import datetime, timezone
from typing import Any

SYSTEM_IDENTITIES = {"localsystem", "nt authority\\system", ".\\localsystem"}


def configured_identity(report: dict[str, Any]) -> bool:
    name = report.get("service_identity")
    return (
        report.get("service_query") == "OK"
        and isinstance(name, str)
        and bool(name.strip())
        and name.strip().casefold() not in SYSTEM_IDENTITIES
    )


def inspect() -> dict[str, Any]:
    import pywintypes  # type: ignore[import-untyped]
    import win32api  # type: ignore[import-untyped]
    import win32service  # type: ignore[import-untyped]

    report: dict[str, Any] = {
        "at": datetime.now(timezone.utc).isoformat(),
        "evidence": "READ_ONLY_SCM_PREFLIGHT",
        "operator_identity": win32api.GetUserNameEx(2),
        "create_service_access": "UNKNOWN",
        "service_query": "UNKNOWN",
        "service_identity": None,
        "identity_tls_dpapi_verified": False,
        "lifecycle_verified": False,
        "paper_trading_ready": False,
    }
    try:
        manager = win32service.OpenSCManager(
            None, None, win32service.SC_MANAGER_CREATE_SERVICE
        )
    except pywintypes.error as exc:
        report["create_service_access"] = "DENIED_OR_UNAVAILABLE"
        report["create_service_error"] = exc.winerror
    else:
        report["create_service_access"] = "GRANTED"
        win32service.CloseServiceHandle(manager)
    manager = None
    service = None
    try:
        manager = win32service.OpenSCManager(
            None, None, win32service.SC_MANAGER_CONNECT
        )
        service = win32service.OpenService(
            manager,
            "AUREVONPaper",
            win32service.SERVICE_QUERY_CONFIG | win32service.SERVICE_QUERY_STATUS,
        )
        config = win32service.QueryServiceConfig(service)
        status = win32service.QueryServiceStatus(service)
        report.update(
            service_query="OK",
            service_identity=config[7],
            start_type=config[1],
            current_state=status[1],
        )
    except pywintypes.error as exc:
        report["service_query"] = (
            "NOT_INSTALLED" if exc.winerror == 1060 else "UNAVAILABLE"
        )
        report["service_query_error"] = exc.winerror
    finally:
        if service is not None:
            win32service.CloseServiceHandle(service)
        if manager is not None:
            win32service.CloseServiceHandle(manager)
    report["configured_non_system_identity"] = configured_identity(report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--require-configured-identity", action="store_true")
    args = parser.parse_args()
    report = inspect()
    print(json.dumps(report, indent=2))
    if args.require_configured_identity and not configured_identity(report):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
