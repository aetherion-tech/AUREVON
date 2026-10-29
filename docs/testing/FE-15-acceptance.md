# FE-15 Live screen acceptance

2026-10-29, D04. Scope: FE-15-01 through FE-15-15. These are UI/code
acceptance checks with synthetic replay evidence; they do not activate a managed
paper trial, verify TradingView parity or qualify a formal paper session.

| IDs | Delivered behavior and evidence |
| --- | --- |
| 01 | Responsive Live workspace; initial typed snapshot, entry capability, feed quality, missing domains, recovery and disconnected/stale banners. |
| 02–03 | SVG Renko bodies without wicks; ascending brick-index axis retains equal timestamps; last 100/300 windows, older paging, follow-latest and incremental keyed updates. Existing history is scanned by its cursor when a stopped owner has no latest-brick snapshot. |
| 04–05 | Published Supertrend segments stop across flips/missing values; flip markers and bias tint; ENTRY/T1/EXIT markers retain direction/trade/family tooltip text and replacement identity. Keyboard-accessible event labels and a detailed data table accompany SVG tooltips. |
| 06–07 | Active indicator entry/T1/T2/safety, ceiling/floor and next up/down lines; flat positions remove active levels. Per-browser layer toggles persist separately from server strategy settings. Source/configuration/revision and INDICATOR_REPLAY/reference-unverified labels remain visible. |
| 08 | Direction/strength/score/probability with expandable factor explanations; missing factors and warm-up remain unavailable. |
| 09–10 | Open spread cards show both legs, quantities, entry/mark prices, server MTM/margin return, planned premium stop/target, duration and stale marks. Close confirmation guards duplicate clicks, retains an ambiguous command's key per trade, displays pending closure and polls actual detail until CLOSED with final reason/results. A button click or pending reply never proves a fill. |
| 11–12 | Latest closed trade's reason, gross/cost/net and margin/capital returns; daily closed-trade counts/wins/net/capital return. Daily-loss usage comes from the owner's dated risk basis, valid open marks and costs; missing marks or a different session date stay unavailable. Cash flows are not treated as profit. |
| 13–14 | Newest-first source-scoped signals with grades, risk and accepted/rejected explanations; persistent loaded-alert summary plus paged durable feed and server acknowledgement. Indicator acceptance is explicitly distinct from execution admission/fills. |
| 15 | Unit/component and real Chromium fixtures verify ordering, nulls, paging, layers, financial action states, mobile overflow, alert acknowledgement, tick isolation, incremental bricks, gaps and source conflict recovery. |

## Verification

From `frontend`:

```powershell
npm.cmd run build
npm.cmd run lint
npm.cmd test
npm.cmd run test:browser
```

- Strict TypeScript/production Vite build and ESLint pass.
- 15 frontend unit/component tests (8 foundation + 7 Live) pass.
- 13 Chromium flows (6 foundation + 7 Live) cover real HTTPS/same-origin auth
  and API calls, with deterministic route/socket fixtures for additional states.
- A real isolated SQLite database contains 655 synthetic Renko bricks, three
  bricks per exchange timestamp, processed by the actual indicator repository and
  explicitly published using the existing chart-history producer. No independently
  verified reference source is substituted for this replay fixture.
- Live browser cases cover published history/markers/order/paging/layer retention,
  mobile empty history and readiness, durable alert acknowledgement, last/daily
  server results, duplicate/pending/final manual close, DOM-node preservation on
  ticks and appended bricks, gap-triggered REST/history recovery, and revision
  conflict fencing/reload. Desktop/mobile screenshots are ignored artifacts.
- The full backend suite passes: **771 tests**, including 3 new domain cases.
  New domain tests compare projected stops/targets and risk utilisation with the
  actual stored plan/book, preserve unknown marks, verify final close reasons and
  exact settled returns, and check integer history filters/export over HTTP.
- Ruff lint/format, strict mypy and generated OpenAPI/TypeScript drift/compile
  checks pass. The existing Starlette/httpx test deprecation warning is retained.

The browser test service now uses **5174** and isolated backend **18765** rather
than reusing operator ports **5173/8000**. The operator backend was not restarted. Normal
startup remains PAPER/unarmed and does not attach an executor, initialize funds,
enable entries or change a schema. Browser fixture passwords, funds, positions,
results, synthetic faults and clocks are test-only. No broker credentials are
loaded by that harness; it uses temporary SQLite/TLS state.

## Read-only API integration fixes

Position projections now expose persisted plan stop/target, target enablement,
margin return and final closed timestamp. Wallet projections expose the actual
owner's risk date, loss limit, used loss and utilisation. These optional additions
are backward compatible; no migration is added. The UI leaves absent fields
unavailable when talking to an older running backend.

HTTP history query strings are parsed at the route boundary before constructing
the unchanged strict internal HistoryQuery. This fixes valid `limit=1`/grade
queries and exports being rejected by strict integer validation. Invalid/fractional
limits and reversed date ranges still reject. Financial lifecycle/accounting gates
and mutations are unchanged.

Snapshot subscriptions select stable domains, and chart merging uses indexed
identity rather than exchange timestamps. Tick-only events do not refetch chart
history or replace existing SVG nodes. Source/revision/configuration conflicts
reset the chart generation; cross-source pages are never merged. Stale data and
missing publication never silently become valid overlays. Signal changes also
recheck the overlay source. Missing history stops automatic retry rather than
creating an unbounded request loop.

The running operator backend was not restarted. Load these API additions at its
next safe owner stop/restart; do not migrate or interrupt an observation baseline.
Pending prior migrations and managed/reference gates remain separate work.

Next: FE-16-01 History/P&L layout. OPS-19-08 actual shadow evidence stays Pending;
D33 is partial despite completion of its five FE-15 IDs. Qualifying sessions: 0.
