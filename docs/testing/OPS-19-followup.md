# OPS-19 follow-up: owner maintenance, retention, shadow and crash evidence

2026-10-30, D05. This continues the initial six-row release batch recorded in
[OPS-19-acceptance.md](OPS-19-acceptance.md). Three additional product rows are
accepted: **OPS-19-04, OPS-19-05, QA-19-12**. Section 19 now has **9 Completed /
9 Pending**; project totals are **234 Completed / 46 Pending of 280**.

## Delivered and verified

- **OPS-19-04:** A real MarketService owner step calls the explicitly attached
  synthetic runtime. After the cutoff, missing quotes leave a CLOSING position,
  retained margin and no report/backup. Fresh quotes complete both legs and
  square-off, release margin, reconcile the exact ledger and emit one nightly
  report. Restore into a separate database verifies counts/integrity. No extra
  scheduler was added. This is controlled engineering evidence, not a real session.
- **OPS-19-05:** Original raw ticks and verified sealed-run gzip copies are kept
  indefinitely as recovery/reference evidence. Daily logs retain 90 daily archives.
  Migration 0012 adds optional derivative P&L observations. Owner polling records
  exact decimal strings and explicit unknown marks; nightly maintenance backs up
  before pruning ONLY P&L samples strictly older than 90 days. Boundary,
  idempotence, financial book/ledger preservation and scheduled compression are
  tested. Recording compression and sampling default false; maintenance remains
  opt-in. No operator data was compressed, pruned or migrated.
- **QA-19-12:** A separate OS process commits a synthetic OPEN paper position and
  abruptly exits with code 71 (no graceful finally). A new process restores that
  exact DB, verifies both entry fills, retries the same decision without a second
  position, closes both legs, and checks four fills total, unique ledger keys,
  exact gross-minus-costs balance and zero margin. Existing execution cases cover
  partial legs, rollback, restart boundaries and duplicates. This does not accept G5.

## Implemented foundations with acceptance still pending

| ID | Actual result / remaining requirement |
| --- | --- |
| OPS-19-03 | SCM wrapper, graceful-stop/duplicate-lease tests and explicit ConfigureRecovery command are prepared. Current Windows identity is not elevated; OpenSCManager(SC_MANAGER_CREATE_SERVICE) returned error 5, Access denied. No service installed, started or reconfigured. Actual lifecycle, service identity/DPAPI/TLS and restart verification remain. |
| OPS-19-08 | Disabled authenticated inbox, bounded durable rate counter, idempotent receipts, source fencing, two-brick maximum one-to-one comparison and Live mismatch panel implemented. Original Pine family grouping is preserved. Needs actual reachable TLS-authenticated recipient ingress, calibrated Pine/debug event identity and G2 acceptance. No tunnel or public endpoint configured. |
| QA-19-10 | Actual recorded eligible day and G3 reconciliation evidence absent. Synthetic replay fixtures remain separate. |
| QA-19-11 / 13 | Existing socket/recovery/readiness, loss-lock/close/kill/square-off/clock tests are retained in the drill report. Integrated formal operational drill evidence remains unaccepted. |
| QA-19-14 | A bounded synthetic timing tool and two reports exist. The phase run measured 63.89 ms p95 / 75.23 ms max on 48 brick-emitting ticks out of 500 ticks, missing 50 ms. Market storage p95: 23.49 ms; indicator/readback p95: 41.69 ms. These separate percentiles cannot be summed. No queue/network/option fanout, twenty-day warmed history or brick-to-order dispatch measurement. No performance gate accepted. |
| QA-19-15 / 16 / 17 | Zero qualifying formal sessions; no actual daily shadow/weekly review or 20-session/G4/G5 acceptance. Dates and synthetic tests cannot satisfy them. |

The original raw-deletion enhancement was rejected by automatic approval review
as an unauthorized destructive side effect. That implementation was not added.
The delivered tick policy preserves originals indefinitely, so no raw-deletion
approval is needed for these changes.

## Validation and evidence boundaries

- Broad backend run: **797 passed / 1 failed of 798**. The failure was the older
  0011 migration test using `head` while asserting only 0011 tables. It now targets
  `0011_domain_api`; the separate operations migration test verifies 0012 upgrade,
  downgrade and retained data. The failed full-run record is preserved, not edited.
- Corrected affected integration suites: **69 passed**. Latest scheduled
  compression/retention checks: **8 passed**. Latest shadow/retention/owner checks
  also passed their 14-case focused invocation. This is combined evidence across
  runs, not a claim of a later green 798-case full invocation.
- Evidence: `OPS-19-followup-drills.json` (all 798 initial case outcomes),
  `OPS-19-followup-focused.json` (69 corrected outcomes),
  `OPS-19-synthetic-performance.json` and
  `OPS-19-synthetic-performance-phases.json`.
- Frontend: **35 tests pass**, production build/strict TypeScript and ESLint pass.
  New disabled/mismatch panel scenarios pass. Initial full release browser runs
  had 37 pass / 1 fail in the history cursor test. Its fixture now keeps a stale
  cursor invalid and waits for the initial socket/query resync before paging;
  the corrected case passed three consecutive repeats. A later run exposed the
  same initial-resync timing in Settings. Settings/Wallet helpers now also wait
  for Connected. Final built FastAPI HTTPS run: **38/38 passed**. No assertions
  were weakened, skipped or given longer timeouts.
- Ruff/format, strict mypy and generated OpenAPI/TypeScript checks are run for
  this batch. Source and operator runtime readiness remain distinct.
- Migration **0012_operations was tested ONLY on isolated databases**. Pending
  operator migrations now include 0007 through 0012. No owner restart, .env
  write, broker access, service activation, original Pine edit or real trade.
- Prior dependency audit remains: frontend clean after the Vitest update; backend
  12 advisory records unresolved. No finding was suppressed or force-overridden.

## Use and next handoff

See [paper release operations](../operations/paper-release.md) and
[shadow alert operations](../operations/shadow-alerts.md). Start the built UI only
after building FE and safely transitioning its owner outside an observation:

```powershell
cd D:\WorkSpace\AUREVON\frontend
npm.cmd run build
```

```powershell
cd D:\WorkSpace\AUREVON\backend
.\.venv\Scripts\python.exe -m app.tools.serve
```

URL: https://127.0.0.1:8443/dashboard/. Live shows **TradingView shadow comparison**;
it correctly reports disabled by default. No separate FE server is needed for
the built release. Existing 5173/8000 development commands remain supported;
do not start concurrent owners.

Next task remains **OPS-19-03**, requiring an elevated Windows session with the
intended service identity. Other pending work is explicitly listed above. Usage,
cash, headroom, allowance and renewal/reset are Unknown; extra paid usage INR 0;
ceiling INR 20,000; formal sessions 0. No background alerts configured.
