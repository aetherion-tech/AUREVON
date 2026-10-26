# AUREVON

A Python application for a Renko indicator, a future React dashboard, and paper
trading with Zerodha Kite market data. Development follows small, testable steps.

## Current progress

| Step | Status | Result |
| --- | --- | --- |
| 1. Backend foundation | Completed | FastAPI, settings, health checks, rotating logs |
| 2. Kite authentication | Completed | Login, encrypted session; real login verified |
| 3a. Instrument catalog | Completed | Daily NSE/NFO catalog; real download verified |
| 3b. Price data and Renko | Pending | Managed data/recovery core completed; real-market acceptance and TradingView parity pending |
| 4. Indicator engine | Pending | Pine port and TradingView signal parity |
| 5. Paper execution | Pending | Option mapping, risk limits, wallet, simulated fills |
| 6. React dashboard | Pending | Live, History, Wallet, Settings; frontend directory not created |

The current application reports PAPER mode; it does not simulate fills yet.
Kite login and instrument metadata are implemented. Live prices, strategy
calculations, and live orders are not implemented in the web application. A
standalone live price monitor is available as described below.
The original project specification is saved in [docs/SPEC.md](docs/SPEC.md).

## Start here - delivery plan v2 (45-day target, 60-day review)

**Plan updated: 2026-10-26. Product status: 82 Completed / 198 Pending of 280.**
**Cash target: INR 10,000; absolute project ceiling: INR 20,000 including taxes/fees.**
This replaces the execution schedule, not the product acceptance requirements.
The original master checklist, stable IDs and all unfinished scope remain below.

| Active control | Current value |
| --- | --- |
| Short next-session handoff | [NEXT_SESSION.md](docs/plans/NEXT_SESSION.md) |
| Immutable Version 1 backup | [README.v1.md](docs/plans/README.v1.md), [SHA-256](docs/plans/README.v1.sha256) |
| Plan preparation | Completed on 2026-10-26; documentation only, outside the 280 product tasks |
| Current implementation slot | D01 code Completed: BE-05-10/11; REF-00-03 Pending user settings. BE-05 (17/17) and BE-06 (11/11) complete; BE-13-01 shared contracts Completed; next ready code: BE-13-02 (dashboard authentication). |
| Kickoff / elapsed day | 2026-10-26 IST / D01; task carry-over and early batches are recorded without renumbering elapsed days |
| Existing plan, all-in price, renewal and usage-reset times | Unverified; obtain actual account readings, never assume a reset/renewal date |
| Cash already spent / reserved / remaining | Unverified; reconcile receipts before proposing any purchase |
| Paper status | Manual practice can begin with the user's Pine chart; automated paper and formal burn-in not ready |
| Qualified formal paper sessions | 0 evidenced; dates, release/config identity, shadow checks and reconciliation required |
| Latest application verification | D01, 2026-10-26: 328 tests, Ruff lint/format and strict mypy passed |

### Delivery scope, day numbering and realistic targets

- D01-D45 target the local, single-user NIFTY **paper application** and the 198
  remaining reference/backend/frontend/paper-release tasks. D46-D60 reserve time
  for observation, verified defects and acceptance. All dates are targets.
- D01 is the actual kickoff calendar day in IST, not a billing date. Later day
  numbers are elapsed calendar slots, not 60 guaranteed trading sessions. Record
  dates in the daily log; do not silently renumber delays to claim on-time delivery.
  On weekends/holidays work on replay/UI/tests; no live-session evidence is invented.
- One-month target: functioning automated paper trial around D24-D30 **if** its
  prerequisites pass. D45: application candidate. D60: paper acceptance review if
  at least 20 qualifying paper trading sessions and all other gates are satisfied.
  Finishing earlier is welcome; never skip a test/gate to meet the target.
- Phase 20's 15 live-money tasks and phase 21's 5 extensions stay Pending outside
  this funded milestone. They are neither deleted nor promised within 60 days.
  Real-order execution, cloud/static-IP deployment and trading capital are not
  funded by this paper-only budget. New live scope needs a separate funded plan.
- Planning assumption: the user supplies broker login, chart settings/exports and
  daily observations, with roughly 2-4 focused review/operation hours on working
  days. AI coding time/allowance must also be available. Re-estimate after D03,
  D15 and D30 from accepted batches and actual usage, not task-count percentages.

### Spending envelope - ceilings, not purchase instructions

Use the existing Codex entitlement for coding first. A subscription can be used
only for coding even if it also includes other products. Keep one coding agent
and Standard speed by default. No API key, automatic recharge, extra subscription
or paid model switch is enabled by this document.

| Category, all-in INR allocation | Lean target | Maximum envelope |
| --- | ---: | ---: |
| Two monthly Codex-including subscription payments | 5,000 | 5,000 |
| Two months of Kite data access | 1,200 | 1,200 |
| Needed TradingView/export/reference access | 2,500 | 4,000 |
| Optional paid Codex credit top-ups | 0 | 5,000 |
| Unspent contingency: tax/FX variance, data access or exceptional review | 1,300 | 4,800 |
| **Total allocation** | **10,000** | **20,000** |

These are inclusive planning allocations, not verified local prices or an available
account balance. Reserve for existing payments inside the envelope; never count a
prepaid subscription again when using its included allowance. If needed export
access costs more than its allocation, use unspent contingency or defer that gate;
do not buy an annual plan based on its advertised monthly-equivalent price.
Keep the existing PC/local database; no hosted AI is needed for indicator runtime.

Before any proposed payment calculate:

`headroom = 20000 - confirmed_spend_to_date - committed_unpaid_costs - proposed_payment`

Also reserve known remaining essential subscription/data bills. Unknown baseline
spend/charges means headroom is **Unknown**, not INR 20,000. Empty ledgers do not
prove zero spending. Only the user confirms receipts and purchases; this plan
authorizes development, not subscriptions or money transfers. Stop optional paid
usage before breaching a category ceiling or the total ceiling. Reallocate only
after recording the decision, without exceeding INR 20,000.

Receipts go in [spend-ledger.csv](docs/plans/spend-ledger.csv). Subscription charges
are cash on their charge dates; credit-pack purchases are cash when purchased.
Credit consumption is a separate usage measurement, not a second cash charge.
The subscription allowance allocation averages INR 83.33/day over 60 days; it is
not a daily payment, available credit or a token-price conversion.

### Token and daily paid-usage policy

Included subscription allowance is not a fixed daily token grant. Actual account
usage/reset readings control availability. Token amounts below are initial **soft
engineering checkpoints**, not guaranteed quotas, measured past usage, token
entitlements or hard billing controls. Recalibrate them after the first three
batches; lower them if useful work fits, raise/re-scope only with measured evidence.

| Profile | Planned total input checkpoint | Planned total output checkpoint | Default new paid cash/day | Exceptional paid cash ceiling/day |
| --- | ---: | ---: | ---: | ---: |
| H: state/indicator/accounting/integration | 90,000 | 20,000 | 0 | 150 |
| M: bounded UI/API/fixture batch | 50,000 | 10,000 | 0 | 100 |
| L: operational evidence/review | 20,000 | 4,000 | 0 | 0 |

- Each D01-D60 row selects a profile; [daily-log.csv](docs/plans/daily-log.csv)
  contains its numeric checkpoints plus blank actual fields. Every day starts at
  **INR 0 extra paid cash**, regardless of the exception ceiling. Ceilings do not
  accumulate as permission to spend. Combined top-up purchases remain <= INR 5,000.
  If the offered credit pack exceeds the day's/remaining cap, wait; do not assume
  custom pack sizes or bypass the cap. Prefer the next included-allowance reset.
- Track actual input, cached-input subset and output from an available usage meter.
  Count cached input once inside total input; count reasoning inside total output
  when the meter includes it. Record a reasoning subset separately only if shown.
  Never infer billing from visible response length or add these subsets twice.
- Account percentages, reset times and purchased credits are separate fields.
  Where exact tokens/cost are unavailable, write `Unknown`/leave actual fields blank
  and record the source. Never estimate actual spend from an API rate card when
  using included subscription allowance. No billing/usage integration is installed.
- At roughly 80% of an observable checkpoint, finish the smallest reviewable
  change and required checks; save a compact handoff instead of starting a large
  unrelated task. If token counts are invisible, say so and use bounded scope plus
  account allowance readings. Safety/correctness checks are never dropped to fit.
- After two attempts at the same failure, diagnose root cause or narrow the batch;
  do not repeat full prompts/tests blindly. Use high reasoning only for demonstrated
  complexity. Keep the current capable coding model for trading/accounting/state;
  a cheaper available model may handle proven routine work. Do not silently change
  the user's model or lower critical verification quality to save tokens.

### Renewal and recharge notifications at each active session

The assistant must show `Budget/usage alert: ...` at session start when relevant,
and repeat unresolved actionable alerts in its final handoff. This is an in-session
reminder policy: no unattended scheduler, push/email/SMS service or billing access
has been configured. If the user is absent, no notification is guaranteed.

| Trigger, using actual account data | Required reminder/action |
| --- | --- |
| Plan/renewal/expiry/reset/cash baseline unknown | Ask once for the missing readings; keep them Unknown and continue already-included independent work |
| Subscription or necessary data entitlement renews/expires within 3 calendar days | State exact date, known all-in price, remaining work and headroom; suggest renew/cancel decision, never auto-pay |
| Allowance remaining <=20%, or a reported rate/weekly limit | State reset time; shorten scope, use included cheaper option if suitable, or wait; no automatic top-up |
| Short window reset is near | Distinguish that reset from monthly renewal and any weekly limit; renewing is not assumed to reset every limit |
| Included usage exhausted and a critical acceptance blocker remains | Propose at most the actual offered pack within daily/category/total caps after checking expiry/credit balance; otherwise wait/replan |
| Confirmed spend reaches INR 10,000 / 15,000 / 18,000 | Report target reached / full forecast review / essential-only reserve respectively |
| Proposed spend would exceed INR 20,000, or unknown baseline prevents checking | Do not purchase or start new optional paid usage; report the blocker and continue unaffected included/offline work |
| D07/14/21/28/35/42/49/56, D30, D45, D59 | Reconcile receipts, allowance, renewal dates, qualifying sessions and forecast; do not recharge merely because it is a checkpoint |

At D01 record actual renewal dates. Review the next month before it is charged,
not automatically on D30. A 60-day run can overlap three billing dates depending
on the existing cycle: record all actual charges and revise the envelope before
any additional renewal. Cancel/avoid an unnecessary renewal when coding is done.

### Daily operating loop and paper trading alongside development

1. Read the short handoff, current day, matching master rows and relevant code/Pine.
   Check `git status` to preserve user edits. Do not reload this entire README,
   SPEC, Pine or long logs on every turn; use targeted searches/line ranges.
2. Read latest ledger/usage facts; issue renewal/budget alerts. State the smallest
   dependency-ready batch, profile, token visibility and INR 0 default extra spend.
3. Before each actual market session, the user checks login, clock/calendar, feed,
   source/configuration identity, open paper positions, limits and kill/close route.
   Record a daily observation even if there are no signals or the system is blocked.
4. Implement related tasks together, reusing fixtures/contracts and accepted modules.
   One writer by default. Parallel work needs explicit user authorization, isolated
   ownership and a measured benefit; no duplicated paid reviews by default.
5. Run relevant meaningful checks during work and the required broader checks at
   batch integration. Re-run only after changes/failures/unresolved concerns. Save
   concise results and first failing evidence, not full repetitive tool output.
6. Update real master completions/evidence, task totals, day status, actual usage,
   receipts, paper evidence and `NEXT_SESSION.md` in the same change. A daily row is
   Completed only when its stated acceptance is met; partial rows stay Pending with
   done/remaining IDs. Split partial product tasks into stable sub-IDs when needed.
7. Final report: delivered IDs/checks, next batch, actual tokens or Unknown,
   cumulative cash/headroom or Unknown, qualifying sessions and next renewal alert.

From D01 the user may manually journal simulated decisions from the original Pine
chart in [paper-journal.csv](docs/plans/paper-journal.csv), using `MANUAL_PRACTICE`.
This plan does not implement that execution service, create any trade or claim a
day's profit. Record real observed prices and assumed fills/costs honestly; a day
with no signal is `NO_SIGNAL`, unavailable data is `BLOCKED`, and replay is `REPLAY`.
These are not qualifying automated burn-in sessions and do not become such later.

An **automated paper trial** can start as soon as the managed pipeline, paper fill/
position/ledger path, readiness/risk gates, manual close/kill and restart checks
are actually ready, without waiting for all frontend polish. Target D24-D30; use
authenticated operator APIs/commands first. Before then the current application
still does not simulate trades. Never place a real order to obtain paper evidence.

**Formal burn-in** starts only after G1/G2/G3, required failure drills and daily
shadow comparison setup pass. Target the first eligible session after D25. Count
only real exchange sessions with the documented release/configuration, daily notes,
shadow evidence and clean reconciliation. A clean zero-trade day may count as an
observed session. Manual practice, replay, outages and unverified days do not.
At least 20 qualifying sessions are required; D45/D60 do not waive that minimum.

Keep the market-hour paper release/configuration frozen. Develop against replay or
a separate test database off-session, without a second production socket/writer.
Deploy after close with backup/rollback; never restart/delete an active paper book
for a UI task. Strategy, fill, risk or accounting changes require a versioned new
baseline and an explicit decision to extend/restart affected observation evidence.
Expected operation notes continue every session even when coding allowance is
exhausted. Real defects, unavailable inputs/holidays or lost sessions move acceptance
later; schedule pressure does not authorize reduced controls.

### Day-by-day task batches and usage checkpoints

The table schedules **all 198** remaining tasks through paper release once as
primary targets. Work slices mentioned in the last column are not full completion
claims. Dependencies and actual evidence outrank the order; paired accounting/
execution work may need to be completed together. On a blocked/non-market slot,
take a ready independent UI/fixture task from a later day and record the move.
Do not wait for the next numbered day when a batch finishes early. Protect market
observation and budget; carry over unfinished IDs rather than buying speed blindly.
Day statuses below are separate from the 280 product-task counts.

| Day | Status | Batch / acceptance focus | Primary product IDs | Usage profile | Paper, budget or dependency action |
| --- | --- | --- | --- | --- | --- |
| D01 | Pending | Code Completed: correction + bounded retry; input still Pending | BE-05-10, BE-05-11, REF-00-03 | H; extra cash 0 by default | BE-05-10 through BE-05-17 and BE-06-01 through BE-06-11 and BE-13-01 Completed; latest checks below; REF-00-03 awaits actual settings. Billing/tokens Unknown; no recharge initiated. Next ready code: BE-13-02. |
| D02 | Pending | REST pacing and recording/checkpoint crash reconciliation | BE-05-12, BE-05-13, REF-00-04 | H; extra cash 0 by default | BE-05-12/13 Completed early on D01; REF-00-04 Pending. Keep original Pine intact. |
| D03 | Completed | Readiness, delay, recovery checks and explicit tick-fidelity policy | BE-05-14, BE-05-15, BE-05-16, BE-05-17 | H; extra cash 0 by default | BE-05-14/15/16/17 verified early on D01 with 290 tests and quality checks. Calibration/account readings remain Unknown; no entries enabled. |
| D04 | Completed | Managed worker ownership and initial typed contracts | BE-06-01, BE-06-02, BE-06-03, BE-13-01 | H; extra cash 0 by default | BE-06-01/02/03 and BE-13-01 Completed early on D01; 328 tests and quality checks passed. Dashboard auth next; no worker-control route activated. |
| D05 | Completed | Expiry, calendar, morning catalog and scheduled sessions | BE-06-04, BE-06-05, BE-06-06, BE-06-07 | H; extra cash 0 by default | BE-06-04/05/06/07 verified early on D01 using sourced 2026 calendar and fake broker/socket tests. Account/billing still Unknown; no purchase. |
| D06 | Pending | Day context, quality events, production replay and lifecycle tests | BE-06-08, BE-06-09, BE-06-10, BE-06-11 | H; extra cash 0 by default | BE-06-08/09/10/11 Completed early on D01 (308 tests); actual market recording/observation remains unperformed, so daily observation acceptance stays Pending. |
| D07 | Pending | Reference exports and real historical/feed checks | REF-00-05, REF-00-06, REF-00-07, QA-07-01, QA-07-02 | M; extra cash 0 by default | Weekly usage/cash review; input-dependent work stays Pending if exports/feed unavailable. |
| D08 | Pending | Reconnect evidence and ten-reference-day Renko acceptance | QA-07-03, QA-07-04, QA-07-05, QA-07-06, QA-07-07 | H; extra cash 0 by default | Historical exports can cover past sessions; never substitute synthetic G1 evidence. |
| D09 | Pending | Pine inputs and streaming RSI/ATR/Supertrend helpers | BE-08-01, BE-08-02, BE-08-03, BE-08-04, BE-08-05, BE-08-06 | H; extra cash 0 by default | Review seeding and equal-boundary behavior; one reusable sequence fixture. |
| D10 | Pending | Indicator state, once-only bricks, runs and swings | BE-08-07, BE-08-08, BE-08-09, BE-08-10 | H; extra cash 0 by default | Checkpoint schema first; avoid rewriting helpers already accepted. |
| D11 | Pending | Futures flow, daily alignment and maths-reference comparison | BE-08-11, BE-08-12, BE-08-13, BE-08-14 | H; extra cash 0 by default | Resolve first divergence before expanding signal logic. |
| D12 | Pending | CORE, divergence, pullback, breakout and trap signals | BE-09-01, BE-09-02, BE-09-03, BE-09-04, BE-09-05 | H; extra cash 0 by default | Port literal Pine rules; share fixture builders and state transitions. |
| D13 | Pending | Opening/flow signals, priority, odds, direction and grading | BE-09-06, BE-09-07, BE-09-08, BE-09-09, BE-09-10, BE-09-11 | H; extra cash 0 by default | Review cross-signal interaction in one coherent batch. |
| D14 | Pending | Trade IDs, indicator entries/exits, text and persistence | BE-09-12, BE-09-13, BE-09-14, BE-09-15, BE-09-16 | H; extra cash 0 by default | Weekly spend/usage/forecast review; no real-order path. |
| D15 | Pending | Indicator parity CLI, reference coverage and G2 review | BE-09-17, BE-09-18, QA-09-19, QA-09-20 | H; extra cash 0 by default | Reforecast timeline from measured accepted work; parity mismatch blocks formal burn-in. |
| D16 | Pending | Two-leg plan, option contracts/quotes and spread valuation | BE-10-01, BE-10-02, BE-10-03, BE-10-04, BE-10-05, BE-10-06 | H; extra cash 0 by default | Use catalog lot/expiry/strike data; no fabricated live quotes. |
| D17 | Pending | Paper wallet primitives and persisted broker/mode models | BE-12-01, BE-12-02, BE-12-03, BE-11-01, BE-11-13 | H; extra cash 0 by default | Use exact currency and migrations before execution implementation. |
| D18 | Pending | Sizing, margin, strike preview and strategy validation | BE-10-07, BE-10-08, BE-10-09, BE-10-10 | H; extra cash 0 by default | Size from initialized wallet; test missing/stale/illiquid instruments. |
| D19 | Pending | Paper fills, hedge-first lifecycle and durable idempotency | BE-11-02, BE-11-03, BE-11-04, BE-11-05, BE-11-06, BE-12-07 | H; extra cash 0 by default | Configure current cost assumptions; no blind retry of ambiguous fills. |
| D20 | Pending | MTM, exits, final entry gates and atomic margin/P&L | BE-11-07, BE-11-08, BE-11-09, BE-11-10, BE-12-04, BE-12-06 | H; extra cash 0 by default | Integrate accounting and execution as one batch; do not mark partial gates complete. |
| D21 | Pending | Top-ups, returns, summaries, history and ledger reconciliation | BE-12-05, BE-12-08, BE-12-09, BE-12-10, BE-12-11, BE-12-12 | H; extra cash 0 by default | Weekly budget and renewal-date review; prior task evidence decides next batch. |
| D22 | Pending | Kill/session locks, execution drills, repeatable replay and G3 | BE-11-11, BE-11-12, BE-11-14, QA-11-15, QA-11-16 | H; extra cash 0 by default | Check 20 strike examples; formal paper sessions require accepted G1/G2/G3. |
| D23 | Pending | Dashboard access and authenticated headless paper controls | BE-13-02, BE-13-03, BE-13-04, BE-13-08, BE-13-11, BE-13-15, BE-13-19 | H; extra cash 0 by default | Operator can inspect/close/kill paper positions before the full dashboard exists. |
| D24 | Pending | Feed/chart/signal snapshots; shadow-check service slice | BE-13-05, BE-13-06, BE-13-07 | H; extra cash 0 by default | Also build OPS-19-08 ingestion/comparison slice; its UI/master completion is D33. Trial only if ready. |
| D25 | Pending | Failure drills before formal paper observation | QA-19-11, QA-19-12, QA-19-13 | H; extra cash 0 by default | Prepare OPS-19-02 operator command slice; final packaging is D41. Shadow setup and readiness required. |
| D26 | Pending | History/settings/preview/alerts APIs; paper observation start target | BE-13-09, BE-13-10, BE-13-12, BE-13-13, BE-13-14 | H; extra cash 0 by default | First eligible exchange session after gates/drills/shadow setup; actual session count starts at zero. |
| D27 | Pending | Bounded WebSocket delivery, ordering and snapshot resync | BE-13-16, BE-13-17, BE-13-18 | H; extra cash 0 by default | Develop off-session against replay; run the stable paper release during market hours. |
| D28 | Pending | Frontend scaffold, shared UI, number/time formats and typed client | FE-14-01, FE-14-02, FE-14-03, FE-14-04, FE-14-05, FE-14-06 | M; extra cash 0 by default | Weekly budget review; check renewal due dates, not an assumed monthly reset. |
| D29 | Pending | Login, Kite status, top bar, wallet chip and kill dialog | FE-14-07, FE-14-08, FE-14-09, FE-14-10, FE-14-11 | M; extra cash 0 by default | Session-time read-only observation; merge UI changes after market close. |
| D30 | Pending | Socket reducers, shared error states, tests and contract generation | FE-14-12, FE-14-13, FE-14-14, FE-14-15, BE-13-20 | H; extra cash 0 by default | Formal D30 delivery/usage review; discuss second subscription only if actually due and useful. |
| D31 | Pending | Live Renko chart, history loading and indicator/event overlays | FE-15-01, FE-15-02, FE-15-03, FE-15-04, FE-15-05 | M; extra cash 0 by default | Use stable brick indices and shared fixtures; never redraw entire history per tick. |
| D32 | Pending | Trade/level overlays, toolbar, direction and active-position actions | FE-15-06, FE-15-07, FE-15-08, FE-15-09, FE-15-10 | M; extra cash 0 by default | Verify manual close/kill result semantics; preserve paper accounting baseline. |
| D33 | Pending | Live summaries, signals, alerts, resync and shadow UI completion | FE-15-11, FE-15-12, FE-15-13, FE-15-14, FE-15-15, OPS-19-08 | M; extra cash 0 by default | Complete shadow ingestion/comparison/UI row only with full evidence; retain earlier daily comparisons. |
| D34 | Pending | History cards, P&L charts, period tables and filters | FE-16-01, FE-16-02, FE-16-03, FE-16-04 | M; extra cash 0 by default | Daily paper session/reconciliation note; no strategy tuning during observation. |
| D35 | Pending | Trade table/details/export and consistency verification | FE-16-05, FE-16-06, FE-16-07, FE-16-08 | M; extra cash 0 by default | Weekly usage/cash and qualifying-session count review. |
| D36 | Pending | Wallet balances/deposit/withdraw/reset controls | FE-17-01, FE-17-02, FE-17-03, FE-17-04 | M; extra cash 0 by default | Do not reset the observation wallet or erase paper records. |
| D37 | Pending | Ledger/history options/top-up display and wallet verification | FE-17-05, FE-17-06, FE-17-07, FE-17-08 | M; extra cash 0 by default | Keep optional destructive UI unavailable unless its backend contract exists. |
| D38 | Pending | Settings forms, Pine defaults and strategy groups | FE-18-01, FE-18-02, FE-18-03, FE-18-04 | M; extra cash 0 by default | Match backend schema rather than duplicate validation rules. |
| D39 | Pending | Risk/data/display settings and versioned import/export | FE-18-05, FE-18-06, FE-18-07, FE-18-08 | M; extra cash 0 by default | Behavior changes use a new config/baseline; never alter the running burn-in silently. |
| D40 | Pending | Strike preview, dangerous-change controls and usability checks | FE-18-09, FE-18-10, FE-18-11 | M; extra cash 0 by default | Review whether D45 scope is achievable with remaining budget; retain failed acceptance rows. |
| D41 | Pending | Local serving, Windows commands/service and backup/restore schedule | OPS-19-01, OPS-19-02, OPS-19-03, OPS-19-04 | H; extra cash 0 by default | Use existing Windows machine; preserve secrets and verify separate-database restore. |
| D42 | Pending | Retention, access review and dependency audits | OPS-19-05, OPS-19-06, OPS-19-07 | M; extra cash 0 by default | Weekly spend/renewal review; fix actual findings, avoid unrelated rewrites. |
| D43 | Pending | Browser end-to-end acceptance flows | QA-19-09 | H; extra cash 0 by default | Run focused browser flows against replay; no interference with market-hour observation. |
| D44 | Pending | Browser/backend recorded-day reconciliation and latency checks | QA-19-10, QA-19-14 | H; extra cash 0 by default | Measure representative load; optimize demonstrated bottlenecks only. |
| D45 | Pending | Application candidate and verified operational guide | OPS-19-18 | M; extra cash 0 by default | Application target, not automatic G4/G5 acceptance; list remaining rows/session deficit. |
| D46 | Pending | Paper observation and first reserve-day defect triage | Carry-over/observations only; no new mandatory product IDs | L; extra cash 0 by default | Observe qualified sessions; prioritize safety/accounting defects and preserve evidence. |
| D47 | Pending | Review daily shadow mismatches and source quality | Carry-over/observations only; no new mandatory product IDs | L; extra cash 0 by default | A no-signal day can be a valid observed session; never invent a trade. |
| D48 | Pending | Targeted repair of an observed blocker, only if needed | Carry-over/observations only; no new mandatory product IDs | M; extra cash 0 by default | No blocker: use L and spend no extra tokens; record any burn-in extension. |
| D49 | Pending | Weekly ledger/usage/session-count review | Carry-over/observations only; no new mandatory product IDs | L; extra cash 0 by default | Calculate actual cash plus committed renewals; warn before crossing INR 15,000. |
| D50 | Pending | Paper session and backup evidence review | Carry-over/observations only; no new mandatory product IDs | L; extra cash 0 by default | Reuse daily operational checks; broad regression only after relevant changes. |
| D51 | Pending | Targeted remaining acceptance blocker, if present | Carry-over/observations only; no new mandatory product IDs | M; extra cash 0 by default | No blocker: downgrade to L; no paid usage to fill an empty schedule. |
| D52 | Pending | Paper/shadow review and unresolved-issue audit | Carry-over/observations only; no new mandatory product IDs | L; extra cash 0 by default | Inspect recorded observations, not just aggregate profit or win rate. |
| D53 | Pending | Review qualified-session count and remaining calendar | Carry-over/observations only; no new mandatory product IDs | L; extra cash 0 by default | Use real holiday/special-session calendar; reforecast if fewer than 20 qualified sessions. |
| D54 | Pending | Final necessary fixes and affected-path checks only | Carry-over/observations only; no new mandatory product IDs | M; extra cash 0 by default | Behavior-changing fixes may extend/restart observation; preserve old baseline. |
| D55 | Pending | Freeze release evidence and review readiness | Carry-over/observations only; no new mandatory product IDs | L; extra cash 0 by default | No unused-budget spending or speculative refactor; confirm next actual renewal. |
| D56 | Pending | Twenty-session and daily shadow evidence review | QA-19-15, QA-19-16 | L; extra cash 0 by default | Complete only if real observed-session/evidence requirements pass; otherwise remain Pending. |
| D57 | Pending | Paper G4/G5 acceptance review | QA-19-17 | M; extra cash 0 by default | All drills, reconciliation and observation evidence required; calendar date alone proves nothing. |
| D58 | Pending | Release handoff and remaining scope review | Carry-over/observations only; no new mandatory product IDs | L; extra cash 0 by default | Broader checks only for new changes/unresolved concerns; archive receipts and report actual spend. |
| D59 | Pending | Subscription/credit expiry and future-renewal decision | Carry-over/observations only; no new mandatory product IDs | L; extra cash 0 by default | Check actual account dates; notify about next charge; never automatically buy a third month. |
| D60 | Pending | Final scope, cash, observation and unfinished-task handoff | Carry-over/observations only; no new mandatory product IDs | L; extra cash 0 by default | Stop at budget cap; carry unresolved gates forward with dates and reasons, not false completion. |

### Usage ledger, cash records and reassessment

- [daily-log.csv](docs/plans/daily-log.csv): one initialized row per elapsed day;
  actual dates, inputs/outputs, allowance readings, costs and evidence are blank
  until observed. Fill `done_ids`, `remaining_ids`, `blocker` and `next_action` at
  each checkpoint. Do not overwrite earlier evidence or insert imaginary usage.
- [spend-ledger.csv](docs/plans/spend-ledger.csv): append actual all-in charges,
  category and sanitized receipt references. The starting history is unverified;
  reconcile it before reporting a remaining balance. Never store card/account
  numbers, access tokens, passwords or private callback URLs in these files.
- [paper-journal.csv](docs/plans/paper-journal.csv): separate manual practice,
  replay, automated trials and qualifying burn-in. Link large/raw sanitized
  evidence rather than embedding it in README or passing it all back to the model.
- D03: use measured tokens/allowance per accepted batch to revise H/M/L checkpoints.
  D15: resolve data/parity bottlenecks. D30: decide whether integrated paper is on
  schedule. D45: list every unresolved paper-release row. D60: report actual spend,
  accepted scope and session count; unresolved work stays Pending without a third
  month purchase being assumed. Unused budget is saved, not a spending target.

### Official pricing and account checks

Checked 2026-10-26: Plus lists USD 20/month with Codex included; local checkout,
tax and existing entitlements decide actual cash. Included usage varies by task;
the usage dashboard (or CLI `/status`) supplies allowance/reset information.
Purchased-credit rates and API rates are separate from included subscription usage.
See [official Codex pricing/usage](https://learn.chatgpt.com/docs/pricing?codex-pricing-plans=individual)
and [API pricing](https://developers.openai.com/api/docs/pricing) only if API use
is separately chosen. Recheck before renewal or any model/credit purchase.
Kite and TradingView entitlements must be checked against the actual accounts and
their current checkout pages; the INR allocations above are not product quotes.

**Next-session prompt:** `Read docs/plans/NEXT_SESSION.md and the current README
daily row. Check budget/renewal facts, then finish the next dependency-ready batch
using included Codex usage. Preserve paper observation, run required checks, and
update master statuses, daily usage, cash evidence and the handoff. Do not purchase
credits or mark unverified acceptance complete.`

<!-- END V2 EXECUTION PLAN: original product master record follows. -->

## Master task record: backend, frontend and release

**Last reviewed: 2026-10-26. This README is the authoritative task/status record.**
The specification describes intended behavior; an unchecked box in the original
specification is not evidence that implemented work is missing. The checklist below
was reconciled with the current application, tests and previous verification notes.

**Task totals: 280 — Completed: 82; Pending: 198.** Frontend: 57 Pending.
These are checklist counts, not time/effort percentages. Recount them whenever
rows are added, split or completed.

Status rules:

- **Completed** means the narrowly described implementation or verification is
  finished. Implementation tested with synthetic data does not establish real
  broker operation or TradingView parity; those have separate Pending tasks.
- **Pending** means work or its stated acceptance evidence remains. A phase stays
  Pending until all tasks required for that phase are Completed.
- Each row is a small actionable subtask, not a promise that it takes one minute.
  IDs are stable references for future work, reviews and AI handoffs.
- Existing completed work is dated by the verification notes: foundation/auth/catalog
  on 2026-10-23; data tools/recording/persistence on 2026-10-24. The latest recorded
  backend result is **328 passing tests, Ruff lint/format and mypy passing**
  (2026-10-26). This does not imply real-market verification.

### How every future contributor or AI must update this record

1. Read this master record, relevant code/tests, and the matching SPEC/Pine section
   before selecting work. Never restart a Completed task merely because chat history
   is unavailable. Keep the original Pine reference intact.
2. Select the next Pending task whose prerequisites are satisfied. Report its ID.
   Default next backend task: **BE-13-02**. Use the v2 daily batch and
   `docs/plans/NEXT_SESSION.md` for dependency-ready batching and usage checks.
3. Implement the scoped behavior and its meaningful acceptance checks. If only
   part is finished, split the row into stable sub-IDs and leave unfinished parts
   Pending; do not mark a broad phase Completed from a partial implementation.
4. In the same change, mark finished rows **Completed**, add completion date and
   file/test/manual evidence in the last column, recount task totals, update the phase overview and
   next-task pointer, and append a dated task-update entry below.
5. Keep external dependencies visible. Never label real-market checks, ten-day
   parity, paper burn-in or live-pilot gates Completed from synthetic tests.
6. If work changes scope, update the acceptance description and dependent IDs.
   Keep task IDs/history; do not delete unfinished tasks to make progress look better.
   Do not print credentials, session tokens or private callback URLs as evidence.
7. Prefer this README over secondary status summaries. Update or link secondary
   notes when their descriptions would conflict with this master record.
8. Follow v2 budget/renewal/paper-session checks on every future next-task turn.
   Read the compact handoff and relevant rows first; preserve real evidence,
   leave invisible usage/cash Unknown, and do not assume this plan buys credits.

### Ordered phases and frontend starting point

| Order | Phase | Status | Entry / exit condition |
| --- | --- | --- | --- |
| 00 | References and validation inputs | Pending | Pine saved; chart settings, debug export and reference fixtures still needed |
| 01–04 | Foundation, auth, instruments, standalone data/storage | Completed | Scoped implementation rows below completed; external checks remain in stage 07 |
| 05 | Historical warm-up and gap recovery | Completed | All 17 core tasks verified; synthetic acceptance matrix, recovery/readiness diagnostics and explicit tick fidelity policy implemented; managed lifecycle and real-market acceptance remain in stages 06/07 |
| 06 | Backend lifecycle and market calendar | Completed | All 11 managed-data core tasks verified; opt-in lifespan ownership, sourced calendar, recovery/selection/jobs/context/events and replay; real-feed acceptance and trading remain separate |
| 07 | Market-data acceptance gate G1 | Pending | Real downloads/feed, then zero Renko mismatches over ten trading days |
| 08–09 | Pine indicator port and acceptance gate G2 | Pending | Maths/state/signals/exits implemented and reference-verified |
| 10–12 | Strategy, paper execution, wallet and gate G3 | Pending | Reproducible option-spread trades, risk controls and accounting |
| 13 | Dashboard API and event contracts | Pending | Stable REST/WebSocket snapshots, actions and recovery semantics |
| 14–18 | Frontend foundation, Live, History, Wallet, Settings | Pending | Can start foundation now; integrate each screen as its BE services become available |
| 19 | Integrated paper release and acceptance | Pending | Browser replay, operational drills and paper burn-in completed |
| 20 | Live-money deployment and pilot | Pending | Later phase; not a prerequisite for frontend or paper-dashboard development |
| 21 | Explicit future extensions | Pending | Deferred beyond the single-user, single-underlying v1 scope |

**Frontend can start now at FE-14-01.** Build the shell, login/status and instrument
views against existing endpoints. Mock unavailable services explicitly after agreeing
contracts. Real charts depend on BE-06 and BE-13; indicator overlays depend on BE-08/09;
wallet/history/positions depend on BE-10/11/12 and their APIs. Starting frontend does
not imply the paper trading backend or live-money execution is ready.

### 00. Source references and validation inputs

These input tasks may run alongside implementation. User-provided chart settings
and TradingView exports must be real reference evidence, not invented fixtures.

| ID | Status | Task and completion requirement | Evidence / prerequisite |
| --- | --- | --- | --- |
| REF-00-01 | Completed | Save the original Pine script at its reference path and preserve its contents. | `docs/pine/renko_indicator.pine`; placed by user, 2026-10-24 |
| REF-00-02 | Completed | Preserve the original project specification for implementation decisions. | `docs/SPEC.md` |
| REF-00-03 | Pending | Record actual TradingView symbol, chart resolution, Traditional Renko box, close source, wick setting, timezone and grid anchor. Done when reproducible chart settings are documented. | Actual user chart; required for G1 |
| REF-00-04 | Pending | Create a separate Pine debug version exposing RSI, Supertrend, scores, signal flags and trade events for export. Keep the original unchanged. | REF-00-01; SPEC 18.2 |
| REF-00-05 | Pending | Export ten trading days of Renko OHLC and indicator/debug values with matching settings. Preserve original files and export metadata. | REF-00-03/04; TradingView export |
| REF-00-06 | Pending | Obtain matching spot minute closes, futures volume/OI and daily context for the reference period; record contract identities and rollover boundaries. | Historical downloader; REF-00-05 |
| REF-00-07 | Pending | Store sanitized reference fixtures, provenance and expected comparison tolerances; never modify expected values to hide a mismatch. | REF-00-05/06 |
| REF-00-08 | Completed | Record the complete granular roadmap and update rules in README for future user/AI sessions. | This master task record, 2026-10-24 |

### 01. Backend foundation

| ID | Status | Task and completion requirement | Evidence / prerequisite |
| --- | --- | --- | --- |
| BE-01-01 | Completed | Create Python backend package and uv project/lockfile; locked dependency setup works. | `backend/pyproject.toml`, `uv.lock`; setup verified 2026-10-23 |
| BE-01-02 | Completed | Load typed environment settings without requiring broker credentials to boot. | `app/config.py`, `test_foundation.py` |
| BE-01-03 | Completed | Provide blank credential template and exclude secrets, logs, local data and caches from Git. | `.gitignore`, `backend/.env.example` |
| BE-01-04 | Completed | Add FastAPI app factory, lifespan cleanup and PAPER-only health response. | `app/main.py`; health test and real HTTP check |
| BE-01-05 | Completed | Add JSON request/application logs, request IDs and size-based rotation without query/token values. | `app/logging_setup.py`, foundation tests |
| BE-01-06 | Completed | Configure pytest, Hypothesis, Ruff and strict mypy checks. | `backend/pyproject.toml`; latest recorded checks pass |
| BE-01-07 | Completed | Create SQLAlchemy engine/session foundation and Alembic migration environment. | `app/db/session.py`, `alembic/env.py` |
| BE-01-08 | Completed | Document Windows startup, health/docs URLs and repeatable quality-check commands. | Setup instructions in this README |

### 02. Kite authentication

| ID | Status | Task and completion requirement | Evidence / prerequisite |
| --- | --- | --- | --- |
| BE-02-01 | Completed | Redirect browser to official Kite login using configured API key. | `app/api/kite_routes.py`, `app/broker/kite_auth.py` |
| BE-02-02 | Completed | Bind temporary login state to an HttpOnly browser cookie with expiry and single-use validation. | `test_kite_auth.py` |
| BE-02-03 | Completed | Validate callback and exchange request token server-side using checksum; omit tokens from final redirect URL. | Auth callback tests |
| BE-02-04 | Completed | Save access token encrypted with Windows DPAPI and restore with the same Windows account. | Encrypted session restoration tests |
| BE-02-05 | Completed | Enforce next 06:00 IST session expiry and reject mismatched app keys. | Auth expiry/settings tests |
| BE-02-06 | Completed | Verify saved session through Kite profile; distinguish configured from authenticated. | `/api/auth/kite/status` and tests |
| BE-02-07 | Completed | Handle cancelled login, invalid state, rejected token and network/storage failures with safe responses. | Auth failure tests |
| BE-02-08 | Completed | Complete real browser login and verify authenticated status. | User verification recorded 2026-10-23 |

### 03. Instrument catalog

| ID | Status | Task and completion requirement | Evidence / prerequisite |
| --- | --- | --- | --- |
| BE-03-01 | Completed | Create instrument/snapshot tables using exchange + symbol identity and an Alembic migration. | `0001_instruments.py`, `app/db/models.py` |
| BE-03-02 | Completed | Download authenticated NSE/NFO catalog CSVs with safe connection errors. | `KiteAuth.download_instruments`, catalog tests |
| BE-03-03 | Completed | Validate headers, identities, expiry, numerical values and lot-size exceptions. | `app/broker/instruments.py`, parser tests |
| BE-03-04 | Completed | Atomically replace both exchange snapshots and preserve old data on bad downloads/transactions. | Catalog failure tests |
| BE-03-05 | Completed | Reuse today's catalog and reject stale NIFTY lookup until refresh. | Catalog freshness/cache tests |
| BE-03-06 | Completed | Resolve NIFTY spot, nearest nonexpired future, option expiries and selected expiry contracts. | `/api/market/nifty`, selection tests |
| BE-03-07 | Completed | Expose instrument status, manual refresh and expiry-filtered NIFTY endpoints. | `app/api/instrument_routes.py` |
| BE-03-08 | Completed | Verify actual catalog download and NIFTY selections. | Real NSE/NFO download recorded 2026-10-23 |

### 04. Existing standalone price tools, candles, recording and storage

These are completed implementation tasks. They do not claim automatic backfill,
managed FastAPI integration, real live-market validation or TradingView parity.

| ID | Status | Task and completion requirement | Evidence / prerequisite |
| --- | --- | --- | --- |
| BE-04-01 | Completed | Add authenticated minute/five-minute historical requests with optional futures OI. | `KiteAuth.historical_data`, `test_historical.py` |
| BE-04-02 | Completed | Split historical ranges into overlapping 30-day chunks with per-process historical request pacing. | `app/market/historical.py`; fake-clock tests |
| BE-04-03 | Completed | Validate OHLC/time/volume/OI, deduplicate identical overlap, reject conflicting data and omit unfinished candles. | Historical validation tests |
| BE-04-04 | Completed | Atomically export historical CSV with both opening and completed-close timestamps. | `app/tools/download_prices.py`, CSV replay test |
| BE-04-05 | Completed | Build exact decimal anchored Renko with inclusive continuation and two-box reversals. | `app/market/renko_builder.py`, property tests |
| BE-04-06 | Completed | Handle first-price seed, multi-brick gaps, increasing source timestamps and cross-day Renko continuity. | `test_renko.py` |
| BE-04-07 | Completed | Replay close/tick CSV inputs and compare every generated brick with a reference export; report first mismatch and exit status. | `app/tools/replay.py`, `parity_check.py` |
| BE-04-08 | Completed | Create credential-safe SDK market socket with bounded pending callbacks and tick queue. | `app/broker/kite_ticker.py`, `test_ticker.py` |
| BE-04-09 | Completed | Subscribe spot/futures in full mode and resubscribe after SDK reconnect; report exhausted attempts. | Fake-socket subscription/reconnect tests |
| BE-04-10 | Completed | Normalize SDK timestamps, reject invalid/older prices and retain valid same-second updates. | Timestamp and validation tests |
| BE-04-11 | Completed | Report per-token stale data, clock/feed delay, overflow and persistent gap flags with entries disabled. | Worker status tests; weekday calendar only |
| BE-04-12 | Completed | Provide standalone monitor CLI and safe shutdown that drains the accepted queue. | `app/tools/watch_prices.py`, shutdown tests |
| BE-04-13 | Completed | Aggregate completed one-minute spot candles without inventing volume or empty bars. | `app/market/candles_5m.py`, `test_candles.py` |
| BE-04-14 | Completed | Aggregate five-minute futures OHLC, cumulative volume deltas and latest OI; flag initial/gapped/counter-reset bars partial. | Candle sequence tests |
| BE-04-15 | Completed | Calculate session HLC3-volume VWAP, reset by IST date and retain partial-session quality flags. | VWAP/reset tests; Pine `ta.vwap(hlc3)` source |
| BE-04-16 | Completed | Finalize elapsed candles from clock events without reopening finished intervals on late packets. | Candle clock and late-packet tests |
| BE-04-17 | Completed | Record allowlisted accepted ticks/clock/gap events in versioned IST daily files isolated by run ID. | `app/market/tick_recording.py`, recorder tests |
| BE-04-18 | Completed | Replay recording events deterministically, preserve order and reject missing/reordered/mixed/corrupt input. | `app/tools/replay_ticks.py`, replay tests |
| BE-04-19 | Completed | Stop on recording write errors, exclude credential fields and verify disk-failure shutdown. | `test_tick_recording.py` |
| BE-04-20 | Completed | Add completed candle/brick/checkpoint tables and matching second migration. | `0002_market_state.py`; migration/model check |
| BE-04-21 | Completed | Save candle/brick/checkpoint changes atomically using exact decimal JSON strings. | `app/market/persistence.py`, rollback tests |
| BE-04-22 | Completed | Feed completed spot candles into persistent minute-close Renko with an explicit chart anchor. | `--stream` integration, persistence tests |
| BE-04-23 | Completed | Restore active candles, volume baseline, VWAP, recent completed bars and Renko seed/index/source timestamp. | `test_market_persistence.py` |
| BE-04-24 | Completed | Reject changed stream configuration and conflicting writers; mark downtime gaps on restart. | Configuration/concurrent-writer tests |
| BE-04-25 | Completed | Include initial restored candle checkpoint in new recording runs so candle replay still matches. | Restart recording/replay test |
| BE-04-26 | Completed | Apply market-state migration to the current local database. | Successful `uv run alembic upgrade head`, 2026-10-24 |

### 05. Historical warm-up and recovery — next backend work

Start after stages 01–04. Entry readiness must stay false until warm-up/recovery
has completed and quality checks pass. Reference-data tasks can run alongside this.

| ID | Status | Task and completion requirement | Evidence / prerequisite |
| --- | --- | --- | --- |
| BE-05-01 | Completed | Add typed warm-up lookback, recovery limits and readiness settings. Define first startup versus checkpoint restart; validate defaults and invalid values. | 2026-10-25: `backend/app/config.py`, `.env.example`, `test_warmup_settings.py`; startup policy below; 100 tests, Ruff and mypy passed |
| BE-05-02 | Completed | Plan exact spot-minute/futures-five-minute ranges from checkpoint and session calendar; include configured session lookback and the Pine futures-bar minimum; validate Renko brick sufficiency after rebuilding. | 2026-10-25: `backend/app/market/warmup.py`, `test_warmup_plan.py`; explicit calendar coverage and checkpoint boundaries; 115 tests, Ruff and mypy passed |
| BE-05-03 | Completed | Fetch and persist historical spot candles through the existing downloader; retain provenance and completion times. | 2026-10-25: `app/market/spot_history.py`, historical models/migration `0003_historical_spot.py`, `test_spot_history.py`; 128 tests, Ruff and mypy passed; local migration applied |
| BE-05-04 | Completed | Fetch/persist matching futures OHLC/volume/OI and daily previous-close/open/high/low context. Handle absent OI explicitly. | 2026-10-25: `app/market/context_history.py`, daily broker support, opt-in missing-OI parser, migration `0004_historical_context.py`; 152 tests, Ruff and mypy passed; local migration applied |
| BE-05-05 | Completed | Import historical candle volumes directly instead of treating them as cumulative tick counters; seed session VWAP correctly. | 2026-10-25: `CandleBuilder.import_completed`, `app/market/history_import.py`, `test_history_import.py`; direct-volume and session-quality checks; 169 tests, Ruff and mypy passed |
| BE-05-06 | Completed | Rebuild Renko in timestamp order from completed spot history while execution remains disabled. Make repeat imports idempotent. | 2026-10-25: `app/market/history_renko.py`, `test_history_renko.py`; atomic candles/bricks/checkpoint, no-write repeat and worker restore checks; 183 tests, Ruff and mypy passed |
| BE-05-07 | Completed | Merge historical and queued live data at an explicit timestamp boundary; prevent duplicate candles/bricks and half-formed closes. | 2026-10-26: `TickerWorker.start(buffer_only=True)` / `merge_history`, `test_history_renko.py`; explicit per-token fences, overlap filtering, partial-volume flags, failure/overflow and recording replay checks; 188 tests, Ruff and mypy passed |
| BE-05-08 | Completed | Detect reconnect, overflow and downtime gaps; track missing ranges and hold entry readiness false. | 2026-10-26: `app/market/gaps.py`, worker/persistence/recording integration, `test_gaps.py`; bounded per-token/cause spans, calendar-aware completed recovery ranges, restart and replay checks; 202 tests, Ruff and mypy passed |
| BE-05-09 | Completed | Recover missing minute/five-minute candles, rebuild affected derived state and preserve unrecoverable-quality flags. | 2026-10-26: `app/market/recovery.py`, persistence metadata retention, `test_recovery.py`; missing-only downloads, atomic source/output/checkpoint rebuild, retained partial/OI/missing flags, rollback/concurrent-writer/retry checks; 221 tests, Ruff and mypy passed |
| BE-05-10 | Completed | Define correction rules for existing partial candles and downstream bricks; rebuild affected outputs rather than silently retaining stale values. | 2026-10-26: explicit `correct_partial=True` recovery policy; atomic candle/VWAP/Renko rebuild, before/after market and staged-source audit, missing-source retention and rollback/idempotency tests in `test_recovery.py`; 241 tests and quality checks passed |
| BE-05-11 | Completed | Add bounded recovery retries/backoff for network/429 failures without deleting valid sessions or claiming recovery succeeded. | 2026-10-26: `recovery_requests.py`, safe transient metadata in `KiteAuth`; configured per-read attempts/capped backoff, numeric Retry-After, no retry of auth/validation, exhaustion/session preservation and no-write checks; 241 tests, Ruff and mypy passed |
| BE-05-12 | Completed | Coordinate request limits across managed REST calls; document standalone-process limits and avoid concurrent recovery storms. | 2026-10-26: process-wide `request_limits.py`; all managed REST paths share pacing/cooldown; fail-fast recovery guard; mixed-client, concurrent-request and overlapping-recovery tests in `test_request_limits.py`; 244 tests, Ruff lint/format and strict mypy passed |
| BE-05-13 | Completed | Reconcile recording events ahead of the last committed DB checkpoint after a failed transaction/crash; avoid double applying events. | 2026-10-26: atomic recording cursor in `persistence.py`; startup tail reconciliation in `recording_recovery.py`; synced recording appends, seed/config validation and per-event atomic resume; `test_recording_recovery.py` covers rollback, repeat restart, replay interruption, corruption and daily rotation; 257 tests, Ruff lint/format and strict mypy passed |
| BE-05-14 | Completed | Resume live processing only after warm-up/recovery validation; implement the SPEC post-warm-up entry delay. | 2026-10-26: `readiness.py`, `resume_validated_history`, revision/coverage/quality and candle/VWAP/Renko checks; monotonic entry hold after healthy queue drain; 18 new tests in `test_readiness.py`; all 275 tests, Ruff lint/format and strict mypy passed |
| BE-05-15 | Completed | Test cold start, mid-session restart, repeated recovery, day rollover, expired session, partial history and rollback. Preserve source fixtures. | 2026-10-26: `docs/testing/BE-05-acceptance.md` maps required cases to preserved source fixtures/tests; new expired-session and validation/adoption race/rollback tests; all 290 tests, Ruff lint/format and strict mypy passed |
| BE-05-16 | Completed | Expose recovery progress, last successful source time, failure reason and readiness state for later API/UI use. | 2026-10-26: thread-safe `RecoveryProgress` phases/range counts/committed source times/safe failure codes; recovery and worker handoff integration; worker status includes recovery and volatile readiness snapshots; rollback watermark/status tests; 290 tests and quality checks passed |
| BE-05-17 | Completed | Support explicit tick-mode restoration only if lost tick ordering is available; otherwise require rebuild or report unrecoverable fidelity. | 2026-10-26: `tick_restore.py` full-run rebuild requires explicit complete-order attestation and gap-free validated recording/calendar; equal-time sequence retained in tick Renko; missing ordering/seed/gap/corruption rejected with rebuild-required error; entries disabled; `test_tick_restore.py`; 290 tests and quality checks passed |

### 06. Managed backend worker, market sessions and scheduling

Depends on stage 05 for trustworthy readiness; lifecycle scaffolding may be built
earlier while trading remains disabled. Reuse existing tools instead of duplicating them.

| ID | Status | Task and completion requirement | Evidence / prerequisite |
| --- | --- | --- | --- |
| BE-06-01 | Completed | Move market worker ownership into FastAPI lifespan/service with one active worker and clean cancellation/disposal. | 2026-10-26: lifespan-owned `MarketService`, OS owner lock, one scheduler/worker, off-loop work joined on cancellation; `test_market_service.py`; 308 tests and quality checks passed |
| BE-06-02 | Completed | Select spot/futures tokens from today's catalog automatically; expose selected contract identity and detect token/contract changes. | 2026-10-26: current NSE/NFO snapshot gate, unique nearest unexpired NIFTY future selection; full metadata fingerprint creates a distinct stream and replaces old socket on token/contract change; integration tests passed |
| BE-06-03 | Completed | Add controlled worker start/stop/status operations and idempotent handling of repeated requests. | 2026-10-26: serialized in-process start/stop/status on `app.state.market_service`; repeated starts/opens/stops are idempotent; no unprotected HTTP control route; lifecycle tests passed |
| BE-06-04 | Completed | Handle broker login expiry/re-login by stopping/replacing the socket safely; recover gaps before declaring ready. | 2026-10-26: local expiry/private generation checks plus periodic server verification; stop on missing/expired login, reconcile/recover before replacement handoff and fresh hold; real recovery code tested with fake broker |
| BE-06-05 | Completed | Implement IST market sessions, annual holiday data and configured special sessions; replace weekday-only assumptions. | 2026-10-26: sourced `calendars/nse_2026.json`, holiday/Budget/Muhurat overrides; missing year blocks; calendar flows into worker/candle processing. Application 15:30 cutoff is distinct from published 15:40 F&O close. Sources in `docs/testing/BE-06-acceptance.md` |
| BE-06-06 | Completed | Refresh instruments on the morning schedule with retries and readiness blocking on stale/missing catalogs. | 2026-10-26: preparation-window catalog refresh, bounded retries/backoff, current-day snapshot/identity gate; stale or unavailable catalogs stop ownership path; transient success and exhaustion tests passed |
| BE-06-07 | Completed | Schedule login reminders, warm-up, feed start/stop and session rollover without duplicate jobs after restart. | 2026-10-26: one opt-in coroutine schedules pre-session preparation/login reminder/start/close and day rollover; reminders persist once per day, fresh catalog/checkpoints avoid duplicate jobs; lease prevents duplicate managed owners |
| BE-06-08 | Completed | Calculate previous/current day context and opening-range lifecycle using exchange times; preserve it through restart. | 2026-10-26: `session_context.py` computes exact prior/current committed-day values and first-15-minute range, retaining partial/missing flags; context persists in migration 0005 lifecycle table; complete/partial/restart/rollover tests passed |
| BE-06-09 | Completed | Publish structured health/readiness/quality events for stale feed, clock delay, recovery and session changes. | 2026-10-26: bounded structured session/contract/service/recovery/quality/context journal with sequence/run identity, deduplication, defensive snapshots and resync indications; internal producers ready for later API/WS contracts |
| BE-06-10 | Completed | Add tick-to-candle-to-Renko replay integration using the same production processing path; preserve provenance and partial flags. | 2026-10-26: `production_replay.py` reuses event reader, worker, candle and Renko persistence paths in a new isolated stream; source SHA-256/run/sequence and gap/partial evidence retained; repeat deterministic replay tests passed |
| BE-06-11 | Completed | Test backend startup/shutdown, duplicate starts, token change, session expiry, market close and missing holiday data. | 2026-10-26: 18 new lifecycle/calendar/replay/migration acceptance cases; `docs/testing/BE-06-acceptance.md`; all 308 tests, Ruff lint/format and strict mypy passed; local additive migration verified at 0005_market_lifecycle |

### 07. Market-data acceptance and Renko parity — G1

Implementation can progress while awaiting exports, but this gate remains Pending
until real reference comparisons pass. Never substitute synthetic tests for it.

| ID | Status | Task and completion requirement | Evidence / prerequisite |
| --- | --- | --- | --- |
| QA-07-01 | Pending | Verify real authenticated spot/futures historical downloads, timestamp boundaries and optional OI; store sanitized results. | Broker session/market-data entitlement |
| QA-07-02 | Pending | Observe real market-hours spot/futures ticks, stale flags, candle boundaries and daily recording. | Actual trading session; BE-06 |
| QA-07-03 | Pending | Verify a real controlled reconnect and restart restores/replays missing data without duplicate bars/bricks. | BE-05/06; QA-07-02 |
| QA-07-04 | Pending | Align TradingView grid, seed period and source history; verify wick/source assumptions with actual exports. | REF-00-03–07 |
| QA-07-05 | Pending | Run ten-day brick comparison, diagnose first mismatch, correct implementation and retain regression evidence. | QA-07-04; comparison CLI |
| QA-07-06 | Pending | Accept G1 only with zero open/close/direction mismatches across agreed reference days and documented settings. | QA-07-05 |
| QA-07-07 | Pending | Compare sampled live candle volume/OI/VWAP with historical data; document feed approximations and remaining partial flags. | QA-07-01/02 |

### 08. Pine maths, state and market context

Use `docs/pine/renko_indicator.pine` as the source of truth. These modules do not
exist yet. Build pure streaming functions with reference tests and explicit warm-up.

| ID | Status | Task and completion requirement | Evidence / prerequisite |
| --- | --- | --- | --- |
| BE-08-01 | Pending | Map Pine inputs/defaults to validated indicator settings without changing trading semantics. | Original Pine; SPEC input map |
| BE-08-02 | Pending | Implement SMA-seeded Wilder RMA with Pine-compatible missing-value/warm-up behavior. | Unit sequences; debug fixtures when available |
| BE-08-03 | Pending | Implement streaming RSI using the same smoothing and zero-gain/loss handling as Pine. | BE-08-02 |
| BE-08-04 | Pending | Implement true range and ATR on Renko OHLC with Pine seeding. | BE-08-02; brick OHLC |
| BE-08-05 | Pending | Implement Supertrend carry/flip rules and Pine direction convention; test equal-boundary behavior. | BE-08-04 |
| BE-08-06 | Pending | Implement crossover, crossunder, barssince, rolling sums/averages and series-history access with warm-up tests. | Pine helper semantics |
| BE-08-07 | Pending | Define persistent indicator state for all Pine `var` values and versioned snapshots. | Original Pine variable inventory |
| BE-08-08 | Pending | Process each completed brick once, in deterministic order; reject duplicate/out-of-order execution events. | BE-08-07; market pipeline |
| BE-08-09 | Pending | Track brick color, same-color runs, trend flips and trend age exactly as Pine. | BE-08-05/07/08 |
| BE-08-10 | Pending | Track swing tops/bottoms, prices, RSI values and brick ages at the exact Pine transition. | BE-08-03/09 |
| BE-08-11 | Pending | Build futures rolling price/OI windows, VWAP-side and prior-volume/SMA ratio with correct completed-bar alignment. | Stage 05 futures context; Pine flow timeframe |
| BE-08-12 | Pending | Implement futures build-up classifications, day comparison and final flow score; define missing-OI behavior. | BE-08-11 |
| BE-08-13 | Pending | Expose daily close/open/high/low and opening-range context to each brick using exchange-time alignment. | BE-06-08 |
| BE-08-14 | Pending | Verify RSI/Supertrend values against exported debug columns and stated tolerance; report first divergence. | REF-00-07; BE-08-03/05 |

### 09. Signals, grading, indicator trade engine and parity — G2

Depends on stage 08. Indicator trade state is distinct from actual option positions.

| ID | Status | Task and completion requirement | Evidence / prerequisite |
| --- | --- | --- | --- |
| BE-09-01 | Pending | Port CORE's Supertrend-flip alignment window and once-per-flip behavior. | BE-08-09; Pine CORE block |
| BE-09-02 | Pending | Port regular bullish/bearish divergence, equal/extreme price rules, RSI thresholds and max-gap expiration. | BE-08-10 |
| BE-09-03 | Pending | Port hidden and forming divergence with cross-day reset behavior. | BE-09-02; Pine divergence state |
| BE-09-04 | Pending | Port PB pullback-resume conditions and minimum trend age. | BE-08-09 |
| BE-09-05 | Pending | Port BRK swing crossing/age and TRAP failed-breakout windows. | BE-08-10; crossover helpers |
| BE-09-06 | Pending | Port ORB range, minimum boxes and IST cutoff rules. | BE-08-13; market calendar |
| BE-09-07 | Pending | Port SRG onset window, flow threshold and volume-spike requirement. | BE-08-12 |
| BE-09-08 | Pending | Resolve simultaneous signal priorities per direction and apply cooldown exceptions exactly as Pine. | BE-09-01–07 |
| BE-09-09 | Pending | Port outlook brick statistics, sample thresholds, support/resistance and stretch calculations. | Pine outlook block; state storage |
| BE-09-10 | Pending | Calculate ten-factor direction score, bias hysteresis and strong-bias threshold. | BE-08/09 factors |
| BE-09-11 | Pending | Port DIV/TRAP evidence grading and other-signal scoring, late-entry penalties and minimum-strength filtering. | BE-09-09/10 |
| BE-09-12 | Pending | Generate Pine-compatible five-character trade IDs and accepted/rejected signal explanations. | Pine ID/text helpers |
| BE-09-13 | Pending | Implement one-position indicator entry, same-direction ignore and T1/T2 targets from index price. | BE-09-08/11/12 |
| BE-09-14 | Pending | Evaluate exits before entries; implement opposite-brick, T2 and optional safety exits without same-entry-brick exits. | BE-09-13 |
| BE-09-15 | Pending | Track per-family/direction outcomes and reproduce explanation/tooltip text as structured data. | BE-09-12–14 |
| BE-09-16 | Pending | Persist indicator snapshots, results, signals and trade events with migrations and restart recovery. | BE-08-07; BE-09-15 |
| BE-09-17 | Pending | Extend parity CLI to maths, bias, flow, signal grades, IDs and ENTRY/T1/EXIT events. | REF-00 debug fixtures; BE-09-16 |
| BE-09-18 | Pending | Test all eight signals, priorities, cooldowns, missing context, day reset and exit/re-entry on the same brick. | BE-09-01–17 |
| QA-09-19 | Pending | Match every ENTRY/EXIT and required indicator series across ten reference trading days; retain mismatch/regression reports. | G1; REF-00 fixtures; BE-09-17/18 |
| QA-09-20 | Pending | Accept G2 and freeze the reference baseline/settings once parity passes; preserve later changes in a changelog. | QA-09-19 |

### 10. Option strategy and order plans

Depends on catalog, reliable live option quotes and indicator events. Use catalog
lot sizes, strikes and expiry dates; never hard-code them from SPEC examples.

| ID | Status | Task and completion requirement | Evidence / prerequisite |
| --- | --- | --- | --- |
| BE-10-01 | Pending | Define versioned signal-to-strategy input and two-leg TradePlan models. | BE-09 event contract; SPEC 11 |
| BE-10-02 | Pending | Select eligible expiry and enforce configured expiry-day policy. | Catalog expiries and session date |
| BE-10-03 | Pending | Select short/hedge strikes for bullish PE and bearish CE spreads using available strike grid. | BE-10-02; spot price |
| BE-10-04 | Pending | Subscribe candidate/traded option quotes with depth and track quote freshness. | Managed ticker; BE-06 |
| BE-10-05 | Pending | Reject unavailable/illiquid/wide-spread legs and invalid net credit; save reasons. | BE-10-03/04 |
| BE-10-06 | Pending | Calculate spread credit, defined maximum loss, stop/target references and leg quantities using exact amounts. | BE-10-05 |
| BE-10-07 | Pending | Size lots from settings and free capital; apply lot/tick rounding and configured caps. | BE-10-06; wallet/free-margin contract |
| BE-10-08 | Pending | Estimate required margin with configured buffer; separate paper estimates from broker-reported live margin. | BE-10-07 |
| BE-10-09 | Pending | Expose nonexecuting strike preview using the same selector/risk checks as actual plans. | BE-10-01–08; settings API later |
| BE-10-10 | Pending | Test both directions, absent strike/hedge, expiry day, changing lot size, stale quotes and insufficient credit. | BE-10-01–09 |

### 11. Paper broker, positions and risk

Wallet primitives in stage 12 can be developed alongside this stage; order and
wallet updates must form one coherent persisted lifecycle before G3.

| ID | Status | Task and completion requirement | Evidence / prerequisite |
| --- | --- | --- | --- |
| BE-11-01 | Pending | Define shared broker protocol, order/fill/position enums and persistence migrations. | SPEC 12/13; BE-10 TradePlan |
| BE-11-02 | Pending | Implement paper market fills from bid/ask or configurable last-price slippage, with `P-` order IDs. | BE-10-04; BE-11-01 |
| BE-11-03 | Pending | Implement touch-based limit fills, cancellation, simulated latency and deterministic fill timestamps. | BE-11-02 |
| BE-11-04 | Pending | Orchestrate hedge-first entries, fill tracking, partial failure and safe unwind; record every state transition. | BE-11-01–03 |
| BE-11-05 | Pending | Persist trade/leg/order/fill state machine; restore open paper positions after restart. | BE-11-04 |
| BE-11-06 | Pending | Use durable signal/order idempotency keys; repeated signals or retries cannot duplicate trades/fills. | BE-09 events; BE-11-05 |
| BE-11-07 | Pending | Monitor both leg prices, spread debit, MTM and realised/unrealised P&L with quote-quality checks. | BE-10-04; BE-11-05 |
| BE-11-08 | Pending | Close positions on indicator exits, premium stops/targets, manual close and configured time square-off. | BE-09-14; BE-11-07 |
| BE-11-09 | Pending | Enforce daily loss/max trades/position limits, entry window, capital and configured event restrictions. Persist rejects. | BE-12 accounting; SPEC risk rules |
| BE-11-10 | Pending | Enforce feed/session/recovery/clock readiness and one-position rules at the final entry gate. | BE-05/06; BE-11-09 |
| BE-11-11 | Pending | Implement kill actions from service/API and flag-file polling; cancel pending orders, close paper positions and lock entries. | BE-11-08/10 |
| BE-11-12 | Pending | Reset daily risk counters on valid session rollover; persist session loss-limit locks across restart. | BE-06 calendar; BE-11-09 |
| BE-11-13 | Pending | Represent PAPER/LIVE/armed state explicitly; startup stays PAPER and live sending remains unavailable until stage 20. | Current PAPER-only health; execution mode service |
| BE-11-14 | Pending | Test fill semantics, partial legs, duplicate events, manual/scheduled exits, kill, stale data and restart. | BE-11-01–13 |
| QA-11-15 | Pending | Run recorded market data through indicator, strategy and paper execution twice and prove identical trades/fills. | BE-06-10; G2; BE-11/12 |
| QA-11-16 | Pending | Accept G3 after strike preview matches 20 manually checked examples and risk rejects/end-to-end paper accounting agree. | BE-10-10; BE-11-14; QA-11-15 |

### 12. Wallet, costs, P&L and history storage

| ID | Status | Task and completion requirement | Evidence / prerequisite |
| --- | --- | --- | --- |
| BE-12-01 | Pending | Create mode/user-scoped wallet, ledger, trade summaries and daily P&L tables with indexes and migrations. | SPEC 13/16 |
| BE-12-02 | Pending | Initialize configured paper capital once and support positive exact-currency deposits within storage precision. | BE-12-01 |
| BE-12-03 | Pending | Support withdrawals limited to free balance and a reset ledger baseline; do not silently erase trade history. | BE-12-02 |
| BE-12-04 | Pending | Block/release spread margin atomically with order/position state; reject insufficient free balance. | BE-10-08; BE-11 lifecycle |
| BE-12-05 | Pending | Implement optional exact-shortfall auto-top-up as an auditable DEPOSIT entry. | BE-12-04 |
| BE-12-06 | Pending | Book gross realised P&L and separate costs exactly once on closure, including restart/retry handling. | BE-11-05/08; BE-12-04 |
| BE-12-07 | Pending | Implement configurable brokerage/tax/fee estimates and version their assumptions; do not hard-code outdated rates. | SPEC cost model; verify rates when implementing |
| BE-12-08 | Pending | Snapshot period-start capital and calculate margin/capital return percentages without counting deposits as profit. | BE-12-06/07 |
| BE-12-09 | Pending | Produce daily totals and derived weekly/monthly/all-time summaries consistent with trades and ledger. | BE-12-08 |
| BE-12-10 | Pending | Query history by date/mode/family/direction/grade/result with deterministic paging, detail and exports. | Trade indexes; BE-12-09 |
| BE-12-11 | Pending | Verify ledger identity nightly; alert on balance, margin, trade or daily-summary mismatch. | BE-12-06–10; scheduler |
| BE-12-12 | Pending | Test deposits/withdrawals, reset/open-position restrictions, repeated close, auto-top-up and period-boundary percentages. | BE-12-01–11 |

### 13. Dashboard access, REST APIs and live WebSocket contracts

Endpoints below are target work from SPEC 14. Existing health/Kite/instrument
routes remain valid; reconcile naming in the API contract rather than breaking them.

| ID | Status | Task and completion requirement | Evidence / prerequisite |
| --- | --- | --- | --- |
| BE-13-01 | Completed | Define shared Pydantic request/response/event schemas, error envelope, pagination, IST dates, rupee amounts and API compatibility. | 2026-10-26: `app/api/schemas.py`, existing route response models and shared sanitized error handlers; exact INR strings/IST/date/pagination/typed-event/version contracts; `docs/api/contracts.md`; 20 new cases in `test_api_contracts.py`; all 328 tests, Ruff lint/format and strict mypy passed |
| BE-13-02 | Pending | Add single-user dashboard password hashing, login/logout/status and secure session cookies; distinguish dashboard login from Kite login. | SPEC 17; not current Kite state cookie |
| BE-13-03 | Pending | Protect mutating routes and WebSockets with authentication/origin/CSRF rules; implement the specified five-failure login lockout and audit mutations. | BE-13-02 |
| BE-13-04 | Pending | Configure explicit development origins/proxy and production same-origin serving; never expose secrets to clients. | Frontend development contract |
| BE-13-05 | Pending | Add managed feed/readiness/status API and initial `/api/live/snapshot` with selected instrument and data-quality state. | BE-06; BE-13-01 |
| BE-13-06 | Pending | Add paged brick/candle/chart-history queries with indicator overlays and source/configuration identity. | Stored market data; BE-09 results |
| BE-13-07 | Pending | Add signals/decisions endpoints including rejected reasons and explanation text. | BE-09; BE-11 risk decisions |
| BE-13-08 | Pending | Add open-position, trade-detail, manual-close, decision-confirm and kill endpoints with idempotency and audit. | BE-11; BE-13-03 |
| BE-13-09 | Pending | Add trade filters/paging/detail and CSV export using the same query filters. | BE-12-10 |
| BE-13-10 | Pending | Add P&L summary, daily series, period tables and by-family statistics endpoints. | BE-12-09 |
| BE-13-11 | Pending | Add wallet read/deposit/withdraw/reset endpoints with validation and ledger paging. | BE-12; BE-13-03 |
| BE-13-12 | Pending | Add settings read/update/defaults/import/export schemas, versioned persistence and audit; require rebuild for grid changes. | BE-08 inputs; BE-13-03 |
| BE-13-13 | Pending | Add strike preview endpoint with no side effects; show missing quote/expiry/liquidity errors. | BE-10-09; BE-13-12 |
| BE-13-14 | Pending | Add alerts read/acknowledge service and persisted risk/recovery/reconciliation alerts. | BE-06/11 events |
| BE-13-15 | Pending | Add mode/status/arming contracts with paper-only behavior until live gate is enabled. | BE-11-13; later stage 20 |
| BE-13-16 | Pending | Implement one typed event hub and `/ws/live` with tick/brick/signal/trade/position/status/alert messages. | BE-13-01; managed producer services |
| BE-13-17 | Pending | Throttle high-rate tick events, bound slow-client queues and preserve reliable trade/alert delivery. | BE-13-16; SPEC update rates |
| BE-13-18 | Pending | Define snapshot/event ordering, sequence IDs and reconnect resync so browsers neither miss nor duplicate state changes. | BE-13-05/16/17 |
| BE-13-19 | Pending | Expose development replay with PAPER-only restrictions; disable it for armed/live operation. | BE-06-10; access controls |
| BE-13-20 | Pending | Generate/version OpenAPI and frontend client types; verify schemas and integration tests for auth/actions/WebSocket recovery. | BE-13-01–19; FE-14 tooling |

### 14. Frontend project, shared UI and data foundation

All frontend rows are Pending: no `frontend/` project exists yet. This stage may
start now; backend-dependent controls stay unavailable or use clearly labeled mocks.

| ID | Status | Task and completion requirement | Evidence / prerequisite |
| --- | --- | --- | --- |
| FE-14-01 | Pending | Create React + TypeScript frontend project, package lock, scripts and documented local start/build workflow. | Frontend starting task; SPEC technical choices |
| FE-14-02 | Pending | Add routes for Live, History, Wallet and Settings with persistent shell/navigation and not-found handling. | FE-14-01 |
| FE-14-03 | Pending | Define dark theme, spacing/type/color tokens, accessible contrast and reusable cards/buttons/inputs/dialogs. | FE-14-01; SPEC 15 |
| FE-14-04 | Pending | Add Indian currency/number grouping and explicit IST date/time/percentage formatters. | FE-14-01; API conventions |
| FE-14-05 | Pending | Add typed API client, development proxy/base URL, cancellation and consistent error handling. | Existing health/auth/catalog endpoints; BE-13 contracts |
| FE-14-06 | Pending | Add request cache/state management with separate server data and local display preferences. | FE-14-05 |
| FE-14-07 | Pending | Add dashboard login/logout/session-expiry screens with guarded routes. | BE-13-02/03; may mock initially |
| FE-14-08 | Pending | Add Kite login action and verified/configured/expired status UI without exposing broker secrets. | Existing `/api/auth/kite/login` and `/status` |
| FE-14-09 | Pending | Build top bar with underlying/price, Kite/feed/market chips and IST clock; render missing data honestly. | FE-14-03–08; BE-13-05 for live data |
| FE-14-10 | Pending | Add paper wallet chip/quick deposit and mode display; keep live controls unavailable until live implementation. | BE-13-11/15 |
| FE-14-11 | Pending | Add global kill dialog with pending/result/error feedback and duplicate-click prevention. | BE-13-08 |
| FE-14-12 | Pending | Implement one live-socket hook with reconnect/backoff, authentication handling and snapshot reload after reconnect. | BE-13-16–18 |
| FE-14-13 | Pending | Apply typed event reducers without duplicate trade markers or chart-wide rerenders on every tick. | FE-14-06/12 |
| FE-14-14 | Pending | Add explicit loading, empty, stale, disconnected, unauthorized and recoverable-error states across shared components. | FE-14-05/12 |
| FE-14-15 | Pending | Add unit/component tests, lint/typecheck/build scripts and accessible keyboard/focus behavior checks. | FE-14-01–14 |

### 15. Frontend Live screen

Build against agreed fixtures first if needed; mark mock data visibly. Connect
real behavior only as stage 13 and the indicator/paper services become available.

| ID | Status | Task and completion requirement | Evidence / prerequisite |
| --- | --- | --- | --- |
| FE-15-01 | Pending | Build responsive chart/cards layout and load initial live snapshot with quality/readiness banners. | FE-14 shell; BE-13-05 |
| FE-15-02 | Pending | Render no-wick Renko bricks with stable brick-index ordering, including multiple bricks sharing exchange time. | BE-13-06; chart library time-axis adapter |
| FE-15-03 | Pending | Add zoom to last 100/300 bricks, incremental updates and older-history loading without full chart rebuilds. | FE-15-02 |
| FE-15-04 | Pending | Render Supertrend segments/flips, bias tint and source/configuration identity. | BE-09 result data; FE-15-02 |
| FE-15-05 | Pending | Render ENTRY/T1/EXIT markers with family/direction/trade ID and detailed tooltips. | BE-09 events/text; FE-15-02 |
| FE-15-06 | Pending | Render entry/T1/T2/safety, ceiling/floor and next-brick price lines; remove/update them on position changes. | BE-13 snapshot/event models |
| FE-15-07 | Pending | Add chart toolbar layer toggles and persist display preferences. | FE-15-03–06; FE-18 display settings |
| FE-15-08 | Pending | Build direction/strength/score card and expandable ten-factor explanation. | BE-09-10/11 |
| FE-15-09 | Pending | Build active spread card with both legs, quantities, prices, MTM, margin return, targets, stop and duration. | BE-11-07; BE-13-08 |
| FE-15-10 | Pending | Wire manual close with confirmation, in-flight protection and final exit reason; do not assume success from button click. | FE-15-09; close API |
| FE-15-11 | Pending | Build last-closed-trade card with exit reason and realised results. | BE-12 summaries |
| FE-15-12 | Pending | Build Today card with trades/wins/net/capital return and daily-loss utilization. | BE-13-10; risk state |
| FE-15-13 | Pending | Build newest-first signal feed with grade/risk/accepted/rejected explanation. | BE-13-07 |
| FE-15-14 | Pending | Build persistent alerts strip/feed and acknowledgment with stale/recovery/login/limit states. | BE-13-14; FE-14-12 |
| FE-15-15 | Pending | Verify chart/event resync, repeated timestamps, empty history, stale prices and responsive layout using browser fixtures. | FE-15-01–14 |

### 16. Frontend History screen

| ID | Status | Task and completion requirement | Evidence / prerequisite |
| --- | --- | --- | --- |
| FE-16-01 | Pending | Build Today/Week/Month/All-time cards with net, capital return, trades and win rate. | BE-13-10 |
| FE-16-02 | Pending | Add daily P&L bars/cumulative line and monthly charts with consistent IST buckets. | BE-13-10; currency formatters |
| FE-16-03 | Pending | Add weekly/monthly summary tables with gross/costs/net/return and best/worst trade. | BE-12-09/BE-13-10 |
| FE-16-04 | Pending | Add date/mode/family/direction/result/strength filters, reset and URL persistence. | BE-13-09 filter contract |
| FE-16-05 | Pending | Build sortable paged trade table with SPEC date/time, signal, spread, quantity, price, cost, P&L and duration columns. | FE-16-04; BE-13-09 |
| FE-16-06 | Pending | Add expandable trade details: legs/fills, order timeline, signal explanation and trade chart. | BE-13-08/09 |
| FE-16-07 | Pending | Export CSV using active server filters, with progress/error handling and stable field names. | BE-13-09 |
| FE-16-08 | Pending | Test paging/filter changes, no-trade periods, zero denominators and consistency between tables/cards/charts/export. | FE-16-01–07 |

### 17. Frontend Wallet screen

| ID | Status | Task and completion requirement | Evidence / prerequisite |
| --- | --- | --- | --- |
| FE-17-01 | Pending | Show paper total/free/blocked capital and clear paper-money identity. | BE-13-11 |
| FE-17-02 | Pending | Add exact-currency deposit form and shared quick-add dialog; validate positive amounts and display server limits. | BE-12-02; FE-14-10 |
| FE-17-03 | Pending | Add withdrawal form showing available free funds and rejection reasons. | BE-12-03 |
| FE-17-04 | Pending | Add reset-to-amount flow with confirmation and open-position rules; preserve history by default. | BE-12-03; reset API |
| FE-17-05 | Pending | Add separately confirmed optional paper-history deletion only if the backend implements it. | SPEC reset option; destructive-operation API |
| FE-17-06 | Pending | Display paged ledger with DEPOSIT/WITHDRAW/PNL/COST/RESET and running balance. | BE-13-11 |
| FE-17-07 | Pending | Display auto-top-up setting/status and explain deposit versus profit treatment. | BE-12-05/08; settings API |
| FE-17-08 | Pending | Refresh wallet/top bar after mutations and trade closes; test duplicate clicks, insufficient funds and mode separation. | FE-17-01–07; live events |

### 18. Frontend Settings and usability

| ID | Status | Task and completion requirement | Evidence / prerequisite |
| --- | --- | --- | --- |
| FE-18-01 | Pending | Build settings loading, local edits, field errors, unsaved-change guard and save/result state. | BE-13-12 |
| FE-18-02 | Pending | Add Supertrend/direction/trade-plan groups with exact Pine defaults, bounds and tooltips. | BE-08-01; original Pine |
| FE-18-03 | Pending | Add divergence, extra-signal, flow and outlook groups with dependency-aware controls. | FE-18-02; Pine input map |
| FE-18-04 | Pending | Add strategy, lots, strikes, hedges, expiry policy and margin settings. | BE-10 settings contract |
| FE-18-05 | Pending | Add risk limits, entry windows, stops, square-off and paper fill/slippage controls. | BE-11 settings contract |
| FE-18-06 | Pending | Add data mode/box/anchor/lookback controls and explicit rebuild/progress feedback for grid changes. | BE-05; BE-13-12 |
| FE-18-07 | Pending | Add display layer preferences, alternative color palette and optional user-enabled sounds/notifications. | FE-15 toolbar; browser permissions on request |
| FE-18-08 | Pending | Add restore defaults and validated JSON settings import/export with schema version. | BE-13-12 |
| FE-18-09 | Pending | Add read-only strike preview and show selected expiry/legs/margin/credit or rejection details. | BE-13-13 |
| FE-18-10 | Pending | Add explicit confirmation for dangerous changes when enabled; record server audit outcome. | BE-13-03/12; no implicit live enablement |
| FE-18-11 | Pending | Verify backend/frontend default parity, invalid imports, stale edits, tooltips and keyboard-accessible forms. | FE-18-01–10 |

### 19. Paper release, security, operations and burn-in

These are delivery tasks, not claims about current readiness. Follow the SPEC's
paper-first acceptance gates; actual observation periods cannot be replaced by tests.

| ID | Status | Task and completion requirement | Evidence / prerequisite |
| --- | --- | --- | --- |
| OPS-19-01 | Pending | Serve the built frontend through FastAPI with SPA fallback and same-origin API/WebSocket routing. | FE-14–18; BE-13 |
| OPS-19-02 | Pending | Add repeatable Windows setup/run/backup scripts and IDE run configurations without overwriting existing secrets. | Stable backend/frontend commands |
| OPS-19-03 | Pending | Configure Windows service start/restart and graceful stop; verify one managed worker and no duplicate schedulers. | BE-06; OPS-19-01/02 |
| OPS-19-04 | Pending | Schedule close/report/ledger reconciliation/backups after the session; verify backup restoration on a separate database. | BE-11/12; BE-06 scheduler |
| OPS-19-05 | Pending | Add tick compression/retention, daily log rotation/90-day retention and 90-day P&L tick retention; preserve bricks/trades/audit data. | SPEC 13.6/17; current size-only logs |
| OPS-19-06 | Pending | Review localhost binding, dashboard access, secret redaction, cookie settings and cross-origin handling against implemented paths. | BE-13 security; no company-policy assumptions |
| OPS-19-07 | Pending | Add repeatable backend/frontend dependency audits and documented update checks; investigate actual findings. | Backend lockfile; FE package lock |
| OPS-19-08 | Pending | Add authenticated TradingView shadow-alert ingestion, event comparison and mismatch UI; never execute trades from alerts. | G2; BE-13/FE alerts; reachable webhook setup |
| QA-19-09 | Pending | Add Playwright flows for login/status, Live chart, history filters/export, wallet mutations, settings and manual close/kill. | FE-14–18; paper APIs |
| QA-19-10 | Pending | Replay a recorded day through backend and browser; reconcile chart markers, trades, wallet and history totals. | G3; QA-19-09 |
| QA-19-11 | Pending | Drill disconnect/overflow/token expiry and prove entries are blocked until recovery. | BE-05/06/11 |
| QA-19-12 | Pending | Drill crash/restart mid-position, partial-leg failure and duplicate signals without double booking fills or ledger entries. | BE-11/12; persistence |
| QA-19-13 | Pending | Drill daily-loss lock, kill switch, manual close, square-off retry and wrong-clock warning; retain results. | BE-11 controls; UI |
| QA-19-14 | Pending | Measure tick-to-brick-to-indicator under 50 ms and brick-to-order-dispatch under 1 second at representative load; diagnose bottlenecks. | SPEC budgets; end-to-end paper system |
| QA-19-15 | Pending | Run at least the specified 20 paper trading days with daily notes on signals, trades, rejects and anomalies. | G1/G2/G3; failure drills |
| QA-19-16 | Pending | Compare daily TradingView shadow events and review weekly results by family/grade/time; log one-at-a-time settings changes. | QA-19-15; OPS-19-08 |
| QA-19-17 | Pending | Accept paper burn-in gates G4/G5 from reconciled results, resolved anomalies and recorded failure-drill evidence. | QA-19-09–16; SPEC gate criteria |
| OPS-19-18 | Pending | Publish local operational guide covering morning login, startup, recovery, close, backup restore and troubleshooting. | Verified release behavior |

### 20. Later live-money deployment and controlled pilot

This phase is deliberately separate from the paper dashboard. Implementation rows
do not authorize placing live orders; explicit user-approved live operation and
the completed safety gates are still required for any real-money pilot.

| ID | Status | Task and completion requirement | Evidence / prerequisite |
| --- | --- | --- | --- |
| LIVE-20-01 | Pending | Verify then-current broker/exchange requirements, market-data/order permissions and registered static-IP setup before live implementation. | Official sources at implementation time; G4/G5 |
| LIVE-20-02 | Pending | Prepare production VM/static IP, HTTPS reverse proxy and restricted dashboard access; separate production configuration. | Deployment choices; LIVE-20-01 |
| LIVE-20-03 | Pending | Replace Windows-only DPAPI storage for the deployment environment and test secure daily session persistence/expiry. | LIVE-20-02 |
| LIVE-20-04 | Pending | Verify PostgreSQL migrations, decimal/time handling and checkpoint concurrency; add Compose configuration. | LIVE-20-02; current SQLite-tested schema |
| LIVE-20-05 | Pending | Add off-machine encrypted backups, retention, restore drill and operational health/feed alerts. | LIVE-20-02/04 |
| LIVE-20-06 | Pending | Implement LiveBroker through the shared protocol with one guarded real-order path and server-side risk/mode/armed checks. | BE-11; completed paper gates |
| LIVE-20-07 | Pending | Add durable broker tags/idempotency, status polling, bounded order pacing and network-ambiguity reconciliation before retry. | LIVE-20-06 |
| LIVE-20-08 | Pending | Handle partial live fills, hedge-first sequencing and failed-leg unwind without assuming an order succeeded. | LIVE-20-07 |
| LIVE-20-09 | Pending | Reconcile broker orders/positions/funds on startup and periodically; block entries on unresolved mismatch. | LIVE-20-06–08 |
| LIVE-20-10 | Pending | Implement explicit typed Live arming, restart-to-Paper behavior and optional manual decision confirmation. | BE-13-15; server-side controls |
| LIVE-20-11 | Pending | Connect frontend live warnings, read-only real funds, confirmation and reconciliation indicators without mixing paper wallet. | FE-14/15/17; LIVE-20-09/10 |
| LIVE-20-12 | Pending | Complete dry-run mode that logs plans but sends no live orders; verify every guard and failure path. | LIVE-20-06–11 |
| LIVE-20-13 | Pending | Verify broker-side protection and real close/kill/reconciliation procedure in the approved pilot setup. | LIVE-20-12; explicit pilot authorization |
| LIVE-20-14 | Pending | Run approved one-lot pilot for at least ten trading days, manual confirm on and small daily loss limits, with paper twin; review slippage/anomalies. | LIVE-20-13; user approval to trade |
| LIVE-20-15 | Pending | Accept G6 only after pilot review, reconciled records and all required controls pass. | LIVE-20-14; SPEC live gate |

### 21. Deferred extensions outside v1

These remain Pending but do not block the paper dashboard or single-underlying v1.
Start them only when the user selects that scope; no detailed implementation is
claimed before requirements are agreed.

| ID | Status | Task and completion requirement | Evidence / prerequisite |
| --- | --- | --- | --- |
| FUT-21-01 | Pending | Add Telegram/email delivery for selected alerts with preferences, retries and deduplication. | Later alerts integration; explicit service setup |
| FUT-21-02 | Pending | Add scheduled reports and richer performance analysis beyond required daily/weekly/monthly views. | Verified accounting; agreed report scope |
| FUT-21-03 | Pending | Add configurable BANKNIFTY/other-underlying support and independent fixtures; do not merely rename NIFTY symbols. | Stable v1; per-underlying reference validation |
| FUT-21-04 | Pending | Add multi-user account isolation, broker-app ownership and permissions after requirements review. | Currently single-user; SPEC later scope |
| FUT-21-05 | Pending | Design backtesting UI or mobile client only if requested; retain CLI replay as the current testing scope. | Explicit future requirements |

### Task update history

- **2026-10-26 (D01, D04 contract carry-over):** Completed BE-13-01 and the D04
  code batch. Shared Pydantic models now describe existing route responses, a
  sanitized request-correlated error envelope, bounded pagination, distinct IST
  timestamps/calendar dates, exact two-decimal INR strings and versioned typed
  events. Existing success shapes stay flat; Kite login's 303 redirect is correctly
  declared. API version headers and error schemas match runtime responses, including
  framework validation/HTTP and fixed unexpected-error handling without secret
  reflection. `docs/api/contracts.md` defines the first formal v1 compatibility
  policy. Twenty new contract cases; all 328 tests, Ruff lint/format and strict mypy
  passed (one existing dependency warning). No migration, real account/feed,
  observation, trade or purchase. Counts: 82 Completed / 198 Pending of 280.
  Next ready code: BE-13-02 dashboard authentication, distinct from Kite login.
  REF-00-03/04 remain external/independent work. Usage, cash/headroom and renewals
  remain Unknown; qualifying paper sessions remain zero.

- **2026-10-26 (D01, early D04-D06 BE-06 work):** Completed all 11 BE-06 tasks.
  FastAPI lifespan now owns an opt-in market service with a cross-process owner
  lease, idempotent in-process controls and clean cancellation/disposal. Current
  catalog identity changes and login replacement stop the old worker and require
  recovery/validated handoff. One coroutine schedules preparation, catalog retries,
  durable daily login reminders and session/day cleanup. Sourced 2026 annual and
  special-session data feeds workers/candles; missing years fail closed. Daily/
  previous/ORB context persists in migration 0005, structured internal events carry
  resync/run identity, and isolated replay uses production candle/Renko persistence
  with source hashes. Integration exposed and fixed the missing audited retirement
  of fully proven completed gap prefixes; unfinished live fragments remain partial.
  Added 18 acceptance cases: all 308 tests, Ruff lint/format and strict mypy passed
  (one existing dependency deprecation warning). Local additive schema upgrade to
  `0005_market_lifecycle` applied under the owner lock; market data was not replaced.
  See `docs/testing/BE-06-acceptance.md`. No real socket, observation, trade or purchase.
  Counts: 81 Completed / 199 Pending of 280. BE-13-01 is next; D04 stays Pending for
  that shared-contract task. D05 code batch Completed early; D06 code is complete
  but actual market recording/observation remains Pending. Cash, headroom, tokens
  and renewals remain Unknown; zero qualifying paper sessions.

- **2026-10-26 (D01, remaining early D03 batch):** Completed BE-05-15/16/17 and
  the 17-task stage 05 core. The preserved-fixture acceptance matrix is
  `docs/testing/BE-05-acceptance.md`; new tests cover session rejection and
  validation/adoption failure. `RecoveryProgress` exposes phases/range counts,
  committed per-token source times and fixed failure codes; worker snapshots add
  delay/readiness diagnostics without authorizing entries. Explicit tick restore
  requires complete captured ordering, validates gap-free files/calendar and
  preserves same-time sequence. Minute checkpoints, missing ordering and gaps
  require rebuild; no tick parity or enabled execution is claimed. All 290 tests,
  Ruff lint/format and strict mypy passed (one existing dependency deprecation
  warning). No migration, live observation, trade or purchase. Recount: 70 Completed
  / 210 Pending of 280. D03 Completed early; D01 awaits REF-00-03, D02 awaits
  REF-00-04. Next: BE-06-01 (D04). Tokens/allowance, cash/headroom and renewals remain
  Unknown. Zero qualifying paper sessions evidenced.

- **2026-10-26 (D01, early D03 work):** Completed BE-05-14. The explicit managed
  handoff validates source coverage, quality, builder/VWAP and recomputed Renko,
  checks the checkpoint revision, then adopts history and drains queued live data.
  A volatile monotonic hold begins only after a healthy handoff; minimum 60 seconds,
  no restart reuse. Entry eligibility also requires auth/session/indicator/live
  quality gates; gaps, invalid data and failed checks revoke it. Partial live
  volume is never authorized by elapsed time alone. Diagnostic paths stay disabled.
  Added 18 tests; all 275 tests, Ruff lint/format and strict mypy passed (one existing
  dependency deprecation warning). No migration, live market observation, trade or
  purchase. Totals: 67 Completed / 213 Pending of 280. Next: BE-05-15. D01 remains
  Pending for REF-00-03; D03 still needs BE-05-15/16/17. Usage, spend/headroom and
  renewal facts remain Unknown; qualifying paper sessions remain zero.

- **2026-10-26 (D01, early D02 work):** Completed BE-05-13. Recording-linked
  checkpoints now atomically retain the run/sequence cursor. Startup validates
  the frozen prior run and replays only its uncommitted tail before marking
  downtime and seeding the next run. Appends flush/fsync; old files stay intact.
  Thirteen new tests cover failed spot/futures/clock/gap transactions, repeat
  restart, a second crash during replay, invalid/missing files, daily rotation
  and same-timestamp updates. All 257 tests, Ruff lint/format and strict mypy
  passed; one existing dependency deprecation warning. No migration, live feed,
  trade, purchase or qualifying paper session. Product total: 66 Completed /
  214 Pending of 280. Next: BE-05-14; REF-00-04 remains independent and Pending.
  D01 remains Pending for REF-00-03; usage, spend/headroom and renewals Unknown.

- **2026-10-26 (D01, early D02 work):** Completed BE-05-12. All managed REST
  requests share process-wide serialization, 0.4-second pacing and numeric
  Retry-After cooldowns applied before releasing the request lock. Overlapping
  recoveries fail before database/source access and release their guard on errors.
  Added mixed-client/catalog cooldown, threaded pacing and overlap/failure tests.
  All 244 tests, Ruff lint/format and strict mypy passed (one existing dependency
  deprecation warning). No live feed, market observation, purchase or migration.
  Product totals: 65 Completed / 215 Pending of 280. Next: BE-05-13; D01 remains
  Pending for REF-00-03. Tokens, allowance, spend/headroom and renewals Unknown.

- **2026-10-26 (D01):** Completed BE-05-10 and BE-05-11. Recovery now supports
  opt-in completed-partial replacement with atomic downstream VWAP/Renko rebuild
  and before/after source provenance. Complete/unfinished bars are not replaced;
  absent correction sources remain partial. The historical read wrapper retries
  only classified transient failures with configured attempts/capped backoff;
  exhausted/auth/invalid responses cannot commit sources or derived state. Added
  20 tests; all 241 tests, Ruff lint/format and strict mypy passed. No migration,
  live broker request, order, purchase or recharge was performed. Recounted 280
  tasks: 64 Completed, 216 Pending. D01 stays Pending solely for REF-00-03 actual
  chart input; its template is `docs/pine/chart_reference.md`. Kickoff is 2026-10-26
  IST. Usage/account cash/renewal facts remain Unknown; no readings fabricated.
  Next ready coding batch: BE-05-13, with REF-00-04 independently available.

- **2026-10-26 (plan v2):** Preserved the exact prior README as
  `docs/plans/README.v1.md` with matching SHA-256. Added a 60-day execution schedule
  with D45 application target, all 198 pending paper-scope tasks mapped, included-
  usage-first token checkpoints, daily logs, in-session renewal/recharge alerts,
  INR 10,000 target / INR 20,000 ceiling, and manual/trial/formal paper separation.
  No subscriptions, reminders, trades or product implementations were activated.
  All 280 master task rows and statuses retained: 62 Completed, 218 Pending.
  Billing baseline/renewal and kickoff dates remain unverified. Documentation
  checks verify backup integrity, ID coverage, day/log/profile consistency and
  unchanged master rows; inherited application checks remain 221 passing tests.

- **2026-10-26:** Completed BE-05-09: offline `recover_missing_history` reads a
  consistent persisted stream, fetches only absent completed minute/five-minute
  candles and replays retained plus recovered sources to rebuild Renko and session
  VWAP. One revision-guarded transaction stages source provenance and replaces
  candles, bricks and checkpoint state. Missing source/OI and retained partial-bar
  flags stay explicit; entries stay disabled. Existing completed partial bars and
  staged source conflicts require the upcoming correction workflow. Elapsed active
  fragments are audited; unfinished fragments are retained as partial. Historical
  import/recovery metadata now survives ordinary checkpoint saves. Added 19 tests
  for uninterrupted-reference rebuild, idempotency, retries, failure rollback,
  concurrent writers, calendar/weekend behavior, quality flags and worker restore.
  All 221 tests, Ruff lint/format and strict mypy passed. Recounted 280 tasks:
  62 Completed, 218 Pending. Next: BE-05-10. No migration or live broker check was
  performed; managed startup, retries/backoff and entry readiness remain Pending.

- **2026-10-26:** Completed BE-05-08: detect disconnect/reconnect, bounded
  callback/queue overflow and checkpoint downtime; track unresolved spans per
  instrument and cause without clearing quality flags on reconnect. Persist gap
  metadata on worker saves and connection events, and replay recorded gap events.
  Older queued ticks cannot close gaps detected later. Calendar-supplied recovery
  ranges include only completed affected buckets, exclude non-session periods and
  retain unfinished buckets for later passes. Metadata remains bounded using
  conservative envelopes, which can include intact intervals between incidents.
  Added 14 synthetic tests; all 202 backend tests, Ruff lint/format and strict mypy
  passed. Recounted 280 tasks: 61 Completed, 219 Pending. Next: BE-05-09.
  No real feed verification, recovery implementation or entry readiness is claimed.

- **2026-10-26:** Completed BE-05-07: the worker can subscribe into a bounded
  queue while history is initialized, adopt a persisted seed at explicit per-token
  boundaries and then consume queued ticks in order. Historical overlap is skipped
  before live state/recording changes; unfinished buckets remain open. Missing tail
  intervals are fenced for later recovery, and futures volume starts from a fresh
  cumulative baseline with partial-quality flags. Fences are persisted before queue
  release; failed adoption stays blocked. Added five tests for overlap, same-second
  updates, unfinished closes, restore, invalid boundaries, overflow, failed saves,
  shutdown and recording replay. All 188 tests, Ruff lint/format and strict mypy
  passed. Recounted 280 tasks: 60 Completed, 220 Pending. Next: BE-05-08.
  Managed startup, gap recovery, entry delay and real-market parity remain Pending.

- **2026-10-25:** Completed BE-05-06: rebuild minute-close Renko from staged
  spot candles in exchange-close order and atomically initialize candles, bricks
  and a restorable checkpoint. Identical repeats issue no writes; changed source,
  configuration, active state and orphaned outputs fail without replacement.
  Execution stays disabled and checkpoint gap/quality metadata remains explicit.
  Added 14 tests including reversals, multi-brick closes, cross-day continuity,
  seed-only history, rollback, idempotency and existing-worker restoration.
  All 183 tests, Ruff lint/format and strict mypy passed. Recounted 280 tasks:
  59 Completed, 221 Pending. Next backend task: BE-05-07. No new schema migration
  is needed. Historical/live merge, indicator readiness and real parity remain Pending.

- **2026-10-25:** Completed BE-05-05: direct-volume historical candle import
  and deterministic isolated spot/futures seeds from staged history. Session VWAP
  uses exact HLC3-weighted bar totals, resets per IST session, and preserves missing
  history flags. Source volume is never treated as a cumulative exchange counter;
  the first live counter sample retains partial quality. Added 17 tests covering
  weighted values, gaps, zero volume, restart state, repeat reads, source-boundary
  validation and conservative live handoff. All 169 tests, Ruff lint/format and
  strict mypy passed. Recounted 280 tasks: 58 Completed, 222 Pending. Next backend
  task: BE-05-06. Live adoption, Renko rebuild and readiness remain Pending.

- **2026-10-25:** Completed BE-05-04: atomically stage explicit-contract futures
  five-minute OHLC/volume/OI and daily spot context. Added daily broker requests,
  opt-in missing-OI support (null remains distinct from zero), contract identity
  provenance and migration 0004, applied locally. Current-session context uses
  completed minutes through the cutoff; missing prior-day values stay unknown.
  Added 24 tests; all 152 backend tests, Ruff lint/format and strict mypy passed.
  Recounted 280 tasks: 57 Completed, 223 Pending. Next backend task: BE-05-05.
  Real broker acceptance, VWAP seeding, derived-state updates and readiness remain
  Pending. Official Kite historical API documentation was checked for day/OI and
  explicit contract request semantics.

- **2026-10-25:** Completed BE-05-03: fetch planned spot-minute ranges through
  the existing downloader and atomically stage exact candles, completion times
  and source/request provenance. Added migration 0003 and applied it locally.
  Catalog identity checks, repeat imports, missing minutes, conflicting data and
  network/database rollback have synthetic acceptance coverage (13 new tests).
  All 128 backend tests, Ruff lint/format and mypy passed. Recounted 280 tasks:
  56 Completed, 224 Pending. Next backend task: BE-05-04. No real-market download,
  indicator warm-up, live merge or readiness claim is made by this task.

- **2026-10-25:** Completed BE-05-02 with pure session-calendar range planning,
  separate checkpoint boundaries, completed-candle cutoffs, recovery gap limits,
  current-session futures VWAP context and previous-session daily context date.
  Added 15 planner checks; all 115 backend tests, Ruff and mypy passed. Recounted
  280 tasks: 55 Completed, 225 Pending. Next backend task: BE-05-03.
  Production calendar loading, downloads/imports and post-rebuild indicator
  readiness remain their separate Pending tasks.

- **2026-10-25:** Completed BE-05-01 with bounded typed warm-up/recovery/readiness
  settings, environment examples, startup policy and 18 configuration checks.
  All 100 backend tests, Ruff lint/format and strict mypy passed. Recounted
  280 tasks: 54 Completed, 226 Pending. Stage 05 remains Pending; next is
  BE-05-02. Historical fetching, recovery and readiness enforcement are not
  implemented by this settings task.

- **2026-10-24:** Added the master granular BE/FE/QA/operations/live/future task
  record and completion-update rules (REF-00-08 Completed). Reconciled current
  implementations through persistence against code and recorded 82-test validation.
  Next backend item is BE-05-01; frontend can independently start at FE-14-01.
  No application features were changed by this documentation task.

## Shared API contracts (BE-13-01)

[API v1 contract rules](docs/api/contracts.md) document the shared models in
`backend/app/api/schemas.py`: existing response DTOs, safe error envelopes,
request IDs, aware IST timestamps, explicit exchange dates, exact INR strings,
pagination and typed event envelopes. Existing route success shapes are retained;
all HTTP responses advertise `X-AUREVON-API-Version: 1.0`. Errors use the shared
shape and never return raw validation inputs/context or unexpected exception text.
Current response models and the Kite login 303 redirect match OpenAPI.

This is the contract foundation. Dashboard authentication, mutation/origin/CSRF
protection, managed feed APIs and public WebSocket wrapping remain their Pending
BE-13 tasks. No worker controls or trading routes are exposed by this change.

## Managed market lifecycle (BE-06)

All 11 BE-06 core tasks are complete. [Acceptance evidence and sourced calendar
policy](docs/testing/BE-06-acceptance.md) records the exact tests and external-data
boundaries. `create_app` owns `app.state.market_service`; its asynchronous
`start()`, `stop()` and `status()` operations are trusted in-process controls.
No public HTTP start/stop route or WebSocket was added before the later shared
schema/authentication work. `MARKET_SERVICE_ENABLED=false` is the default, so
normal application startup does not log in, download data or create a market socket.

The opt-in service uses the existing local database and broker client, one owned
worker and an OS lease (`data/market-worker.lock`) shared across managed processes.
A second owner fails before opening a socket. One coroutine handles the known
session's preparation window, bounded catalog refresh retries, one persisted daily
login reminder, warm-up/feed start, login/token replacement, session close and day
rollover. Blocking work runs off the event loop and is joined before disposal.
Fresh current-day NSE/NFO metadata and an exact selected contract are mandatory.
Contract/token/lot/tick metadata changes create a separate stream fingerprint.
Original checkpoints and recordings are retained; no current book is overwritten.

Managed startup runs the accepted cold/recovery stages, reconciles original
recording tails first and catches history up to stable handoff fences. A fresh
validated drain/hold is required after replacement. Fully checked completed gap
prefixes now retire with their original incident snapshots, source revision and
fences retained in checkpoint audit metadata. Partial completed sources, missing
bars/OI, mismatched VWAP/Renko, unfinished active state and new buffered gaps still
block validation; fresh live volume fragments remain partial and cannot authorize
entries merely because a delay elapsed. The service always reports entries false.

The bundled annual data covers 2026, including the Budget Sunday and Muhurat
session. Session windows propagate to the worker and candle builder, replacing
weekday-only logic on this managed path. Unknown/missing years block startup,
including a prior year required by the history window. Update sourced files before
crossing into an uncovered year. The 15:30 shared processing cutoff is an
application policy; NSE currently lists a 15:40 normal F&O close. See the linked
source notes rather than treating an application cutoff as an exchange timetable.

Committed spot minutes and exact prior-session daily sources drive evolving daily
context and the first-15-minute range. Unknown prior data stays unknown; partial
range evidence never becomes complete by clock alone. The new lifecycle table
stores context/reminder facts. Bounded internal quality/recovery/session events
carry sequence/run identity and resync indications for later APIs. Production
replay requires a new isolated stream and preserves file hashes, run/sequence,
source flags and the same candle/Renko persistence path.

Migration `0005_market_lifecycle` is applied to the local database. It adds the
lifecycle table without replacing market source/output tables. Environment examples
list the opt-in controls and path defaults; the existing `.env` was not changed.
Real broker/feed operation, TradingView comparison, operator API authentication,
indicator integration and paper execution/burn-in remain separate Pending tasks.

## Recovery diagnostics and tick-restoration policy (BE-05-15/16/17)

The [synthetic acceptance matrix](docs/testing/BE-05-acceptance.md) records the
cold start, mid-session restart, repeated recovery, day rollover, unavailable
valid broker session, partial history and rollback evidence. Fixtures and original
Pine content are preserved. These tests do not replace real-feed/parity or paper
acceptance gates.

Pass a shared `RecoveryProgress` through `recover_missing_history(..., progress=...)`
and `TickerWorker(..., recovery_progress=...)` to observe planning, downloading,
rebuilding, committing, validating, draining, complete and failed phases. Download
progress counts requested source ranges (not HTTP attempts or a percentage of all
work). Per-token `last_successful_source_time` reports the latest committed source
candle end; it is not proof of contiguous coverage. Failed downloads/transactions
do not advance those times. A restored worker recovers committed source diagnostics
while readiness remains blocked. Duplicate recovery calls fail before disturbing
an active run's progress. Use one lifecycle owner and quiescent writer.

`worker.status()` includes JSON-ready `recovery` and `readiness` snapshots. Failures
use fixed public codes, never raw exceptions, credentials or broker response bodies.
Readiness reports awaiting validation, delay, blocked or elapsed hold, remaining
seconds and external gates still required; every snapshot leaves entries disabled.
Snapshots do not advance or authorize a gate. A completed recovery can still have
quality pending. Progress/failure records are process-local diagnostics; failure
history is not a durable audit log, and no API route/UI has been activated here.

`restore_tick_renko(paths, box=..., anchor=..., calendar=...,
ordering_complete=True)` explicitly rebuilds tick-mode Renko from a complete frozen
recording run. The caller must establish complete captured ordering. The function
validates recording sequence/tokens/timestamps and calendar eligibility; it rejects
gaps, truncated/missing/out-of-order files and minute-checkpoint seeds. Equal-time
spot updates retain recording order, which may materially change bricks. Futures
updates and clock events do not drive spot Renko. The result contains rebuilt state,
bricks, sample count, source run and `recorded_order_only` fidelity; entries stay
false. No exchange-wide tick completeness or TradingView parity is inferred.

Without explicit complete ordering, `TickFidelityError` reports
`rebuild_required=True`. Candles never synthesize missing tick order. Retain/recover
complete ordered source files or explicitly rebuild under a new minute-close
baseline. Persistent database checkpoints and managed resumption remain
minute-close only; arbitrary tick checkpoint continuation is not supported.

## Validated managed resumption and entry hold (BE-05-14)

`await worker.resume_validated_history(store, boundaries, settings, calendar)` is
an explicit managed handoff for a fresh running worker started with
`buffer_only=True`. Call it on the worker event loop with the persistence writer
quiescent. The existing `merge_history` and standalone monitor remain diagnostic;
they never start the managed eligibility timer.

Before adopting history, the validator checks the configured completed-session
lookback plus current completed candles, exact per-token unfinished-bucket fences,
source counts, quality flags and idle builders. It recomputes candles, futures
VWAP and all retained spot-close Renko bricks, comparing them with stored outputs
and checkpoints. Calendar coverage is required for retained source dates. Missing
history/OI/VWAP, partial source/active state, changed settings, inconsistent derived
state or unresolved recovery flags block handoff. Retained incident markers can retire for their completed prefix only after full
affected source coverage and derived-state checks. Original gaps, source revision
and per-token completed fences are archived in `validated_recovery`; the fresh
unfinished live bucket remains partial. No missing tick order is inferred.
Extend history when there are no emitted bricks. This does not prove the future
indicator engine's lookback sufficiency or TradingView parity.

The checked revision must still match during restore, and any new buffered feed
gap blocks adoption. Only then is queued processing released. After the queue
drains, the consumer must still be alive, both feeds fresh and connected, and the
handoff free of new invalid/dropped data, unresolved gaps and clock/feed delay.
Failures or cancellation leave the hold revoked and processing paused; stop and
recover into a fresh worker. Recording reconciliation remains required first.

The configured hold (minimum 60 seconds) starts after that successful drain, using
a monotonic elapsed clock. No eligible state is restored across restart. New gaps,
invalid live ticks, observed stale intervals, backward clock readings or a failed
eligibility check revoke it; a fresh validated handoff and full hold are required.
`entry_eligible` additionally defaults authentication, session eligibility and
indicator readiness to false, and checks live feed/queue/consumer and forming
candle/VWAP quality. In particular, an initial partial live volume fragment still
blocks entry after the timer expires. Callers must supply verified external gate
values and enforce final execution, position and risk rules in their later stages.

This task supplies the managed primitive; stage 06 now owns its lifecycle. Stage
08 indicator integration remains Pending. There is no bypass setting, order path,
activated paper execution or live-market acceptance evidence. The existing monitor
still reports `entries_enabled=False`.

## Recording and checkpoint crash reconciliation (BE-05-13)

When persistence and recording are both enabled, `TickerWorker` commits an initial
recording checkpoint before accepting events. Each subsequent DB transaction stores
its recording run/sequence cursor together with candle, VWAP, Renko and gap state.
Recording appends flush and call `fsync` before advancing the cursor. This adds
synchronous disk I/O; representative-load performance remains a separate gate.

On restart, the worker locates the previous run under the supplied recorder root,
validates the entire frozen run (sequence, tokens, configuration, timestamps and
replay payloads), then applies only events beyond the committed cursor. Each event
and its cursor commit together; a second crash resumes from the last successful
commit. Old events are not re-recorded. Tick, clock and gap events are supported,
including same-time updates and daily rotation. Replay finishes before marking
new downtime uncertainty and committing the new recording seed; entries remain
outside this recovery service and are not enabled by reconciliation.

Retain all daily files from the referenced run, including its checkpoint seed.
Missing files, truncated lines, identity/configuration mismatches or a missing
committed event stop startup before reconciliation writes. Stop the writer and
retain files for explicit rebuild; do not trim/guess a damaged tail. Use one
quiescent writer and frozen files: concurrent file edits and other processes are
not supported. A recording-linked checkpoint requires the original recorder root,
even when restarting without a live socket. Reconcile before historical correction.

Legacy checkpoints without a recording cursor still restore as before; automatic
linkage to old independent recordings cannot be inferred. Use explicit replay or
rebuild for those historical crash tails. No schema migration, real-market replay,
trade execution or formal paper-session evidence is implied by synthetic tests.

## Managed REST coordination (BE-05-12)

All `KiteAuth` instances in one process share a conservative 0.4-second minimum
between REST request starts, including login, profile, instruments, historical
reads and recovery retries. Requests are serialized through completion; numeric
finite nonnegative Retry-After on 429/service errors extends the shared cooldown
before another caller can send. Existing bounded recovery retry policy still
controls whether the recovery retries or fails. This is an application policy,
not a broker quota guarantee. Run these blocking calls off the async event loop.

Only one managed `recover_missing_history` call may run per process. A concurrent
call raises `RecoveryBusyError` immediately, before database/source access; retry
later after the active run finishes. The guard releases on success or failure.
The stream writer must still be stopped and checkpoint revision checks still apply.

These locks do not coordinate separate processes, external scripts/SDK REST calls,
or other applications using the same account. Run one backend worker and do not run
standalone downloads/recovery alongside it; stop managed work first, or implement
an account-wide external coordinator before adding processes. WebSocket traffic is
outside the REST limiter. No broker-limit or real-market verification is claimed.

## Setup and operating instructions

The sections below explain the current implementation. Use the master record
above for current task statuses and future sequencing.

## Step 1: run the backend

Use PowerShell. Python 3.12 and uv must be installed.

```powershell
cd D:\WorkSpace\AUREVON\backend
uv sync --locked
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000 --no-access-log
```

Copy `.env.example` only on the first setup; do not overwrite an existing `.env`.
Keep the terminal running. Press Ctrl+C to stop the server.

Open these addresses:

- http://127.0.0.1:8000/docs — interactive API documentation.
- http://127.0.0.1:8000/api/health — application status.
- http://127.0.0.1:8000/api/auth/kite/status — session status, verified with Kite when logged in.

Expected health response:

```json
{"status":"ok","application":"AUREVON","mode":"PAPER","live_orders_enabled":false}
```

The server starts without any Kite keys. `configured: false` is expected initially.
If you see `No pyproject.toml found`, change to the `backend` directory first.
If port 8000 is occupied, stop your previous server before starting another.

If login ends with `ERR_CONNECTION_REFUSED`, check the address in the browser.
The Kite redirect must be `http://127.0.0.1:8000/api/auth/kite/callback`.
An address such as `http://127.0.0.1:8080/kite/callback` has both the wrong port
and the wrong path for this setup. Correct the Redirect URL in the Kite developer
console, save it, and start a fresh login from `/api/auth/kite/login`.

## Where your Kite credentials go

Open the
[Kite developer console](https://developers.kite.trade/), create your application,
and register this redirect URL:

```text
http://127.0.0.1:8000/api/auth/kite/callback
```

The callback is now implemented. The URL must match exactly, including
`127.0.0.1` rather than `localhost`.

Edit **backend/.env** locally:

```dotenv
APP_NAME=AUREVON
LOG_LEVEL=INFO
KITE_API_KEY=your_actual_api_key
KITE_API_SECRET=your_actual_api_secret
```

Restart the server after changing `.env`. Both values are needed for Kite login
in step 2. You do not need them for the health check or offline tests.
Keep your actual values on your computer; do not paste them into chat or README.
`.gitignore` excludes `.env` and logs. The checked-in `.env.example` stays blank.

Kite's official flow sends you to its login page, returns a short-lived
`request_token` to the registered callback, then exchanges that token on the
backend using the API secret. The resulting access token expires at 6 AM the
next day unless invalidated earlier. AUREVON uses the next 06:00 IST boundary
as a conservative local expiry, including when login occurs before 06:00.
See the [official login documentation](https://kite.trade/docs/connect/v3/user/).

## Step 2: connect your Kite account

1. Ensure your real key and secret are saved in `backend/.env`.
2. Register the callback URL above in the Kite developer console.
3. Restart the backend using the step 1 command. Run a single worker on Windows.
4. Open http://127.0.0.1:8000/api/auth/kite/login in your browser.
5. Sign in on Zerodha's page using your normal credentials and second factor.
6. Kite returns to AUREVON, which exchanges the temporary token, saves the session,
   and redirects to `/api/auth/kite/status` without tokens in the final URL.

After a successful login, status looks like this (account and expiry vary):

```json
{
  "configured": true,
  "authenticated": true,
  "user_id": "YOUR_ACCOUNT_ID",
  "expires_at": "2026-10-24T00:30:00Z",
  "message": "Kite session verified. Application remains in PAPER mode."
}
```

`configured: true` alone only means both settings are present. `authenticated: true`
means the saved session passed a `/user/profile` check with Kite. The status route
makes a broker request when a session exists; refresh manually rather than polling
rapidly. A connection failure returns HTTP 502 without deleting your saved session.

The access token is encrypted with Windows DPAPI in
`backend/data/kite-session.bin`. The same Windows account can restore it after a
server restart until expiry. This Windows-specific store will need a different
implementation for cloud deployment. Session files are excluded from Git.

Login attempts expire after ten minutes and are tied to a browser cookie. Start
again from `/login` if the server restarts during login, you cancel, or a temporary
token expires. Do not paste callback URLs or tokens into chat.

If Kite rejects a login, check that key and secret belong to the same app and that
the app permits your Kite user. Errors deliberately omit broker response bodies,
which can contain private data. Restart after editing `.env`.

This step has been tested with fake broker responses. On 2026-10-23 the user also
completed a real browser login: the status endpoint reported `configured: true`
and `authenticated: true` after verifying the session with Kite.

## Logs: what to look for

Application logs appear in the terminal and `backend/logs/aurevon.log` as JSON
lines. Times are UTC; request durations are milliseconds. Files rotate at 5 MB,
with five backup files retained.

| Event | Meaning |
| --- | --- |
| `application_started` | Settings loaded; shows PAPER mode and credential presence |
| `request_completed` | Request finished; includes status, duration, request ID |
| `request_failed` | Unexpected request failure; includes request ID |
| `application_stopped` | Server shut down |
| `kite_login_started` | Browser login initiated |
| `kite_login_succeeded` | Token exchanged and encrypted session saved |
| `kite_session_invalidated` | Broker rejected a saved token; login required |
| `kite_session_unavailable` | Saved session expired, changed app, or could not be read |
| `kite_connection_failed` | Broker connection/response failure |
| `kite_request_rejected` | Broker rejected the request; HTTP status only |
| `kite_session_save_failed` | Local encrypted session could not be saved |
| `instruments_refresh_started` | Downloading NSE and NFO instrument CSVs |
| `instruments_refresh_completed` | Both snapshots saved; includes row counts |
| `instruments_cache_used` | Today's saved catalog reused without downloading |
| `instrument_download_failed` | Download connection failed; includes exchange |
| `instruments_save_failed` | Database transaction failed; old snapshot retained |

Each response includes `X-Request-ID` to match it with its log entry. Request
query strings and credential values are not included in application log events.
The run command disables Uvicorn access logs to avoid logging callback tokens.

To watch the log in a second PowerShell window:

```powershell
Get-Content D:\WorkSpace\AUREVON\backend\logs\aurevon.log -Tail 20 -Wait
```

## Code map

| File | Responsibility |
| --- | --- |
| `backend/app/main.py` | App startup/shutdown, request logging, API endpoints |
| `backend/app/config.py` | Typed settings; reads backend/.env |
| `backend/app/logging_setup.py` | JSON logging and file rotation |
| `backend/app/broker/kite_auth.py` | Login exchange, session encryption, expiry, profile checks |
| `backend/app/api/kite_routes.py` | Login redirect, callback, status endpoints |
| `backend/app/broker/instruments.py` | CSV validation, atomic snapshot, NIFTY selection |
| `backend/app/api/instrument_routes.py` | Catalog refresh, status, and NIFTY endpoints |
| `backend/app/db/models.py` | Instrument, snapshot, market candle, brick and checkpoint tables |
| `backend/alembic/versions/0001_instruments.py` | First database migration |
| `backend/alembic/versions/0002_market_state.py` | Market storage and restart checkpoint migration |
| `backend/app/broker/kite_ticker.py` | Standalone queued worker, status and candle/storage integration |
| `backend/app/market/historical.py` | Chunked historical candles and atomic CSV exports |
| `backend/app/market/renko_builder.py` | Anchored decimal Renko construction |
| `backend/app/market/candles_5m.py` | Live spot/futures candle aggregation and partial-session VWAP |
| `backend/app/market/tick_recording.py` | Versioned daily market-event recording |
| `backend/app/market/persistence.py` | Atomic candle/brick/checkpoint persistence and restore |
| `backend/app/tools/` | Download, monitor, replay and parity CLI entry points |
| `backend/tests/test_foundation.py` | Health, config loading, secret handling checks |
| `backend/tests/test_kite_auth.py` | Fake broker login, failures, expiry, encrypted session restoration |
| `backend/tests/test_instruments.py` | Catalog selection, bad downloads, caching, migration checks |
| `backend/pyproject.toml` | Dependencies and quality tool settings |
| `backend/uv.lock` | Resolved dependency versions |

## Check your changes

Run from `backend`:

```powershell
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy
```

Tests use fake credentials and never contact Zerodha.

Latest recorded validation on 2026-10-24: **82 tests passed**, Ruff lint/format
and mypy passed; migration `0002_market_state` applied successfully. Earlier,
on 2026-10-23, `uv sync --locked` passed and a real Uvicorn process returned HTTP 200 for the health
endpoint. Starlette currently emits a deprecation warning about its httpx test
adapter; this does not prevent the tests or application from running.

## What you need to do next

1. Run the server and open `/api/health` and `/docs`.
2. Repeat the browser login when the session expires or Kite invalidates it.
3. Open `/api/market/instruments/status` and `/api/market/nifty` to inspect the catalog.
4. The original Pine reference is already saved at `docs/pine/renko_indicator.pine`.
5. Record actual chart settings/anchor and export TradingView reference data for
   REF-00-03–07. The comparison tool exists; real parity is still Pending.
6. Continue implementation at BE-13-02, using the master task record and v2 daily plan above.

## Step 3a: daily instrument catalog

The database migration and first real download have already been run on this
workspace. The download saved 10,377 NSE records and 43,344 NFO records on
2026-10-23. NIFTY spot, the nearest unexpired future, and option contracts were
resolved from those records. Counts and contract details will change over time.

Restart the server if needed using the step 1 command. Open:

- http://127.0.0.1:8000/api/market/instruments/status — today's cache status/counts.
- http://127.0.0.1:8000/api/market/nifty — spot, nearest future, available option
  expiry dates, and all options for the nearest expiry (including today).
- `/api/market/nifty?expiry=YYYY-MM-DD` — options for a listed expiry date.

Before each trading day, log in and refresh the catalog from a second PowerShell
window while the server is running:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/market/instruments/refresh
```

Alternatively, use the POST endpoint's **Try it out** button in `/docs`.
Opening that POST URL directly in a browser address bar sends a GET and will
return HTTP 405. Refresh reuses today's catalog to avoid repeated large downloads.
No scheduled refresh is implemented yet.

Metadata is saved in `backend/data/aurevon.db` (SQLite). Use
`uv run alembic upgrade head` from `backend` on each new checkout or when a new
migration is added. This command is safe to repeat. A missing schema returns HTTP
503 with that instruction. `DATABASE_URL` can override the default database path.

NIFTY spot is resolved by `NSE:NIFTY 50`; NFO contracts must have the exact
underlying name `NIFTY`, so BANKNIFTY is excluded. Expired contracts are excluded
using the date in Asia/Kolkata. Lot sizes, strikes, expiry dates, tick sizes, and
instrument tokens come from the dump. An index record legitimately has lot size
zero; it is not an orderable contract. Expiry-day trading policy will be added
with the strategy layer; this endpoint only lists contracts.

The catalog stores exchange + trading symbol as its key because derivative
tokens may be reused. Both exchange downloads are validated before replacement;
a malformed download or failed transaction preserves the previous catalog.
NIFTY lookup rejects a stale catalog with HTTP 409 until you refresh it.

The instrument list is metadata, not a live option chain. Its last-price column
is intentionally not used. Kite recommends downloading and storing this daily
list: [official instrument documentation](https://kite.trade/docs/connect/v3/market-quotes/).

## Development log

- 2026-10-24: Added offline close-source Renko construction and CSV replay/parity
  tools, with synthetic algorithm and property tests. Original Pine reference is
  available in `docs/pine/renko_indicator.pine`. Real TradingView parity remains
  pending. Later work on the same date added historical downloads, live monitoring,
  candles, recording/replay and persistence as described below.
- 2026-10-24: Added candle/brick/checkpoint persistence, named-stream restart
  restoration, opt-in live minute-close Renko integration and migration 0002.
  Verified 82 backend tests, Ruff and mypy; real-data acceptance remains Pending.
- 2026-10-24: Added the canonical granular BE/FE/QA/operations roadmap and mandatory
  completion-update rules; documentation only, no new application behavior.

- 2026-10-23: Initialized the uv project and installed the specified dependencies;
  verified `uv sync --locked`.
- 2026-10-23: Added step 1 backend foundation, configuration template, health and
  Kite configuration status, JSON logs, tests, and setup instructions.
- 2026-10-23: Added Kite browser login, single-use browser state checks, token
  exchange, Windows DPAPI persistence, expiry handling, and verified session status.
  Tested with fake broker responses; real browser login subsequently confirmed
  by the user's successful session-status screenshot.
- 2026-10-23: Added the first Alembic migration, SQLite instrument catalog,
  daily refresh and NIFTY lookup endpoints. Verified a real authenticated
  NSE/NFO download and contract selection; added catalog and migration tests.

## Step 3b: offline Renko replay and comparison

The builder follows SPEC section 9: fixed boxes (default 50), an explicit grid
anchor, two-box reversals, inclusive boundaries, and multiple bricks per gap.
It preserves state across days. Minute-close mode ignores duplicate/older source
timestamps; explicit tick mode retains equal-time updates in supplied sequence.
Prices use decimal arithmetic. Reversal bricks open at the previous brick's
open; only continuation bricks open at the previous close. No wicks or index
volume are inferred. The Pine script consumes chart bricks; it does not build
the underlying Renko chart.

Prepare two separate CSV files covering the same history and seed period:

- Source prices: `time,close` for completed one-minute candles. Time must be
  ISO-8601 with an explicit offset, e.g. `2026-10-23T09:15:00+05:30`.
- TradingView Renko export: `open,close` columns (case-insensitive); extra
  columns are allowed. Keep repeated brick timestamps and all exported rows.

From `backend`, compare the files using a real brick close as the anchor:

```powershell
uv run python -m app.tools.parity_check renko --csv path/to/tradingview.csv --prices path/to/minute_closes.csv --anchor 24025 --box 50
```

The anchor above is an example; use your chart's actual grid. Exit codes are
0 for identical open/close/direction sequences, 1 for differences (including
extra/missing bricks), and 2 for invalid inputs. The tool reports the first
mismatch and total mismatches; it does not silently realign or discard bricks.
The first price seeds the grid without emitting a brick. Replay the same file
from the beginning to rebuild state; changing box or anchor requires a rebuild.

For recorded ticks, use `time,price` and add `--mode tick`. Minute-close mode
requires completed candles supplied by the caller; it does not aggregate ticks.
Distinct source samples require increasing timestamps under the current duplicate
policy. Multiple bricks emitted by one sample retain that sample's timestamp.

Optional backend settings are `RENKO_BOX=50`, `RENKO_MODE=minute_close`, and
`RENKO_ANCHOR=<real chart close>`. Anchor defaults to unset rather than guessing
your chart grid. The offline CLI takes explicit arguments independently of `.env`.

Next validation: compare ten trading days of TradingView bricks with matching
one-minute source prices. Synthetic tests establish algorithm behavior only.
Standalone WebSocket ingestion, daily tick recording and database brick restoration
are implemented in the later sections below. Managed backend integration and
warm-up/gap recovery remain Pending in the master task record.

## Historical prices for Renko validation

Log in through the backend first and refresh today's instrument catalog. Get the
NIFTY spot token from `/api/market/nifty`; use that token for Renko prices. Use the
actual futures token separately for five-minute volume/OI data. Tokens must come
from the catalog, not copied from examples or hard-coded.

From `backend`, replace `<spot-token>` with that integer:

```powershell
uv run python -m app.tools.download_prices --token <spot-token> --start "2026-10-12T09:15:00+05:30" --end "2026-10-23T15:29:00+05:30" --output data/nifty_minute.csv
```

For futures, use `--interval 5minute --oi` and a separate output path. The
download uses the existing encrypted session, overlapping 30-day chunks, and
serialized historical requests spaced at least 0.4 seconds apart within that
process. Run one downloader at a time; separate processes do not share a limiter.
Rate-limit failures stop the download with a safe error; retry later.

The date range selects candle **opening** times, inclusive. Only candles whose
full interval has elapsed are exported. CSV `time` is the completed-close time;
`candle_open_time` preserves the broker timestamp. OHLC, volume, optional OI, and
interval are included. This file can be supplied directly to parity-check
`--prices`. It is a price-source file, not a TradingView brick reference.

All chunks are validated before replacing the output atomically. Identical
overlapping candles are deduplicated; conflicting candles and invalid OHLC data
fail the download. Empty results preserve an existing output. Successful downloads
replace the chosen file; use separate paths for different instruments/intervals.
No missing candles are synthesized and no futures rollover is inferred.

The request format follows the [official Kite historical API documentation](https://kite.trade/docs/connect/v3/historical/).
Intraday futures use the specific contract token, with continuous mode disabled.
The CSV downloader does not warm up indicators or write SQLite. The planned
spot-history service below now stages historical spot candles in SQLite; derived
live candle integration remains Pending. Cold historical Renko initialization is
now implemented in the service below.

Verified on 2026-10-24 with fake broker responses; a real authenticated historical
download and TradingView parity comparison remain to be verified.

## Live price monitor (Step 3b: ticker worker)

After login and today's instrument refresh, copy the spot and nearest futures
tokens from `/api/market/nifty`. In a separate terminal, from `backend`, run:

```powershell
uv run python -m app.tools.watch_prices --spot-token <spot-token> --future-token <future-token>
```

Replace both placeholders with catalog token integers. The monitor uses your
encrypted Kite session and subscribes to both instruments in full mode, following
the [official WebSocket interface](https://kite.trade/docs/connect/v3/websocket/).
No credentials are printed. It runs independently of Uvicorn; Ctrl+C stops it.
Use one monitor process and restart it after refreshing an expired Kite login.

Every five seconds it prints connection status, latest prices, futures volume/OI,
accepted/invalid/dropped counts, and data-quality flags. SDK callbacks hand ticks
to a bounded queue; an asyncio consumer validates prices and exchange times.
Both queued ticks and pending tick callbacks are bounded. Earlier exchange times
are rejected; distinct updates in the same second are retained, since the feed's
timestamp precision is one second. Index volume/OI are absent rather than inferred.

The SDK handles exponential reconnects with a 30-second maximum delay and 50
attempts; each successful connection resubscribes both tokens. During weekday
09:15–15:30 IST hours, missing or over-five-second-old data for either instrument
sets `stale`. `clock_or_feed_delay` flags an exchange-time difference over two
seconds. Holiday scheduling is not yet implemented, so holidays on weekdays can
also show stale data. Outside those hours, `session_expected` is false.

Disconnects and queue overflow set a persistent `gap_requires_replay` flag.
Automatic historical replay of reconnect gaps and indicator integration remain
Pending. Minute-close Renko feeding is available with `--stream` below. The monitor reports
`entries_enabled: false`; reconnecting does not clear the replay requirement.
This worker is not yet wired into the backend lifecycle or dashboard.

Verified with fake socket callbacks and clocks: subscriptions, queued consumption,
resubscription, per-instrument staleness, timestamp handling, overflow, reconnect
exhaustion, and shutdown. A real market-hours WebSocket session remains unverified.

## Completed live candles and remaining work

The price monitor also produces one-minute spot candles and five-minute futures
candles. Its JSON output includes `closed_candle_counts` and `last_closed_candles`.
The last 100 completed candles per instrument are retained in memory. The loop
finalizes elapsed intervals every five seconds, after draining queued ticks;
late packets cannot reopen finalized candles. Active candles are not published
as completed, and empty intervals are not filled with invented prices.

Futures volume is the difference between successive daily cumulative counters;
OI is the latest observed value. The first observation establishes a baseline,
so the initial candle is partial. Counter decreases, disconnects, queue overflow,
and missing intervals also mark affected candles partial. Cross-boundary volume
deltas are assigned to the arriving tick's candle, a sampled-feed approximation.
Spot candles have no inferred volume or OI.

Session VWAP uses `(high + low + close) / 3` weighted by completed futures candle
volume, matching the source used by `ta.vwap(hlc3)` in the Pine reference. It resets
by IST session date; zero cumulative volume yields no VWAP. The standalone monitor keeps `vwap_partial` true because earlier session volume
may be missing. The isolated historical seed service below can establish complete
session VWAP from contiguous staged candles; managed live adoption is still Pending. A mathematically correct calculation does not establish parity
between broker and TradingView feeds.

Without `--stream`, candles remain in the standalone monitor's memory. Opt-in
database persistence and live minute-close Renko feeding are described below.
Historical warm-up and web API integration remain pending.
Verified on 2026-10-24: 62 tests passed; Ruff and mypy passed.

Use the [master task record](#master-task-record-backend-frontend-and-release) above
for all task statuses, prerequisites and implementation/validation milestones.

## Daily tick recording and offline replay

`watch_prices` now records accepted, validated spot/futures ticks by default to
`backend/data/ticks/<run-id>/YYYY-MM-DD.jsonl`. Dates use IST and each monitor
run gets its own directory, preventing restarts from mixing sequences. The status
output includes `recording_directory`. Use `--record-dir <directory>` to change
the parent directory; keep one monitor per run.

Each versioned JSON line includes sequence number, run ID, spot/futures tokens,
and receipt time. Tick records contain normalized exchange time, price, cumulative
volume and OI; clock events preserve candle finalization times. Gap markers preserve
partial-data handling after disconnects/overflow. Credentials, arbitrary SDK fields,
and market depth are excluded. Invalid or dropped ticks are not recorded, and the
recording cannot recreate market updates never received by the consumer.

Replay one complete run from `backend`, replacing the example run ID:

```powershell
uv run python -m app.tools.replay_ticks data/ticks/<run-id>/2026-10-23.jsonl
```

For a run spanning multiple days, pass every daily file in recorded order. Replay
requires sequence zero and rejects missing/reordered events, mixed runs/tokens,
invalid records, and truncated JSON. It streams completed candle JSON to stdout
with fixed field ordering, using the same candle builders as the live monitor.
Repeated replay of an unchanged recording produces identical output, without
broker credentials, network calls, sleeps, or use of the current clock.

No unfinished candle is closed implicitly at end-of-file; only recorded clock
events or later ticks close candles. If a corrupt file fails after earlier results
were printed, discard that partial output. Replay is currently candle-only;
Offline recorded-tick-to-Renko replay and end-to-end trade replay remain later tasks.
Live minute-close Renko integration is available with database persistence below.

Recording appends and flushes each event in the consumer, outside SDK callbacks.
It stops the monitor on a write failure; normal shutdown drains queued ticks.
Flush does not guarantee survival of a power loss, and recordings do not yet have
automatic retention/compression. Slow disks can cause queue overflow, reported
through the existing counters and gap flag. Files under default `backend/data`
are excluded from Git.

Offline tests cover live/replay candle equivalence (including clock closes,
same-second updates and gap flags), IST rotation, restart isolation, malformed
files, sequence errors, credential-field exclusion and disk-failure shutdown.
Real market-hours recording remains to be verified.

## Warm-up and recovery settings (BE-05-01)

These settings control the opt-in managed warm-up/recovery service. They load
from `backend/.env` or environment variables; the standalone monitor remains
diagnostic and does not grant entry readiness.

| Environment variable | Default | Valid values / meaning |
| --- | --- | --- |
| `WARMUP_LOOKBACK_TRADING_DAYS` | 20 | Integer 1–250; completed trading sessions of initial history, not calendar days |
| `RECOVERY_MAX_GAP_DAYS` | 30 | Integer 1–365; maximum elapsed calendar-day gap eligible for automatic recovery |
| `RECOVERY_MAX_ATTEMPTS` | 5 | Integer 1–20; total attempts per recovery request, including the first |
| `RECOVERY_BACKOFF_SECONDS` | 1 | Finite positive seconds, at most 300; initial retry delay |
| `RECOVERY_BACKOFF_MAX_SECONDS` | 30 | Finite positive seconds, at most 300 and at least the initial delay; exponential retry cap |
| `READINESS_ENTRY_DELAY_SECONDS` | 60 | Integer 60–3600; minimum entry hold after successful warm-up/recovery |

Startup contract for subsequent tasks:

- **First startup:** no checkpoint exists for the named stream. Plan completed
  spot-minute and matching futures-five-minute history for the configured trading
  sessions, including indicator lookback and daily context. Spot closes drive
  Renko, consistent with SPEC 8.1/9 and the current persistence implementation;
  SPEC 8.4's mention of futures as the Renko source is superseded by that mapping.
  The 20-session default is an initial policy, not proof of sufficient Pine parity.
- **Checkpoint restart:** restore a valid, configuration-matching checkpoint and
  plan history from its processed candle boundaries to the completed-history/live
  handoff. Reuse saved state rather than reseeding Renko. Missing checkpoints use
  first-start policy; invalid or incompatible checkpoints fail explicitly, as the
  current persistence layer does. Never silently discard them.
- **Recovery limits:** the gap limit bounds automatic elapsed-time recovery, not
  initial lookback or the downloader's chunk size. A longer gap or exhausted
  attempts requires an explicit rebuild/recovery decision and keeps entries blocked.
  Retry delays are intended as initial delay times powers of two, capped at the
  configured maximum; later recovery tasks implement this policy.
- **Readiness:** remain false during startup, replay and gaps. The delay begins
  only after history, derived state and queued-live handoff pass quality checks.
  Entry eligibility additionally requires valid authentication, fresh feed,
  session eligibility and no unresolved quality gaps. A new gap revokes readiness
  and requires recovery plus a fresh delay. There is no setting to bypass these
  checks or enable entries; runtime enforcement belongs to BE-05/06.

## Historical range planner (BE-05-02)

`app.market.warmup.plan_history(settings, calendar, now, checkpoint=None)` returns
an immutable plan without broker calls or database writes. `SessionCalendar`
declares an inclusive date coverage and ordered session opening/closing times;
absent dates within that coverage are non-trading days. Callers must supply
verified calendar data; there is no weekday fallback. Production calendar loading
and scheduling remain BE-06 work. Special sessions are supported when their
same-day bounds align to five minutes.

Cold starts include the configured number of completed trading sessions plus
any completed candles in the current session. Plans contain one inclusive
opening-time range per session and instrument, directly matching `download`:
one-minute spot and five-minute futures. Each range exposes its completed-close
time. No request includes a candle still forming at the explicit cutoff.
The previous completed session before today's date is returned for daily context.

Checkpoint restarts accept separate spot/futures next-unprocessed opening times
from validated restored state: use the active candle opening if present, otherwise
`closed_until`. Missing boundaries require an explicit rebuild decision. The
planner rejects naive, future, unaligned, uncovered or over-limit boundaries.
It also fetches current-session futures context from session open for VWAP;
this may intentionally overlap saved data. Future import/merge tasks must apply
that context idempotently and preserve the checkpoint application boundary.
Planning does not correct existing partial candles or rebuild state itself.

Cold plans require at least 21 completed futures bars for Pine's
`volume[1] / ta.sma(volume, 20)[1]`. The configured trading-day lookback is also
included, but elapsed days cannot guarantee enough Renko bricks or recursive
indicator convergence. Validate brick sufficiency and indicator state after
BE-05-06/BE-08 rebuilding; extend history or keep readiness false if insufficient.
Every plan reports `entries_enabled=False`. No downloads, calendar verification,
indicator parity or runtime readiness are established by synthetic planner tests.

## Planned historical spot storage (BE-05-03)

`app.market.spot_history.fetch_spot_history(auth, engine, stream, token, plan)`
accepts a BE-05-02 `WarmupPlan`, an existing `KiteAuth`, and the configured database
engine. The token must match `NSE:NIFTY 50` in the local instrument catalog.
Refresh the catalog before preparing a plan. The managed pipeline calls this service when opted in; it is not a standalone
web endpoint. Default application startup leaves the broker untouched.

Migration `0003_historical_spot` adds `historical_spot_batches` and
`historical_spot_candles`; it was applied locally on 2026-10-25. Run
`uv run alembic upgrade head` from `backend` on other checkouts before using it.
The existing historical downloader handles authenticated requests, pacing,
chunking, OHLC validation and duplicate overlap. All planned spot requests finish
before one transaction saves the batch and new candles. A later download failure
writes nothing; a conflict or database failure rolls back the entire batch.

Candles are keyed by stream, token and UTC opening time, with explicit UTC
completed-close time and exact decimal JSON values. Original broker volume is
retained as source data; it is not a live cumulative tick counter or inferred
spot volume. Each new candle links to its original download batch. Batch metadata
records the source, exchange/symbol, minute interval, request ranges, plan cutoff,
fetch time and expected/received/missing minute counts, without authentication
fields. Matching repeated downloads preserve original candles and provenance,
while adding a new batch audit record; different decimal scale alone is equivalent.
Conflicting saved values are rejected for the later explicit correction workflow.

Empty or partial responses retain a batch with missing-minute counts; no bars are
fabricated and no readiness is granted. This staging service does not change live
`market_candles`, checkpoint revisions, candle builders or Renko bricks itself.
BE-05-05 reads staged history into isolated candle/VWAP seeds; BE-05-06 can now
commit those seeds and rebuilt Renko for a cold stream. The later merge/recovery
tasks apply live handoff and validate derived state. Real authenticated historical acceptance remains Pending under stage 07.

## Futures history and daily context (BE-05-04)

`app.market.context_history.fetch_context_history(auth, engine, stream,
futures_symbol, plan, calendar)` stages the matching five-minute futures ranges
and spot daily context in one transaction. Pass the BE-05-02 plan, a verified
`SessionCalendar`, and the actual NFO futures symbol from the catalog. The calendar
must include the session immediately before the earliest planned spot/futures
session so each daily context can reference the correct previous close. Unknown
calendar coverage, malformed ranges, missing/wrong contracts and expired current
catalog contracts fail explicitly. No continuous futures or rollover is inferred;
historical expired-contract identity management remains separate work.

Migration `0004_historical_context` adds `historical_context_batches` and
`historical_context_candles`; it was applied locally on 2026-10-25. Other checkouts
must run `uv run alembic upgrade head` from `backend`. Source candles retain exact
decimal OHLC, direct per-candle volume, nullable OI, UTC opening/completion times,
and their original batch link. Futures identity includes exchange, symbol and
expiry; provenance records the requested token and lot size. Repeated identical
imports preserve source candles; conflicts roll back the entire new batch.

Futures requests use the existing paced/chunked downloader with OI requested.
Missing OI (an absent field or explicit null) is stored as null with a missing-OI
count; zero is a supplied value, and invalid/negative/non-finite OI is rejected.
This tolerance is opt-in for this service; existing strict parsing stays strict.
Expected/received/missing futures bars are recorded without fabricating bars.

For completed sessions, spot `day` candles provide daily OHLC using calendar close
times as completion times. For a currently open session, only completed spot
minute candles through the plan cutoff supply evolving OHLC. Source minutes are
also retained. Such context is explicitly partial, includes missing-minute counts
and observed-through time, and leaves today's open unknown if the opening minute
is missing. Before session open, no current-session context is invented. Missing
previous-session data stays null, never replaced with an older available close.
Each batch persists these per-session context snapshots and calendar/request
provenance. These source rules follow the
[official Kite historical API](https://kite.trade/docs/connect/v3/historical/).

All broker downloads finish before the database transaction; a failed request,
invalid response, conflicting source row or database failure leaves earlier data
intact. This service does not mutate live candles, checkpoints, VWAP or Renko and
does not enable entries. Managed lifecycle, context updates on live ticks, volume
live adoption and real-market acceptance remain their later Pending tasks.
Isolated direct-volume import/VWAP seeding is completed below.

## Historical volume import and VWAP seed (BE-05-05)

`CandleBuilder.import_completed(candle, session_open=..., session_close=...,
cutoff=...)` accepts a completed candle directly into an idle builder. Futures
volume is the candle's own traded volume, added once to session accumulators;
it never passes through tick-counter subtraction. Session VWAP is
`sum(((high + low + close) / 3) * volume) / sum(volume)` using decimal arithmetic.
Zero total volume produces no VWAP. Missing OI remains null and does not change
volume weights. Imported spot candles have no inferred volume, OI or VWAP.

`app.market.history_import.build_historical_seed(engine, stream, spot_token,
futures_identity, plan, calendar)` reads BE-05-03/04 staged sources in a database
snapshot and returns isolated builders, completed candles and missing-bar counts.
Use the exact futures identity from staging, such as `NFO:<symbol>:<expiry>`.
Ranges, OHLC, alignment and stored opening/completion timestamps are validated.
The service reads the selected ranges only into its result; it does not write
live candles, checkpoints or Renko. Rebuilding from unchanged sources produces
the same seed without double-counting. Appending duplicate/older historical
candles or importing into an active live interval fails explicitly.

A session beginning at its verified calendar open with contiguous history can
have `vwap_partial=False`. Starting late, missing an interval, or a source partial
flag keeps that session's VWAP partial. A missing requested tail also marks the
returned builder partial. A new session resets its weights and quality; missing
older-session bars remain reported without tainting a complete later session's
VWAP. Returned candle quality describes the information available at each close.

History does not establish the exchange cumulative-volume counter at the live
boundary. Imported builders therefore retain no cumulative tick baseline. The
first subsequent live tick establishes a baseline without subtracting historical
bar totals, and conservatively marks the affected candle and VWAP partial.
Later ticks use normal counter deltas. A verified historical/live handoff remains
implemented by the explicit BE-05-07 handoff below; the standalone CLI does not automatically adopt these seeds.
Seed state uses the existing checkpoint serialization, and every returned seed
reports `entries_enabled=False`. Real feed/TradingView parity remains Pending.

## Historical Renko initialization (BE-05-06)

`app.market.history_renko.rebuild_historical_renko(engine, settings, stream,
spot_token, future_token, futures_identity, plan, calendar)` initializes a cold
stream from staged history. It requires `RENKO_MODE=minute_close`, a configured
chart anchor, distinct catalog-matching tokens and a `cold_start` plan. The exact
futures identity must match its catalog symbol and expiry. Existing staging and
market-state tables are reused; no additional migration is required.

The service builds BE-05-05 candle/VWAP seeds in isolation and feeds completed
spot closes to the existing decimal Renko builder at candle close timestamps.
The first close seeds the anchored grid without a brick. Subsequent closes may
emit multiple bricks, including reversals, with indices and grid continuity
preserved across trading dates. Empty spot history fails explicitly. Missing
source intervals may produce diagnostic bricks, but missing counts remain in
the checkpoint and no readiness is granted.

One transaction saves all imported spot/futures candles, generated bricks and
checkpoint revision 1, including builder/VWAP state, the Renko seed/last brick,
last processed source time, counts, plan/calendar metadata and source-quality
counts. A database failure rolls back the whole initialization. Repeating the
same inputs verifies every stored output and checkpoint and makes no writes;
`imported=False` identifies that result. Changed inputs or outputs, a checkpoint
advanced by a worker, and orphaned outputs without a checkpoint are rejected.
Use the forthcoming merge/recovery workflow or an explicitly prepared new stream
for those cases; this initializer never replaces existing state.

The existing persistent worker can restore the checkpoint and continue brick
numbering. The returned result always reports `entries_enabled=False` and the
checkpoint deliberately keeps `gap=True`, including for complete source data.
Queued-live handoff, recovery, entry-delay enforcement and managed ownership are
implemented. Indicator sufficiency and real TradingView acceptance remain Pending.
The opt-in managed pipeline calls this initializer; no dashboard action is exposed.

## Historical to queued-live handoff (BE-05-07)

This is an explicit worker service, not yet wired into the standalone CLI or
FastAPI startup. On the event loop, create a fresh `TickerWorker` without
persistence and call `await worker.start(buffer_only=True)`. The socket subscribes
normally, but the consumer waits while callbacks fill the existing bounded queue.
Build and persist the historical seed using BE-05-03 through BE-05-06 (run blocking history work
off the event loop so callbacks can continue). Do not advance candles during buffering.

Call `worker.merge_history(store, boundaries)` with a `MarketPersistence` matching
the worker tokens and stream, and a timezone-aware boundary for each token. Each
boundary is the exclusive historical end and inclusive live start, aligned to the
instrument's one-minute or five-minute buckets. For example, at a 10:02:30 cutoff,
use 10:02 for spot and 10:00 for futures, with history completed through those
boundaries. Buffer early enough to retain the unfinished futures bucket. The first
live bucket remains partial because the feed cannot establish complete coverage or
the futures cumulative-volume baseline from historical bar volume.

The checkpoint must exist and contain idle builders with no history ending after
the supplied boundary. Missing tail intervals before a boundary stay missing and
gapped for explicit recovery; queued fragments never fill them silently. The
handoff persists the boundaries before releasing the queue. Older ticks are counted
as `history_overlap` and skipped before updating latest prices, recording or storage.
Ticks exactly at the boundary, including same-second updates, are live inputs.
Closes and Renko bricks are produced only at completed candle boundaries.

Invalid handoffs and persistence failures leave consumption blocked. Stop and retry
with a fresh worker after inspecting the cause. Stopping a buffering worker cancels
the consumer without waiting for a queue that cannot drain. Queue overflow retains
its dropped count and gap flags. When recording is enabled, the adopted checkpoint
is the first event and the accepted live events can be replayed deterministically.
`history_pending` reports buffering state; entries remain disabled and gap quality
flags are preserved. Gap tracking, recovery and the managed post-warm-up entry
delay are implemented below. Managed scheduling, indicator integration and real
TradingView parity remain Pending.

## Missing-data tracking (BE-05-08)

`TickerWorker.gaps` retains unresolved uncertainty spans for each subscribed token
and cause: `disconnect`, `reconnect`, `overflow` and `downtime`. Disconnect and
reconnect incidents start conservatively at an active candle opening or the last
completed boundary; restored checkpoints add downtime from that same boundary.
When no source boundary exists, the incident observation time is used. The SDK
pending-callback limit and event-loop queue limit both flag overflow. Only bounded,
locked metadata is updated from the SDK thread; database writes stay on the worker
thread. Overflow flags reach persistence on the next save/clock event or shutdown.
Recording/DB crash reconciliation is implemented at BE-05-13 below.

`status()["missing_ranges"]` exposes the raw uncertainty spans, including a
`resume_after` observation time and `end=None` while the instrument has not resumed.
Queued exchange timestamps older than `resume_after` cannot close a span. A fresh
tick closes the open span for that token only; it never clears the unresolved gap
or enables entries. Multiple incidents with the same token/cause widen one envelope,
so metadata uses at most eight spans for the two-token worker. Recovery may fetch
intact candles inside an envelope; this deliberately avoids losing recovery work.

Call `worker.gaps.ranges(token, minutes, calendar, now)` with `minutes=1` for spot
or `5` for futures and an explicit `SessionCalendar`. It returns ordered,
deduplicated `HistoryRange` objects with inclusive candle-opening endpoints. Only
completed affected buckets are returned, including the resumed bucket once it is
complete. Open gaps extend through the supplied cutoff. Sessions clip the ranges;
absent dates inside calendar coverage are non-trading dates, with no guessed
holidays. Insufficient calendar coverage fails explicitly. Calling this method does
not clear gaps, fetch history, mutate candles or grant readiness.

Gap metadata is backward-compatible with checkpoints/recordings lacking a `gaps`
field. New checkpoints retain it, new recording tick/clock events include snapshots,
and connection events record explicit `gap` events. Replay applies gap flags before
subsequent candles, preserving partial-bar behavior. Historical handoff retains the
SDK callback tracker and merges seed gaps before releasing the queue. Recording
waits for the seed checkpoint while history buffering is active.

Missing-candle downloads and derived-state rebuilds are implemented below. Existing
explicit partial-candle corrections and bounded request retries are implemented below;
request coordination and validated handoff/entry delay are Completed at BE-05-12/14.
The original Pine reference is unchanged.

## Missing-candle recovery service (BE-05-09)

`app.market.recovery.recover_missing_history(auth, engine, settings, stream,
spot_token, future_token, futures_identity, calendar, cutoff)` operates on a
quiescent persisted minute-close stream. Stop its writer before invoking it, and
restore a **new** worker from the resulting checkpoint afterward. The service does
not mutate an existing worker or run automatically from the CLI/FastAPI lifecycle.
Run its blocking network/database work off an event loop that is buffering a new
feed. The usual explicit chart anchor, stream configuration, catalog tokens and
exact futures symbol/expiry identity must match. Futures rollover is not inferred.

The service combines tracked gaps, checkpoint downtime and interior holes in the
retained source coverage. Calendar coverage must include all retained sources and
the recovery cutoff; only completed buckets in supplied sessions are requested.
The automatic recovery age limit is enforced before broker requests. Spot is
requested at one-minute intervals, futures at five-minute intervals with OI,
through the existing validated/chunked historical downloader. Contiguous absent
openings share a request. By default, stored completed candles, including partial ones, are not redownloaded.
Explicit `correct_partial=True` also requests completed partial bars, with audited
replacement as described below. Complete bars are never correction candidates. No daily-context requests are needed.

Retained and recovered candles are replayed in timestamp order from the stream's
original source coverage. This preserves the anchored Renko seed and recomputes
all later brick indices and session HLC3-volume VWAP when an earlier hole is filled.
The implementation replaces derived outputs in full for correctness; it does not
download the full history again. In default missing-only mode, existing partial
candles retain their OHLC/volume and partial flags; derived VWAP is recomputed. Explicit correction may replace completed partial bars and their matching staged
source values with before/after evidence; other staged conflicts still fail. An elapsed active fragment
can be superseded by its completed historical bar; its payload remains in recovery
metadata. Unfinished active fragments remain partial and are never closed early.
Missing elapsed fragments are not promoted into fabricated completed bars.

One transaction stages recovered source candles and audit batches in the existing
history tables, replaces completed candle/brick outputs and advances the checkpoint
revision. Network/validation failures leave all tables unchanged; database failures
roll back sources and derived state together. A writer advancing the checkpoint
during download causes recovery to fail without replacing its outputs. Identical
recovery at the same cutoff and correction policy issues no broker requests or
database writes once all requested sources are present. A later
attempt may fill bars that were absent from an earlier broker response.

`RecoveryResult` reports inserted spot/futures bars, remaining missing bars, retained
partial bars and absent OI. Checkpoint `recovery` metadata retains coverage, cutoff,
identity, quality counts and elapsed-fragment evidence; ordinary worker saves now
preserve it and original import provenance. Per-token boundaries prevent missing
tail intervals from being reconstructed from late tick fragments. Gap flags and
`entries_enabled=False` remain in force even when all requested bars were recovered;
this service does not establish indicator sufficiency or TradingView parity.

Completed-candle corrections and per-read retries are implemented below;
BE-05-12 and BE-05-13 implement coordinated requests and recording/database crash reconciliation;
BE-05-14 covers validated resumption and entry delay. No additional schema migration
is required. Original Pine contents remain unchanged.

## Completed-partial correction and historical retry policy (BE-05-10/11)

Call `recover_missing_history(..., correct_partial=True)` on a quiescent stream to
request absent bars plus existing **completed partial** bars inside the validated
coverage. Default `False` preserves the BE-05-09 missing-only behavior. Full bars
are never overwritten, and unfinished active candles are not fetched or closed
prematurely. Missing correction responses retain the old partial candle; missing OI
remains explicit rather than invented. Existing configuration, identity, calendar,
cutoff and automatic age limits still apply.

Each returned correction replaces the entire sampled OHLC/volume/OI candle using
one validated historical source. All retained and recovered spot closes are then
replayed from the original stream seed, rebuilding later brick values/indices;
session VWAP and checkpoint accumulators are recomputed from direct bar volumes.
This avoids retaining downstream values derived from the former partial candle.
One revision-guarded transaction applies source replacements, derived outputs and
checkpoint. Any validation, concurrent-writer or database failure rolls it back.
Restore a new worker afterward; entries remain disabled and gap flags persist.

Existing history-batch provenance stores `market_corrections` with before/after
market payloads and `staged_replacements` with the former source payload, completion
time and batch ID plus the replacement payload. Old batches are retained; the
current staged row points to the new audited source. A staged conflict is allowed
only at the exact token/time of a completed partial being corrected. Other source
conflicts still require a separate explicit rebuild/correction decision. Recovery
metadata retains cumulative `corrected_counts`; `RecoveryResult` distinguishes
inserted bars, corrected bars, retained partials, absent OI and request retries.
An identical repeat makes no requests/writes after sources are present.

`RecoveryHistoryClient` wraps only read-only historical requests made by recovery.
`RECOVERY_MAX_ATTEMPTS` includes the first attempt. Subsequent delays are
`min(initial_backoff * 2**(attempt-1), maximum_backoff)`, with no sleep after the
final failure. Numeric nonnegative finite `Retry-After` values raise that delay;
if the requested wait exceeds the configured maximum, recovery fails for later
rescheduling instead of retrying too soon. Unsupported/malformed header values use
the configured backoff. Tests inject sleeps; production calls are blocking and
must run off the market event loop.

Transport failures, HTTP 429 and HTTP 5xx are classified as transient, including
non-JSON rate-limit/service responses. Authentication/token errors, bad requests,
malformed successful data, invalid candles and persistence conflicts are not
retried. Safe `AuthError` metadata distinguishes these cases even where outward
HTTP errors share code 502. Retry exhaustion raises `RecoveryRequestError` with
attempt count/status and a fixed message; valid stored sessions are never deleted
by this client. A successful spot request is not repeated when a futures request
needs retry. All downloads still finish before any recovery transaction starts.

Every attempt uses the process-wide managed REST pacer added in BE-05-12.
Overlapping managed recovery calls fail fast; separate processes remain uncoordinated. Recording crash reconciliation is implemented at BE-05-13; reconnect orchestration
remains separate Pending work; entry-delay enforcement is implemented at BE-05-14. Broker error classifications were checked
against [official Kite error documentation](https://kite.trade/docs/connect/v3/exceptions/).
No schema migration is required; original Pine content is unchanged.

## Candle/brick persistence and restart recovery

Migration `0002_market_state` adds `market_candles`, `renko_bricks`, and
`market_checkpoints`. It has been applied on this workspace. On a new checkout,
run from `backend`:

```powershell
uv run alembic upgrade head
```

Set `RENKO_ANCHOR` in your existing `backend/.env` to an actual TradingView brick
close, with `RENKO_BOX=50` (or your chart's box size) and
`RENKO_MODE=minute_close`. Preserve your existing Kite credentials. Restart the
monitor with an explicit stream name:

```powershell
uv run python -m app.tools.watch_prices --spot-token <spot-token> --future-token <future-token> --stream nifty-paper-01
```

Replace token placeholders with the current catalog tokens. Without `--stream`,
recording and monitoring continue as before without database writes or Renko
integration. Persistence requires a configured anchor and minute-close mode;
tick-mode persistence is not implemented.

With persistence enabled, completed spot candles feed the Renko builder at their
closing timestamps; futures candles are stored separately. The first completed
spot candle seeds the grid. Each accepted tick or clock advance saves active
candle state, cumulative volume baselines, VWAP accumulators and Renko state.
Completed candles, new bricks and their checkpoint commit in one transaction.
JSON decimal strings avoid rounding stored price levels. Status includes the
stream name, Renko brick count, and the last Renko state (index -1 is the seed).

Restart with the same stream, tokens, box and anchor to restore active candles,
the last 100 completed candles per instrument, and Renko continuation/reversal
state, including the last processed source timestamp. Configuration changes are
rejected for an existing stream; use a new stream name for a rebuilt grid or
different futures contract. Existing streams are retained. Concurrent writers
are detected by checkpoint revision conflicts; run one monitor per stream.

Restored workers mark downtime as a gap and keep entries disabled. This step
restores saved state; it does not fetch missed prices or establish TradingView
parity. Partial candles are retained and can produce diagnostic Renko bricks;
neither these nor post-gap bricks are validated trading signals. Historical
cold initialization is now available through BE-05-06. Historical/live merge
and gap recovery remain Pending.

Recording runs that start from a database checkpoint include that initial candle
state as their first event, so the offline candle replay remains reproducible.
Recording files and database transactions are separate writes; after a crash or
storage failure they may end at different events. Tick files remain available
for explicit recovery; automatic reconciliation is not implemented yet.

Missing schema, invalid checkpoints, settings conflicts and failed commits stop
the persistent worker. Previously committed transactions remain available.
Database writes run in the consumer, outside socket callbacks; slow storage can
still cause queue overflow. API exposure, historical imports and retention are
not included in this step.

Verified on 2026-10-24: 82 tests passed, including migration/model matching,
active-state/seed restoration, brick continuation after restart, checkpoint-based
recorded replay, configuration/concurrent-writer rejection and commit rollback.
Ruff and mypy passed. Real market-hours persistence remains unverified.
