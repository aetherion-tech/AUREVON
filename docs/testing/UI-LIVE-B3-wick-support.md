# UI-LIVE-B3 observed wick support

2026-10-31 D06. WICK1 engineering foundation delivered. Overall B3 Pending;
241 Completed / 39 Pending, formal sessions0. No new master acceptance.

## What changed

Added immutable WickBrick for supplied OHLC evidence. Its explicit Decimal
wick_high/wick_low must be finite, positive and enclose the brick body. The
existing Brick and RenkoBuilder remain unchanged: body-only serialized payloads,
retry identities and old checkpoints retain their original fields/semantics.

brick_from restores observed extrema instead of dropping them. Indicator
repository input identity and chart publication retain them, and changing only
a wick rejects a committed retry or invalidates source-bound publication. The
full parity reader now supplies actual high/low via WickBrick; it still requires
independent context and full signals/events inputs, and does not fabricate them.

BrickData has additive optional exact-decimal wick fields; incomplete or invalid
OHLC is rejected. OpenAPI and generated TypeScript are updated together. The
renderer draws supplied wick strokes, includes extrema in the price scale and
accessible descriptions, and retains body-only rendering for legacy data. Wicks
are not inferred for an old body-only payload.

## Actual reference validation

Retained export SHA2569497c1713821e75703883b5e54ffd1b451aaf53c47fbecae6f4acc5bf20f9d68:
6904 bricks,1274 with extending wicks, exact storage/restoration/API values.
All6904 RSI/ST/direction results after actual WickBrick restoration match the
observed export at unchanged1e-8 tolerance. Max RSI error4.263256414560601e-14;
max ST error3.637978807091713e-12. Settings used atrLen10/factor2.5/rsiLen14;
remaining exact saved inputs are not certified as source defaults. This is
observed OHLC/maths validation, not independent construction or full G1/G2.
Machine receipt: UI-LIVE-B3-wick-replay.json. Originals are unchanged/local.

## Checks

- Selected82 backend tests PASS: new wick validation/legacy identity plus Renko,
  history, chart publication/API/source tampering and full-parity regressions.
- 38 frontend tests PASS; build, types and ESLint PASS; regenerated contracts/check
  PASS; selected Ruff lint/format and strict mypy PASS; Pine integrity PASS.
- Five built HTTPS checks PASS on isolated5174: real wick publication/API/render,
  desktop/mobile layout, equal-time history/paging/layers, incremental updates and
  source-revision recovery. Retained screenshots UI-LIVE-B3-wick-desktop.png
  and UI-LIVE-B3-wick-mobile.png inspected. Test fixture data are synthetic and reference
  unverified; they are never operator trades or genuine live-feed evidence.
- Initial dev browser run4/5: new assertion treated a vertical SVG line's zero
  layout width as hidden. Replaced that unsuitable assertion with visible parent,
  attached stroke, computed stroke/width, in-bounds y extents and screenshot review.
  Final built run5/5 PASS. Windows socket-reset message during deliberate WS
  recovery retained; checks passed. No feature check or reference gate was removed.
- Full backend suite:881 PASS,455.43s,one existing Starlette/httpx deprecation
  warning. Final29 focused full-parity/wick tests PASS, including one new parser
  sensitivity regression added after full-suite collection. Continuous tolerance
  is unchanged. No FE/browser check is presented as genuine market evidence.

Commands from backend:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_wick_bricks.py tests/test_chart_history.py tests/test_pine_parity.py tests/test_renko.py tests/test_history_renko.py -q
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m app.tools.export_api --check
.\.venv\Scripts\python.exe -m app.tools.reference_debug --check
```

From frontend:

```powershell
npm.cmd test
npm.cmd run build
npm.cmd run lint
$env:PLAYWRIGHT_BUILT='1'
npm.cmd run test:browser -- tests/live.spec.ts --grep 'observed wick|chart|Renko'
```

## Next and runtime limits

Managed spot aggregation and Renko construction still use minute closes/body-only
bricks. No five-minute/wick capability or readiness switch was enabled. Next is
a coherent five-minute Close/wick construction path across history/live,
unfinished-period persistence, restoration and explicit configuration fencing,
validated against matching independent source inputs. Then publish a matching
seeded history and verify genuine eligible-session updates. No more export-prefix
or debug/original equality requests are needed. Current UI may still show no
history; renderer support alone cannot supply absent operator data.

Existing8000/5173 owners, operator DB/.env/feed and original Pine preserved.
Refresh5173 loads renderer changes. Backend contract/restore changes require a
future safe owner restart after observation/flat/feed-stop checks, never duplicate
owners. Replay results have not been silently rebuilt. Usage/cash/headroom/renewal
Unknown; extra paidINR0, ceilingINR20000; no purchase.
