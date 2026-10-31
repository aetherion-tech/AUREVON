# HIST-REPLAY-DATA1: actual-option input foundation

Delivered: offline validation, point-in-time quote adapter, coverage CLI and durable isolated input folders. Full historical strategy playback remains Pending. Evidence: HIST-REPLAY-DATA1.json.

## Coverage finding

Read-only audit of the default operator database found 34,004 current option contracts, earliest expiry 2026-11-03. The instrument snapshot is dated 2026-10-30; it does not establish contract/lot identities in January-March 2025. The retained 2026-10-30 recording contains 3,742 spot/futures tick events and 150 clock advances with no bid/ask depth. Eight CSVs contain spot/futures or indicator exports. No valid actual-option bundle was supplied. This is a scoped local finding, not a claim that external archives do not exist. Never substitute today's lot sizes or option premiums.

## Delivered contract

`HistoricalOptions` accepts a version-1 JSON object with `price_basis: ACTUAL_RECORDED_DEPTH`, provider and source_reference strings, chronological `catalogs` snapshots (existing Catalog schema) and chronological `quotes` (existing OptionQuote schema). Each quote embeds its exact historical OptionContract including expiry, strike, type, lot_size and tick_size. Decimal prices are strings; timestamps include a timezone. Provider metadata declares provenance; it does not independently prove authenticity.

Quote availability requires both exchange and receipt time, exact matching historical catalog identity, valid tick grid and freshness at the replay clock. Future/duplicate/out-of-order events, missing identities and estimated-price bundles are rejected. Replay can seek backward deterministically. Catalog changes invalidate old-identity quotes. Quote prices are recorded depth, not broker fills. Existing option execution assumptions and risk checks remain required before any simulated order.

Minute candles alone are deliberately insufficient for this adapter: the current planner requires executable bid/ask depth, spreads and liquidity. A separate, explicit candle execution policy would require additional design and verification; no bid/ask depth is fabricated from OHLC.

`prepare_inputs` copies bounded source bytes to a temporary folder, validates/hash-checks the copy, then atomically publishes a unique run directory containing options.json and manifest.json. A reread verifies the source digest and recomputes coverage. Each run has entries_enabled=false and no wallet/runtime connection. It stores inputs only, not trades or completed backtest results. Manifests are local metadata, not signed attestations.

Coverage reports count evidence, not full-session continuity or strategy readiness. Even a populated bundle reports INPUT_PRESENT_NOT_EXECUTION_READY. Missing data reports BLOCKED; option P&L remains null. No actual-option data was imported during development; all new test fixtures are synthetic engineering inputs.

## Commands

From backend:

```powershell
.\.venv\Scripts\python.exe -m app.tools.historical_option_coverage --start 2025-01-01T00:00:00+05:30 --end 2025-03-03T23:59:59+05:30
```

Observed: BLOCKED / historical_option_bundle_not_supplied; no estimated fallback or P&L.

When an actual depth bundle is available, append `--bundle <path>` and optionally `--runs-dir data/historical-replays` to validate and persist isolated inputs. This command does not execute trades or start the market feed. Schema generation is available through HistoricalOptions.model_json_schema().

## Remaining work

Source/verify actual historical option contracts and quotes; prepare spot/context warm-up and calendar; connect an isolated historical clock to existing indicator/planner/execution/accounting; then implement date controls, playback, positions/P&L and saved result export. No current Live-screen change, runtime restart, broker request, original Pine change or master task completion is claimed. Formal paper sessions remain zero.

## Validation results

- 35 focused input/quote/replay cases PASS (16 new input tests plus existing quote/replay cases).
- 114 existing planner, paper-execution and historical-acceptance cases PASS.
- Selected four-file Ruff lint and format checks PASS; strict mypy on the three new application modules PASS.
- Existing Starlette/httpx deprecation warning retained; no verification weakened.
- Local UI readiness still BLOCKED on BE-08-14, QA-09-19/20 and QA-11-15/16; runtime NOT_CHECKED.
- No frontend files changed or frontend/browser verification claimed in this backend input batch.

Reproduce from backend:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_historical_options.py tests/test_option_quotes.py tests/test_dashboard_replay.py -q
.\.venv\Scripts\python.exe -m pytest tests/test_option_planner.py tests/test_paper_execution.py tests/test_historical_acceptance.py -q
.\.venv\Scripts\python.exe -m mypy app/market/historical_options.py app/market/historical_replay_inputs.py app/tools/historical_option_coverage.py
```
