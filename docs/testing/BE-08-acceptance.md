# BE-08 acceptance — 2026-10-28 (D03)

BE-08-01 through BE-08-13 are implemented and covered by 54 focused tests.
BE-08-14 remains **Pending**: no actual REF-00-07 TradingView debug export or
confirmed chart settings are present. Synthetic sequences are development tests,
not TradingView parity, paper observations, trades or formal burn-in evidence.

| IDs | Implementation and evidence |
| --- | --- |
| 01 | `app/indicator/inputs.json` records every original Pine input with literal names, defaults, bounds and options. `settings.py` rejects unknown inputs, invalid types, nonfinite values and invalid HHMM. Defaults are source defaults, not user-confirmed chart settings. |
| 02–04 | `math.py`: SMA-seeded Wilder RMA, ignored missing observations, RSI gain/loss smoothing, true range including previous-close gaps, ATR on supplied Renko OHLC. Hand-calculated warm-up, monotone/flat/alternating and gap sequences. |
| 05 | Supertrend band carry, strict crossing/equality boundaries, negative uptrend direction, downtrend initialization and explicit ATR warm-up. Tests include equal upper/lower boundaries and gap ATR smoothing. |
| 06 | Crossover/crossunder with previous equality, missing history, barssince before/after first occurrence, bounded series access, missing-skipping SMA and rolling sums. Both use the requested count of nonmissing values within retained history. |
| 07 | `variables.json` inventories every Pine `var`, its original expression/type/default, and presentation-only handles. All computational values/arrays are stored in a version-1 JSON snapshot together with RSI/ATR smoothing, previous series, run/day/order identity and exact input map. UI handles remain null. Persistent storage reuses `LifecycleStore`; no production database migration is required. Invalid identity/config/version and damaged smoothing/variable values are rejected. BE-09 owns future signal/trade state updates and atomic event/result persistence. |
| 08–10 | `engine.py` consumes committed `market.renko_builder.Brick` objects, requires contiguous indices from zero, permits ordered equal-time bricks and rejects duplicates/gaps/backward/naive timestamps before mutation. Tracks Pine color/run, flips and `nz(barssince,99)+1` trend age. Swings capture the previous brick close/RSI/index on the exact color transition, after Pine's day reset. Restart outputs match continuous processing across multiple warm-up split points. |
| 11–12 | `flow.py` uses bounded completed futures bars and exact contract identity. Window deltas use `flowBars` prior observations; volume is previous volume divided by the previous 20-bar mean. Session VWAP uses HLC3 weighted by volume. Build-up thresholds, daily references, VWAP side, volume spike, day direction and final score follow Pine. Absent/disabled OI stays unavailable and contributes neutral build-up without disabling price/volume factors. Duplicate, overlapping, missing same-day and unfinished bars are rejected. Pass the exchange `SessionCalendar` for timeframe/session alignment checks (including shortened last bars); calendar-free use is for synthetic tests. |
| 13 | `IndicatorEngine.context` exposes the existing committed-source `session_context` at a brick's aware timestamp. Daily/prior-session OHLC and first-15-minute range retain missing/partial states and exchange calendar alignment; no future candle is admitted. Isolated persistence/context test plus existing market-context tests. |
| 14 | `python -m app.indicator.parity debug.csv --settings inputs.json --tolerance 1e-8` compares each aligned RSI/ST/direction column and reports the first divergent brick/column/expected/actual. Absolute numeric tolerance defaults to 1e-8; direction must match exactly. Empty/invalid exports fail. Hand-authored CSV tests verify match and first divergence; actual exported comparison remains blocked. |

Validation: 421 full tests passed (54 focused BE-08), with one existing
Starlette/httpx dependency warning. Ruff lint and format checks passed across
the backend; strict mypy passed for all 62 application source files. After the
rolling-sum missing-value correction, all 54 focused tests and quality checks
were rerun successfully.

Run commands from `backend` with the existing `.venv/Scripts/python.exe`.
Debug CSV columns: `index,time,open,high,low,close,rsi,supertrend,direction`.
Indices start at zero, times include timezone, and empty/`na` cells mean warm-up.
Use the same complete source history, inputs and OHLC (including wick settings)
as TradingView. This checker consumes exported OHLC directly; it does not prove
Renko construction parity. Reconcile the actual chart/export identity first.

Reference material: original `docs/pine/renko_indicator.pine` is unchanged;
[TradingView Supertrend calculations](https://www.tradingview.com/support/solutions/43000634738-supertrend/)
and [RSI calculations](https://www.tradingview.com/support/solutions/43000502338-relative-strength-index-rsi/).
These formulas guide the implementation; only the missing export can establish
observed equality with the user's Pine execution, including startup edge cases.

The engine is an isolated library for replay/development. It does not activate
the managed feed, produce trading signals or simulate fills. The live worker and
its release/configuration are untouched. Futures context is rebuilt from committed
source bars after restart; indicator snapshots alone do not restore that source.
No purchase, broker login, real market session or live database change occurred.

Next independent implementation: **BE-09-01**. Remaining BE-08 acceptance:
**BE-08-14**, awaiting REF-00-07. No stage/G2 completion is claimed.
