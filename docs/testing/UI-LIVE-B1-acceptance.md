# UI-LIVE-B1 — positions and P&L

Completed 2026-10-31 (D06), incremental UI batch; product counts remain
237 Completed / 43 Pending. Next UI-LIVE-B2. No formal session evidenced.

The existing active-spread card now includes side, strike, expiry, lots,
quantity, entry, current last-traded price and supported per-leg P&L. Backend
projection reads metadata from the position's saved contract, never symbol
parsing or current instrument assumptions. Optional new fields allow an older
backend to display Unavailable until safely restarted.

Per-leg P&L uses short ask / hedge bid liquidation prices, entry fills and
quantities with Decimal rounding to paise. It is available only for OPEN
positions with entry fill, depth and valid server MTM. Missing depth requires
executor slippage settings not present in this projection; transitions can
contain exit fills, so these per-leg values remain unavailable. The table
explains that current last price and liquidation valuation differ. Server
spread MTM remains authoritative, including its configured no-depth fallback
and transition accounting. Leg rounding can differ from aggregate rounding
by a paise; no accounting or execution policy was changed.

The prominent aggregate sums server spread MTM using BigInt paise. Missing
MTM makes the aggregate unavailable; an empty successful position list shows
zero with an empty-state message. Failed position retrieval shows unavailable.
Profit is green, loss red and zero neutral. Totals are explicitly before costs,
separate from realised/day/account balances. Marks older than 15 seconds,
missing timestamps or future timestamps flag the total as stale/unavailable;
existing per-spread freshness remains. Cached observations are not fresh quotes.
Close confirmation, in-flight protection, idempotent retry and final settlement
review remain on the existing path.

## Verification

- `.\.venv\Scripts\python.exe -m pytest tests/test_domain_api.py tests/test_api_contracts.py -q`
  from backend: **75 passed**, one existing Starlette/httpx deprecation warning.
  Initial new test found last-price leg MTM -37.50 versus liquidation spread
  MTM -75.00 (74 passed / 1 failed). Corrected projection and assertion to
  liquidation basis; final selected suite above passed.
- `.\.venv\Scripts\python.exe -m pytest tests/test_domain_api.py -k live_b1 -q`
  from backend: **1 passed / 54 deselected**, after adding missing-depth and
  transition assertions. Also verifies metadata, quantities, both leg signs,
  aggregate reconciliation and missing marks using an isolated real paper wallet.
- Frontend `npm.cmd run test`: **37 passed**. Includes exact mixed-sign/large
  aggregate arithmetic, null/invalid marks, empty total and profit/loss styling.
- Frontend `npm.cmd run build`, `npm.cmd run lint`: **PASS** (includes TypeScript).
- Frontend `npx.cmd playwright test --config playwright.release.config.ts tests/live.spec.ts --grep "B1 |manual close duplicate" --reporter=json`:
  **3 passed**, zero skipped/flaky/unexpected. Retained receipt:
  [UI-LIVE-B1-browser-checks.json](UI-LIVE-B1-browser-checks.json).
  Built HTTPS app with isolated backend on 5174; fixtures test metadata, lots,
  mixed-sign P&L, stale/missing marks, empty positions, fresh negative total,
  390px viewport without page overflow, and duplicate guarded close through
  pending/final settlement. Routed fixtures do not prove real feed acceptance.
- Targeted Ruff lint/format and mypy for changed API modules: **PASS**.
- `python -m app.tools.export_api --check` and tools/api-contracts
  `npm.cmd run check`: **PASS**; generated OpenAPI/TypeScript updated together.

No operator DB/config, Pine, service/feed, running 8000/5173 owners or real
trades were changed. Backend projection requires a safe restart of the existing
backend after any observation ends, feed stop and flat-state checks. Do not
start duplicate owners. Refresh the existing Vite page after restart.

Usage, spend/headroom and renewal remain Unknown. Extra paid usage INR 0;
no purchase. B3 reference/feed configuration and paper-entry gates remain
unaccepted. This batch does not activate trading or supply missing reference data.

Read-only `python -m app.tools.local_ui_readiness` from backend returns BLOCKED,
paper_trading_ready=false and runtime NOT_CHECKED; outstanding reference gates:
BE-08-14, QA-09-19/20 and QA-11-15/16. No runtime acceptance inferred.
