# UI-LIVE-B3 five-minute Close construction

D06,2026-10-31. Later BIND1 connects the managed lifecycle paths described as next work below; see UI-LIVE-B3-managed-binding.md. Operator activation/feed acceptance remain Pending. CONSTRUCT1 engineering delivered; overall B3 Pending.
Counts241 Completed/39 Pending;formal0. No master acceptance inferred.

## Implementation

FiveMinuteCloseRenko consumes completed spot minute candles against an explicit
exchange calendar. It accepts a source close only when all five ordered minutes
of that session-aligned bucket are present and complete. It never flushes an
unfinished bucket, fills a missing minute or treats an intraperiod move as a
completed Renko brick. Direct on_price calls are rejected on this profile.

Only completed five-minute Close values accumulate wick extrema. Raw minute
high/low and intraperiod minute closes are not wick inputs. Extending wicks are
on the opposite side only, for swings greater than one box; synthetic properties
verify one-to-two-box bounds, two-box reversal and unchanged anchored body grids.
First emitted brick carries the accumulated excursion; later bricks from the
same close preserve equal-time index order. The residual actual close remains
available as the next excursion seed. This explicit implementation still needs
matched independent-source/reference construction acceptance.

Public rule source: TradingView, What do Renko wicks mean?
https://www.tradingview.com/support/solutions/43000481040-what-do-renko-wicks-mean/
Its Close-source rule and reversal-side interpretation guided construction;
it does not certify this implementation or the user's full historical chart.

Missing/partial periods are discarded, with sticky gap evidence. Subsequent
complete source periods may produce diagnostic output, but the gap is not
silently cleared. Overnight continuity is permitted only across consecutive
supplied sessions with a completed prior close and new opening; missing a whole
supplied session remains a gap. Invalid/duplicate/backward/out-of-calendar input
cannot mutate the construction state.

MarketPersistence has an explicit source_minutes=5/calendar opt-in, with a
version2 construction identity (interval, close-wick rule, box/anchor and calendar
fingerprint). Default source_minutes=1 retains the original configuration and
checkpoint layout. New state also retains bucket, completed-minute count/close,
last source timestamp and pending wick extrema. Restore validates the shape,
calendar alignment, geometry, summary consistency and immutable configuration.
The same method serves historical minute sequences and the worker's completed
minute buffer. Commit/CAS handling remains atomic; failed save does not advance
construction/counters, and retry consumes the buffered source exactly once.

## Verification

105 selected tests PASS: construction, restart at each of29 split points,
property-based close/body/wick checks, invalid inputs, missing/partial periods,
calendar/session boundaries, damaged checkpoints, SQLite rollback/retry and old
profile rejection, plus existing persistence/recovery/history/production replay
coverage. Selected Ruff lint/format and strict mypy PASS; original/append-only
Pine integrity PASS. A source-file annotation cycle found by strict mypy was
resolved with explicit existing persistence attribute types, without ignores or
weakened checks. Full backend suite932 PASS in373.68s (one existing Starlette/httpx warning).
Final106 focused cases PASS, including a positive-grid-seed guard/regression
added after full-suite collection; test counts overlap. Selected lint/format and
strict mypy rechecked PASS after that guard.

Commands from backend:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_five_minute_renko.py tests/test_market_persistence.py tests/test_recovery.py tests/test_history_renko.py tests/test_market_calendar_replay.py -q
.\.venv\Scripts\python.exe -m mypy app/market/five_minute_renko.py app/market/persistence.py
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m app.tools.reference_debug --check
```

Actual retained QA-07-01 historical spot source SHA256
4b322de55cd1e611cba33e2ca49b1cdf1415facdec7e636b42ae2c2812603575 was read-only:
375 completed minutes,75 periods,4 generated bricks,no extending wicks,zero
construction gaps. Restart after minute188 yields identical bricks and state.
No new download or broker access. This is a cold grid seed using the recorded
22700 grid, not a restoration of the full TradingView historical calculation
state. There are no real wick observations in this single-day output; synthetic
wick tests and prior observed-wick transport checks remain separate evidence.
Receipt: UI-LIVE-B3-five-minute-actual-sample.json.

## Next / current limits

The managed service, Settings profile, historical import/recovery factories and
operator stream are not switched to this experimental profile. Next task binds
the coherent constructor into those lifecycle paths with stable calendar identity,
matching seed/reference validation and guarded chart publication. A rolling
calendar coverage change currently refuses checkpoint reuse intentionally; owner
binding must supply stable, versioned coverage rather than silently relabel it.
Current renko_reference_check still reports managed construction unsupported
because the default managed factories remain minute-close; that is accurate.
No actual five-minute/wick parity or genuine socket/feed acceptance occurred.
No more CSV-prefix exports or debug/original equality questions are needed.

This backend-only batch changes no frontend flow; prior WICK1 renderer/browser
acceptance remains separate. Existing8000/5173 owners/operator DB/.env/feed/Pine
preserved. No restart performed. Backend code needs a future safe owner restart
after observation/flat/feed-stop checks; restarting alone does not activate the
new profile or make the current empty chart populate. No fake operator trades.
Usage/cash/headroom/renewal Unknown; extra paidINR0;ceilingINR20000;no purchase.
