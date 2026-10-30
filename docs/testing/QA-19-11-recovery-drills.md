# QA-19-11 isolated recovery and admission drills

2026-10-30, D05. **QA-19-11 engineering drill requirement accepted.** Four new
integrated scenarios and the selected regression group pass: **47 tests, exit 0**.
Two selected built HTTPS browser recovery checks also pass. No production
behavior or operator state changed. These results are not G1/G3/G5 acceptance.

## Executed scenarios

`backend/tests/test_recovery_drills.py` joins the existing managed-market and
domain/API fixtures through an explicit test-owner readiness callback. Both use
temporary, independently isolated SQLite databases and fake clocks/providers.
The managed fixture uses historical downloads, recording/recovery persistence,
actual worker queues and gap validation. The API fixture uses its own persisted
synthetic indicator candidate and wallet, real authenticated HTTP confirmation
and final execution risk gates. The callback projects actual worker/auth/clock/
entry-source quality into the test runtime. This is cross-service engineering
evidence, not a claim of a matching recorded indicator/strategy pipeline or G3.

| Scenario | Actual observed result |
| --- | --- |
| Disconnect | SDK close callback clears connected state and opens a replay-required gap. Socket reconnection restores transport but leaves the gap and admission block intact. Owner recovery stops/joins the old consumer and creates exactly one replacement worker. |
| Queue overflow | A deliberately bounded two-item queue receives three updates, dropping exactly one and retaining overflow provenance. Admission is denied; recovery replaces the worker, validates completed historical coverage and retains recovery metadata. |
| Token expiry | Local-session provider reports expiry. MarketService stops the worker and reports login_required. A replacement login generation alone does not create a ready worker or admit entries; owner recovery must run. |
| Failed recovery | After disconnect, the historical provider fails. MarketService leaves no worker and reports a fixed recovery-failed reason without exposing injected private error text; final paper admission stays blocked. |

For successful recoveries the persisted checkpoint records retired gaps and
`unfinished_live_bucket_partial=true`. The new worker's entry delay is initially
unelapsed. Calling full final source eligibility while live-volume provenance is
partial revokes its hold, and advancing the test monotonic clock by 60 seconds
cannot release it. The test never clears partial flags to manufacture readiness.
There is no claim that these scenarios permit new entries after recovery: the
remaining source/reference requirements must also pass.

At fault, transport-only restoration, entry delay and remaining partial-source
stages, the actual runtime gate is unready. A stable prepared candidate and
confirmation idempotency key are retained; initial confirmation is durably
rejected and all retries preserve that outcome. No positions, reservations,
fills, balance changes or ledger changes occur. Changing a rejected financial
request's key is not used to bypass its terminal outcome.

## Validation evidence

- `QA-19-11-recovery-drills.json`: 47 selected worker/readiness/managed-market and
  new admission scenarios PASS, including four new integrated cases. This is
  not a later full backend run.
- `QA-19-11-browser-checks.json`: two built HTTPS checks PASS on the temporary
  5174 fixture. Session expiry injects a 401 response; WebSocket resync injects a
  socket closure. They establish client behavior, not external broker expiry or
  real-market reconnect evidence. Actual recovery paths are tested separately
  by the backend scenarios above.
- Ruff lint/format and strict mypy for the changed runner pass. The existing
  Starlette/httpx deprecation warning remains.
- Initial focused tests exposed incorrect test assumptions: regenerating keys
  for the same rejected signal and looking up a gap `cause` instead of `reason`.
  The test now keeps the original financial command identity, observes the
  actual source gate's revocation semantics and uses the real gap field. No
  production rule or data-quality gate was changed.

Repeat with a NEW filename:

```powershell
cd D:\WorkSpace\AUREVON\backend
.\.venv\Scripts\python.exe -m app.tools.ops_drills --group QA-19-11 --output ../docs/testing/QA-19-11-next-recovery.json
```

Browser checks:

```powershell
cd D:\WorkSpace\AUREVON\frontend
npm.cmd run test:browser -- --config playwright.release.config.ts --grep "session expiry|socket reconnect"
```

## Remaining QA-19 acceptance

QA-19-09/11/12/13 are Completed as engineering requirements. Five rows remain:

| ID | Actual missing requirement |
| --- | --- |
| QA-19-10 | A qualifying recorded day through backend/browser, chart/trade/wallet/history reconciliation and G3 prerequisites. Existing synthetic charts are not recorded-day proof. |
| QA-19-14 | Representative warmed workload and end-to-end dispatch measurements meeting the targets. Existing synthetic brick-emitting p95 63.89 ms missed 50 ms; dispatch latency remains unmeasured. |
| QA-19-15 | At least 20 qualifying automated paper trading sessions with actual daily notes. Evidenced count remains zero. |
| QA-19-16 | Actual daily TradingView shadow comparisons and weekly reviews with controlled settings changes; real ingress/reference evidence is absent. |
| QA-19-17 | Explicit G4/G5 acceptance from all prerequisites, clean reconciliation, resolved anomalies and retained drills. This remains last. |

Next engineering batch: QA-19-14 bounded profiling/optimization of the measured
storage/indicator path. Representative-load/dispatch acceptance must remain
Pending until actually measured; arbitrary synthetic load cannot certify it.
In parallel, REF-00-03/05/06/07 require actual TradingView settings and exports,
then QA-07 G1 and QA-09 G2, followed by QA-11 G3. OPS-19-03 remains a separate
unresolved Windows-service track; development dashboard 5173 remains supported.

Project **237 Completed / 43 Pending of 280**; section 19 **11 Completed /
7 Pending**. Formal sessions zero; G4/G5 unaccepted. Original Pine, immutable
README v1, operator DB/feed/credentials and service configuration were untouched.
Usage, spend, headroom and renewal/reset Unknown; extra paid usage INR 0, ceiling
INR 20,000. No purchase, background monitoring or unattended notification claim.
