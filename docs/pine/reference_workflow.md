# REF collection and validation

2026-10-30, D05. REF-00-01/02/08 were already complete. REF-00-04 now has a
separate generated debug source. REF-00-03/05/06/07 remain Pending until actual
chart/data evidence is supplied. No TradingView chart or account was accessed.

## Actual chart settings — REF-00-03

Fill `chart_reference.md` from the actual chart, including exact exchange/symbol,
underlying resolution, Traditional Renko method, box size, Close/other source,
wick setting, timezone, loaded-history start, one completed brick close AND its
timestamp, date range and every input override. Application/Pine defaults do
not establish actual chart settings. Wicks require explicit review because the
full backend engine currently accepts body-only Renko OHLC. Do not remove actual
wicks from an export to make it pass.

Copy `reference_package.template.json` to a new local evidence directory and
fill known values only. Null values remain unknown, not confirmed defaults.
The existing canonical input names live in `backend/app/indicator/inputs.json`.
Record actual overrides in a separate `inputs.json`; use `{}` only after the
operator confirms every input matches the original defaults.

## Separate debug build — REF-00-04

Open `renko_indicator_debug.pine` in TradingView Pine Editor, save it under a
separate name and compile it. The source includes the original bytes unchanged
plus read-only functions and Data Window plots. It intentionally retains the
original indicator title; add only ONE copy when exporting to avoid ambiguous
column names. Never replace the original script or paste diagnostics into it.

The generated file has not been compiled in this environment. Verify the actual
compiler result, plot precision and exported column headers before REF-00-05.
Report any compiler errors verbatim without credentials. No new webhook alert
payload or signal behavior was added. Existing alert conditions are unchanged.

Thirty appended `ref_` plots cover:

- `index`, `confirmed`, `rsi`, `supertrend`, `direction` (original Supertrend
  direction convention), `bias_score`, `bias_direction`, `flow_score`, `flow_ok`,
  `run_len`.
- `sig_long/short`, `type_long/short`, `grade_long/short`, `entry_long/short`,
  `exit_now`, `t1_now`, `exit_direction/type`, `position_direction/type`, `trade_seq`.
- `active_id`, `exit_id`, `t1_id`, `t1_type`, `t1_direction`. T1 uses the prior
  position identity/type/direction so a same-brick replacement cannot relabel it.

Types: 0 none, 1 CORE, 2 DIV, 3 HDIV, 4 PB, 5 BRK, 6 TRAP, 7 ORB, 8 SRG.
CO groups CORE; DIV groups DIV/HDIV; OT groups the rest. Position fields can
retain prior state while flat: use event flags, not a nonempty ID, as evidence
of an event. An opposite-signal overwrite is not an EXIT unless `exit_now` is set.

IDs encode the five characters inside the original brackets as base 40 using
`ABCDEFGHJKLMNPQRSTUVWXYZ23456789#@$%&*+!`. This is reversible, not a sequential
trade counter. Missing IDs stay empty. The intake decodes them into additional
`active_trade_id`, `exit_trade_id`, `t1_trade_id` columns. Duplicate generated IDs
still need source/index lineage; do not treat an ID string alone as global identity.

Each debug plot requests precision 12. Check the actual CSV precision; never
relax comparison tolerance just to accommodate an unreviewed rounded export.
A conservative source plot-count bound is 63, under TradingView's 64-count
limit; this is a static check, not a compiler result.

Recheck generation from backend:

Git attributes keep the original reference checked out with its recorded CRLF
bytes and preserve the generated debug file verbatim. This keeps the original
checksum and append-only generation check stable across checkouts.

```powershell
cd D:\WorkSpace\AUREVON\backend
.\.venv\Scripts\python.exe -m app.tools.reference_debug --check
```

## Preserve exports — REF-00-05

Load at least ten actual exchange sessions plus the required matching seed and
warm-up history. Export the chart INCLUDING indicator values. Only loaded chart
history is exported; retain the original file with export time and exact chart/
input metadata. The intake requires `ref_index` starting at zero and increasing
by one. Do not rebase a truncated export or sort/deduplicate equal-time bricks.
Only confirmed bricks are accepted; re-export if an open brick is included.

After obtaining an actual file, replace the source path below and choose a NEW
output directory. `backend/data` is ignored; raw files remain local pending a
separate sanitization review. The tool does not contact TradingView or Kite.

```powershell
cd D:\WorkSpace\AUREVON\backend
.\.venv\Scripts\python.exe -m app.tools.reference_export "D:\Exports\TradingView-reference.csv" --output data/references/new-reference
```

Outputs: byte-identical `original.csv`, observed `debug.csv`, canonical `math.csv`
and SHA-256 `manifest.json`. Existing directories are refused. It accepts exact
or `Indicator: ref_name` column titles, epoch seconds/milliseconds or aware ISO
timestamps. Missing/ambiguous columns, unconfirmed bricks, nonfinite numeric
values, malformed OHLC and reordered data fail before creating output.

This is transport validation only: it does not certify ten exchange sessions,
chart settings, exported precision, provenance truth, G1/G2 or REF-00-07. No
full signals/events JSON envelope is synthesized from backend calculations.

## Matching independent source inputs — REF-00-06

Supply the same date range's NIFTY spot minute closes, exact futures five-minute
OHLCV/OI and daily context. Record exchange, segment, token, symbol, expiry and
rollover boundaries per contract. Never use a current token for an unverified
historical contract or fabricate OI when access/data is absent. Record gaps and
data-entitlement failures explicitly. Daily context needs point-in-time source
availability; do not inject later end-of-day information into earlier bricks.

The existing downloader is `python -m app.tools.download_prices --help`.
It needs confirmed token/start/end and uses the existing local Kite session.
For spot use minute candles; for exact futures use `--interval 5minute --oi`.
Use new output paths and retain original responses/files and metadata. No
download was attempted in this batch because the reference range and identities
are not supplied. Do not rotate/login broker credentials to collect fixtures
over an observing market owner.

## Reference package and comparisons — REF-00-07

Retain raw originals locally. Review account identifiers and other sensitive
metadata separately before committing sanitized fixtures; preserve market values,
row order, provenance and original/sanitized hashes. Never commit credentials.
Complete the package template with chart/settings/debug hashes, source files,
contract transitions, calendar identity, confirmed session dates and gaps.

Once actual `inputs.json` and normalized data exist, the maths check is:

```powershell
cd D:\WorkSpace\AUREVON\backend
.\.venv\Scripts\python.exe -m app.indicator.parity data/references/new-reference/math.csv --settings data/references/new-reference/inputs.json --tolerance 1e-8 --report data/references/new-reference/math-comparison.json
```

Choose a new report path to preserve earlier failures. Existing CLI policy uses
absolute 1e-8 for continuous RSI/Supertrend/event prices; categorical outputs are
exact. Review and freeze the policy before the actual baseline; never change
expected values or tolerances to conceal a mismatch. This command reports the
first difference; a passing synthetic test is not real reference acceptance.

G1 also requires independent Renko reconstruction with
`app.tools.parity_check renko`. Full G2 needs the audited JSON
signals/events/context/futures envelope described in
`backend/app/indicator/full_parity.py` and ten verified exchange sessions.
The new intake does not manufacture that envelope, missing candidate decisions,
contract context or acceptance evidence. REF-00-07 remains Pending.

## Local evidence and next action

Latest focused run: 91 tests covering intake, original preservation, maths,
parity transport and historical providers. Inputs are synthetic unit fixtures.
Receipt with source hashes and explicit acceptance limits:
`docs/testing/REF-00-source-intake-checks.json`.
Ruff lint/format, strict mypy for new tools and generation drift check pass.
Original Pine SHA-256:
`d1b4e220a8e575c3e6839ca5e2058d2de190ee56fcf308ccf31e7864088170b2`.
No operator DB, .env, owner, feed, service, original Pine or real data changed.

Next input: fill actual REF-00-03 settings; compile the separate debug build and
provide actual REF-00-05 export paths. Reference readiness remains blocked.
Using dashboard port 5173 is supported; Windows SCM verification OPS-19-03 stays
Pending and can be revisited separately. No paid access was bought. Usage,
headroom, spend and renewal Unknown; extra paid usage INR 0, ceiling INR 20,000;
formal qualifying sessions zero.

Official TradingView sources checked for this workflow:

- [Plot export and Data Window titles](https://www.tradingview.com/pine-script-docs/faq/indicators/)
- [Chart-data export and loaded history](https://www.tradingview.com/support/solutions/43000537255-how-to-export-chart-data/)
- [Plot count limits](https://www.tradingview.com/pine-script-docs/writing/limitations/)
- [Plot precision](https://www.tradingview.com/pine-script-docs/visuals/plots/)

## Batches after the current REF package

The repeat execution request found no actual chart settings or reference CSVs in
the workspace/local backend data directory. The original/debug integrity check
still passes; no unchanged test suite was rerun. REF-00-03/05/06/07 remain Pending,
not silently completed by the tooling. Counts stay 235 Completed / 45 Pending.

| Order | Batch IDs | Acceptance needed |
| --- | --- | --- |
| Current | REF-00-03/05/06/07 | Actual chart metadata, ten-session TradingView export, matching independent source data and reviewed fixtures/provenance |
| Next G1 batch | QA-07-01 through QA-07-07 | Actual historical/feed observations, controlled reconnect/restart, aligned reference grids, ten-day Renko comparison, volume/OI/VWAP samples and explicit G1 acceptance |
| Maths/G2 batch | BE-08-14 + QA-09-19/20 | Actual maths series and full event parity; QA-09 requires G1, ten sessions and explicit baseline/settings freeze |
| Integrated paper/G3 batch | QA-11-15/16 | G2, deterministic recorded indicator/strategy/execution replay twice, 20 manually checked strike examples and explicit G3 acceptance |

BE-08-14 maths comparison can proceed alongside the G1 work once valid input
exists; QA-09-19/20 cannot bypass G1. Each batch stays Pending until its specific
evidence passes. Windows service OPS-19-03 is a separate pending track; use
5173/8000 for development. Formal G4/G5 acceptance QA-19-17 remains last.
