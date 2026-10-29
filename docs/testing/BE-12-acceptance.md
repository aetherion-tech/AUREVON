# BE-12 wallet, cost, P&L and history acceptance

2026-10-29 (D04), early D17/D19/D20/D21. BE-12-01 through BE-12-12 are accepted
as backend code, integrated with the isolated BE-11 PAPER executor. Managed
paper execution, public wallet APIs and a local paper-trading UI remain inactive.

## Evidence

44 new `tests/test_wallet.py` cases passed, plus the existing 54 BE-11 drills.
Full suite: 696 passed, including all 44 wallet cases. One existing Starlette/httpx dependency warning. Ruff lint/format,
strict mypy, OpenAPI drift and generated TypeScript drift/compile pass.

| Task | Delivered behavior |
| --- | --- |
| BE-12-01 | Additive `0010_wallet`: user/PAPER-scoped accounts, ordered idempotent ledger, closed trade summaries, daily P&L, period capital bases and reconciliation runs; unique scope/key and history/time/filter indexes. Exact decimal text avoids SQLite floating-point conversion. |
| BE-12-02 | Explicit one-time configured initialization; exact-paise positive deposits; finite/precision checks through INR 999,999,999,999.99; retries and concurrent initialization cannot grant money twice. |
| BE-12-03 | Withdraw up to free balance; idempotent RESET records the change to a selected baseline. Reset is blocked with any open/pending position/reservation and preserves all trades, ledger, kill/loss locks and daily counters. No history-delete implementation. |
| BE-12-04 | Admission/reservation, order/position updates and wallet projections share one SQLite writer transaction. Insufficient or changed capital rejects; exit margin is retained until flat. Projection failure rolls everything back. |
| BE-12-05 | Opt-in auto-top-up deposits the exact shortfall only after all entry gates pass, in the same transaction as reservation. Defaults off; duplicate signals do not fund twice. It cannot bypass loss/max-trade/readiness restrictions. |
| BE-12-06 | Once-only gross and separate costs settlement, linked by trade keys; book-to-fill-to-ledger identities and relational projection consistency checked on every access. BE-11 restart/rollback drills remain passing. |
| BE-12-07 | Versioned effective-dated configurable brokerage, exchange, SEBI, IPFT, sell-side STT, buy-side stamp and GST estimates; per-fill itemized amounts and schedule identity persisted. Legacy flat/bps estimates remain supported; mixing models rejects. |
| BE-12-08 | Persist daily/weekly/monthly/all-time opening capital; net/margin and net/entry-capital trade returns. Deposits, withdrawals and reset adjustments are external flows, never trading P&L. Nonpositive/unavailable capital bases yield null percentages. |
| BE-12-09 | Daily and derived weekly/monthly/all-time summaries include trades, wins, gross, costs, net, cash flows and by-family net. Closed trade net matches the ledger and daily projections. |
| BE-12-10 | Scope-enforced date/family/direction/grade/result history filters, stable `(closed_at, trade_id)` keyset order, bounded pages and revision/filter-bound cursors; detail and CSV share the same scope/filters. CSV escapes formula-leading symbols. |
| BE-12-11 | Durable reconciliation results and alerts on aggregate/ledger/margin/trade/daily/period projection mismatch. Checks fail closed and never repair corrupt rows silently. Opt-in 15:35 IST nightly polling uses the existing leased MarketService owner loop. |
| BE-12-12 | Precision/overflow, initialization, withdrawals, reset/history/lock restrictions, duplicate closes, auto-top-up, scoped history, cost arithmetic, rollback, migrated legacy book bootstrap, period boundaries, projection corruption and nightly owner-hook tests. |

## Storage and operation

The validated JSON execution book remains the transactional source. Wallet/indexed
report projections are synchronized in that same transaction, with a matching
revision. Reads compare persisted projections to recomputed book evidence.
Mismatch blocks financial actions and creates a durable dashboard alert, rather
than silently rebuilding damaged financial evidence. An older valid BE-11 book
without projections can bootstrap them once after migration, without reseeding
funds or duplicating fills. Reconciliation run records are audit evidence only.

`WalletService(..., user_id="local", settings=WalletSettings(...))` retains the
existing `PAPER` identity for the local user; other bounded internal identities
use distinct PAPER books. This supplies storage isolation, not a multi-user login
or LIVE wallet. Construction does not initialize funds; call `initialize(at)`
explicitly with the configured paper capital. Reconfiguration requires a future
audited settings path; restart rejects unexpected changed assumptions.

`capital(at)` always returns actual free capital. With auto-top-up enabled,
`planning_capital(at)` is an explicit simulated funding ceiling for BE-10 planning,
not a displayed wallet/account balance. Actual session capital still controls
risk gates. Admission funds only the exact margin shortfall after those gates.
Neither value reads broker funds or the INR 20,000 project cash budget.

RESET is stored as a delta whose resulting balance is the chosen baseline.
Earlier trade history stays in history and all-time P&L. It does not reset daily
risk counters or clear a loss lock. Initialization establishes the first daily
capital baseline. Periods that predate wallet creation have no positive opening
base and report null return percentages. Periods after creation use balance
immediately before their first date, including earlier cash flows. This is a
documented opening-capital return, not time-weighted performance.

History cursors are invalid after any book revision or filter change; reload page
one rather than combining different wallet snapshots. Export is bounded at 10,000
trades; narrow date filters beyond that. Public REST DTOs and frontend history,
wallet and P&L integration remain BE-13/FE work.

Nightly polling defaults off (`WALLET_RECONCILIATION_ENABLED=false`) and does not
create a new scheduler. After migrations and integration, the enabled existing
MarketService owner invokes it at/after 15:35 IST. That owner must be running and
desired; a stopped process cannot perform unattended checks. Successful checks
are deduplicated by scope/day/revision; changed books recheck, failures remain
visible and retry. Manual isolated checks can call `WalletReconciler.poll(at,
force=True)`. No notification outside the active local application is implied.

## Cost reference and limits

Reviewed the official [Zerodha charges](https://zerodha.com/charges/) reference
on 2026-10-29 for cost categories, side applicability and tax basis. No forever
current rates are hard-coded or automatically fetched into execution. Configure
explicit exact-decimal assumptions, source/identity and effective dates; an
out-of-date schedule rejects a fill and preserves the pending exposure/reserve
for review/retry. Actual broker contract-note rounding or account-specific
charges may differ from the per-fill paise-rounded PAPER_ESTIMATE. No options
exercise/physical settlement, real brokerage debit or live order is implemented.
GST applicability on IPFT is an explicit schedule option; costs are not represented
as measured broker/account charges. Tests use clearly synthetic rates.

Migration `0010_wallet`, including downgrade/retained BE-11 rows and indexes, is
verified on disposable databases only. The BE-11 migration test now pins its own
`0009_paper_execution` target; the BE-12 test exercises current head. Pending local
0007/0008/0009/0010 must use the existing owner/backup procedure at integration.
No application DB migration, `.env` edit, real recording/feed activation, actual
trade, purchase or receipt was produced in this batch. Original Pine and README.v1
remain unchanged. Exact usage, spend/headroom, renewal/reset facts remain Unknown;
extra paid usage INR 0; zero qualifying formal paper sessions evidenced.

Next: remaining BE-13 domain APIs and runtime integration, then the working local
UI slice. See [local paper UI readiness and usage](../operations/local-paper-ui.md)
and run `python -m app.tools.local_ui_readiness` on subsequent implementation
sessions. BE-08-14, QA-09-19/20 and QA-11-15/16 reference/G2/G3 evidence remains
Pending; backend code completion does not waive it.
