"""Opt-in Windows SCM wrapper. Never installed or started by normal setup."""

import sys
import threading
from pathlib import Path

import servicemanager  # type: ignore[import-untyped]
import uvicorn
import win32service  # type: ignore[import-untyped]
import win32serviceutil  # type: ignore[import-untyped]

from app.config import BACKEND_DIR, Settings
from app.market.lifecycle_state import ProcessLease
from app.tools.serve import server
from app.tools.service_access import validate_service_access


class AurevonService(win32serviceutil.ServiceFramework):  # type: ignore[misc]
    _exe_name_ = str(Path(sys.executable).parent / "pythonservice.exe")
    _svc_name_ = "AUREVONPaper"
    _svc_display_name_ = "AUREVON local paper dashboard"
    _svc_description_ = "Single local HTTPS paper owner. No live orders."

    def __init__(self, args: list[str]) -> None:
        super().__init__(args)
        self.stopping = threading.Event()
        self.http: uvicorn.Server | None = None

    def SvcStop(self) -> None:
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING, waitHint=60000)
        self.stopping.set()
        if self.http is not None:
            self.http.should_exit = True

    def SvcDoRun(self) -> None:
        owner = ProcessLease(BACKEND_DIR / "data" / "https-server.lock")
        owner.acquire()
        try:
            validate_service_access(
                BACKEND_DIR.parent / "frontend" / ".local-tls",
                Settings().kite_session_file,
            )
            self.http = server()
            if not self.stopping.is_set():
                self.http.run()
        except Exception:
            servicemanager.LogErrorMsg(
                "AUREVON service failed; inspect local safe logs"
            )
            raise
        finally:
            owner.release()


if __name__ == "__main__":
    win32serviceutil.HandleCommandLine(AurevonService)
