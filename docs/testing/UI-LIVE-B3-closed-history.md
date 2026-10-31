# UI-LIVE-B3 closed-session historical chart

2026-10-31,D06. CLOSED1 engineering fix delivered. Overall B3 operator/reference/
genuine-feed acceptance remains Pending;241 Completed/39 Pending,formal0.

## Root cause and fix

User reported executing BIND1 startup commands. Screenshots show Kite Verified,
requested data,session_closed and no Renko history. The sourced application
calendar has no2026-10-31 session. The owner returned before historical warm-up,
and the UI selected a stream with no bricks. A restart alone could not fix that.
The new closed-session path loads completed historical spot data independently
of sockets,futures subscriptions and paper execution readiness.

An explicit Start market data request with LOCAL_UI_ENABLED=true can authenticate
and fetch completed spot minute history,ending at the last sourced session close.
The selected lookback is made of complete supplied-calendar sessions. Spot catalog
identity is required; no token or missing bar is invented. A missing catalog may
be refreshed only after valid broker authentication. Futures/OI inputs are not
fabricated or required for a price-only historical chart.

A separate :closed:<profile-hash> stream has source_kind=CLOSED_SESSION_HISTORY,
scope=SPOT_ONLY_DISPLAY,future=null,completed-through time,source profile and
reference_verified=false. Only complete ordered source grids are constructed
through the accepted minute/five-minute constructor. Raw sources are retained.
A transaction publishes its immutable checkpoint,brick manifest and source candles.
It never overwrites a live observation,financial row or existing display stream.

Matching cache reads do not authenticate,download,recalculate Renko or publish.
They work across app restart without a new broker login/download,while existing
dashboard authentication remains required. Incompatible/corrupt cache is rejected
and retained,not silently overwritten. Missing source minutes,no resulting brick,
broker errors or absent initial login publish no display checkpoint.

The Live projection reads the final stored brick by index and its own profile,
so default100-brick window begins near the end of actual history. Historical/stale
labels show completed source coverage in IST,not a fabricated current quote.
Quality stays disconnected/stale;live ticks and unmatched signals are hidden;
entry permission is forced false even if a domain provider reports true. Missing
wallet/positions/execution domains remain explicitly unavailable. Display history
never supplies option marks or a trading owner. On validated live takeover,the
historical labels/source context disappear and the managed stream takes priority.

## Checks and limits

-954 full backend tests PASS in403.71s,one existing Starlette/httpx warning.
- Final21 service cases PASS in17.93s,including the new closed-to-live transition
  case and final unavailable-domain fallback check added after full-suite collection.
  Earlier137 selected integration/chart/history/readiness/construction cases passed.
-38 FE unit tests PASS;build/types/ESLint PASS;selected Ruff/format/strict mypy,
  OpenAPI drift and original/append-only Pine integrity PASS.
- Seven distinct built HTTPS browser cases PASS: new closed-cache chart/read-only
  API/reload/desktop/mobile case plus six live/wick/paging/layout/update/recovery
  regressions. Closed case repeated once to retain screenshots outside temporary
  test-results cleanup;it is not an additional distinct case. Windows socket-reset
  teardown message retained;all checks passed.
- Synthetic broker inputs in isolated DBs verify source loading without a socket,
  both1/5-minute profiles,cache reuse without broker calls,immutability of retained
  observation rows,login/broker/missing-minute failures,corrupt-cache rejection,
  hard entry block and historical-to-live transition. Screenshots contain only
  synthetic paper balances/prices;they are not operator trades or real feed proof.
- No real broker request,operator DB/config edit,owner restart or Pine change was
  made by this implementation session. Operator closed-history loading and fresh
  live-feed verification remain to be observed. This is a price-only chart;
  indicator overlays/direction remain unavailable until matching publication.

Retained screenshots UI-LIVE-B3-closed-history-1440.png and
UI-LIVE-B3-closed-history-390.png inspected. Machine receipt:
UI-LIVE-B3-closed-history.json.

Backend checks:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pytest tests/test_market_service.py -q
.\.venv\Scripts\python.exe -m mypy app/market/closed_history.py app/market/service.py app/api/live_service.py
.\.venv\Scripts\python.exe -m app.tools.export_api --check
.\.venv\Scripts\python.exe -m app.tools.reference_debug --check
```

Frontend checks:

```powershell
npm.cmd test
npm.cmd run build
npm.cmd run lint
$env:PLAYWRIGHT_BUILT='1'
$env:PLAYWRIGHT_CLOSED_HISTORY='1'
npm.cmd run test:browser -- tests/closed-history.spec.ts
$env:PLAYWRIGHT_CLOSED_HISTORY='0'
npm.cmd run test:browser -- tests/live.spec.ts tests/unavailable-source.spec.ts --grep 'observed wick|five-minute profile|chart|Renko'
```

## Apply to the operator instance

User-restarted owners are currently8000=16236 and5173=19968;both were preserved.
The existing backend process cannot acquire this new Python behavior without a
restart. When observation/flat/feed-stop checks allow,stop the existing backend
with Ctrl+C in its own terminal,then run the following process overrides. They
select the recorded50-point/five-minute Close/wick grid without editing .env:

```powershell
cd D:\WorkSpace\AUREVON\backend
$env:LOCAL_UI_ENABLED='true'
$env:RENKO_SOURCE_MINUTES='5'
$env:RENKO_MODE='minute_close'
$env:RENKO_BOX='50'
$env:RENKO_ANCHOR='22700'
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log
```

Keep the existing frontend running;otherwise:

```powershell
cd D:\WorkSpace\AUREVON\frontend
npm.cmd run dev
```

Open https://localhost:5173/dashboard/ ->Live and hard-refresh. Verify Kite login
locally,then click Start market data once to fetch the initial completed history.
It now works while the calendar is closed;waiting until Monday is not required
for this historical view. Allow historical requests to finish. Inspect Historical/
stale,completed-through date,5-minute Close/wicks,rendered bricks and Entries
blocked. Subsequent reloads use the matching cache without another download.
Fresh quotes/genuine-feed acceptance still require an eligible market session.
No new CSV-prefix/anchor screenshots or debug-versus-original equality question.

Usage/cash/headroom/renewal Unknown;extra paidINR0;ceilingINR20000;no purchase.
