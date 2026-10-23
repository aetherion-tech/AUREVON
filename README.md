# AUREVON

A Python application for a Renko indicator, a future React dashboard, and paper
trading with Zerodha Kite market data. Development follows small, testable steps.

## Current progress

| Step | Status | Result |
| --- | --- | --- |
| 1. Backend foundation | Implemented | FastAPI, settings, health checks, rotating logs |
| 2. Kite authentication | Verified with real browser login | Login, encrypted session, verified status |
| 3a. Instrument catalog | Implemented; real download verified | Daily NSE/NFO catalog and NIFTY lookup |
| 3b. Price data and Renko | Next | Recorded data, brick builder, parity checks |
| 4. Indicator engine | Planned | Pine port verified against TradingView exports |
| 5. Paper execution | Planned | Option mapping, risk limits, wallet, simulated fills |
| 6. React dashboard | Planned | Live, History, Wallet, Settings |

The current application reports PAPER mode; it does not simulate fills yet.
Kite login and instrument metadata are implemented. Live prices, strategy
calculations, and live orders are not implemented.
The original project specification is saved in [docs/SPEC.md](docs/SPEC.md).

## Step 1: run the backend

Use PowerShell. Python 3.12 and uv must be installed.

```powershell
cd D:\WorkSpace\AUREVON\backend
uv sync --locked
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000 --no-access-log
```

Copy `.env.example` only on the first setup; do not overwrite an existing `.env`.
Keep the terminal running. Press Ctrl+C to stop the server.

Open these addresses:

- http://127.0.0.1:8000/docs — interactive API documentation.
- http://127.0.0.1:8000/api/health — application status.
- http://127.0.0.1:8000/api/auth/kite/status — session status, verified with Kite when logged in.

Expected health response:

```json
{"status":"ok","application":"AUREVON","mode":"PAPER","live_orders_enabled":false}
```

The server starts without any Kite keys. `configured: false` is expected initially.
If you see `No pyproject.toml found`, change to the `backend` directory first.
If port 8000 is occupied, stop your previous server before starting another.

If login ends with `ERR_CONNECTION_REFUSED`, check the address in the browser.
The Kite redirect must be `http://127.0.0.1:8000/api/auth/kite/callback`.
An address such as `http://127.0.0.1:8080/kite/callback` has both the wrong port
and the wrong path for this setup. Correct the Redirect URL in the Kite developer
console, save it, and start a fresh login from `/api/auth/kite/login`.

## Where your Kite credentials go

Open the
[Kite developer console](https://developers.kite.trade/), create your application,
and register this redirect URL:

```text
http://127.0.0.1:8000/api/auth/kite/callback
```

The callback is now implemented. The URL must match exactly, including
`127.0.0.1` rather than `localhost`.

Edit **backend/.env** locally:

```dotenv
APP_NAME=AUREVON
LOG_LEVEL=INFO
KITE_API_KEY=your_actual_api_key
KITE_API_SECRET=your_actual_api_secret
```

Restart the server after changing `.env`. Both values are needed for Kite login
in step 2. You do not need them for the health check or offline tests.
Keep your actual values on your computer; do not paste them into chat or README.
`.gitignore` excludes `.env` and logs. The checked-in `.env.example` stays blank.

Kite's official flow sends you to its login page, returns a short-lived
`request_token` to the registered callback, then exchanges that token on the
backend using the API secret. The resulting access token expires at 6 AM the
next day unless invalidated earlier. AUREVON uses the next 06:00 IST boundary
as a conservative local expiry, including when login occurs before 06:00.
See the [official login documentation](https://kite.trade/docs/connect/v3/user/).

## Step 2: connect your Kite account

1. Ensure your real key and secret are saved in `backend/.env`.
2. Register the callback URL above in the Kite developer console.
3. Restart the backend using the step 1 command. Run a single worker on Windows.
4. Open http://127.0.0.1:8000/api/auth/kite/login in your browser.
5. Sign in on Zerodha's page using your normal credentials and second factor.
6. Kite returns to AUREVON, which exchanges the temporary token, saves the session,
   and redirects to `/api/auth/kite/status` without tokens in the final URL.

After a successful login, status looks like this (account and expiry vary):

```json
{
  "configured": true,
  "authenticated": true,
  "user_id": "YOUR_ACCOUNT_ID",
  "expires_at": "2026-10-24T00:30:00Z",
  "message": "Kite session verified. Application remains in PAPER mode."
}
```

`configured: true` alone only means both settings are present. `authenticated: true`
means the saved session passed a `/user/profile` check with Kite. The status route
makes a broker request when a session exists; refresh manually rather than polling
rapidly. A connection failure returns HTTP 502 without deleting your saved session.

The access token is encrypted with Windows DPAPI in
`backend/data/kite-session.bin`. The same Windows account can restore it after a
server restart until expiry. This Windows-specific store will need a different
implementation for cloud deployment. Session files are excluded from Git.

Login attempts expire after ten minutes and are tied to a browser cookie. Start
again from `/login` if the server restarts during login, you cancel, or a temporary
token expires. Do not paste callback URLs or tokens into chat.

If Kite rejects a login, check that key and secret belong to the same app and that
the app permits your Kite user. Errors deliberately omit broker response bodies,
which can contain private data. Restart after editing `.env`.

This step has been tested with fake broker responses. On 2026-10-23 the user also
completed a real browser login: the status endpoint reported `configured: true`
and `authenticated: true` after verifying the session with Kite.

## Logs: what to look for

Application logs appear in the terminal and `backend/logs/aurevon.log` as JSON
lines. Times are UTC; request durations are milliseconds. Files rotate at 5 MB,
with five backup files retained.

| Event | Meaning |
| --- | --- |
| `application_started` | Settings loaded; shows PAPER mode and credential presence |
| `request_completed` | Request finished; includes status, duration, request ID |
| `request_failed` | Unexpected request failure; includes request ID |
| `application_stopped` | Server shut down |
| `kite_login_started` | Browser login initiated |
| `kite_login_succeeded` | Token exchanged and encrypted session saved |
| `kite_session_invalidated` | Broker rejected a saved token; login required |
| `kite_session_unavailable` | Saved session expired, changed app, or could not be read |
| `kite_connection_failed` | Broker connection/response failure |
| `kite_request_rejected` | Broker rejected the request; HTTP status only |
| `kite_session_save_failed` | Local encrypted session could not be saved |
| `instruments_refresh_started` | Downloading NSE and NFO instrument CSVs |
| `instruments_refresh_completed` | Both snapshots saved; includes row counts |
| `instruments_cache_used` | Today's saved catalog reused without downloading |
| `instrument_download_failed` | Download connection failed; includes exchange |
| `instruments_save_failed` | Database transaction failed; old snapshot retained |

Each response includes `X-Request-ID` to match it with its log entry. Request
query strings and credential values are not included in application log events.
The run command disables Uvicorn access logs to avoid logging callback tokens.

To watch the log in a second PowerShell window:

```powershell
Get-Content D:\WorkSpace\AUREVON\backend\logs\aurevon.log -Tail 20 -Wait
```

## Code map

| File | Responsibility |
| --- | --- |
| `backend/app/main.py` | App startup/shutdown, request logging, API endpoints |
| `backend/app/config.py` | Typed settings; reads backend/.env |
| `backend/app/logging_setup.py` | JSON logging and file rotation |
| `backend/app/broker/kite_auth.py` | Login exchange, session encryption, expiry, profile checks |
| `backend/app/api/kite_routes.py` | Login redirect, callback, status endpoints |
| `backend/app/broker/instruments.py` | CSV validation, atomic snapshot, NIFTY selection |
| `backend/app/api/instrument_routes.py` | Catalog refresh, status, and NIFTY endpoints |
| `backend/app/db/models.py` | Instrument and snapshot database tables |
| `backend/alembic/versions/0001_instruments.py` | First database migration |
| `backend/tests/test_foundation.py` | Health, config loading, secret handling checks |
| `backend/tests/test_kite_auth.py` | Fake broker login, failures, expiry, encrypted session restoration |
| `backend/tests/test_instruments.py` | Catalog selection, bad downloads, caching, migration checks |
| `backend/pyproject.toml` | Dependencies and quality tool settings |
| `backend/uv.lock` | Resolved dependency versions |

## Check your changes

Run from `backend`:

```powershell
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy
```

Tests use fake credentials and never contact Zerodha.

Verified on 2026-10-23: 25 tests passed; Ruff lint/format, mypy, and
`uv sync --locked` passed. A real Uvicorn process returned HTTP 200 for the health
endpoint. Starlette currently emits a deprecation warning about its httpx test
adapter; this does not prevent the tests or application from running.

## What you need to do next

1. Run the server and open `/api/health` and `/docs`.
2. Repeat the browser login when the session expires or Kite invalidates it.
3. Open `/api/market/instruments/status` and `/api/market/nifty` to inspect the catalog.
4. Keep your original Pine script ready for `docs/pine/renko_indicator.pine`.
5. Export TradingView reference data before we implement Renko parity checks.

## Step 3a: daily instrument catalog

The database migration and first real download have already been run on this
workspace. The download saved 10,377 NSE records and 43,344 NFO records on
2026-10-23. NIFTY spot, the nearest unexpired future, and option contracts were
resolved from those records. Counts and contract details will change over time.

Restart the server if needed using the step 1 command. Open:

- http://127.0.0.1:8000/api/market/instruments/status — today's cache status/counts.
- http://127.0.0.1:8000/api/market/nifty — spot, nearest future, available option
  expiry dates, and all options for the nearest expiry (including today).
- `/api/market/nifty?expiry=YYYY-MM-DD` — options for a listed expiry date.

Before each trading day, log in and refresh the catalog from a second PowerShell
window while the server is running:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/market/instruments/refresh
```

Alternatively, use the POST endpoint's **Try it out** button in `/docs`.
Opening that POST URL directly in a browser address bar sends a GET and will
return HTTP 405. Refresh reuses today's catalog to avoid repeated large downloads.
No scheduled refresh is implemented yet.

Metadata is saved in `backend/data/aurevon.db` (SQLite). Use
`uv run alembic upgrade head` from `backend` on each new checkout or when a new
migration is added. This command is safe to repeat. A missing schema returns HTTP
503 with that instruction. `DATABASE_URL` can override the default database path.

NIFTY spot is resolved by `NSE:NIFTY 50`; NFO contracts must have the exact
underlying name `NIFTY`, so BANKNIFTY is excluded. Expired contracts are excluded
using the date in Asia/Kolkata. Lot sizes, strikes, expiry dates, tick sizes, and
instrument tokens come from the dump. An index record legitimately has lot size
zero; it is not an orderable contract. Expiry-day trading policy will be added
with the strategy layer; this endpoint only lists contracts.

The catalog stores exchange + trading symbol as its key because derivative
tokens may be reused. Both exchange downloads are validated before replacement;
a malformed download or failed transaction preserves the previous catalog.
NIFTY lookup rejects a stale catalog with HTTP 409 until you refresh it.

The instrument list is metadata, not a live option chain. Its last-price column
is intentionally not used. Kite recommends downloading and storing this daily
list: [official instrument documentation](https://kite.trade/docs/connect/v3/market-quotes/).

## Development log

- 2026-10-23: Initialized the uv project and installed the specified dependencies;
  verified `uv sync --locked`.
- 2026-10-23: Added step 1 backend foundation, configuration template, health and
  Kite configuration status, JSON logs, tests, and setup instructions.
- 2026-10-23: Added Kite browser login, single-use browser state checks, token
  exchange, Windows DPAPI persistence, expiry handling, and verified session status.
  Tested with fake broker responses; real browser login subsequently confirmed
  by the user's successful session-status screenshot.
- 2026-10-23: Added the first Alembic migration, SQLite instrument catalog,
  daily refresh and NIFTY lookup endpoints. Verified a real authenticated
  NSE/NFO download and contract selection; added catalog and migration tests.
