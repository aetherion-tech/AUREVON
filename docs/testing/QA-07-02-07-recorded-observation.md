# QA-07-02 / QA-07-07 — retained real-feed sample review

Accepted 2026-10-31 (D06) for the bounded actual market-data sample described
below. The capture occurred 2026-10-30 (D05); review occurred offline on D06.
No new live session, execution trial, full-day coverage or formal paper session
is claimed. Project: **241 Completed / 39 Pending**; QA-07: 3 Completed / 4 Pending.

## Source and integrity

Original operator recording retained unchanged:
`backend/data/ticks/21ce9234a1164b8b877c6804cc0420f0/2026-10-30.jsonl`.
SHA-256: `696efc784d9297258842b601b819f3d7064e1a75a2e99836dbfba63c3123715b`.

The file contains3892 ordered events:3742 ticks (3034 spot256265 and708
future15736578) and150 clock advances. Tick receipt range is
2026-10-30 10:45:38.611393–10:58:18.360021 IST, during the sourced exchange
session. Identities match the actual QA-07-01 historical-download receipt and
catalog. Historical CSV hashes are checked before and after the review; original
recording hash is also checked before/after. No database or broker access occurs.

New `app.tools.recorded_feed_review` reuses the existing strict sequence/token/
payload replay validator. It does not reorder, fill or re-record events. Two
independent workers reproduce the same15 completed candles:13 spot-minute and
two futures five-minute. Unfinished tails remain unfinished at spot10:58–10:59
and futures10:55–11:00; no wall-clock advance was added to close them.

The original/detailed comparison is retained in
[QA-07-recorded-sample-acceptance.json](QA-07-recorded-sample-acceptance.json).
Earlier diagnostic review receipts are separate, not additional observations.

## QA-07-02 acceptance: actual recorded market-data observation

The actual retained market-hours ticks, source identities, complete recording
sequence, gap flags and completed candle boundaries have now been reviewed.
This closes the master row's market-data observation scope for this sample.

- Recorded gap flag: false throughout3892 events; this is not proof of absence
  of every possible feed issue.
- Stale/delay flags are **reconstructed**, using current existing worker formulas
  at the recorded event times. Stale=true at2 startup events before both tokens
  are available; clock_or_feed_delay=true at753 sampled events. Counts are events,
  not percentages of elapsed time. The delay flag alone does not prove NTP drift.
- Socket connected state, queue drops and reconnect count were not captured;
  they remain null/Unknown. No current socket observation is claimed.
- Fourteen `advance` capture times precede the previous event by5.003–122.345ms.
  Sequence order is retained. Cross-kind captured timestamps are not guaranteed
  globally monotonic; these samples alone do not prove a wall-clock jump.
  The first review attempted an unsupported global-monotonic requirement and
  stopped at sequence285. The reviewer now reports every such occurrence
  visibly, retaining strict sequence and tick validation. No time sorting,
  suppression or mutation was used to obtain agreement.

This acceptance is based on the **review of retained actual source evidence**,
not synthetic input or a claim of contemporaneously captured status snapshots.
The bounded scope does not satisfy QA-07-03's controlled real reconnect/restart,
daily paper observation requirements, full market acceptance or formal burn-in.

## QA-07-07 acceptance: sampled source comparison and limitations

Every completed sampled candle is aligned by instrument, opening time and
completion time with independently downloaded actual historical data.
No mismatch value was changed or filtered out to make the comparison pass.

| Futures sample | Volume live / history | OI live / history | Status |
| --- | --- | --- | --- |
| 10:45–10:50 IST | 12870 /16575 | 15860520 /15860520 | Initial partial candle; capture started10:45:38, volume difference -3705 retained |
| 10:50–10:55 IST | 15795 /15795 | 15859090 /15859090 | Complete candle: exact OHLC,volume and OI agreement |

Futures closes match both historical bars. Initial partial bar open differs+1.0
and high -2.1; those differences remain in the receipt. Spot sampled closes match
12/13 minute bars exactly; maximum absolute close difference is0.10. Sampled
spot open/high/low differences also remain visible (maxima2.55/3.95/0.45). Tick
sampling and mid-bucket start do not prove historical OHLC extremes. Spot has
no live volume/OI basis; null remains unavailable, never mapped to futures data.

The sample began mid-session, so **both futures VWAP values remain partial**.
At10:55 the sampled HLC3-volume VWAP is22993.25986394557823129251701 while
the full historical-bar session basis is23008.82001167683356485675746.
The tool retains both values and their difference, with vwap_comparable=false:
the historical basis includes earlier session volume absent from the recording.
Spot VWAP is unavailable because index volume is not supplied. No VWAP equality,
TradingView parity or complete session VWAP is accepted here. The master task
asks for sampled comparison with approximations/partial flags documented; those
observed limits are the accepted result, not waived G1/G2 requirements.

## Reproduction and checks

From backend, choose a NEW report filename (existing files are refused):

```powershell
.\.venv\Scripts\python.exe -m app.tools.recorded_feed_review --recording data/ticks/21ce9234a1164b8b877c6804cc0420f0/2026-10-30.jsonl --spot-csv data/qa-07-01-20261031-boundary-verified/spot.csv --future-csv data/qa-07-01-20261031-boundary-verified/future.csv --history-receipt ../docs/testing/QA-07-01-acceptance.json --output ../docs/testing/QA-07-sample-new-review.json
.\.venv\Scripts\python.exe -m pytest tests/test_recorded_feed_review.py tests/test_tick_recording.py tests/test_recording_recovery.py tests/test_candles.py tests/test_market_calendar_replay.py -q
```

**48 selected tests PASS**, then **5 final focused tests PASS** after clarifying
unavailable spot VWAP labels; overlapping counts are not added. Targeted Ruff
lint/format and strict mypy PASS. Tests verify hash/identity/sequence/order
rejections, retained event-time regressions, deterministic replay, unknown socket
state, unfinished tails and unavailable/partial VWAP. Actual source review PASS.
No production runtime changed; no browser rerun or backend restart is needed.
Prior857 full backend and prior browser results are separate earlier evidence.

Remaining: actual controlled reconnect/restart evidence QA-07-03; actual
TradingView export/seed/remaining inputs and5-minute/wick construction for
QA-07-04/05/06/G1/G2/B3; G3,shadow,dispatch,SCM and20 qualifying-session gates.
Original Pine/config/operator DB/session/feed/owners unchanged. Formal sessions0.
Usage/cash/renewal Unknown; extra paid usage INR0; no purchase or new trades.
