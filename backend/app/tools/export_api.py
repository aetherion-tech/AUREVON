"""Export the actual application contract without starting services or accounts."""

import argparse
import json
from pathlib import Path

from app.config import BACKEND_DIR, Settings
from app.main import create_app

DEFAULT_OUTPUT = BACKEND_DIR.parent / "docs" / "api" / "openapi.v1.json"


def export(output: Path, *, check: bool = False) -> None:
    app = create_app(
        Settings.model_construct(
            database_url="sqlite://",
            market_service_enabled=False,
            dashboard_frontend_dir=None,
        )
    )
    try:
        content = json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n"
        if check:
            if not output.is_file() or output.read_text(encoding="utf-8") != content:
                raise SystemExit("API artifact drift; regenerate the v1 contract.")
        else:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(content, encoding="utf-8")
    finally:
        app.state.database_engine.dispose()
        app.state.market_service.auth.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    export(args.output, check=args.check)


if __name__ == "__main__":
    main()
