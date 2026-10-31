# UI-LIVE-B3 maths warm-up correction

D06, 2026-10-31. B3-MATH1 engineering follow-up delivered; overall B3 stays Pending.
No new master completion: 241 Completed / 39 Pending, formal sessions 0.

The retained actual export has 6904 confirmed bricks indexed 0-6903. A complete
read-only scan found exactly one RSI/Supertrend/direction discrepancy under the
source-default maths inputs: first-brick Supertrend was 0 in TradingView and
None in Python. Subsequent warm-up rows were missing, not zero. The backend now
emits the first zero without carrying it into later ATR warm-up bars. ATR seeding,
reversal thresholds, decimal Renko and financial gates are unchanged.

Observed ten-row OHLC/Supertrend regression data contain market values only;
no account metadata. A length-one ATR test protects existing band initialization.
The hand-calculated parity fixture now reflects the observed first output.
Original source/export and comparison tolerance were not edited.

Actual comparison after fix: all6904 RSI/Supertrend/direction rows PASS with
absolute tolerance1e-8 and exact direction. Command from backend:

```powershell
.\.venv\Scripts\python.exe -m app.indicator.parity data/references/nifty-debug-20261031-third/math.csv --report data/references/nifty-debug-20261031-third/math-default-after-warmup-fix.json
```

This uses atrLen10/factor2.5/rsiLen14. Debug-to-original saved input equality is
confirmed; remaining exact saved values are not independently confirmed as
source defaults. This observed maths match does not establish full signals,
strategy/context parity, independent Renko reconstruction or live readiness.
Both before/after reports and byte-identical originals remain local.

Checks:159 selected indicator/strategy/parity cases PASS; Ruff lint/format,
strict mypy for math.py and original/debug Pine generation check PASS. Full backend suite:871 PASS, one existing Starlette/httpx dependency warning,
398.38s; command `.\.venv\Scripts\python.exe -m pytest -q`.
Receipt: UI-LIVE-B3-math-warmup.json. One new
length-one test initially had an incorrect hand expectation (14 versus existing
initial band0); the expectation was corrected using the band recurrence, and
all159 cases then passed. No production behavior was changed for that test.

Next engineering: implement an explicitly versioned five-minute Close/wick
construction path, with matching history/live aggregation, persistence of wick
and unfinished aggregation state, restoration and configuration fences. Extend
public brick OHLC and renderer together; old body-only checkpoints must not be
relabeled. Validate independently against matched price inputs before activation.
Do not use this CSV as an operator live feed or remove wicks to force a match.
Anchor settings, publication and genuine session updates remain separate gates.
No more history/export requests are needed for the resolved prefix issue.

Existing8000/5173 owners, operator DB/config/feed and original Pine preserved.
Backend fix is on disk; existing owner has not been restarted. New code requires
a safe restart after observation/flat/feed-stop checks, never a duplicate owner.
No frontend changes. Existing stored replay results have not been rewritten.
Usage/cash/headroom/renewal Unknown; extra paidINR0, ceilingINR20000; no purchase.
