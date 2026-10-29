"""Run locally: uv run python -m app.tools.dashboard_password.

Read the password interactively; never pass a CLI secret.
"""

import argparse
from getpass import getpass
from pathlib import Path

from argon2 import PasswordHasher
from dotenv import set_key

from app.config import BACKEND_DIR


def save_password_hash(path: Path, password_hash: str) -> None:
    """Preserve other settings and quote Argon2's dollar signs literally."""
    set_key(str(path), "DASHBOARD_PASSWORD_HASH", password_hash, quote_mode="always")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--save", action="store_true", help="Save directly to backend/.env."
    )
    args = parser.parse_args()
    password = getpass("New dashboard password (at least 12 characters): ")
    confirmation = getpass("Confirm dashboard password: ")
    if len(password) < 12 or password != confirmation:
        raise SystemExit(
            "Password too short or confirmation differs; no hash generated."
        )
    password_hash = PasswordHasher().hash(password)
    if args.save:
        path = BACKEND_DIR / ".env"
        save_password_hash(path, password_hash)
        print(f"Dashboard password saved to {path}.")
        print("Restart the backend, then sign in with the password you chose.")
    else:
        print("DASHBOARD_PASSWORD_HASH=" + password_hash)


if __name__ == "__main__":
    main()
