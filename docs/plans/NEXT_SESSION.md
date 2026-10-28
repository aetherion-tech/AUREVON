# Next session - budgeted delivery plan v2

Updated: 2026-10-28. README is authoritative.

- Product tasks: 280 total; 132 Completed; 148 Pending. Latest: 598 tests (74 new BE-10 cases),
  Ruff lint/format and strict mypy passed. One existing dependency warning.
- BE-05 complete (17/17); BE-06 complete (11/11), verified early on D01.
  Evidence: docs/testing/BE-05-acceptance.md and BE-06-acceptance.md.
- BE-13 is 10/20 accepted, NOT complete. Accepted 01/02/03/04/05/15/16/17/18/19.
  Exact remaining requirements: docs/testing/BE-13-acceptance.md.
- BE-08 is 13/14 complete: BE-08-01 through BE-08-13 accepted on D03.
  Pure replay-only indicator library: inputs/maths, all-var snapshots, ordered
  completed bricks, runs/swings and futures/daily context. 54 focused tests.
  Evidence/operation: docs/testing/BE-08-acceptance.md.
  BE-08-14 remains Pending: actual REF-00-07 TradingView debug export absent.
  First-divergence CLI is ready; synthetic tests are not exported parity.
  Next independent code: BE-11-01. BE-11/12 remain upstream of BE-13
  domain APIs. Do not restart completed API/BE-08/BE-09/BE-10 implementation work.
  REF-00-04 separate Pine debug copy remains independent. Preserve original Pine.
  Current elapsed D03 = 2026-10-28. D09/D10 code completed early D03;
  D11 remains Pending only for BE-08-14. Live worker is untouched; this library
  is not activated on the managed feed. Indicator signals/trades exist only in
  synthetic/replay calculations; no actual paper fills or real orders are produced.
- BE-09-01 through BE-09-18 complete on D03 (early D12-D15). Pure replay
  PineEngine, source explanations, eight signals, bias/outlook, ordered indicator
  ENTRY/T1/EXIT, statistics, snapshots and atomic durable retry/event persistence.
  103 new tests; 157 indicator cases; 524 full tests and Ruff lint/format plus
  strict mypy passed, one existing dependency warning.
  QA-09-19/20 remain Pending actual ten-session exports/G1/G2 acceptance.
  No baseline freeze or G2 claim. Evidence: docs/testing/BE-09-acceptance.md.
  Full parity CLI --full --required-days 10 --report compares independent futures
  inputs, maths/bias, grades/decisions and event IDs; synthetic reports are not
  reference acceptance. ORB uses Pine Renko OHLC, distinct from source ORB.
  Replay uses brick IST time and body-only OHLC; chart settings remain unconfirmed.
  Nondefault Pine opposite-signal overwrite is exposed as replaced_trade_id;
  no fabricated EXIT. Review this edge case before any execution integration.
  Additive migration 0007_indicator tested only on isolated databases; local
  application DB unchanged. Apply under owner/backup procedure at integration.
  D12/D13/D14 Completed early; D15 remains Pending QA-09-19/20.
- BE-10 complete (10/10) on D03, early D16/D18. app/strategy implements
  immutable input/TradePlan/capital contracts, catalog-derived expiry/grid/lot/tick,
  bounded quote subscriptions with pinned traded legs, liquidity/credit checks,
  exact amounts/sizing, buffered PAPER_ESTIMATE margin and durable nonexecuting
  POST /api/settings/preview-strikes. 74 focused synthetic cases; 598 full tests,
  Ruff lint/format, strict mypy, OpenAPI/type drift and TypeScript compile passed.
  Generated contracts updated; preview is authenticated/CSRF protected.
  USER_PREVIEW funds are assumptions, not wallet/account/budget readings. No
  executable plan, order, reservation, real option observation or broker margin.
  Option depth records use separate options/*.jsonl sidecars; core replay unchanged.
  Migration 0008_strategy tested in isolated DB only; local DB unchanged, so apply
  pending 0007/0008 under owner/backup procedure before operating new DB paths.
  BE-13-12 settings CRUD remains Pending despite its preview endpoint being ready.
  Evidence/operation: docs/testing/BE-10-acceptance.md. Next BE-11-01; BE-12 wallet
  and accounting prerequisites remain before integrated paper execution.
- D01 Pending only for REF-00-03 actual TradingView settings (already requested;
  do not repeat/invent them). D02 Pending REF-00-04. D03/D05 code batches Completed
  early; D04 Completed early with BE-13-01; D27 transport code Completed early D02.
  D06 code complete; real market recording/observation
  not supplied, so its daily observation acceptance remains Pending.
- BE-13-02 Completed on D02 (2026-10-27), early D23: Argon2 hash setting and
  local prompt tool; /api/auth/dashboard/login/logout/status; Secure HttpOnly
  Strict JWT cookie, eight-hour expiry, rotation/logout/restart invalidation.
  One active session per process; run one application worker. .env unchanged.
  HTTPS required; BE-13-04 explicit origins/proxy/same-origin hooks complete.
  See docs/api/dashboard-operations.md; fetch X-CSRF-Token after login/status.
  BE-13-03 now protects mutations/WS, persists lockout/audit and revokes OAuth
  delegations on dashboard logout/rotation/expiry. Evidence:
  docs/testing/BE-13-02-acceptance.md; 10 focused cases, 338 full tests and checks.
  D02 remains Pending for REF-00-04. No real observation/feed or purchase.
- BE-13-01 Completed: shared DTOs, safe error envelope/request IDs, pagination,
  aware IST dates/times, exact INR strings, typed events and API v1 compatibility.
  Existing response shapes/OpenAPI aligned; docs/api/contracts.md. No public worker
  control/auth/WS route existed then; authenticated routes now added in BE-13.
- Managed service: lifespan-owned app.state.market_service; in-process start/stop/
  status plus authenticated status/start/stop/snapshot and typed /ws/live.
  Default MARKET_SERVICE_ENABLED=false; .env unchanged. No real socket started.
  Public hub retains 256 events; four spot ticks/second, 2s bounded sends, ordered
  run/sequence replay and explicit snapshot resync. Domain event producers Pending.
  BE-13-06 history lacks indicator overlays; BE-13-14 lacks risk/recon producers;
  BE-13-20 has generated REST/WS types but domain actions/FE integration Pending.
  BE-13-15 rejects LIVE/arming; BE-13-19 opt-in replay uses a temporary isolated DB
  and blocks active managed feed/concurrent jobs. Replay job results are ephemeral.
  Migration 0006_dashboard_api applied locally under owner lock after SQLite backup;
  all ten pre-existing table counts retained. Backup in backend/data/backups.
  Prior API/type/drift checks passed; latest D03: 598 full tests, Ruff lint/format
  and strict mypy passed; one existing dependency warning. BE-10 preview contracts
  regenerated and checked with TypeScript compilation/drift checks.
- One owned worker/OS lease and one scheduler; current-day catalog and exact
  contract required. Login/token changes stop old socket and require recovery.
  Blocking jobs are joined on cancellation before disposal. Local additive migration
  0005_market_lifecycle applied under owner lock; existing market data retained.
- Calendar: sourced nse_2026.json includes Budget/Muhurat overrides. Unknown years
  (including needed prior-year history) block. 15:30 is the common application
  cutoff, distinct from published 15:40 F&O close. Source notes are in BE-06 evidence.
- Recovery proves source/derived coverage before retiring completed gap prefixes;
  original gaps/revision/fences are archived. Fresh unfinished live volume remains
  partial and entries blocked. Keep all original recording run files for restart.
- Isolated replay uses production candle/Renko persistence and file-hash provenance.
  Tick restore requires explicit complete recorded ordering; missing/gapped order
  or minute seeds require rebuild. No tick parity or enabled trading is claimed.
- Single coding agent, existing model/Standard speed; no extra agents or paid API.
  H checkpoint: 90k input + 20k output, soft only, not an account quota. Exact
  tokens/allowance unavailable: Unknown. Use included allowance; extra cash INR 0.
- Project ceiling INR 20,000 including fees; target INR 10,000. Historical spend,
  current plan/price, renewal/expiry/reset and headroom UNVERIFIED, not zero or an
  available INR 20,000 balance. No purchase/recharge initiated or authorized.
- Already-requested account inputs remain outstanding: receipts/total spent,
  Codex plan and INR renewal price/date, allowance/reset, Kite/TradingView access.
  Missing readings do not block included independent coding. Ledgers: spend-ledger,
  daily-log and paper-journal CSVs. Blank actuals remain Unknown.
- Paper: zero qualifying sessions; D01 journal is development BLOCKED, not an
  observation/trade. Manual practice not reported; no fills/P&L invented. Preserve
  any market-hour baseline; develop using replay/test DB. Check actual feed/paper
  state before coding when a real session is in progress.
- Targets remain conditional: automated trial D24-D30, candidate D45, D60 review
  only with gates and 20 qualifying sessions. Live-money work stays outside plan.
- In-session alerts: renewal within 3 days, allowance <=20%, cash thresholds and
  missing account facts. No billing meter or background renewal notification exists.
- On next turn read this, current daily row and relevant README/code only. Update
  evidence/counts/daily rows/handoff together. README.v1.md remains immutable.
