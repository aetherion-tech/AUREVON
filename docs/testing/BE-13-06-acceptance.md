# BE-13-06 chart history acceptance

2026-10-29, D04. BE-13-06 Completed. Next task: **BE-13-07**.
BE-13 overall is 11/20 accepted; browser paper trading remains unavailable.

25 new `test_chart_history.py` cases; 43 focused chart/dashboard/projection cases
passed. Full suite: 721 passed, one existing dependency warning. Ruff lint/format,
strict mypy, deterministic OpenAPI export/drift and generated TypeScript
drift/compile passed. No new schema migration or dependency was added.

## Delivered behavior

- Existing authenticated `GET /api/bricks` now includes typed RSI/ATR/Supertrend,
  trend direction, ten-factor bias, support/resistance, next-brick triggers,
  probability, indicator position/targets/stop and ordered ENTRY/T1/EXIT markers.
  Marker tooltips and replacement IDs are retained; these are indicator replay
  events, not broker orders, fills or actual paper positions.
- Preserve existing brick items, source/config hash, market revision and bounded
  keyset paging (1–300 items). Default `after=-1` fixes omission of actual brick
  index 0. Equal-time bricks are matched/ordered by index, never timestamp joins.
- Missing calculation values remain null. Unpublished/stale source is explicit;
  partial pages list missing overlay indices. Empty pages are distinct from an
  unavailable producer. No fake zero indicator or successful empty trading data.
- Explicit SQLite read transactions bind market identity, brick/candle page,
  indicator checkpoint and result lookup to one snapshot. A concurrent market
  writer cannot mix old identity with newly rewritten bricks. Overlay reads use
  four SELECTs, with results limited to the selected brick page, not one query
  per brick or a full indicator recomputation.
- `GET /api/candles` retains independent candle-time paging, token validation,
  source identity/revision and `indicators_available=false`. Renko overlays belong
  to brick indices; multiple same-time bricks are not collapsed onto one candle.

## Replay source publication and client contract

Existing BE-09 results were deliberately standalone replay calculations, without
a market-source binding. Matching timestamps or names alone cannot prove that a
result belongs on the requested chart. An explicit owner operation now validates
and publishes a stable replay prefix:

```python
from app.indicator.chart_history import publish_chart_history

source = publish_chart_history(isolated_engine, "the-committed-stream")
```

Use this only in an owned, isolated replay after market bricks and indicator
results have committed. It validates the restored indicator checkpoint, contiguous
prefix beginning at index 0, every corresponding persisted input brick, settings,
box size, point-in-time context availability and public result shape. It stores a
configuration/revision/settings identity plus input/result fingerprint manifest
as additive `chart_source` metadata in the existing indicator checkpoint JSON.
Publication is one serialized transaction and is idempotent for identical data.
It does not rewrite market data or indicator result/event rows.

Publication validation streams the complete prefix in batches; its work and
manifest storage scale with that replay prefix. It is not an on-tick or HTTP
operation. Page queries only load requested result rows; they also read that
checkpoint provenance metadata. No constant-size provenance or production
throughput claim is made.

1. Request `/api/bricks?stream=...&limit=100` for the first page. Inspect
   `overlay_status`, `overlay_reason`, `missing_overlay_indices` and
   `indicator_source`. Warm-up RSI/ATR/Supertrend may legitimately be null.
2. Retain `revision` and `indicator_source.source_id`. Send both `revision` and
   `indicator_source` query parameters on subsequent pages along with `after`.
   Optional parameters preserve existing API callers; chart clients must use the
   fences before combining pages.
3. On 409 discard the combined chart and reload page one. Revision/configuration,
   settings/publication or indicator advancement cannot silently splice pages.
   A first page without a fence exposes stale/unpublished availability explicitly.

Every market append/recovery revision invalidates the previous publication;
further indicator processing drops its metadata. Republish only after the next
stable replay checkpoint. Changed/missing published results, malformed bindings,
wrong input bricks and settings hashes return conflict, rather than mixed overlays.
Normal API reads never publish, calculate, activate a worker or mutate the book.

This binding verifies persisted lineage and shape, not independently sourced
futures/daily context or TradingView parity. `mode=INDICATOR_REPLAY` and
`reference_verified=false` remain explicit. G1/G2/G3, actual exports and the managed
indicator/strategy/execution pipeline remain separate acceptance requirements.

## Checks and unchanged operations

Tests cover real Pine-engine markers/levels, warm-up nulls, first-index and
equal-time paging, empty/partial/unpublished history, revision/configuration and
settings changes, corrupted inputs/results/bindings, future context, prefix
validation rollback, repository advancement/republication, bounded SQL, auth and
query bounds, candle source identity, and concurrent committed market rewrites.
TypeScript smoke checks preserve nullable maths and reject fabricated parity.

The application DB, pending migrations, `.env`, original Pine, recorded baseline,
receipt and paper journals remain untouched. All generated fixtures use isolated
databases. No real feed, paper fills, real orders, purchase or formal session was
created. Actual usage/allowance, spend/headroom and renewal facts remain Unknown;
extra paid usage INR 0. See [local UI readiness](../operations/local-paper-ui.md).
