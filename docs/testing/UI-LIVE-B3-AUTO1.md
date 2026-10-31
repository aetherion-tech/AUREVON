# UI-LIVE-B3-AUTO1: chart available without starting the feed

The idle local-UI market loop now prepares completed Renko display history after a valid Kite session, without setting desired=true or starting a market socket. A matching saved managed chart is preferred; otherwise the existing completed spot-only history cache is reused/downloaded. Existing operator processes, .env, DB, wallet and Pine were not changed by development. Synthetic tests use isolated databases.

## Display and prior signals

The saved source must match the configured spot, box, anchor, mode, source interval and annual five-minute construction calendar. Brick order, prefix, timestamps and checkpoint tail are checked. Matching published indicator history is validated against its configuration/revision/settings and full source/result manifest. The Live snapshot and signal feed use that same stream; chart API returns existing overlays and markers. This read path never computes indicators or publishes/replaces reference evidence.

Saved history is explicitly historical/stale, disconnected, timestamped and entry-blocked. Stopped history can be visible even after broker login expires; dashboard authentication still applies. No matching publication means previous signals remain unavailable, not zero-valued or fabricated. A damaged source/publication is rejected. The active managed worker takes over when explicitly started; old historical labels disappear.

Idle preparation takes/releases the process lease, skips paper polling/reconciliation/maintenance and never creates a socket. Missing/expired login does not fetch history. Failed authentication/downloads are bounded/backed off; a new broker-session generation can retry. Cache reads perform no broker requests or indicator recomputation. No new endpoint, API schema or dependency was introduced.

## Verification

109 selected backend cases PASS across market lifecycle, saved display, Live projection, chart publication and domain API; 38 frontend cases PASS. Build/typecheck/ESLint, selected seven-file Ruff lint/format and four-module strict mypy PASS. Six new backend cases cover auto history on open/closed sessions, login/retry, source restoration and integrity fences.

Two distinct built HTTPS browser tests PASS: saved chart/prior signals/markers/desktop/mobile/reload without any Start request, and closed-history regression. The first saved reload attempt encountered Windows TLS connection resets/ERR_TOO_MANY_RETRIES; a single rerun passed. Closed-history test passed with a Windows connection teardown warning. Desktop/mobile closed regression screenshots use AUTO1-specific filenames; original CLOSED1 screenshots preserved. The saved-chart screenshot was visually inspected during the successful checks.

Readiness remains BLOCKED on BE-08-14, QA-09-19/20 and QA-11-15/16; operator runtime NOT_CHECKED. No genuine feed/reference acceptance, new master completion or formal paper session is claimed. Totals241/39, formal0. Usage/cash/headroom/renewal Unknown; extra paid INR0.

## Apply and inspect

When the operator feed is stopped/flat and it is safe to stop observation, use Ctrl+C in the existing backend terminal before restarting (do not create duplicate owners):

```powershell
cd D:\WorkSpace\AUREVON\backend
$env:LOCAL_UI_ENABLED='true'
$env:RENKO_SOURCE_MINUTES='5'
$env:RENKO_MODE='minute_close'
$env:RENKO_BOX='50'
$env:RENKO_ANCHOR='22700'
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log
```

Reuse the running frontend; if stopped:

```powershell
cd D:\WorkSpace\AUREVON\frontend
npm.cmd run dev
```

Open https://localhost:5173/dashboard/, complete Kite login and open Live. Do not click Start market data to load history. Allow the first historical download to finish. Check Historical/stale, as-of, five-minute Close/wicks and saved signals if matching publication exists; otherwise the signal feed explains missing data. Reload should preserve the matching cache. Entries remain blocked. Explicit Start is still required for real feed updates, which need an eligible market session. Historical backtesting remains deferred.

## Reproduce checks

Backend:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_saved_chart.py tests/test_market_service.py tests/test_live_projection.py tests/test_chart_history.py tests/test_domain_api.py -q
.\.venv\Scripts\python.exe -m mypy app/market/saved_chart.py app/market/service.py app/api/live_service.py app/api/domain_service.py
.\.venv\Scripts\python.exe -m app.tools.local_ui_readiness
```

Frontend: npm.cmd run test; npm.cmd run build; npm.cmd run lint; npm.cmd run typecheck. Built browser checks require PLAYWRIGHT_BUILT=1 and PLAYWRIGHT_SAVED_CHART=1 for saved-chart.spec.ts; run closed-history.spec.ts separately with PLAYWRIGHT_CLOSED_HISTORY=1 and the saved-chart flag unset. Tests start isolated5174 only; they never bind operator8000/5173.
