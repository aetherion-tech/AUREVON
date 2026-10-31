# UI-LIVE-B3 managed five-minute binding

D06,2026-10-31. BIND1 engineering delivered. Overall B3 remains Pending for
controlled operator activation and actual source/reference/feed acceptance.
Counts241 Completed/39 Pending,formal0. No new master acceptance.

## Connected path

Settings has an explicit RENKO_SOURCE_MINUTES=1|5 field,default1. Exact integer
and environment string forms are validated; booleans,floats and unsupported
intervals fail. Existing RENKO_MODE=minute_close retains its meaning of Close
input; source_minutes selects aggregation. No .env or operator setting was edited.

One managed_store factory now serves cold history,recovery,validated handoff and
MarketService ownership. Five-minute source uses the sourced full annual
calendar,so a daily rolling lookback window cannot change checkpoint identity.
Calendar edits/year rollover fail closed and require explicit rebuild/profile
review. Minute/futures source coverage,OI/VWAP and gap checks are retained.

Cold import and recovery consume complete minute candles through the same
constructor and retain pending five-minute bucket/extrema in checkpoint state.
Validation independently rebuilds that state and all stored bricks from retained
sources and compares the full profile,including pending state and gap summary.
The five-minute owner uses a distinct :5m-close-wicks-v2 stream suffix. Legacy
checkpoints are neither overwritten nor silently reinterpreted.

The producer emits through the existing live snapshot/brick journal/history API;
no extra worker or scheduler was added. Live displays a 5-minute Close/wicks label
from actual source configuration. A construction-gap warning keeps the chart
visible while clearly blocking trading readiness.

## Partial handoff and restart corrections

A known first unfinished live minute can be partial. A construction gap is now
separate from a socket/source incident: it remains in checkpoint evidence,
readiness diagnostics and entry-source-quality checks,revokes the entry hold,
and never enables entries. It does not force an endless socket reconnect for
that known partial chart prefix. Actual socket/missing-range incidents retain
their existing stop/replay behavior. Later complete periods may update diagnostic
chart data while the construction gap remains flagged until validated recovery.

The new restart test originally failed with Active partial state requires
recovery before handoff. That gate was preserved. The five-minute owner now waits
explicitly until retained active spot/futures fragments close,then performs
independent historical recovery and validation. Waiting does not consume the
retry failure budget. Future/malformed active state still fails. No partial
candle is admitted as complete,erased or promoted to formal evidence.

Annual calendar objects are frozen and now shared during transactional cloning;
mutable construction state is still independently copied. This avoids copying
hundreds of immutable sessions on every tick/minute. Final focused tests include
copy independence and rollback/retry checks. No performance acceptance claimed.

## Evidence

- 163 final focused backend cases PASS (162 before immutable-calendar clone check).
  Managed fake-broker/socket lifecycle follows real SQLite import,recovery and
  handoff: historical chart,ten minutes of live test ticks,incremental UI sample
  and history page,flagged partial prefix with same worker,completed-bucket wait,
  recovery,restart and incompatible profile rejection. Entries remain false.
- 38 frontend tests PASS;build/types/ESLint PASS;selected Ruff/format/strict mypy,
  OpenAPI drift and original/append-only Pine integrity PASS.
- Six built HTTPS checks PASS: source label/gap warning,wick rendering and
  mobile/desktop bounds,layout,paging/equal-time history,incremental updates and
  source-revision recovery. Label/gap browser case injects presentation fixtures;
  it is not genuine-feed evidence. Screenshot UI-LIVE-B3-managed-profile-gap.png
  retained and inspected. Synthetic paper balances in screenshots are test-only.
- Retained real spot source375 minutes ->75 periods/4 bricks/0 extending wicks
  through the shared managed factory. Same annual configuration across rolling
  windows;restored state identical. Original hash unchanged,no broker request.
  UI-LIVE-B3-managed-five-sample.json. No real wick or full matching-seed parity
  evidence is inferred from that one-day cold-grid sample.
- Full backend suite947 PASS in404.80s,one existing Starlette/httpx warning.
  The calendar clone change/regression was added after collection;final163 focused
  cases cover the final state. Counts overlap. Receipt UI-LIVE-B3-managed-binding.json.

From backend:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_market_service.py tests/test_managed_construction.py tests/test_renko_reference_check.py tests/test_recovery.py tests/test_history_renko.py tests/test_readiness.py tests/test_five_minute_renko.py tests/test_market_persistence.py -q
.\.venv\Scripts\python.exe -m pytest -q
```

From frontend:

```powershell
npm.cmd test
npm.cmd run build
npm.cmd run lint
$env:PLAYWRIGHT_BUILT='1'
npm.cmd run test:browser -- tests/unavailable-source.spec.ts tests/live.spec.ts --grep 'five-minute profile|observed wick|chart|Renko'
```

## Controlled activation remaining

Existing8000/5173 owners remain19708/5240 at final read-only check;no restart,
operator DB/config changes,financial actions or Pine edits. The existing backend
still runs its previous settings/code. Refreshing the frontend alone cannot
activate a new backend source.

After an eligible,quiescent operator stop (no observation interruption and flat/
feed-stop checks),these process overrides select the recorded chart grid/profile
without editing .env. Keep the defaults PAPER/unarmed and entry gates intact:

```powershell
cd D:\WorkSpace\AUREVON\backend
$env:RENKO_SOURCE_MINUTES='5'
$env:RENKO_MODE='minute_close'
$env:RENKO_BOX='50'
$env:RENKO_ANCHOR='22700'
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log
```

Reuse the existing frontend;otherwise:

```powershell
cd D:\WorkSpace\AUREVON\frontend
npm.cmd run dev
```

Open https://localhost:5173/dashboard/ ->Live. Verify broker status locally,
start market data during an eligible session and wait for validated historical
warm-up/partial-bucket handling. Inspect 5-minute Close/wicks source identity,
Renko history and later completed-period updates,quality/recovery messages and
entries-blocked state. Market closed today is not fresh-feed evidence;the normal
owner still obeys its calendar/preparation windows. Empty/stale/unavailable
states must not be concealed. Unknown seed/full inputs/reference/source-context
and genuine-feed acceptance remain separate from this engineering completion.
No further CSV-prefix exports or debug/original input-equality questions needed.

Usage/cash/headroom/renewal Unknown;extra paidINR0;ceilingINR20000;no purchase.
