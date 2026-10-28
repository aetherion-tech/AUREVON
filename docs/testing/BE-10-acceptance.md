# BE-10 acceptance — 2026-10-28 (D03)

BE-10-01 through BE-10-10 are implemented. The new 74 focused cases use synthetic
catalogs, quotes, capital inputs and fake sockets. They do not establish actual
liquidity, real broker margin, fills, TradingView parity or paper-session evidence.

| ID | Implementation and evidence |
| --- | --- |
| 01 | `app/strategy/models.py`: immutable version-1 signal, settings, exact catalog identity, depth quote, capital snapshot, two-leg TradePlan and accepted/rejected decision. `SignalInput.from_indicator` maps actual version-1 BE-09 ENTRY output. Plan validation enforces side/type/expiry, equal whole-lot quantities, tick prices, credit/loss/margin arithmetic, caps and exit references. Plan IDs hash the signal/settings/quotes/capital/catalog/time inputs. Direction/version integers and settings booleans reject ambiguous coercions. |
| 02 | `planner.py` chooses the nearest available unexpired catalog expiry, without a fixed weekday assumption. `skip` rejects the expiry day; `trade_current` uses it; default `trade_next` keeps the current contract before 12:00 IST and switches at/after 12:00, rejecting absent next expiry. Exchange calendar, current catalog, signal age and entry-window gates apply. |
| 03 | Strike step is derived from decimal catalog strike differences, including missing grid points. ATM rounds half up to the derived grid; short is offset further OTM for bullish PE or bearish CE, hedge is further OTM by configured width. Missing contracts are never synthesized. Optional premium mode chooses the valid further-OTM hedge with ask closest to the configured premium. Both directions and changing grids/lots are tested. |
| 04 | `OptionQuoteBook` is bounded to 200 identities, keeps candidate and pinned traded contracts separate, retains full five-level bid/ask depth, OI and exchange/receipt times. Managed TickerWorker dynamically subscribes/unsubscribes in FULL mode on the SDK reactor thread, serializes updates, resubscribes on reconnect and preserves its original two core tokens/recovery path. Disconnect/gap/stop clears cached option quotes. Failed subscriptions block quote use and can retry the same desired set. Accepted option ticks are fsynced to a separate run `options/<IST-date>.jsonl` stream with contract identity and sequence; existing core recordings and their sequence remain unchanged. |
| 05 | Unavailable, stale/future/delayed, identity-mismatched, low-OI, crossed/empty/unsorted depth, wide-spread and insufficient-entry-depth quotes fail. Pair timestamp skew is bounded. Spread cap is `max(absolute cap, midpoint × percent / 100)`, making the SPEC's “2% or INR 1” interpretation explicit. Up to two retries move short/hedge one derived step further OTM. Every attempt retains rejection reason/symbols. Accepted/rejected preview decisions are persisted. |
| 06 | SELL reference floors best bid to its catalog tick; BUY reference ceils best ask. Net credit must meet its minimum and be strictly below strike width. Credit and gross defined loss use exact Decimal × whole-lot quantity. Spread stop-debit and optional profit-capture debit references are distinct from retained index targets. No float arithmetic or premium-to-index target substitution. |
| 07 | Fixed-lot and risk-percent sizing consume an explicit current free-capital snapshot; there is no invented wallet balance. Risk lots floor risk budget / max loss per lot, then cap against buffered margin affordability, max lots and max quantity. Fixed lots cap against configured quantity/lot limits but reject insufficient capital rather than silently shrinking for funds. Best short-bid and hedge-ask quantities must cover the resulting entry quantity. Stale/missing capital and zero-lot sizing fail. |
| 08 | Paper margin is each lot's gross maximum loss plus configured buffer, rounded **up** to INR 0.01 per lot, then multiplied by lots. Output is explicitly `PAPER_ESTIMATE`, with null broker-reported margin; payoff basis is `GROSS_BEFORE_FEES`. USER_PREVIEW capital is distinguished from the future PAPER_WALLET contract. No live-margin claim or broker request. |
| 09 | Authenticated/CSRF-protected `POST /api/settings/preview-strikes` calls the same planner as the future paper path, reads today's persisted NFO catalog and the owned worker's option quote book, saves decisions, and returns `executable=false`. Optional subscription only changes an already-running worker's candidates, preserves traded pins, and never starts a socket/feed or submits an order. OpenAPI/TypeScript contracts expose preview and exact decimal wire strings; smoke checks reject execution flags and floating wire credit. |
| 10 | Tests cover both spread directions, catalog lot/step changes, half-grid rounding, expiry-day/cutoff/missing-next policies, absent short/hedge, quote age/OI/depth/identity/spread/skew, retry limits, invalid/insufficient credit, risk/fixed sizing, funds/margin/caps, premium hedge mode, model tampering, subscription lifecycle/failure, isolated recording, auth/CSRF, durable rejection and absent-migration failure. Migration 0008 is tested up/down/up with preservation of pre-existing rows. |

Validation: **598 full tests passed**, including **74 new BE-10 cases**. Ruff
lint/format checks and strict mypy passed (75 application source files). OpenAPI
drift, generated TypeScript drift and strict TypeScript compilation passed, including
nonexecution and exact wire-amount smoke checks. One existing Starlette/httpx
dependency deprecation warning remains. The earlier migration-0007 test now pins
its own revision; the new migration-0008 test independently verifies head upgrade,
rollback, repeat upgrade and preservation of existing rows.

## Use and boundaries

Core library: `build_plan(signal, catalog, quotes, capital, now, calendar, settings)`.
Use `discover=True` to list the same possible contracts without needing quotes or
capital; it still applies time/catalog/signal filters. Durable library preview:
`app.strategy.service.preview(...)`. Both return the same nonexecuting decision
contract; preview additionally assigns/stores a decision ID. Neither reserves
capital or mutates a wallet. Every eventual execution must recheck live readiness,
wallet revision/free margin, daily/open-position limits and quote age under BE-11/12.

Example request (after dashboard login; normal Origin/CSRF rules apply):

```text
POST /api/settings/preview-strikes
{
  "signal": { ...version-1 SignalInput from an actual indicator ENTRY... },
  "free_capital": "100000.00",
  "subscribe_quotes": false
}
```

`free_capital` here is explicitly a **USER_PREVIEW assumption**, never a reading of
the user's wallet, account or project budget. Omit it to retain `capital_unavailable`.
An absent/offline/unready worker yields missing quotes and cannot produce a plan.
With `subscribe_quotes=true`, the first request may return `quote_unavailable`;
fresh ticks must arrive before a later request can pass. The API uses server time,
not a client-selected clock, and does not import untrusted quote prices from requests.
Calendar/cached-catalog failures are retained as rejections. Missing migration or
failed decision persistence returns 503 rather than returning an unsaved success.

Default entry filters: CO/DIV/OT families, Moderate or better, 09:30–14:45 IST
(end exclusive), skip High risk and opposite bias. An indicator replacement without
a matching EXIT is rejected as requiring reconciliation. These defaults mirror
the SPEC; configurable minimum OI (initial 1), quote limits and spread thresholds
are development settings, not observed liquidity or calibrated acceptance evidence.

Hand-calculated synthetic fixture: 200-point width, 75-unit lot, short bid INR 100,
hedge ask INR 10.50 gives unit credit INR 89.50; total credit INR 6,712.50; gross
maximum loss INR 8,287.50; 10% buffered paper margin INR 9,116.25. These are test
values, not current NIFTY prices, lot size or actual account requirements. Exact
wire decimals retain source scale; consumers must parse decimal strings rather
than assuming a fixed number of trailing zeros. Fees/cost schedules belong to BE-12;
no charges or broker margin have been invented.

Source-format reference: [Kite FULL-mode depth and subscription documentation](https://kite.trade/docs/connect/v3/websocket/).
The implementation follows its token-based subscribe/unsubscribe and full-depth
fields. No real broker socket/account call was made for this acceptance.

The application database is unchanged. Additive `0008_strategy` (following the
also-pending local `0007_indicator`) is tested only on isolated databases. Apply
under the existing owner/backup procedure before operating this endpoint against
the user's database. The original Pine, .env, existing recording baseline and
README.v1 are untouched. Extra paid usage INR 0; actual billing/usage/renewal and
spend/headroom remain Unknown. Zero qualifying paper sessions remain evidenced.

Next independent task: **BE-11-01**; wallet/accounting BE-12 is needed before
integrated paper execution. BE-08-14 and QA-09-19/20 reference gates remain Pending.
