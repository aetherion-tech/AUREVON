# BE-13 remaining domain/API acceptance

2026-10-29, D04. BE-13-07/08/09/10/11/12/13/14/20 Completed as backend API and
frontend-client contract code. BE-13 now 20/20 accepted. Next: **FE-14-01**.
This is not acceptance of a local trading dashboard, G2/G3 or a managed paper
trial. Normal startup still has no attached wallet/executor/runtime and no orders.

47 new `test_domain_api.py` cases. Full suite 768 passed, one existing
Starlette/httpx dependency warning. Ruff lint/format, strict mypy, OpenAPI drift,
generated TypeScript drift/compile pass. The 47-case domain suite also exercises
the final explicit ENTRY-link fields and CSV/replay-mode contract refinements.

| Task | Accepted implementation/evidence |
| --- | --- |
| BE-13-07 | Authenticated bounded signals with source/index/candidate ordinal, grades/risk, accepted/rejected reasons and source explanation text. Explicit `entry_event_ordinal`/`signal_id` link only candidates with an actual persisted ENTRY; candidate ordinal is never guessed as event ordinal. Indexed preview/admission/risk-reject decisions, paging and detail. |
| BE-13-08 | Actual open spreads, legs, mark quality, orders/fills/costs and trade detail. Durable prepare/confirm, manual close and kill controls with audit/idempotency. Confirm rebuilds from current server catalog/quotes/capital/settings/readiness and verifies persisted signal/chart-source lineage. It never accepts a client TradePlan, readiness, quote, clock, LIVE mode or arming switch. |
| BE-13-09 | Scoped PAPER history filters, deterministic keyset cursor/revision checks, detail and bounded CSV with identical filters. Accurate CSV OpenAPI media contract and formula escaping retained. |
| BE-13-10 | Real closed-trade P&L summary, bounded daily series, weekly/monthly period tables and by-family net, with exact INR and nullable opening-capital returns. Deposits/reset/withdrawals remain external flows. |
| BE-13-11 | Explicit wallet availability/read/initialize/deposit/withdraw/reset and ordered ledger paging. Exact-string INR, positive/precision/free-balance validation, reset confirmation and no-open-exposure restriction. Missing owner returns 409, never a fabricated zero wallet. |
| BE-13-12 | Validated version-1 Pine/strategy/risk/fill/wallet/data/display schemas, Pine input metadata, defaults/read/update/import/export, immutable version history, compare-and-swap and durable retry recovery. Data or Pine changes require rebuild acknowledgement; financial changes are blocked during active feed/exposure. Owner rebind verifies rebuilt source for stateful changes and preserves funds/history/risk locks. |
| BE-13-13 | Canonical `/api/strikes/preview` does not subscribe, store a strategy decision, reserve money or trade; only mandatory security audit writes occur. Missing catalog/quotes/expiry/liquidity/funds are explicit. The existing durable `/api/settings/preview-strikes` is retained for compatibility, with its explicit subscription option. |
| BE-13-14 | Risk rejects create indexed decisions and durable warning alerts in the paper-book transaction; existing recovery and BE-12 reconciliation producers retained. Read/ack and live journal projection use the public alert contract. |
| BE-13-20 | Regenerated REST/WS/OpenAPI types and actual `frontend/src/api/client.ts` integration: typed requests/results, exact INR, required mutation keys, in-memory CSRF, same-origin cookie fetch, session/logout/401 handling, cancellation, CSV, WSS cursor URL and ordered resync reducer. Real Node fetch against an isolated local FastAPI server verifies auth/wallet/prepare/confirm/close/kill and recovery; backend real WebSocket tests verify domain producers and ordering. React UI/scaffold remains FE-14 work. |

## Transaction and retry boundaries

Migration `0011_domain_api` adds indexed `domain_decisions`, append-only
`dashboard_settings_versions` (including unique command provenance) and durable
`domain_commands`. It backfills existing preview/admission/reject evidence without
creating trades, funds or fills. Upgrade/downgrade and retention are tested only
on disposable DBs. Earlier task migration tests pin their own stage boundaries.
Apply pending 0007/0008/0009/0010/0011 only with the existing owner/backup procedure.
The application DB was not migrated.

Each mutation begins with the existing authenticated/origin/CSRF audit intent.
New wallet/prepare/confirm/settings actions require an `Idempotency-Key` (ASCII
letters/numbers/colon/underscore/hyphen, at most 120 characters). Reuse the same
key and exact body after a lost response. A different action/body conflicts.
Terminal rejection is retained; retrying the same rejected intent cannot later
turn into an unexpected debit/order. Never generate a new key automatically
after an ambiguous financial result.

Command intent, domain commit and reply-cache completion are separate explicit
transactions. Recovery is supported by durable domain keys: wallet ledger keys,
deterministic prepared-decision identity, unique settings command provenance and
signal/decision admission identity. Tests interrupt after those domain commits
and recover without a second transfer, version, candidate or trade. Existing
close/kill hooks accept a supplied key and retain deterministic legacy retries.
Cached successful replies describe the original acknowledgement; reload state
to learn subsequent fills or closure.

## Runtime and settings boundary

`DomainService` binds to explicit `app.state.paper_execution` and optional
`app.state.paper_runtime`. No HTTP endpoint constructs/attaches these, deposits
startup capital, arms LIVE or enables entries. A low-level foreign wallet scope
is rejected; the dashboard remains single-user/local PAPER. Reads expose existing
persisted data only. Feed snapshots remain usable on the existing 0006 schema;
unmigrated domain APIs fail with storage unavailable. Schema discovery is cached
until owner restart, consistent with stopping before migrations.

An isolated owner may construct `WalletService` and `PaperRuntime` with current
settings plus server-owned catalog, full option quotes, execution prices and
readiness providers. Entry permission defaults false. The owner must validate
reference/session/data readiness and explicitly authorize its isolated trial;
HTTP cannot forge those providers. Confirmation checks the current configuration,
publication, source signal, contract grid, capital and final BE-11 gate. It commits
an admitted ENTERING state/reservation, not a claim that both orders filled.

The existing leased MarketService loop has one optional paper poll hook before
feed recovery. It drives attached runtime exits even on failed readiness. A
stopped process or non-desired owner cannot poll: isolated replay owners must
call `domain.poll(at)` on their own clock. Feed-stop HTTP refuses open/pending
paper exposure; close/kill acknowledges pending closure and still needs eligible
fresh prices and polling to finish. No extra scheduler is created.

Settings updates persist desired versions, never mutate a running book or `.env`.
Stateful Pine/data changes require a rebuilt market/indicator publication with
matching grid/settings. Owner-only `domain.rebind_wallet(stream)` requires a
stopped feed and flat book, verifies that publication, atomically updates book
assumptions and then sets the in-process managed configuration. An explicitly
selected rebuilt stream preserves the old stream/baseline. Construct/attach the
matching runtime after rebind; a newer saved version blocks new confirmations
until then. Reset/rebind never clears daily loss/kill locks or reseeds cash.
`requires_rebuild` records the version's stateful impact; GET settings reports
`activation=active` only for the matching attached runtime version. Live arming
and real-order sending remain unavailable regardless of this owner capability.

This batch does not automatically generate managed indicator/strategy decisions
from the live feed or claim that G1/G2/G3 have passed. Such activation remains
behind the existing reference, recorded-pipeline and operational gates. The
providers and client flows are tested with actual services and synthetic inputs,
not represented as real sessions or exported TradingView parity.

## Public API and client use

- Signals: `GET /api/signals?stream=...`; decisions: `GET /api/decisions`,
  `GET /api/decisions/{identity}`.
- Candidate: `POST /api/decisions/prepare` with persisted `stream`, `index` and
  `event_ordinal` from a signal's explicit `entry_event_ordinal`; then
  `POST /api/decisions/{identity}/confirm` with `{}`. Read-only previews cannot be
  confirmed directly and remain `executable=false`.
- Positions/trades: `/api/positions/open`, `/api/trades`, `/api/trades/export`,
  `/api/trades/{identity}`, `/api/trades/{trade_id}/close`, `/api/kill`.
- Wallet: `/api/wallet`, `/api/wallet/ledger`, POST `/initialize`, `/deposit`,
  `/withdraw`, `/reset` under `/api/wallet`. Reset requires
  `confirm="RESET PAPER WALLET"`; history deletion is not implemented.
- P&L: `/api/pnl/summary`, `/daily`, `/periods`, `/by-family`. Daily/family date
  windows are ordered, capped at 367 inclusive dates and exclude future dates.
- Settings: GET `/api/settings`, `/defaults`, `/schema`, `/export`; PUT base,
  POST `/import` or `/defaults` with expected revision and validated full bundle.

Snapshots/status events now include actual available wallet/P&L; positions and
the last closed trade appear only from an attached book. Signals retain explicit
INDICATOR_REPLAY identity and detail. Missing marks remain null. Typed signal,
trade, position and persisted risk/reconciliation alert events enter the existing
bounded reliable journal. Recent transition replay is bounded; on resync reload
snapshot plus paged signals/history/alerts. A replay calculation is not a broker
fill, a frontend screenshot or a qualifying paper session.

The frontend client module is framework-independent; there is no React package,
UI, frontend build or verified local browser trading workflow yet. It contains no
secret storage, money arithmetic or automatic retry that changes intent keys.
The integration harness's HTTP/cookie transport is test-only and carries synthetic
data; real browser operation still requires the documented local HTTPS/WSS proxy.

No real feed, account balance, actual trade, purchase or qualifying paper session
was produced. Original Pine, observation/recording baseline, receipt journal and
README.v1 remain untouched. Usage/allowance, cash/headroom and renewal/reset stay
Unknown; extra paid usage INR 0. See [local UI readiness](../operations/local-paper-ui.md).
