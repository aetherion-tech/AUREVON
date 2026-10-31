# UI-LIVE-B3 — construction compatibility and activation status

2026-10-31, D06. Later WICK1 supersedes the representation/replay/renderer limitations below: observed wicks now survive end to end. Managed five-minute/wick construction and feed acceptance remain Pending. See UI-LIVE-B3-wick-support.md. **B3 remains Pending**, not a completed UI/live batch.
Product counts remain 237 Completed / 43 Pending; formal sessions zero.

## Completed preparation

All supplied settings/anchor screenshots are retained and hashed in
`UI-LIVE-B3-input-evidence.json`. A machine-readable partial actual package now
exists at `docs/pine/reference_package.actual.json`, separate from the template.
It records NSE:NIFTY, five-minute Traditional50, Close, wicks enabled,
Asia/Kolkata, and completed historical close22700 at
2026-10-27T13:25:00+05:30. Known saved trade-plan inputs are separate from the
unconfirmed remaining overrides. Missing history dates/exports remain null/empty.
No expected results, dates or confirmations were synthesized.

New read-only diagnostic, from backend:

```powershell
.\.venv\Scripts\python.exe -m app.tools.renko_reference_check
.\.venv\Scripts\python.exe -m app.tools.renko_reference_check --check
```

The first command prints a report; `--check` exits **2** when blocked. It does
not import app.main, open a DB, access Kite, change configuration or start/stop
services. Only selected nonsecret Settings fields are printed. Other reference
packages can be checked with `--reference PATH`. Valid numeric/time/input shapes
are required; matching settings only permit isolated validation, never readiness.
Anchors on an equivalent 50-point grid are compared as equivalent; the observed
timestamp remains reference lineage, not a runtime seed.

Retained current result: [UI-LIVE-B3-compatibility.json](UI-LIVE-B3-compatibility.json).

## Why configuration alone cannot complete B3

- `market/renko_builder.py`: Brick.high/low derive only from open/close; it cannot
  represent the observed high22804.85 above body22700–22750.
- `market/service.py`, `history_renko.py` and readiness/resumption paths require
  minute_close. The five-minute futures flow aggregator does not change this
  underlying Renko construction interval.
- `indicator/full_parity.py` explicitly rejects non-body-only OHLC. Dropping
  actual wicks changes ATR/Supertrend and other high/low-dependent calculations.
- Current local Settings still has renko_anchor=null. Blindly setting 22700
  would leave the interval/wick mismatch and does not recover a matching history.
- Loaded seed/reference history and remaining saved indicator overrides are not
  supplied; no genuine feed-driven acceptance was performed. Replays are not live
  evidence. Existing gates remain unaccepted.

Engineering still needed: a coherent five-minute Close/wick-capable construction
model covering history/live, persistence/restoration, source identity, renderer
and indicator validation, tested against actual reference exports. Screenshots
cannot establish intra-period wick behavior, seed history or sequence parity.
Do not change the TradingView settings to conceal this mismatch or bypass
entry gates. Existing source checkpoints must not be relabeled/overwritten.

## Verification performed

- Selected Renko/reference/history/service tests: **52 passed**, one existing
  Starlette/httpx deprecation warning. Command from backend:
  `python -m pytest tests/test_renko_reference_check.py tests/test_renko.py tests/test_history_renko.py tests/test_market_service.py -q`.
- After adding malformed input-confirmation validation: final focused diagnostic
  suite **14 passed**. This is a separate final focused run, not a repeated
  full 52-case suite or evidence of five-minute/wick functionality.
- Targeted Ruff lint/format and strict mypy: PASS. `--check` exit2 verified.
- Original hash/append-only debug source integrity PASS; Pine compilation not
  performed. Read-only local_ui_readiness: BLOCKED, runtime NOT_CHECKED.
- No frontend change/new browser run in this B3 preparation. B2's 13 HTTPS
  checks and B1's accounting tests remain separately recorded.

Operator .env/DB/feed/services/processes and original Pine unchanged. This CLI
needs no running-server restart. Usage/cash/headroom/renewal remain Unknown;
extra paid usage INR0. No purchase. Continue independent B4 while reference-led
construction work is blocked; do not mark B3 Completed.
