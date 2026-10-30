"""SCM import root keeps the backend package available to PythonService.exe."""

from pathlib import Path

import win32serviceutil

from app.tools.windows_service import AurevonService

if __name__ == "__main__":
    win32serviceutil.HandleCommandLine(
        AurevonService,
        serviceClassString=str(Path(__file__).with_suffix("")) + ".AurevonService",
    )
