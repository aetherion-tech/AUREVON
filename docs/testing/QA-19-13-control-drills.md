# QA-19-13 integrated paper control drills

2026-10-30, D05. This batch supplies new integrated engineering drill evidence
for daily-loss lock, kill, manual close, square-off retry and clock warnings.
It uses a temporary SQLite wallet, real domain/API/execution/reconciliation
services, synthetic prices and an in-memory ticker. No broker connection, operator
database, market observation, service change or original Pine edit occurs.

## New integrated scenarios

`backend/tests/test_control_drills.py` runs five scenarios:

| Scenario | Trigger and verified result |
| --- | --- |
| Manual close | Authenticate, admit/fill a synthetic two-leg paper position, POST close twice with the same idempotency key; one outcome. Withhold quotes for three owner polls: CLOSING, original margin retained, only two entry fills. Restore quotes while entry readiness is false: both exits complete, CLOSED/manual, four fills total. |
| Kill | Same real API/persistence path via POST /api/kill. Pending exits wait for quotes and complete even with entry readiness false; kill lock persists after wallet reload. |
| Daily-loss lock | Adverse exact option quotes breach the actual configured daily limit. The wallet locks, moves exposure to CLOSING/daily_loss, retains margin without quotes, then closes and preserves the loss lock after reload. No direct book/lock mutation is used to trigger it. |
| Square-off retry | Advance the isolated owner clock to 15:30 and withhold quotes. The position remains CLOSING/square_off with reserved margin and no false fill. Fresh quotes complete both legs and release margin despite failed new-entry readiness. |
| Clock warning | Inject complete spot/futures ticks with a three-second exchange-time lag into the actual TickerWorker; confirm clock/feed-delay true while stale false. LiveService produces the durable clock_or_feed_delay dashboard alert. Its clock quality feeds the isolated runtime readiness callback; HTTP confirmation is rejected without opening exposure. Fresh ticks restore clock quality/entry capability; retrying the original rejected command remains rejected. |

Each financial scenario additionally verifies unique ledger keys, exact
initial-balance plus gross minus costs, four fills, zero reserved margin, empty
open-position API, agreement between trade/P&L/wallet APIs, a forced actual
WalletReconciler PASS, restored-book equality and no extra fills/ledger rows on
further polling. The isolated owner controls readiness and prices; HTTP callers
do not inject them. The clock callback is a test owner, not a claim that managed
production indicator execution has passed its reference gates.

## Retained checks

- Five new integrated cases pass. The initial focused run had four passes and
  one invalid-fixture failure: the injected futures tick omitted volume/OI,
  making feed stale rather than isolating the clock warning. Complete synthetic
  futures fields corrected the fixture; no application behavior was weakened.
- `QA-19-13-control-drills.json` retains per-case outcomes for the new scenarios
  plus domain/API and paper-execution regressions: **114 passed, exit 0**. It is a selected group run,
  not a new full backend suite. `app.tools.ops_drills --group` now supports this
  bounded, repeatable invocation and still refuses overwriting old evidence.
- Four selected built HTTPS browser checks pass; receipt:
  `QA-19-13-browser-checks.json`. Foundation kill/auth/deposit uses the temporary
  actual backend wallet. Risk/alert/manual-close UI cases use mocked responses;
  these verify presentation/interaction while the integrated backend scenarios
  above establish actual temporary-book execution and accounting.
- Ruff lint/format and strict mypy for the changed runner pass. The existing
  Starlette/httpx deprecation warning remains recorded.

Repeat the selected group with a NEW evidence filename:

```powershell
cd D:\WorkSpace\AUREVON\backend
.\.venv\Scripts\python.exe -m app.tools.ops_drills --group QA-19-13 --output ../docs/testing/QA-19-13-next-drill.json
```

Browser regression command (isolated harness on 5174, temporary TLS/DB):

```powershell
cd D:\WorkSpace\AUREVON\frontend
npm.cmd run test:browser -- --config playwright.release.config.ts --grep "manual close|pending kill|alerts remain|today risk values"
```

## Acceptance boundary and next batch

QA-19-13 accepts the engineering control drill requirement, following the same
synthetic-versus-formal distinction as QA-19-12. **G5 remains unaccepted and zero
qualifying formal sessions are evidenced.** These tests do not certify an actual
market feed, ten-day parity, production strategy readiness, measured broker costs,
Windows SCM lifecycle or burn-in. Entry readiness stays blocked by BE-08-14,
QA-09-19/20 and QA-11-15/16.

Next locally executable batch: **QA-19-11** integrated disconnect/queue overflow/
token-expiry recovery admission drills. Retain real gap/recovery/entry-denial
observations from isolated providers; do not substitute UI mocks for recovery
proof. REF-00-03/05/06/07 still await actual chart settings and reference inputs.
After REF, the separate market-data G1 batch QA-07-01 through 07 still needs
actual historical/feed evidence before G2/G3. QA-19-17 remains the final paper
acceptance task after all gates, drills and 20 qualifying sessions.

Use development https://localhost:5173/dashboard/ with its backend on 8000.
No production-code restart is required by this tests/runner batch. Reuse the
existing owner and frontend. Extra paid usage INR 0; cash/headroom, usage and
renewal/reset remain Unknown. No purchase or background notifications.

Accepted product counts: **236 Completed / 44 Pending of 280**; section 19
**10 Completed / 8 Pending**. No documentation-only task increments.
