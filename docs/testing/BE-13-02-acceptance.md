# BE-13-02 dashboard authentication acceptance

Accepted 2026-10-27 (D02, early D23). Product counts: 83 Completed / 197 Pending.

Subsequent D02 work completed BE-13-03 access protection, lockout and audit.
The limits below describe the original BE-13-02 checkpoint; current behavior
and counts are in [BE-13 acceptance](BE-13-acceptance.md) and
[dashboard operations](../api/dashboard-operations.md). Logout now requires
an authenticated session and CSRF header; revoked sessions receive 401.

- `app/api/dashboard_routes.py`: independent dashboard password and session state;
  no broker token, state cookie or account login is reused.
- Argon2 hash only in `DASHBOARD_PASSWORD_HASH` (SecretStr); no default password.
  Empty hash returns configured=false and rejects login with 503. Invalid hash
  rejects app construction without reflecting the value.
- GET `/api/auth/dashboard/status`: configured/authenticated booleans.
- POST `/api/auth/dashboard/login`: JSON password, bounded and redacted. Invalid
  credentials return the shared 401 envelope; success sets a signed HS256 JWT in
  `__Host-aurevon-dashboard`, Secure, HttpOnly, SameSite=Strict, Path=/, no Domain.
  Status/login/logout never return the token in JSON.
- POST `/api/auth/dashboard/logout`: idempotent cookie deletion and server-side
  revocation. Replaying the revoked cookie fails. Stale logout cannot revoke a
  replacement session. Both auth mutations reject explicit foreign Origin and
  cross-site Fetch Metadata.
- Expiry defaults to eight hours (60..86400 seconds configurable). Random process
  signing key and one active session ID invalidate sessions on restart and login
  replacement. Run one application worker; sessions are intentionally process-local.

## Local setup

From backend, run `uv run python -m app.tools.dashboard_password` locally. Enter
and confirm a unique password of at least 12 characters at the hidden prompts.
Copy the resulting Argon2 hash into the ignored `.env` as
`DASHBOARD_PASSWORD_HASH`. Do not send passwords or hashes in conversation.
Restart the application after changing the hash. Actual `.env` was not changed.

Use HTTPS for portable Secure cookie behavior. Tests use https://testserver;
development proxy and production serving configuration remain BE-13-04. Do not
disable Secure to work around an HTTP client that does not send the cookie.

## Checks and limits

`test_dashboard_auth.py`: 10 cases cover cookie lifecycle, disabled/malformed
configuration, wrong passwords, rotation, stale logout, revocation, expiry,
tampering, process restart, invalid tokens, cross-origin mutation and redaction.
Full suite: 338 passed, one existing Starlette/httpx warning. Repository-wide
Ruff lint/format and strict mypy passed. Existing migration import spacing was
normalized for Ruff; no schema change or migration was run.

BE-13-03 remains Pending: existing API routes are not yet protected by dashboard
authentication; full mutation/WebSocket origin/CSRF policy, five-failure login
lockout and mutation audit are not delivered here. No production readiness,
broker connection, real market observation, trade or qualifying session claimed.
