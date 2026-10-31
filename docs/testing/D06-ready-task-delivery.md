# D06 ready-task audit and delivery

2026-10-31. Accepted **REF-00-03** and **QA-07-01**. Project now
**239 Completed / 41 Pending of 280**. REF section: 5/3; QA-07: 1/6.
The remaining 41 rows consist of 21 paper-scope tasks with acceptance prerequisites
and 20 Phase20/21 tasks outside the funded paper scope. Formal sessions remain zero.

## REF-00-03 — Completed

The exact master-row fields are now evidenced in retained screenshots:
NSE:NIFTY / Nifty50, five-minute Traditional50, Close source, Wick enabled,
Asia/Kolkata and historical completed close22700 at 2026-10-27T13:25:00+05:30.
See [chart reference](../pine/chart_reference.md) and
[actual package](../pine/reference_package.actual.json).

This accepts chart-setting intake, not G1/G2, matching seed history, remaining
saved indicator overrides or genuine feed-driven B3 updates. No runtime anchor
or operator configuration was changed. Earlier input-blocker notes are historical.

## QA-07-01 — Completed

Actual broker authentication succeeded. Probe and download used a temporary
copy of the encrypted session, so expiry/invalidation could not remove the
operator's original. The catalog was read through SQLite mode=ro. Actual selected
identities: spot256265 / NSE NIFTY50 and future15736578 / NFO NIFTY26NOVFUT,
expiry2026-11-23. No API key, access token or account identity is in receipts.

For the completed 2026-10-30 processing session:

| Actual source | Result |
| --- | --- |
| Spot minute | 375 bars, 09:15 through15:29 IST, completed by15:30 |
| Futures five-minute | 75 bars, 09:15 through15:25 IST, completed by15:30 |
| Futures OI | Present and positive on all75 bars |
| Independent overlapping requests | First two bars match both full downloads |
| Ordering/coverage/shape | Exact expected grid, aware timestamps, valid OHLC/volume/OI |

Receipt: [QA-07-01-acceptance.json](QA-07-01-acceptance.json).
Local normalized source CSVs and hashes are retained under ignored
`backend/data/qa-07-01-20261031-boundary-verified/`; only sanitized metadata is
in docs. Spot index volume is zero; no futures-volume proxy was substituted.

The first attempt passed375 spot bars but requested futures only through15:25
and received74 bars, ending15:20. Retained failure:
[QA-07-01-first-attempt.json](QA-07-01-first-attempt.json).
Diagnostic original provider responses are retained locally; sanitized coverage
receipts identify the missing15:25 bar. The acceptance runner now explicitly
requests through the next/closing boundary, then compares completed bars in
[session open, session close). Both sources return exactly the full expected
grid with no outside-session boundary bars in the successful actual run.
No missing candle was synthesized, ignored within the comparison window or
shifted. This adjustment is isolated to the acceptance runner; the existing
production downloader was not changed.

Reproduce from backend with a NEW output directory:

```powershell
.\.venv\Scripts\python.exe -m app.tools.historical_acceptance --date 2026-10-30 --spot-token 256265 --future-token 15736578 --future-symbol NIFTY26NOVFUT --future-expiry 2026-11-23 --output data/qa-07-01-new-check
```

A later broker session/catalog must still authorize these historical identities.
Existing output folders are refused. This is historical download evidence, not
QA-07-02 live observation, QA-07-07 live volume comparison or G1 acceptance.

## QA-19-14 — measured optimization delivered; acceptance Pending

An unprofiled500-tick/48-brick baseline measured59.62ms brick-emitting p95,
still over50ms. Separate cProfile diagnosis showed SQLite commits as the largest
cost (8.869s cumulative of14.132s profiled run). Profiled timings are not used
as the unprofiled before/after baseline.

Local file engines now select SQLite WAL and explicitly retain synchronous=FULL
on every new connection. Memory databases retain their shared StaticPool behavior.
Transactions, per-tick commits, compare-and-swap, rollback and decimal logic are
unchanged. Unsupported WAL selection fails closed. No synchronous NORMAL/OFF,
commit batching or dropped validation was introduced. SQLite documents per-commit
WAL synchronization under FULL: https://www.sqlite.org/wal.html and
https://www.sqlite.org/pragma.html#pragma_synchronous . This supported mode is
for the existing local-file deployment, not network-share database deployment.

| Same unprofiled synthetic workload | Brick p95 | Maximum |
| --- | ---: | ---: |
| Before | 59.62ms | 64.99ms |
| After | 28.76ms | 31.34ms |
| Confirmation | 23.97ms | 48.34ms |

Retained `QA-19-14-{before,after,confirm}-20261031.json`, plus separate before
profile raw.prof/text and profiled baseline. Confirmation records journal=wal,
synchronous=2 (FULL). These are synthetic same-machine results, not a guarantee
for representative warmed option workload. Network/queue/option fanout and
managed signal-to-order dispatch remain unmeasured. **QA-19-14 stays Pending.**

## Validation and operating constraints

- **857 backend tests PASS**, one existing Starlette/httpx deprecation warning,
  342.45s. Run after the database engine change; new acceptance tests added during
  this run were separately tested afterward.
- **149 selected persistence/strategy/wallet/backup tests PASS**, then
  **76 crash/restart/domain/history/Live-projection tests PASS**. These selections
  overlap the full suite; do not add counts as distinct cases.
- Final database/acceptance runner checks: **10 PASS**. Cover durable journal
  mode on reconnection, concurrent read snapshot/write commit, rollback, memory
  engine behavior, incomplete/conflicting history, missing optional OI and
  provider-exclusive end boundaries.
- Targeted Ruff/format and strict mypy PASS for changed modules. Actual history
  runner PASS; benchmark confirmation PASS as synthetic measurement only.
- No frontend changes. Final built HTTPS WAL-backed browser smoke: **3 PASS**,
  zero skipped/flaky/unexpected: chart history, positions/P&L and guarded close.
  Receipt D06-WAL-browser-checks.json. Prior B4 evidence remains separate.
- Read-only SCM preflight: account .\Sanny, manual startup(3), stopped(1),
  create-service access denied(error5). Lifecycle/TLS/DPAPI unaccepted. No service
  was repaired, started or reconfigured.

Existing backend/feed owners and original Pine/.env/session preserved. The WAL
code takes effect on future file-engine connections after a safe backend restart;
the agent did not reopen operator DB through the new engine. Stop feed, verify
flat/no pending exposure and finish observation before stopping the existing
backend with Ctrl+C. Await shutdown and use the standard handoff command; never
start a duplicate owner. Use the online backup procedure for committed WAL data.

Usage/cash/headroom/renewal remain Unknown; extra paid usage INR0. No purchases,
formal paper sessions, reference-parity acceptance or trading activation.
