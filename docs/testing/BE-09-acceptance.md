# BE-09 acceptance — 2026-10-28 (D03)

Implementation tasks **BE-09-01 through BE-09-18** are complete.
**QA-09-19 and QA-09-20 remain Pending**: no ten-day actual TradingView debug
dataset, confirmed chart identity or G1/G2 reference acceptance has been supplied.
BE-08-14 also remains Pending. Synthetic tests do not satisfy those requirements.

| IDs | Implementation / review evidence |
| --- | --- |
| 01 | CORE uses `bsf < coreWindow`; an actual flip resets `coreDone`. Only an accepted CORE consumes it. |
| 02–03 | `features.py` compares prior swing price/RSI/index before processing the new pivot. Half-box equal/extreme boundaries, inclusive `maxGap`, first-pivot RSI thresholds, hidden continuation, armed/forming divergence and `divCrossDay` reset follow Pine ordering. Fresh regular/hidden evidence feeds bias. |
| 04–05 | `signals.py`: PB requires the opposite prior brick, current trend/color alignment and minimum trend age. BRK crosses the current pivot against its **previous-series pivot**, with inclusive age. TRAP arms on BRK even when BRK signals are disabled; failure cannot occur on the arming brick and expires strictly after `trapBars`. |
| 06 | ORB uses **Renko brick** OHLC during 09:15–09:30 IST, as the original signal block does. This is distinct from BE-08's source-market opening range. Width is inclusive; cutoff exclusive. A first outside-range event consumes its side even when ORB is disabled, misaligned, cooled down or below grade. |
| 07 | SRG uses flow score and signed volume spike, onset transitions and an inclusive two-brick arm. Accepted SRG clears its arm; an ongoing surge does not silently rearm. |
| 08 | Priority per side is DIV, CORE, ORB, BRK, TRAP, HDIV, SRG, PB. DIV/CORE ignore cooldown. Selection precedes grading: rejected grade does not fall through to another candidate. Results retain each raw candidate's acceptance/rejection reason. |
| 09–10 | Twelve aligned/run buckets and completed-run statistics, minimum samples, continuation/up probability, remaining run, nearest inclusive ceiling/floor, triggers/stretch; all ten bias factors with Pine hysteresis, bias age and strong/reversal flags. Late-entry uses current plus prior eleven bricks only after index 12; choppiness uses thirty flip observations. |
| 11–12 | DIV/TRAP evidence grades differ from alignment grades; late penalty and minimum strength match Pine. Five-character IDs use the exact alphabet, salt, multiplier/modulus and brackets. Risk factors and structured family/name/meaning/why-now/tooltip text use preserved Pine helper expressions in `text.json`. A small scalar interpreter supports only the required operators and allowlisted helpers, without evaluating Python or executing Pine source. |
| 13–14 | `trades.py`: one **indicator** position, index-price targets and capped safety reference; same-direction signals do not add positions. Exits precede entries and require a later completed brick. T2, optional safety and opposite-run exits have source priority. T1 moves the optional stop to entry, and its marker is suppressed on an exit brick. Same-brick exit/re-entry retains separate IDs and ordered events. |
| 15 | Closed-trade family/direction counts, percentage result, hold lengths, T1/T2 hits and wins; independent signal-type/grade points evaluated at `evalBricks`. Zero results are not wins. Signal, plan and exit explanations retain source wording and structured values. These are indicator outcomes, not option fills, wallet balances or actual paper P&L. |
| 16 | `strategy.py` composes accepted BE-08 maths/state with bounded series history and versioned JSON snapshots. Processing uses a working copy so failures do not advance memory. `persistence.py` commits checkpoint, brick result, candidate decisions and ordered events in one SQL transaction. Exact retries return committed output; changed brick/context/settings under the same index fail. Compare-and-swap checkpoint fencing and unique keys reject stale/racing writers. Tests cover warm-up/run restart identity, first/existing-checkpoint write rollback, retries and concurrent owners. Additive Alembic `0007_indicator` is tested up/down/up in isolated databases. |
| 17 | Full parity CLI compares RSI/ST/direction, bias, independently calculated futures flow, candidate types/directions/grades/decisions, ordered ENTRY/T1/EXIT events and IDs. Reports first divergent brick and nested field, numerical tolerance, source SHA-256 and settings. Ten-date minimum is available; the code does not certify that dates are genuine trading-session reference evidence. |
| 18 | Synthetic tests cover eight families in both directions, threshold/equality boundaries, priority/cooldown and rejected-grade interactions, missing/future context, day reset, exits/re-entry, target/safety behavior, nondefault Pine replacement, restart and persistence failure/concurrency. These are development regressions, not exported Pine parity. |
| QA-09-19/20 | Pending actual ten-session reference comparison, mismatch/regression reports, G1 prerequisites and explicit G2 baseline/settings freeze. No freeze or acceptance is recorded. |

Validation: **524 full tests passed**, including **157 indicator tests** (103
new BE-09 cases). Ruff lint/format and strict mypy passed for all 69 application
source files. One pre-existing Starlette/httpx dependency warning remains. Migration
up/down/up, data preservation, first/existing-checkpoint rollback, concurrent-writer
fencing, six restart split points and every full-parity output category were tested.

## Operation and boundaries

Use `PineEngine(stream, IndicatorSettings(...)).process(committed_brick, PineContext(...))`
for isolated development. For durable processing use
`IndicatorRepository(isolated_database_engine, stream, settings).process(...)`.
`PineContext.from_market` bridges BE-08 daily/flow outputs. All present source
prices/flow require an aware availability timestamp at or before the brick;
missing values stay unavailable. Futures calculations must use matching settings,
verified contract identity and committed exchange-aligned bars. No source context
is guessed from indicator prices. A stream's history must start at index zero or
resume its complete matching snapshot; settings changes require a new/rebuilt stream.

Replay is deterministic and uses each brick's IST timestamp. Live `useClock`
evaluation of the latest brick is not enabled. The engine supports the accepted
body-only `Brick` OHLC contract; the full checker rejects wick-bearing exports
rather than silently comparing different OHLC. Actual chart configuration is still
unconfirmed, so reference compatibility is not assumed.

**Literal Pine edge case:** with nondefault `exitOppN`/exit settings, an opposite
signal may replace an unexited indicator position without emitting EXIT. The port
exposes `replaced_trade_id` on ENTRY and does not invent an exit or closed outcome.
The original may also attach a pending T1 marker to the replacement position. This
is source behavior to include in parity review, not an option-order instruction.

The live market service, `.env`, original Pine, recording/paper baselines and local
application database remain untouched. Migration 0007 has **not** been applied to
the user's application database; apply it later under the established owner/backup
procedure when integrating the replay library. No broker subscription, real or
paper order, purchase, real observation or qualifying burn-in session was created.

## Full parity CSV and reports

From `backend`, using `.venv/Scripts/python.exe`:

```text
python -m app.indicator.parity debug.csv --full --settings inputs.json --required-days 10 --tolerance 1e-8 --report comparison.json
```

Columns are `index,time,open,high,low,close,rsi,supertrend,direction,bias_score,`
`bias_direction,flow_score,signals,events,context,futures`. Indices start at zero;
timestamps are aware; blank/`na` numerical outputs mean warm-up. `signals` and
`events` are JSON arrays. Signal fields: `type,direction,grade,accepted,reason`.
Event fields: `kind,trade_id,type,direction,price`, with null type on T1. Preserve
list order. `context` is a JSON daily-context object with `available_at` and the
optional daily fields in `PineContext`; it must not contain expected flow outputs.
`futures` is a JSON array of newly completed exact-contract bars with
`contract,start,end,high,low,close,volume,oi,previous_close,previous_oi`. Missing OI
and daily references are null. Futures history/rolling warm-up must match the
reference, including prior bars before the comparison interval; contract rollover
requires an explicitly separate reconstruction. Full parity is for confirmed
body-only Renko references; the existing maths-only comparison remains available.

Numeric tolerance applies to RSI, Supertrend and event prices. Bias, flow, grades,
directions, decisions, event order and IDs match exactly. Reports do not establish
input provenance or trading-session qualification on their own. Keep source files,
actual chart settings, G1 evidence, release identity and comparison reports together
for the later QA review. `--required-days 10` failing on a one-day synthetic fixture
is a regression test, not ten-session evidence.

Next independent implementation: **BE-10-01**.
