# Next session - budgeted delivery plan v2

Updated: 2026-10-29, D04. README is authoritative.

- Product tasks: 280 total; 168 Completed / 112 Pending. BE-13 now 20/20 code
  accepted. Latest: 768 full tests, including 47 new domain/client cases; Ruff
  lint/format, strict mypy, OpenAPI and TypeScript drift/compile passed. One
  existing Starlette/httpx warning. Final targeted tests cover ENTRY linkage,
  replay labels and CSV contracts. No actual paper session or real fill claimed.
- NEXT TASK: FE-14-01 React + TypeScript scaffold. Do not restart accepted BE-13
  work. frontend/src/api/client.ts exists and imports generated v1 REST/WS types;
  it is verified against a real isolated FastAPI server with Node fetch. There
  is no React package/scaffold/build or usable paper-trading dashboard yet.
  FE-14-05 has this client foundation but still needs Vite/React/proxy wiring.
- User priority is LOCAL UI PAPER TRADING, not a shell/API explorer. At every
  active implementation turn run from backend:
  .venv/Scripts/python.exe -m app.tools.local_ui_readiness
  Report changed blockers. Keep docs/operations/local-paper-ui.md updated with
  exact verified HTTPS URL/start/build/trading steps when that flow is ready.
  No background monitoring or unattended notification is configured. No honest
  activation date is known while real reference/managed/browser gates remain.

## Accepted backend and remaining real acceptance

- BE-05 complete 17/17; BE-06 complete 11/11. BE-08-01 through 13 complete;
  BE-08-14 Pending actual REF-00-07 TradingView debug export. BE-09-01 through
  18 complete; QA-09-19/20 Pending actual ten-session exports/G1/G2. Pure replay
  indicator/Pine port, not a live enabled signal producer. Preserve original Pine.
- BE-10 complete 10/10: exact-decimal catalog/expiry/grid/lot/tick planning,
  bounded quotes/traded pins, estimate margin, sizing and nonexecuting preview.
  USER_PREVIEW funds are assumptions, not wallet/account/project cash readings.
- Nondefault Pine opposite-signal overwrite is an indicator replacement, not a
  broker EXIT. Preserve replaced_trade_id; the planner requires reconciliation
  rather than inventing an exit. Review this before any real managed activation.
- BE-11-01 through 14 complete as isolated PAPER lifecycle. QA-11-15/16 Pending
  actual recorded indicator/strategy/execution pipeline, 20 manually checked
  strike examples and explicit G3. BE-12 complete 12/12: scoped exact wallet,
  ledger/history/period projections, atomic margin/settlement, versioned costs,
  cash-flow-excluding returns and nightly reconciliation. No gate waiver.
- BE-13 complete 20/20 as domain API and frontend-client contract code. Evidence:
  docs/testing/BE-13-acceptance.md, BE-13-06-acceptance.md and
  BE-13-domain-acceptance.md. Auth/origin/CSRF/audit, bounded REST/WS ordering,
  chart/source fences, signals/decisions, controls, history/CSV, P&L, wallet,
  settings/rebuild, preview and risk/recon producers are accepted.
  Actual React/browser flows remain FE-14 onward; managed automatic indicator/
  strategy generation and trial activation remain behind reference/operational
  gates. Tests use real services with synthetic inputs, never real-session proof.

## Domain operation boundaries

- Normal startup stays PAPER/unarmed with MARKET_SERVICE_ENABLED=false; .env is
  unchanged. It never attaches a wallet/executor/runtime, seeds capital or starts
  paper trades. Missing wallet/actions return 409, not fabricated zero balances.
  LIVE/arming and real-order sending remain unavailable. Current entry capability
  reflects only a matching explicitly attached owner/runtime and readiness.
- DomainService uses app.state.paper_execution and optional app.state.paper_runtime.
  An isolated owner supplies WalletService/PaperRuntime plus server-owned catalog,
  option quotes, execution prices and readiness. Entry permission defaults false.
  No HTTP client may submit quotes, TradePlans, clocks/readiness or entry-enable
  flags. Persisted signal lineage, source/settings, fresh contracts/capital and
  final BE-11 gates are rechecked before an admission.
- GET signals exposes actual entry_event_ordinal/signal_id only when a persisted
  ENTRY exists; never confuse a candidate ordinal with its ENTRY ordinal. Prepare
  a durable candidate from that source, then confirm its server decision ID.
  An ENTERING/admitted response is not a fill; close/kill may remain pending until
  fresh eligible quotes and owner polling complete both legs and settlement.
- New wallet/prepare/confirm/settings mutations require a stable Idempotency-Key.
  Retry the same action/body/key after a lost reply. Commands retain outcomes and
  recover via ledger, admission, deterministic candidate and settings-command keys
  after domain commit. Different bodies/actions conflict; terminal rejects stay
  rejected. Do not auto-generate new keys after ambiguous financial requests.
- Settings are canonical versioned desired values. Pine/data changes require
  rebuild acknowledgement; active feed/exposure blocks financial changes. Owner
  rebind requires stopped/flat state and verifies prepared source/grid/settings
  for stateful changes. It preserves funds/history and loss/kill locks and can
  select a new rebuilt stream without overwriting the prior baseline. Reattach
  the matching runtime afterward. Saved updates alone never mutate .env or trade.
- Existing leased MarketService polling has one optional paper-runtime hook;
  no extra scheduler. Polling services exits despite failed entry readiness.
  A stopped/non-desired owner cannot poll: isolated owners must call domain.poll
  on clock events. HTTP feed stop refuses open/pending paper exposure.
- Canonical /api/strikes/preview is read-only apart from mandatory security audit:
  no subscriptions, saved decisions, reservations or orders. Legacy durable
  /api/settings/preview-strikes and its explicit subscription option remain.
- Chart publication is explicit owned replay work. publish_chart_history validates
  the entire stored prefix/settings/context and binds revision/configuration plus
  result fingerprints in checkpoint JSON. Read APIs never publish/recalculate.
  after=-1 includes brick 0; equal-time bricks use index order. Send revision and
  indicator_source for later pages; reload on 409. Missing/warm-up values stay
  explicit/null. Market/indicator advancement invalidates publication. This is
  INDICATOR_REPLAY, reference_verified=false, not independent G2 evidence.
- Real attached book/replay data feeds typed snapshots/events; unavailable domains
  remain explicit. Restore snapshot plus paged signals/history/alerts on resync.
  Client handles exact INR, CSRF/session/logout/401, cancellation, keys, CSV,
  WSS cursors and duplicate/gapped/run-changed batches. It is not a React UI.
- Wallet amounts are exact paise up to INR 999,999,999,999.99. capital() is actual
  free cash; auto-top-up planning_capital() is an explicit simulated funding
  ceiling, never account/project cash. Risk uses actual session capital. Reset
  never erases trades or clears locks/counters. Cost schedules are dated versioned
  PAPER_ESTIMATE assumptions, not measured broker charges or perpetual rates.
- Nightly 15:35 reconciliation is opt-in WALLET_RECONCILIATION_ENABLED=false by
  default, inside the existing desired/running owner. Durable failures block
  financial actions and raise alerts, never silently repair evidence. No billing
  or unattended message/notification integration exists.

## Preserve local state and acceptance

- Local DB is unchanged. Pending migrations 0007_indicator / 0008_strategy /
  0009_paper_execution / 0010_wallet / 0011_domain_api were tested only on isolated
  DBs. Apply under owner/backup procedure, never while observing a baseline.
  0011 retains decisions, settings versions and command recovery provenance and
  backfills existing preview/admission/reject records. Accepted old feed snapshots
  remain usable before domain migration; new domain paths need their schema.
- Local 0005/0006 were already applied under lease/backup with retained table
  counts. Backup details: docs/api/dashboard-operations.md. Keep recording runs,
  source hashes, gap archives and recovery fences; never replace a real baseline
  with replay state. SQLite financial writes are serialized and reconcile exact
  projections. Schema discovery is cached until an owner restart after migration.
- One app worker/OS lease and scheduler; one coding agent, existing model/Standard
  speed. No extra agents or paid API. Same-day catalog/exact contract required;
  login/token rotation stops the old socket and requires recovery. Blocking jobs
  are joined on cancellation. Fresh unfinished live volume stays partial/blocked.
- Calendar nse_2026 includes Budget/Muhurat overrides; unknown years (including
  prior-year warm-up) block. Application cutoff 15:30 differs from published F&O
  close. No actual feed/paper observation is inferred from calendar dates.
- D01 Pending REF-00-03 chart settings; D02 Pending separate debug copy REF-00-04;
  D06 lacks actual observation; D11 awaits BE-08-14; D15 awaits QA-09-19/20;
  D22 awaits QA-11-15/16. D23 API code complete. D24 API IDs are done but shadow
  slice/real comparison remains Pending. D26 API IDs are done but actual eligible
  paper observation remains Pending. D30 BE-13-20 is done; FE-14 rows remain.
- Zero qualifying formal paper sessions evidenced. Manual Pine practice, synthetic
  replay tests, automated trials and formal burn-in remain distinct. G1/G2/G3,
  drills, daily shadow evidence and at least 20 qualifying exchange sessions are
  required. D24-D30 trial / D45 candidate / D60 review are conditional targets.
  LIVE-money tasks remain outside the funded paper plan.

## Usage, cash and next handoff

- Extra paid usage INR 0; project ceiling INR 20,000 including fees, target
  INR 10,000. Actual spend, committed bills, headroom, plan/price, renewal/expiry,
  allowance and reset remain Unknown. Empty ledgers do not prove zero spending
  or an available INR 20,000 balance. No purchase/recharge authorized or initiated.
- Already-requested receipts/spend, Codex plan/INR renewal price/date, allowance/
  reset and Kite/TradingView access are still outstanding; do not invent/read
  account billing or repeatedly ask. Missing facts do not block included coding.
- Soft H checkpoint 90k input + 20k output is not an account quota or exact meter.
  In-session alerts: actual renewal within 3 days, allowance <=20%, cash thresholds
  and missing facts. No exact token/billing meter or background alerts exist.
- Read this, current daily row and targeted README/task/code on the next turn.
  Preserve existing edits. Update README counts/evidence/next pointer, daily row
  and this handoff together; receipts only when supplied. README.v1 is immutable;
  documentation rows never count as product completions. Next: FE-14-01.
