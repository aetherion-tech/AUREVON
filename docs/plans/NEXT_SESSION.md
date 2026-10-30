# Next session - budgeted delivery plan v2

Updated: 2026-10-30, D05. README is authoritative.

## Immediate user priority - hourly Live screen batches

User requested this persistent queue on 2026-10-30 so a new chat can resume
without losing context. NEXT ACTION: UI-LIVE-B1, then UI-LIVE-B2. This UI
priority precedes the previous QA-19-14 engineering pointer; QA-19-14 remains
Pending and resumes after this queue or while reference-dependent B3 is blocked.
These are incremental UI follow-ups, not new master-task completions. Existing
FE-15 tasks remain Completed; do not rebuild their accepted functionality.

| Batch | Status | Scope / acceptance | Effort estimate |
| --- | --- | --- | --- |
| UI-LIVE-B1 | Pending | Reuse active spread/account projections for a compact positions table: side, strike, expiry, lots/quantity, entry, current price and per-leg/total P&L where supported. Add prominent green/red total P&L. Preserve close confirmation, decimal accounting and explicit unavailable/stale prices; do not substitute zero for missing marks. | 1-2 hours |
| UI-LIVE-B2 | Pending | Reuse existing Renko renderer/overlays: large chart on left, strategy and P&L summary on right, positions below; responsive layout and clear labels. Retain quote-only/missing-history guidance and source identity. | 1-2 hours |
| UI-LIVE-B3 | Pending - input blocked | Confirm actual chart settings/anchor, then configure and verify genuine feed-driven Renko updates. Screenshot visibly suggests Nifty 50, 5-minute, Traditional 50; these are observations, not confirmed operator settings. Source, wicks, timezone, anchor and indicator inputs still require confirmation under REF-00-03. No guessed anchor, signal parity claim or entry-gate bypass. | 1-2 hours only if inputs are ready; reference acceptance separate |
| UI-LIVE-B4 | Pending | Final integrated checks: chart/source updates, option-leg MTM, totals, stale/missing quotes, empty positions, responsive layout and guarded close using isolated replay/test state. Capture evidence and report remaining live/reference gates. | 0.5-1 hour |

Fastest useful delivery: B1+B2, estimated 2-4 working hours, not a deadline.
Run meaningful focused checks with EACH batch; B4 does not defer required
verification. If inputs for B3 remain missing, continue independent B4 checks
and leave B3 explicitly blocked. UI completion does not enable paper entries.
Use backend option-leg marks and quantities for P&L, not NIFTY chart movements.
RSI, payoff curves, POP and Greeks are deferred from this minimal queue.

Implementation starting points: frontend/src/LivePage.tsx, Chart.tsx and
style.css; reuse existing live-data/contracts and FE-15 acceptance evidence.
Screenshot intent is captured above; temporary attachment paths may expire.
Preserve running 5173/8000 owners, market observations, operator DB/config and
original Pine. Use isolated test state; never create fake operator trades.
At each completed batch, update this table, README/current daily-log evidence
and next pointer together; retain product counts 237 Completed / 43 Pending
unless a separate master task is actually accepted. Report exact BE/FE commands
below, dashboard URL and what to inspect. Do not restart Completed batches in a
new chat. Documentation-only queue recording is not implementation completion.
Usage, cash/headroom and renewal remain Unknown; extra paid usage INR 0 by
default, project ceiling INR 20,000 including fees. No purchase authorized.

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

Open https://localhost:5173/dashboard/ (History: /dashboard/history).
Keep both terminals open. Reuse an already-running frontend and refresh the page;
port 5173 already in use usually means that Vite is running. If backend Python
code changed, explain that its existing owner must be stopped safely with Ctrl+C
before restarting; never start duplicate owners or interrupt an observation.
Include npm.cmd ci only when dependencies need installation, and npm.cmd run
setup:https only for a missing local certificate. Missing dashboard password:
run backend python -m app.tools.dashboard_password --save locally and restart;
never request the password/hash in chat. Explain remaining paper readiness gates.

## Current work and evidence

- LATEST D05 user-reported Live 404 fix: local read-only config confirms no
  Renko anchor. Explicit quote-only UI avoids chart requests; signals snapshot
  marked unavailable avoids signal requests and stale cached signals. Chart 404
  shows missing-history guidance; genuine 500 errors remain visible. Archived
  history can exist with latest_brick=null; replay overlays remain valid while
  managed indicators are unavailable. Preserve those distinct semantics.
  Final 12/12 selected built HTTPS checks, 35 frontend tests, build/TypeScript/
  ESLint PASS. Earlier 6/11 and 11/12 browser runs retained as separate receipts;
  do not call them green. docs/testing/live-source-availability.md and
  live-source-final-browser-checks.json. Frontend-only; no backend restart,
  operator DB/.env/Pine/feed/service changes or fake data. Reuse Vite and hard-
  refresh https://localhost:5173/dashboard/. Chart activation still requires
  actual REF-00-03 anchor/settings and reference gates; do not claim it enabled.
  Counts stay 237/43, formal sessions zero; next engineering QA-19-14.

- LATEST D05 QA-19 batch: QA-19-11 Completed as isolated engineering recovery
  drills. Four new scenarios: disconnect, bounded queue overflow, token expiry,
  and failed historical recovery; actual temporary worker/recovery persistence
  feeds explicit test-owner readiness into real API/wallet admission. Original
  confirmation identity is retained, no positions/margin/balance/ledger changes;
  reconnect/login alone or elapsed hold cannot bypass partial source quality.
  47 selected backend PASS; two injected-fault built HTTPS browser checks PASS;
  Ruff/format and strict mypy runner PASS. No production behavior or operator
  state changes. docs/testing/QA-19-11-recovery-drills.md and retained JSONs.
  Project 237 Completed / 43 Pending; section 19 11 Completed / 7 Pending.
  QA-19-09/11/12/13 done; QA-19-10/14/15/16/17 Pending. Formal sessions ZERO;
  G4/G5 unaccepted. NEXT engineering batch QA-19-14 measured-path profiling/
  optimization; do not claim representative-load/dispatch targets from arbitrary
  synthetic inputs. Reference and recorded-day/shadow evidence remain absent.

- LATEST D05 local batch: QA-19-13 Completed as integrated engineering control
  drills (manual close, kill, real synthetic-MTM loss lock, square-off quote
  retry and clock warning/admission denial). Actual temporary API/wallet/ticker/
  reconciliation paths; five new scenarios, 114 selected backend cases PASS.
  Four built HTTPS browser checks PASS; three use mocked projection/interaction
  responses, foundation kill/auth uses actual temporary backend API. Ruff/format
  and strict mypy runner pass. No production behavior or operator-state change.
  docs/testing/QA-19-13-control-drills.md and corresponding retained JSONs.
  Project 236 Completed / 44 Pending; section 19 10 Completed / 8 Pending.
  NEXT LOCAL BATCH: QA-19-11 integrated disconnect/overflow/token-expiry recovery
  admission drills using isolated providers. REF-00-03/05/06/07 remain input-
  blocked; do not re-request the entire same batch or rerun accepted work.
  G5 unaccepted; formal sessions zero. Preserve 5173/8000 working owner.

- D05 REF batch recheck: chart_reference.md still all Pending and no actual
  reference CSVs found in workspace/backend data. Generator integrity check
  passes; no implementation or operator-state changes, no new task completion.
  REF-00-03/05/06/07 await operator settings and real export/source paths.
  Counts stay 235/45. Next after REF: QA-07-01 through 07 for actual G1 evidence;
  BE-08-14 maths can run alongside once inputs exist, then QA-09-19/20 after G1,
  then QA-11-15/16 after G2. See reference_workflow.md batch table.

- ACTIVE D05 REF batch: REF-00-04 Completed as separate debug source creation;
  original Pine hash and exact prefix preserved. 30 Data Window plots include
  maths/scores/flags/events and reversible IDs; TradingView compile/export NOT
  verified. Intake preserves originals/hash manifest and prepares math/debug CSV
  without synthesizing expected values. Latest focused 91 tests, Ruff/format,
  strict mypy and generator drift check pass. See docs/pine/reference_workflow.md.
  Receipt: docs/testing/REF-00-source-intake-checks.json (hashes and limitations).
  REF counts 4 Completed / 4 Pending; project 235 Completed / 45 Pending.
  REF-00-03/05/06/07 require actual settings, ten-session export, independent
  spot/futures/OI/daily/contract context and sanitized reviewed provenance.
  User chart settings/paths question sent; unanswered fields stay Unknown.
  Continue on 5173/8000; unresolved service 8443/OPS-19-03 is separately Pending.
  No operator state/Pine/feed/service/broker login changed; no purchase.

- D05 service-start failure diagnosed from screenshot, actual stopped SCM state, no listener 8443 and SCM events 7000/7009. Old .venv/pythonservice.exe help exits 0xC0000135 (missing dependency), including System32 cwd/minimal PATH. Staged host and exact Python/pywintypes/VC runtime DLLs inside .venv/Scripts; new help exits expected 2 with usage in same environment. New RepairHost action changes ONLY a stopped service binary path; retains account/startup/recovery and never starts it. Future Install uses staged host. 26 focused tests pass; Ruff/format/mypy and PS parsing pass. Evidence: docs/testing/OPS-19-service-host-repair.json. Actual SCM repair/start remains operator-admin work; port 8000 owner still running, untouched. OPS-19-03 remains Pending; counts 234/46; formal sessions zero.
  NEXT: after observation and flat-state/feed-stop check, Ctrl+C existing backend
  and await shutdown. Elevated scripts/service.ps1 -Action RepairHost, then Start,
  then Preflight. No reinstall or account/password reconfiguration required.
  Verify https://localhost:8443/dashboard/ before claiming startup; no recovery
  enablement until graceful stop/restart/duplicate-worker acceptance passes.

- D05 identity evidence: operator preflight 11:30:09 UTC and agent read-only preflight 11:30:58 UTC confirm .\Sanny, configured_non_system_identity true, disabled (4), stopped (1). Agent observed backend port 8000 and Vite 5173 still listening; no owner stopped or service started. Added service-context TLS/DPAPI read-only access guard before app creation so failed decryption preserves the saved session. Latest focused service/access/preflight tests 21 pass; Ruff lint/format and strict mypy pass. Prior 813-pass full suite predates this guard. OPS-19-03 remains Pending for actual lifecycle/TLS/DPAPI and single-worker verification.
  NEXT: after observation, Stop market data and verify flat/no pending exposure;
  Ctrl+C the existing backend and wait for shutdown. Keep it stopped. In elevated
  PowerShell set sc.exe config AUREVONPaper start= demand, then guarded Start and
  Preflight. Open https://localhost:8443/dashboard/; service serves built FE.
  Do not ConfigureRecovery until lifecycle/duplicate/restart checks pass.

- D05 installed-service evidence: operator Install succeeded; elevated preflight 11:25:11 UTC reports service_query OK, LocalSystem, start_type 4 (disabled), current_state 1 (stopped). Agent independently read the same service state at 11:26:01 UTC. No service start or identity change claimed. Next configure the intended operator account privately in Services while keeping startup Disabled, then repeat Preflight; TLS/DPAPI and SCM lifecycle remain pending.

- Operator-supplied elevated preflight at 2026-10-30T11:23:25.757431+00:00 reports create_service_access GRANTED for DESKTOP-0FJTT0S\Sanny, service NOT_INSTALLED (1060). This clears the elevated-terminal permission blocker only; coding-agent session elevation is not inferred. Identity/TLS/DPAPI/lifecycle remain unverified. OPS-19-03 stays Pending.
  Installation subsequently completed; see latest installed-service evidence above.
  Do not rerun Install. Configure intended account privately; do not Start or
  ConfigureRecovery yet.

- D05 11:18:26 UTC: read-only service preflight also run outside workspace sandbox; Windows still denies create-service access (error 5), service absent (1060). No service or feed changed. OPS-19-03/08 remain Pending; 234 Completed / 46 Pending. Prior 813-pass suite retained; no implementation changes or redundant rerun.

- D05 operator update: user confirms fresh Kite login and Start market data are
  done. This is operator-reported UI verification, not independently captured
  quote/reference evidence or a qualifying formal paper session. Preserve the
  running feed. Fresh read-only SCM preflight at 11:12:51 UTC still returns error
  5 (create denied) and 1060 (service absent); OPS-19-03 remains Pending.

- D05 all-OPS review: seven OPS-prefixed rows already Completed; 03/08 remain
  Pending. Fresh SCM preflight: error 5/create denied, error 1060/service absent.
  Service installation now stages disabled; Start/Restart/ConfigureRecovery refuse
  missing/unreadable/LocalSystem identity. New read-only Preflight action; no
  service or operator state changes. See docs/testing/OPS-19-current-blockers.md
  and fresh full-suite OPS-19-session-completion-check.json: 813 passed, exit 0;
  separate focused service/release/shadow checks 21 passed. Ruff/format and strict
  mypy for the new tool pass. Counts stay 234/46;
  formal sessions zero. External ingress/calibrated reference/G2 still required.

- PRIORITY local UI fix APPLIED, D05: see docs/testing/local-ui-recovery.md.
  The actual local DB was 0006, feed stopped, account unattached and last Kite
  callback 400. Guarded setup paused the existing --reload owner gracefully,
  verified an immutable backup, applied 0007 through 0012, saved an explicit
  zero-funded simulated account and resumed that SAME backend. Old table counts
  and audit history retained; separate temporary backup restore verified.
  Receipt: backend/data/backups/local-ui-20261030T044455-b2a6ef6d.setup.json
  (ignored). No active observation/exposure existed; no force-kill/duplicate owner.
- Only LOCAL_UI_ENABLED=true was added to .env, preserving credentials/settings/
  Windows permissions. MARKET_SERVICE_ENABLED remains false. Startup attaches
  the existing flat wallet plus entries-disabled display runtime; never auto-
  seeds funds or enables strategy entries. Actual account/P&L projection and
  running HTTP health verified; one zero-amount INITIAL row, zero positions, zero balance.
  A zero balance is simulated capital, not broker funds or project cash.
- Kite callback grants now retain their initiating UI origin and relay a backend/
  other-loopback callback BACK to it before cookie proof/token exchange. Existing
  cookie/state/expiry/replay/logout protections remain. Unit cross-origin roundtrip
  passes. Fresh login was reported completed by the operator on D05; do not reuse old callbacks
  or claim actual broker authentication based on tests. Use consistently
  https://localhost:5173/dashboard/, sign in, Log in to Kite, then Start market data.
  Operator confirms login/Start market data done; no password/token requested in chat.
- Live now has explicit data Start/Stop controls; no trading activation. Actual
  RENKO_ANCHOR is absent, so opt-in local UI supports genuine quote-only streaming/
  recording with explicit chart blocker and permanently unvalidated entry gate.
  Do not invent a reference anchor. Renko/indicator/strategy activation still needs
  real configuration/reference acceptance. The local setup command is an explicit
  maintenance operation, not a prerequisite to rerun every login. Existing startup
  terminals already updated through reload; reuse/refresh, do not spawn duplicates.
- Recovery checks: 121 auth/domain/wallet/startup cases and 17 owner/startup cases
  pass (overlap), including interrupted zero initialization. 35 frontend tests and
  production build/TypeScript/ESLint/Ruff/mypy/OpenAPI checks pass. Final complete
  built HTTPS browser run 40/40 passes; outcomes in docs/testing/local-ui-recovery.md. This fix adds no product
  completions; counts below stay 234/46, formal sessions ZERO. No real quotes,
  automatic entries or formal burn-in claimed from synthetic browser fixtures.

- Product tasks: 280 total; 237 Completed / 43 Pending. Frontend remains
  57 Completed / 0 Pending. Section 19: 11 Completed / 7 Pending. Completed:
  OPS-19-01/02/04/05/06/07/18 and QA-19-09/11/12/13. Do not restart accepted work.
  Evidence: docs/testing/OPS-19-followup.md (latest) and OPS-19-acceptance.md
  (initial six-row batch). Initial full backend 785 remains historical.
- NEXT TASK: QA-19-14 bounded profiling/optimization of the measured storage/
  indicator path, followed by representative-load and dispatch measurements.
  Acceptance remains Pending until targets actually pass. REF-00-03/05/06/07,
  G1/G2/G3, recorded-day and 20-session evidence remain external prerequisites.
  OPS-19-03 is a separate unresolved service track; use development 5173/8000.
- D05 follow-up accepted OPS-19-04: isolated real owner steps poll a matching
  synthetic runtime, wait for fresh quotes after cutoff, complete square-off,
  reconcile/report and restore separately. No extra scheduler. Accepted OPS-19-05:
  retain original ticks and sealed verified gzip indefinitely, rotate 90 daily
  log archives, record optional exact/unknown P&L mark samples and prune ONLY
  derivative samples strictly older than 90 days after backup. An automatically
  rejected raw-deletion enhancement was NOT added; safe source preservation is
  the selected policy. No deletion approval is needed for the delivered policy.
  Defaults SESSION_MAINTENANCE_ENABLED / PNL_TICK_RECORDING_ENABLED /
  RECORDING_COMPRESSION_ENABLED remain false; .env unchanged.
- QA-19-12 accepted engineering drill: actual isolated child process exits
  abruptly with OPEN paper exposure; a fresh process restores one position,
  completes four fills total, preserves unique ledger keys and exact balance/net,
  releases margin. Existing partial-leg/duplicate/rollback cases pass. This is
  synthetic process-crash evidence, not formal G5 or a qualifying exchange day.
- OPS-19-08 still Pending: authenticated observation-only inbox, durable rate/dedup,
  source fencing, original Pine CO/DIV/OT family grouping, one-to-one two-brick
  comparison and Live mismatch panel implemented. SHADOW_INGESTION_ENABLED=false.
  Needs real reachable TLS-authenticated ingress (TradingView public HTTPS port
  443), calibrated debug-copy event/index/trade identity and G2. No tunnel/public
  service created. Original Pine unchanged. Guide: docs/operations/shadow-alerts.md.
- QA-19-10/14/15/16/17 remain Pending. Missing actual eligible recorded-day,
  formal integrated drill/reference evidence, representative warmed-load and
  dispatch measurements, daily/weekly TradingView comparisons, twenty sessions
  and G4/G5. Synthetic baseline 500 ticks/48 bricks: phase run brick-emitting p95
  63.89 ms and max 75.23 ms; 50 ms target MISSED. Storage p95 23.49 ms;
  indicator/readback p95 41.69 ms. Separate percentiles must not be summed.
  No dispatch latency measurement. Retained JSONs under docs/testing/OPS-19-*.
- Earlier backend broad invocation: 797 pass / 1 outdated migration-test failure
  of 798. The older test now targets 0011 rather than head; corrected affected
  integration suites 69 pass. Latest scheduled retention/compression suite 8 pass.
  Failed full-run and corrected-case JSON evidence both retained, not overwritten.
  Latest changed shadow/owner/retention checks also passed a 14-case invocation.
  These historical runs were not green; the later 813-pass run above is separate
  retained evidence. Ruff/format, strict mypy,
  OpenAPI/TypeScript contract checks, frontend production build/TypeScript/ESLint
  and 35 frontend tests pass. New shadow flows and three repeated cursor checks
  pass. Final built FastAPI HTTPS browser run: 38/38 pass; see docs/testing/OPS-19-followup.md.
  Initial 37/38 runs had a history test resync race; helper now waits for Connected
  before paging; Settings/Wallet helpers also await Connected. Stale-cursor
  rejection persists. Windows Proactor abort/reset
  callbacks remain noted. Frontend audit clean; backend 12 advisory records remain.
- Operations schema 0012 was originally tested in isolation; the subsequent local
  recovery above APPLIED 0007 through 0012 under paused-owner/backup procedure.
  LOCAL_UI_ENABLED is the only new .env opt-in; original Pine remains unchanged.
  Existing frontend HTTPS certificate expires 2027-10-29; development
  5173/8000 remains supported. Dashboard password previously configured=true;
  use hidden local password tool only if missing, never request it in chat.
- Built release: FE npm.cmd run build; BE python -m app.tools.serve from backend;
  https://127.0.0.1:8443/dashboard/. No FE server needed. Live includes the disabled
  shadow comparison panel. Safe startup/recovery/backup/drill instructions:
  docs/operations/paper-release.md. Never run alongside an observing owner; safely
  stop/restart the prior BE owner when no observation/exposure remains. Reuse Vite
  for the development flow above. Backend code changed, so a safe restart is needed.
- At each active implementation turn run backend python -m app.tools.local_ui_readiness
  and report changed blockers. Current reference/gate blockers remain BE-08-14,
  QA-09-19/20 and QA-11-15/16. Default startup stays detached; explicit local UI account remains PAPER/unarmed with entries blocked.
  Formal qualifying sessions remain ZERO. No honest activation date is known;
  no background monitoring or unattended user notifications are configured.

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

- Default startup stays PAPER/unarmed with MARKET_SERVICE_ENABLED=false. Explicit
  LOCAL_UI_ENABLED=true now attaches the setup-created flat wallet/display runtime
  with entries_allowed=false; startup never seeds capital or starts paper trades. Missing wallet/actions return 409, not fabricated zero balances.
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
  Settings, Live, History and Wallet are accepted; next OPS-19-03.
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

- Local recovery APPLIED migrations 0007_indicator through 0012_operations from
  0006 under acknowledged owner pause + market lease + verified backup. Original
  table counts/audit retained; separate restore verified. See local-ui-recovery.md
  for the actual receipt and explicit zero-account initialization. Never migrate
  during an observation or replace a real baseline with replay state.
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
- D01 Pending REF-00-03 chart settings; D02 source work completed D05 with separate debug copy REF-00-04;
  D06 lacks actual observation; D11 awaits BE-08-14; D15 awaits QA-09-19/20;
  D22 awaits QA-11-15/16. D23 API code complete. D24 API IDs are done but shadow
  slice/real comparison remains Pending. D26 API IDs are done but actual eligible
  paper observation remains Pending. D28-D30 code rows completed early D04;
  BE-13-20 and all 15 FE-14 IDs are done. D31/D32 FE-15 IDs also completed early
  D04. D33 remains Pending: FE-15-11 through 15 are done; OPS-19-08 requires actual
  shadow evidence. D34/D35 FE-16 code rows also completed early D04.
  D36/D37 FE-17 code rows also completed early D04 (conditional deletion
  unavailable). D38-D40 FE-18 rows completed early D04. Next OPS-19-03. No actual observation or managed activation
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
  documentation rows never count as product completions. Next engineering: QA-19-14.

## Remaining execution order after operator login verification

Current reference priority: REF-00-03 then actual REF-00-05/06/07; REF-00-04
source created D05. The service path below remains a separate pending track
while dashboard development continues on 5173.

1. OPS-19-03: elevated intended Windows account; private service identity setup,
   isolated TLS/DPAPI/start/stop/restart/recovery and single-owner verification.
   Operator elevated session now has create access (11:23:25 UTC); coding-agent
   session previously lacked it. Service now installed disabled/stopped as
   .\Sanny; account configuration confirmed, actual lifecycle still pending. Do not interrupt the feed
   or install/start another owner over an observation. In a separate elevated
   PowerShell from D:\WorkSpace\AUREVON, first run the read-only preflight:
   `powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/service.ps1 -Action Preflight`.
   A granted probe alone does not complete the task. Service identity remains
   to be confirmed; passwords stay local.
2. Resolve actual chart/debug-reference prerequisites REF-00-03/04 and BE-08-14,
   then QA-09-19/20 (G1/G2) and QA-11-15/16 (recorded/manual evidence and G3).
   OPS-19-08 needs authenticated reachable ingress and aligned real shadow evidence.
3. QA-19-11/12/13 engineering drills are complete. QA-19-10/14 still require
   actual recorded-day reconciliation and representative performance acceptance. Preserve measured failures.
4. QA-19-15/16: at least 20 qualifying automated paper sessions with daily notes,
   daily shadow comparisons and weekly reviews after prerequisites pass.
5. LAST paper acceptance task: QA-19-17, explicit G4/G5 review of reconciled
   results, resolved anomalies and drill evidence. No calendar or code-count waiver.
   Phase-20 live-money work stays outside the funded paper scope.
