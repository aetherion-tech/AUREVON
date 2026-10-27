"""Run locally: uv run python -m app.tools.dashboard_password.

Read the password interactively; never pass a CLI secret.
"""

from getpass import getpass

from argon2 import PasswordHasher


def main() -> None:
    password = getpass("New dashboard password (at least 12 characters): ")
    confirmation = getpass("Confirm dashboard password: ")
    if len(password) < 12 or password != confirmation:
        raise SystemExit(
            "Password too short or confirmation differs; no hash generated."
        )
    print("DASHBOARD_PASSWORD_HASH=" + PasswordHasher().hash(password))


if __name__ == "__main__":
    main()
