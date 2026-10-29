# BE-11 paper execution acceptance

2026-10-29 (D04). BE-11-01 through BE-11-14 are implemented and accepted as
isolated PAPER execution code. QA-11-15 and QA-11-16 remain Pending. No G3,
automated trial, real fill, or qualifying paper session is claimed.

## Evidence

`backend/tests/test_paper_execution.py`: 54 synthetic cases. Full suite: 652
passed, one existing Starlette/httpx dependency warning. Ruff lint/format,
strict mypy, OpenAPI export/drift and generated TypeScript drift/compile pass.

| IDs | Implementation and checked behavior |
| --- | --- |
| BE-11-01 | Shared `Broker` protocol, side/order/position enums, immutable contracts; additive `0009_paper_execution` upgrade/downgrade on isolated SQLite databases. |
| BE-11-02/03 | `PaperBroker`: deterministic `P-` identities; ask/bid market fills, explicit last-price/slippage fallback, side-conservative tick rounding, touch-based limit fills, cancellation and configurable latency. Pre-latency quotes cannot fill later orders. |
| BE-11-04/05 | Hedge BUY before short SELL; short BUY before hedge SELL on close. Persist positions, legs, orders, fills and lifecycle transitions. Partial entry failures unwind the hedge; reserves remain until flat. Restart tested at each of ten entry/exit boundaries. |
| BE-11-06 | Serialized durable decision/signal admission, order/fill identities, deposit keys and settlement keys. Concurrent duplicate admission reserves once; conflicting retries fail. Failed decisions cannot be bypassed by changing their decision ID. |
| BE-11-07 | Both leg marks, spread debit, unbooked gross MTM and separate costs; partial-entry/partial-exit exposure included. Missing, future, stale, skewed or wrong-token marks become Unknown, never zero-valued quotes. Closed gross/costs reconcile to fills and ledger. |
| BE-11-08 | Indicator trade-ID exit, manual close, premium stop/optional profit capture and configured time square-off. Exit rules continue with readiness false. Missing/invalid quotes retain pending exits and margin. |
| BE-11-09/10 | Persist rejects for daily loss lock, per-trade maximum loss, max trades, one position, entry/session window, changed/insufficient capital, stale plan/catalog, expired contracts, family/grade/risk/bias, quote price sanity and feed/auth/recovery/indicator/clock/event readiness. Recheck session/readiness/window/plan age during entry; unwind on loss of permission. |
| BE-11-11 | Idempotent service kill, `POST /api/kill`, manual-close hook and optional flag polling on each `step`. Cancel pending orders, request safe closure, persist entry lock. A persistent flag cannot repeatedly cancel its own exit orders. Auth/CSRF/default-disabled route tests pass. |
| BE-11-12/13 | Daily counters and loss lock survive restart. Only a covered, valid later session with no remaining exposure resets daily limits; kill persists. Persisted mode validates PAPER/unarmed, and no real-order adapter exists. |
| BE-11-14 | Fill, limit/latency, partial-leg, duplicate/concurrent entry, all exit sources, stale data, rollback, restart, loss locks, rollover, kill, corrupt-book and migration drills. |

## Storage and accounting boundary

The single-user PAPER book uses one versioned JSON aggregate in
`paper_execution_books`. Orders, fills, transitions, risk counters and exact
decimal ledger entries commit together under SQLite `BEGIN IMMEDIATE`. The
paper broker is pure; no external broker side effect occurs in a transaction.
Restart validates ledger identities, reservations, decision uniqueness, hedged
exposure and closed fill-to-trade-to-ledger amounts. Storage/validation failures
roll back the whole action. Each `step` commits before the next broker action.

`capital(at)` supplies a revision-bound PAPER_WALLET snapshot for BE-10 planning.
Admission checks the current book revision and free balance. USER_PREVIEW funds
never authorize execution. Buffered margin is held from admission until both
legs are flat; closure books gross and separate costs once, even after retries.
Deposits are explicit, positive exact-paise, idempotent test wallet inputs.

These primitives unblock BE-11; they do not complete BE-12's scoped/indexed
wallet/reporting schema, withdrawals/reset, auto-top-up, period returns, history
or nightly scheduler reconciliation. BE-12-04/06 have tested implementation
primitives here but remain Pending for the BE-12 acceptance batch. Costs are
versioned user assumptions (`fee_per_order`, `fee_bps`, `cost_basis`), not verified
current brokerage/tax schedules; detailed cost categories remain BE-12-07.

Whole orders fill or reject; quantity-partial fills and exchange queue modeling
are not simulated. Thin market depth rejects the whole leg; partial spread
failure safely unwinds. Limits use last-price touch and the limit price without
invented price improvement. Latency and all evaluation timestamps come from the
explicit aware replay clock. Slippage, fees and liquidity are synthetic inputs.

## Operation and activation boundary

Normal FastAPI startup does not construct or attach an executor, deposit funds,
start a paper scheduler, subscribe to options, or place any orders. `/api/mode`
continues to report PAPER/unarmed/entries disabled with
`paper_execution_not_activated`. Existing preview plans remain nonexecuting.
An explicit isolated owner can construct `PaperExecution(engine, calendar,
fills, risk)`, supply capital for planning, call `enter`, and drive `step` with
server-owned readiness and prices. Do not expose synthetic readiness/quotes as
user-controlled HTTP inputs.

The owner must continue calling `step` on clock/poll events even without ticks,
passing `kill_flag=Path(...)` to enable flag polling. This initiates square-off
and kill immediately on the next poll; fresh eligible quotes are still required
to finish exits. Unfinished or rejected exit attempts remain durable and retry
under distinct IDs. Removing the flag does not unlock entries.

Control routes require an explicitly attached `app.state.paper_execution`; they
return 409 on normal startup. Shared mutation middleware provides login, origin,
CSRF and durable audit. Successful kill/close acknowledges a durable request,
with `pending_closures`; it does not claim missing-price positions are flat.
Managed-feed activation, domain API completion and dashboard wiring remain later
integration work behind reference/accounting gates, not enabled by this batch.

Do not apply `0009_paper_execution` to the application database automatically.
Local `0007_indicator`/`0008_strategy` also remain pending; use the existing
owner/backup procedure at integration. Tests use disposable databases only.
The BE-10 migration test now pins its own `0008_strategy` target so adding a later
head does not change its acceptance scope; the new test exercises current head.

## Remaining acceptance

- QA-11-15: actual recorded spot/futures/options through indicator, strategy and
  execution twice, identical trades/fills, accepted G2 and BE-12 accounting.
  Ten synthetic restart comparisons are development evidence only.
- QA-11-16: 20 manually checked strike previews, matching end-to-end risk and
  paper accounting, QA-11-15, then explicit G3 review. No manual examples or
  qualifying exports were supplied; do not generate fictitious acceptance.

Next independent batch: remaining BE-12 wallet/accounting tasks. Preserve the
original Pine, real recording baseline and application DB. Exact token/allowance,
spend/headroom and renewal/reset facts remain Unknown; extra paid usage INR 0.
No receipts or actual trades were supplied; zero qualifying sessions evidenced.
