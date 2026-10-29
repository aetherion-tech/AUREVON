# FE-16 History/P&L acceptance

Accepted 2026-10-29, D04: FE-16-01 through FE-16-08, all eight code tasks.
This acceptance uses isolated synthetic data; it does not enable a managed paper
runtime, verify reference gates or count a formal paper session.

| IDs | Delivered behavior |
| --- | --- |
| 01 | Today/Week/Month/All-time account-wide PAPER cards show exact net, server capital return, trades and win rate. Zero denominators stay unavailable. |
| 02 | Daily net bars/cumulative line for the selected IST date range and twelve calendar-month bars/line. Cumulative sums use exact integer paise; SVG geometry alone uses approximate numbers. Accessible tables retain exact values. Deposits never enter profit. |
| 03 | Weekly/monthly tables include dates, trades/wins, gross, costs, net, capital return and actual best/worst trade IDs/net amounts. Empty periods have no fabricated extrema. |
| 04 | Date, PAPER mode, family, direction, result and grade filters; reset and URL persistence. Invalid dates/ranges, unsupported grades and LIVE mode stay explicit and block trade requests. |
| 05 | Server-sorted, cursor-paged closed-trade table supports time/net ascending/descending; stable ID tie-breaking, IST times, signal/strength, symbols/quantity, entry/exit prices, costs/P&L, returns and duration. Missing legacy fields remain unavailable. |
| 06 | Expandable detail loads persisted legs, fills, order creation/eligibility/fill timeline, matched indicator explanation and a source-labelled Renko context chart around that signal. This is not an option-price chart or proof of original reference settings. Unlinked/unpublished history stays unavailable. |
| 07 | CSV uses the identical active server filters/order, exports all matching pages rather than the displayed page, preserves existing column names, and provides progress/error/retry. Export is cancelled if its filter scope is unmounted. |
| 08 | Tests cover sort/paging ties, stale cursors, filters/reload/reset, request cancellation, empty periods/zero denominators, exact totals and export consistency, invalid URLs, detail/chart, and mobile overflow. |

## Verification

- Full backend suite: **780 passed**, one existing Starlette/httpx warning.
- Follow-up targeted verification: **7 passed**, covering actual entry/exit fill
  projections, both sort directions and time/net cursors, CSV ordering, period
  extrema, signal lineage and HTTP numeric direction parsing.
- Frontend unit/component suite: **21 passed**, including six History cases for
  storage-limit money, exact cumulative sums, cash-flow exclusion, URL parsing,
  invalid calendar dates, zero win-rate denominator and chart values/empty state.
- Full Chromium HTTPS suite: **20 passed**, including six new History workflows.
  They verify cards/charts/table/CSV totals, URL persistence, all-page export,
  paged sort, detail/timeline/chart, stale-cursor reload, empty/error states,
  mobile layout and cancellation of a superseded filter request.
- Build/strict TypeScript/ESLint, Ruff lint/format, strict mypy and generated
  OpenAPI/TypeScript drift/compile checks pass. Desktop/detail/mobile artifacts
  are ignored test outputs; mobile History screenshot inspected.

Run from frontend: `npm.cmd run build`, `npm.cmd run lint`, `npm.cmd test`,
`npm.cmd run test:browser`. Tests use isolated ports 5174/18765 and a temporary
SQLite/TLS environment, preserving operator ports 5173/8000 and market evidence.
Typed browser route fixtures supply deterministic historical outcomes; real
wallet/domain tests independently create and settle synthetic paper spreads.

## Scope and consistency

The UI explicitly separates account-wide fixed-period cards/weekly-monthly tables
from date-range account-wide charts and filtered trade-table/CSV results. Family,
direction, grade and result filters affect table/export, not the account summaries.
This avoids presenting a filtered subset as a total account return. Daily charts
accept up to 367 calendar days; the trade table can query longer ranges.

Time sorting retains indexed keyset paging and the original default ascending
order for existing clients. The History UI and latest-closed card request descending
order explicitly. Net sorting uses exact Decimal comparisons across the entire
filtered result, with a 10,000-match bound; it never sorts money as float or only
within the displayed page. Cursors fence revision, filters, limit and order.
An invalid/stale cursor requires an explicit first-page reload.

Additional quantity/prices/duration fields are read-only projections from the
stored position/orders. Persisted wallet ledger, trade-summary payloads and daily
projections are unchanged; tests compare stored payloads before/after reads. CSV's
existing stable fields and formula protection remain. Period extrema are added at
the API view boundary, preserving accounting projection/reconciliation contracts.
The HTTP boundary now accepts exactly `direction=1` or `direction=-1`; invalid
numeric directions reject while the strict internal query remains intact.

No migration, wallet reset, trade deletion, real-market session, broker action or
operator backend restart was performed. Restart the existing backend safely to
load the new read-only API code. Missing owner/schema/reference acceptance still
blocks paper operation; unavailable states remain honest.

The user's standing request is saved near the top of NEXT_SESSION.md: every task
completion must include exact BE/FE launch commands, the URL/screen to inspect and
already-running/restart guidance. This documentation change is not a product-task
completion. Next: FE-17-01. Formal qualifying sessions: 0; extra paid usage INR 0;
actual allowance/spend/headroom/renewal remain Unknown.
