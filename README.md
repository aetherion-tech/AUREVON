# AUREVON

A Python application for a Renko indicator, a future React dashboard, and paper
trading with Zerodha Kite market data. Development follows small, testable steps.

## Current progress

| Step | Status | Result |
| --- | --- | --- |
| 1. Backend foundation | Completed | FastAPI, settings, health checks, rotating logs |
| 2. Kite authentication | Completed | Login, encrypted session; real login verified |
| 3a. Instrument catalog | Completed | Daily NSE/NFO catalog; real download verified |
| 3b. Price data and Renko | Pending | Tools/storage completed; warm-up, gap recovery, integration and parity pending |
| 4. Indicator engine | Pending | Pine port and TradingView signal parity |
| 5. Paper execution | Pending | Option mapping, risk limits, wallet, simulated fills |
| 6. React dashboard | Pending | Live, History, Wallet, Settings; frontend directory not created |

The current application reports PAPER mode; it does not simulate fills yet.
Kite login and instrument metadata are implemented. Live prices, strategy
calculations, and live orders are not implemented in the web application. A
standalone live price monitor is available as described below.
The original project specification is saved in [docs/SPEC.md](docs/SPEC.md).

## Master task record: backend, frontend and release

**Last reviewed: 2026-10-25. This README is the authoritative task/status record.**
The specification describes intended behavior; an unchecked box in the original
specification is not evidence that implemented work is missing. The checklist below
was reconciled with the current application, tests and previous verification notes.

**Task totals: 280 — Completed: 59; Pending: 221.** Frontend: 57 Pending.
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
  backend result is **183 passing tests, Ruff lint/format and mypy passing**
  (2026-10-25). This does not imply real-market verification.

### How every future contributor or AI must update this record

1. Read this master record, relevant code/tests, and the matching SPEC/Pine section
   before selecting work. Never restart a Completed task merely because chat history
   is unavailable. Keep the original Pine reference intact.
2. Select the next Pending task whose prerequisites are satisfied. Report its ID.
   Default next backend task: **BE-05-07**, followed by the rest of stage 05.
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

### Ordered phases and frontend starting point

| Order | Phase | Status | Entry / exit condition |
| --- | --- | --- | --- |
| 00 | References and validation inputs | Pending | Pine saved; chart settings, debug export and reference fixtures still needed |
| 01–04 | Foundation, auth, instruments, standalone data/storage | Completed | Scoped implementation rows below completed; external checks remain in stage 07 |
| 05 | Historical warm-up and gap recovery | Pending | Historical candle/VWAP/Renko initialization completed; live merge at BE-05-07 is next |
| 06 | Backend lifecycle and market calendar | Pending | One managed worker, scheduled sessions, readiness and stop/restart behavior |
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
| BE-05-07 | Pending | Merge historical and queued live data at an explicit timestamp boundary; prevent duplicate candles/bricks and half-formed closes. | BE-05-05/06 |
| BE-05-08 | Pending | Detect reconnect, overflow and downtime gaps; track missing ranges and hold entry readiness false. | Existing persistent gap flags |
| BE-05-09 | Pending | Recover missing minute/five-minute candles, rebuild affected derived state and preserve unrecoverable-quality flags. | BE-05-07/08 |
| BE-05-10 | Pending | Define correction rules for existing partial candles and downstream bricks; rebuild affected outputs rather than silently retaining stale values. | BE-05-09 |
| BE-05-11 | Pending | Add bounded recovery retries/backoff for network/429 failures without deleting valid sessions or claiming recovery succeeded. | Historical request client |
| BE-05-12 | Pending | Coordinate request limits across managed REST calls; document standalone-process limits and avoid concurrent recovery storms. | BE-05-11; existing historical-only limiter |
| BE-05-13 | Pending | Reconcile recording events ahead of the last committed DB checkpoint after a failed transaction/crash; avoid double applying events. | Existing independent file/DB writes |
| BE-05-14 | Pending | Resume live processing only after warm-up/recovery validation; implement the SPEC post-warm-up entry delay. | BE-05-07–13 |
| BE-05-15 | Pending | Test cold start, mid-session restart, repeated recovery, day rollover, expired session, partial history and rollback. Preserve source fixtures. | BE-05-01–14 |
| BE-05-16 | Pending | Expose recovery progress, last successful source time, failure reason and readiness state for later API/UI use. | BE-05-14/15 |
| BE-05-17 | Pending | Support explicit tick-mode restoration only if lost tick ordering is available; otherwise require rebuild or report unrecoverable fidelity. | Default minute-close path first; no fabricated tick parity |

### 06. Managed backend worker, market sessions and scheduling

Depends on stage 05 for trustworthy readiness; lifecycle scaffolding may be built
earlier while trading remains disabled. Reuse existing tools instead of duplicating them.

| ID | Status | Task and completion requirement | Evidence / prerequisite |
| --- | --- | --- | --- |
| BE-06-01 | Pending | Move market worker ownership into FastAPI lifespan/service with one active worker and clean cancellation/disposal. | Standalone worker; stage 05 |
| BE-06-02 | Pending | Select spot/futures tokens from today's catalog automatically; expose selected contract identity and detect token/contract changes. | BE-03; BE-06-01 |
| BE-06-03 | Pending | Add controlled worker start/stop/status operations and idempotent handling of repeated requests. | BE-06-01 |
| BE-06-04 | Pending | Handle broker login expiry/re-login by stopping/replacing the socket safely; recover gaps before declaring ready. | BE-02; BE-05 |
| BE-06-05 | Pending | Implement IST market sessions, annual holiday data and configured special sessions; replace weekday-only assumptions. | SPEC session rules; sourced calendar |
| BE-06-06 | Pending | Refresh instruments on the morning schedule with retries and readiness blocking on stale/missing catalogs. | BE-03; BE-06-05 |
| BE-06-07 | Pending | Schedule login reminders, warm-up, feed start/stop and session rollover without duplicate jobs after restart. | BE-06-04–06 |
| BE-06-08 | Pending | Calculate previous/current day context and opening-range lifecycle using exchange times; preserve it through restart. | BE-05-04; BE-06-05 |
| BE-06-09 | Pending | Publish structured health/readiness/quality events for stale feed, clock delay, recovery and session changes. | BE-05-16; managed worker |
| BE-06-10 | Pending | Add tick-to-candle-to-Renko replay integration using the same production processing path; preserve provenance and partial flags. | BE-04 tools; BE-05 recovery |
| BE-06-11 | Pending | Test backend startup/shutdown, duplicate starts, token change, session expiry, market close and missing holiday data. | BE-06-01–10 |

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
| BE-13-01 | Pending | Define shared Pydantic request/response/event schemas, error envelope, pagination, IST dates, rupee amounts and API compatibility. | SPEC 14; existing route inventory |
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
6. Continue implementation at BE-05-07, using the master task record above.

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
It preserves state across days and ignores duplicate/older source timestamps.
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

These settings define policy for the upcoming managed warm-up/recovery worker.
They load from `backend/.env` or environment variables, but do not yet trigger
downloads, retries or entry readiness in the standalone monitor.

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
Refresh the catalog before preparing a plan. This service is callable by the
upcoming managed worker; it is not yet a web endpoint or automatic startup job.

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
BE-05-07 work; the standalone worker does not automatically adopt these seeds.
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
Verified queued-live handoff is BE-05-07 work; recovery, entry-delay enforcement,
indicator sufficiency and TradingView acceptance remain separate Pending tasks.
This initializer is a service for the upcoming managed worker, not an automatic
startup job or dashboard action.

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
