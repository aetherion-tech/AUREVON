"""Serve only the dashboard build; client routes never swallow API/asset errors."""

from pathlib import Path

from starlette.exceptions import HTTPException
from starlette.responses import Response
from starlette.staticfiles import StaticFiles
from starlette.types import Scope


class DashboardFiles(StaticFiles):
    def __init__(self, directory: Path) -> None:
        super().__init__(directory=directory, html=True, follow_symlink=False)

    async def get_response(self, path: str, scope: Scope) -> Response:
        try:
            return await super().get_response(path, scope)
        except HTTPException as error:
            # Only extensionless HTML navigations are React routes. Missing chunks,
            # dotfiles and non-HTML requests must remain genuine 404 responses.
            parts = Path(path).parts
            headers = dict(scope.get("headers", []))
            if (
                error.status_code != 404
                or scope["method"] not in ("GET", "HEAD")
                or b"text/html" not in headers.get(b"accept", b"")
                or any(part.startswith(".") for part in parts)
                or "." in Path(path).name
                or (parts and parts[0] in ("assets", "api", "ws"))
            ):
                raise
            return await super().get_response("index.html", scope)
