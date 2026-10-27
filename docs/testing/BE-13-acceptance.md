# BE-13 acceptance and remaining dependencies

2026-10-27, D02: 10 of 20 BE-13 tasks accepted. The whole stage is **not complete**.
Existing BE-13-01/02 work is preserved. New accepted rows: 03/04/05/15/16/17/18/19.
Product total: 91 Completed / 189 Pending of 280. No documentation row is counted.

| Task | Status | Evidence or concrete remaining requirement |
| --- | --- | --- |
| BE-13-01 | Completed | Shared v1 contracts and safe errors; existing evidence retained |
| BE-13-02 | Completed | Argon2 and separate dashboard sessions; existing evidence retained |
| BE-13-03 | Completed | Shared mutation/session/CSRF/origin enforcement; WebSocket auth checked throughout connection; persistent five-failure lockout and payload-free audit intents/outcomes; revoked OAuth delegation |
| BE-13-04 | Completed | Explicit origins, credentialed CORS, proxy contract and optional production same-origin static mount; no client secrets; synthetic built-frontend hosting check |
| BE-13-05 | Completed | Actual managed feed/readiness/status/start/stop and `/api/live/snapshot`; contract selection, quality, recovery and source configuration identity |
| BE-13-06 | Pending | Brick/candle keyset history and revision/config identity implemented; indicator overlays require BE-09 results |
| BE-13-07 | Pending | BE-09 signals/explanations and BE-11 persisted risk decisions do not exist |
| BE-13-08 | Pending | BE-11 positions, close/kill/confirm services and domain idempotency do not exist; no successful stub actions exposed |
| BE-13-09 | Pending | BE-12-10 trade query/export service and trade rows do not exist |
| BE-13-10 | Pending | BE-12-09 verified daily/period/family accounting summaries do not exist |
| BE-13-11 | Pending | BE-12 ledger and transactional deposit/withdraw/reset services do not exist; no invented zero balance |
| BE-13-12 | Pending | Canonical Pine/strategy inputs (BE-08-01) and settings activation/rebuild coordination required; no secrets-backed generic settings endpoint |
| BE-13-13 | Pending | BE-10-09 option-strike preview and BE-13-12 settings contract required |
| BE-13-14 | Pending | Durable alert paging/idempotent acknowledgement, recovery/source-quality producers implemented; BE-11 risk/reconciliation producers still required |
| BE-13-15 | Completed | Authenticated PAPER-only mode/status/arming contract; rejects LIVE and all arming until execution/risk integration exists |
| BE-13-16 | Completed | One public typed hub and `/ws/live`: seven payload kinds, runtime kind/payload validation; real worker tick/brick/status and persisted alert projection; domain producer integrations remain their BE-09/11/12 tasks |
| BE-13-17 | Completed | Four spot ticks/second, 256-event journal, bounded sends, explicit overflow resync and 1013 close; reliable event kinds bypass tick coalescing |
| BE-13-18 | Completed | Atomic snapshot/high-water mark, process run ID, ordered sequences, resume cursor replay, expired/future/run-change resync; stale/expired auth closes 1008 |
| BE-13-19 | Completed | Opt-in authenticated bounded replay, isolated temporary DB, PAPER-only output, live-feed/concurrent-job exclusion and joined shutdown |
| BE-13-20 | Pending | Actual REST/WS OpenAPI plus generated TypeScript and drift/type checks implemented; actions and end-to-end domain/FE-14 integration remain blocked by BE-13-06..14 |

See [operating contract](../api/dashboard-operations.md) for endpoints, security,
single-worker limits, replay lifetime and exact regeneration commands.

Verification: 367 tests passed (one existing dependency warning), Ruff lint/format,
strict mypy, deterministic
OpenAPI export, generated TypeScript drift and compile checks. New suites:
`test_dashboard_api.py`, `test_dashboard_replay.py`, `test_live_projection.py`,
`test_api_artifacts.py`; broker/catalog tests now explicitly authenticate with
synthetic credentials and isolated databases. Real production replay preserves
source bytes and leaves the market database without replay checkpoints.

Local migration 0006 applied under the managed owner lock. A SQLite backup was
created at `backend/data/backups/pre-0006-20261027T170035508706Z.sqlite3` before
upgrade; counts of all ten pre-existing market/catalog/lifecycle tables matched
after upgrade. Existing recording files were retained and no worker was started.

No fake trades, account balances, fills, P&L or signals were created. Mode and
snapshots keep entries disabled. No broker/feed started, no real market observation,
no qualifying session or purchase is claimed. `.env`, original Pine and immutable
README.v1 remain unchanged. Budget, token/allowance, cash/headroom and renewal
facts stay Unknown; existing input requests remain outstanding.

Next upstream dependency: BE-08-01 (validated Pine input map), then the indicator,
strategy/execution and accounting batches already defined in README. Accepted API
transport work must not be restarted. Finish remaining BE-13 rows against real
services; successful empty responses are not substitute acceptance evidence.
