# Next session - budgeted delivery plan v2

Updated: 2026-10-29, D04. README is authoritative.

## Required completion handoff: local execution commands

User instruction: whenever a task/batch is completed, always include exact
backend (BE) and frontend (FE) PowerShell commands in the final answer, followed
by the dashboard URL and the screen/change to check. Preserve this instruction
when updating this handoff so future Codex sessions remember it.

Backend terminal:

```powershell
cd D:\WorkSpace\AUREVON\backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log
```

Frontend terminal:

```powershell
cd D:\WorkSpace\AUREVON\frontend
npm.cmd run dev
```

Open https://127.0.0.1:5173/dashboard/ (History: /dashboard/history).
Keep both terminals open. Reuse an already-running frontend and refresh the page;
port 5173 already in use usually means that Vite is running. If backend Python
code changed, explain that its existing owner must be stopped safely with Ctrl+C
before restarting; never start duplicate owners or interrupt an observation.
Include npm.cmd ci only when dependencies need installation, and npm.cmd run
setup:https only for a missing local certificate. Missing dashboard password:
run backend python -m app.tools.dashboard_password --save locally and restart;
never request the password/hash in chat. Explain remaining paper readiness gates.

## Current work and evidence

- Login follow-up: actual server reported configured=false; local dashboard hash
  was absent. Use backend .venv/Scripts/python.exe -m app.tools.dashboard_password
  --save, entering the password only at hidden local prompts. It saves directly
  to ignored .env, preserving settings and printing no secrets. Restart the backend
  safely afterward. React now explains missing setup rather than offering a login
  that must fail. Local prompt was opened; saved hash is now present/format-valid,
  and the running backend reports configured=true. Actual HTTPS password form
  verified without attempting login or seeing the password. 13 focused backend/auth tests,
  15 frontend tests and two targeted browser flows covered that follow-up.
  Current verification and next task are below.

- Product tasks: 280 total; 225 Completed / 55 Pending. FE-14/15 complete
  15/15 each; FE-16/17 complete 8/8 each; FE-18 complete 11/11.
  Frontend 57 Completed / 0 Pending. Latest FE-18: 100 targeted backend wallet/
  domain regressions plus 1 audit case (101 distinct; existing warning), 35 frontend
  tests, 35 full HTTPS browser flows plus 10 focused Settings flows (36 distinct).
  Production build/strict TypeScript/ESLint, generated Pine/backend manifest parity
  and focused Ruff lint/format pass. Prior full backend result remains 780.
  Evidence: docs/testing/FE-18-acceptance.md.
- NEXT TASK: OPS-19-01 Serve built frontend through FastAPI with SPA fallback
  and same-origin API/WebSocket routing. Do not restart accepted BE-13 or FE-14 through FE-18.
  Settings now has every original Pine group/default/bound/tooltip, strategy/risk/
  fill/data controls, exact validation, per-field change review, confirmation,
  rebuild acknowledgement, stale-edit protection, unsaved navigation guards and
  lost-reply command recovery. Versioned JSON import/export/defaults are explicit;
  read-only strike preview uses saved strategy, shows economics or rejection and
  never places orders. Browser layers/palette/sounds/notifications are opt-in
  preferences; notifications only while signed in with the dashboard open.
  Saved settings remain desired versions: owner rebind/rebuild is separate; no
  rebuild-progress API or automatic activation is invented. Success and stale
  rejection have verified server audit records. Keyboard and mobile are verified.
  Backend/API/schema implementation unchanged; one acceptance test added. No new
  migration or operator restart. Existing working edits preserved.
  Isolated synthetic browser DB/TLS on ports 5174/18765 only; operator 5173/8000,
  local DB, original Pine and observation preserved. No real-session evidence.
  FE-17-05 remains conditional: history deletion disabled without a deletion API.
  Existing earlier metadata/filter/projection API changes still need a safe owner
  restart if its process is older. No duplicate owners or observation interruption.
  Prior pending migrations and managed/reference/G2/G3 are separate blockers.
  Local HTTPS certificate trusted, expires 2027-10-29; loaded automatically from
  ignored frontend/.local-tls. Start npm.cmd run dev or refresh existing frontend.
  URL: https://127.0.0.1:5173/dashboard/; Settings: /dashboard/settings.
  See docs/operations/local-paper-ui.md.
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
  FE-14/15/16/17/18 React/browser foundation, Live, History, Wallet and Settings are accepted; managed automatic indicator/
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
  WSS cursors and duplicate/gapped/run-changed batches. React now uses this client;
  Settings, Live, History and Wallet are accepted; next OPS-19-01.
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
  paper observation remains Pending. D28-D30 code rows completed early D04;
  BE-13-20 and all 15 FE-14 IDs are done. D31/D32 FE-15 IDs also completed early
  D04. D33 remains Pending: FE-15-11 through 15 are done; OPS-19-08 requires actual
  shadow evidence. D34/D35 FE-16 code rows also completed early D04.
  D36/D37 FE-17 code rows also completed early D04 (conditional deletion
  unavailable). D38-D40 FE-18 rows completed early D04. Next OPS-19-01. No actual observation or managed activation
  is inferred from browser acceptance.
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
  documentation rows never count as product completions. Next: OPS-19-01.
