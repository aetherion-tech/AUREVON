# UI-LIVE-B4 — integrated engineering verification

Completed 2026-10-31 (D06), for the independent isolated engineering scope.
Product counts remain 237 Completed / 43 Pending. B1/B2/B4 Completed;
B3 construction/reference/genuine-feed acceptance remains Pending.
Next independent engineering task: QA-19-14 measured-path profiling/optimization.

## Change and integrated coverage

Future-dated per-spread marks now show the same stale/unavailable warning as
the aggregate P&L summary. Review found the aggregate already rejected future
timestamps while the per-spread Freshness label could say Mark received.
No accounting, execution, API schema or feed configuration changed in B4.

New `frontend/tests/live-integrated.spec.ts` exercises two simultaneous spread
projections in one authenticated page: short/hedge prices and P&L, signed total
-1.25, refreshed total +1.25 with changed option marks, stale/future timestamps,
missing short mark/per-leg MTM, unavailable total, HTTP500 and visible errors in
both positions/summary, followed by empty-position recovery and neutral zero.
The final focused test verifies Mark received/no stale warning first, then a
future timestamp, so a previous stale state cannot conceal a future-date bug.
These responses are routed fixtures; real projection maths and settlement are
checked separately by backend tests using isolated databases/wallets.

Existing integrated checks cover equal-time bricks/overlays, source identity,
history paging, tick/node preservation, incremental bricks, sequence gaps and
changed source revisions; quote-only/no-history states and genuine server errors;
chart/summary layout at 1600px and stacking at 1024/768/390px; guarded close
confirmation, duplicate request suppression, pending state and final reason;
feed control/login/entry-lock separation. No synthetic data reaches operator state.

## Results and commands

From `D:\WorkSpace\AUREVON\backend`:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_domain_api.py tests/test_chart_history.py tests/test_live_projection.py tests/test_wallet.py -q
.\.venv\Scripts\python.exe -m app.tools.local_ui_readiness
.\.venv\Scripts\python.exe -m app.tools.reference_debug --check
```

- **129 backend tests PASS**, 334.87s; one existing Starlette/httpx deprecation
  warning. Includes real persisted trade/wallet/ledger, liquidation leg MTM,
  missing depth/transition projections, chart history and Live projection paths.
- Readiness **BLOCKED**, runtime NOT_CHECKED, paper_trading_ready=false.
  BE-08-14, QA-09-19/20 and QA-11-15/16 remain unaccepted.
- Original/debug source integrity **PASS**; Pine compilation not verified.
- An initial command named nonexistent test_live_api.py; no tests ran. Corrected
  to test_live_projection.py before running the accepted 129-case selection.

From `D:\WorkSpace\AUREVON\frontend`:

```powershell
npm.cmd run test
npm.cmd run build
npm.cmd run lint
npx.cmd playwright test --config playwright.release.config.ts tests/live.spec.ts tests/live-integrated.spec.ts tests/unavailable-source.spec.ts tests/feed.spec.ts --reporter=json
npx.cmd playwright test --config playwright.release.config.ts tests/live-integrated.spec.ts --reporter=json
```

- **37 frontend tests PASS**. Final build/TypeScript/ESLint **PASS**.
- **16 built HTTPS browser checks PASS**, zero skipped/flaky/unexpected:
  [full browser receipt](UI-LIVE-B4-browser-checks.json).
- **1 final focused browser check PASS** after strengthening fresh-to-future
  verification: [focused receipt](UI-LIVE-B4-focused-browser-checks.json).
  This repeats one scenario, not a seventeenth distinct test.
- Isolated server port5174 with temporary synthetic replay DB. Final screenshots
  from the reused responsive check retained as [desktop](UI-LIVE-B4-desktop.png)
  and [mobile](UI-LIVE-B4-mobile.png). The reused B2 test also refreshed its B2
  screenshot paths; original B2 browser JSON receipts remain unchanged.
- `git diff --check` PASS.

## Remaining gates and operating handoff

No claim of genuine market-feed acceptance, five-minute/wick parity, actual
shadow observation or formal burn-in follows from these tests. B3 needs coherent
construction/history/restoration/indicator support and actual reference/feed
evidence; see UI-LIVE-B3-engineering-status.md. B4's independent UI verification
does not waive B3 or paper admission gates. Formal sessions remain zero.

B4 is frontend-only: refresh existing Vite at https://localhost:5173/dashboard/,
Live. No B4 backend restart. Existing operator DB/.env/Pine/feed/services and
5173/8000 owners were not changed. README/D06 daily log/NEXT_SESSION updated
together. Usage/cash/headroom/renewal Unknown; extra paid usage INR0; no purchase.
