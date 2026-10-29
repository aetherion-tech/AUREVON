# BE-13 acceptance and remaining dependencies

Updated 2026-10-29, D04: **20/20 BE-13 tasks code accepted**. Actual UI, managed activation and G2/G3 are separate gates.
[Chart-history evidence](BE-13-06-acceptance.md) and [domain/client evidence](BE-13-domain-acceptance.md).
Product total: 168 Completed / 112 Pending of 280. No documentation row is counted.
Latest: 768 full tests, 47 new domain/client cases; Ruff/mypy/OpenAPI/TypeScript checks pass.
The original D02 transport/security acceptance remains preserved below.

| Task | Status | Evidence or concrete remaining requirement |
| --- | --- | --- |
| BE-13-01 | Completed | Shared v1 contracts and safe errors; existing evidence retained |
| BE-13-02 | Completed | Argon2 and separate dashboard sessions; existing evidence retained |
| BE-13-03 | Completed | Shared mutation/session/CSRF/origin enforcement; WebSocket auth checked throughout connection; persistent five-failure lockout and payload-free audit intents/outcomes; revoked OAuth delegation |
| BE-13-04 | Completed | Explicit origins, credentialed CORS, proxy contract and optional production same-origin static mount; no client secrets; synthetic built-frontend hosting check |
| BE-13-05 | Completed | Actual managed feed/readiness/status/start/stop and `/api/live/snapshot`; contract selection, quality, recovery and source configuration identity |
| BE-13-06 | Completed | D04 typed replay overlays, validated source publication, source/settings/revision fences, first-index/equal-time paging and SQLite snapshot isolation; docs/testing/BE-13-06-acceptance.md |
| BE-13-07 | Completed | D04: Persisted source-linked signals/explanations and indexed preview/admission/reject decisions; bounded authenticated reads. docs/testing/BE-13-domain-acceptance.md. |
| BE-13-08 | Completed | D04: Owner-provided PAPER runtime, durable prepare/confirm/close/kill, current server evidence and final gates, actual legs/orders/fills; retries/audit verified. docs/testing/BE-13-domain-acceptance.md. |
| BE-13-09 | Completed | D04: Scoped history/keyset/detail and matching bounded CSV filters/media contract; exact-money schemas. docs/testing/BE-13-domain-acceptance.md. |
| BE-13-10 | Completed | D04: Verified summary, daily series, period tables and by-family net; external cash flows excluded from profit. docs/testing/BE-13-domain-acceptance.md. |
| BE-13-11 | Completed | D04: Actual attached wallet/read/init/deposit/withdraw/reset/ledger; exact input, idempotency, reset confirmation, missing owner 409. docs/testing/BE-13-domain-acceptance.md. |
| BE-13-12 | Completed | D04: Validated canonical versioned settings/defaults/schema/import/export; CAS/idempotency recovery; stateful rebuild and stopped/flat verified owner rebind. docs/testing/BE-13-domain-acceptance.md. |
| BE-13-13 | Completed | D04: Read-only canonical /api/strikes/preview: no subscription/decision/reservation/order effects beyond security audit; legacy endpoint retained. docs/testing/BE-13-domain-acceptance.md. |
| BE-13-14 | Completed | D04: Transactional risk reject + existing recovery/reconciliation producers; contract-valid durable read/ack/live projection. docs/testing/BE-13-domain-acceptance.md. |
| BE-13-15 | Completed | Authenticated PAPER-only mode/status/arming contract; rejects LIVE and all arming until execution/risk integration exists |
| BE-13-16 | Completed | One public typed hub and `/ws/live`: seven payload kinds, runtime kind/payload validation; real worker tick/brick/status, attached book/replay signal/trade/position and durable alert producers; normal startup remains detached |
| BE-13-17 | Completed | Four spot ticks/second, 256-event journal, bounded sends, explicit overflow resync and 1013 close; reliable event kinds bypass tick coalescing |
| BE-13-18 | Completed | Atomic snapshot/high-water mark, process run ID, ordered sequences, resume cursor replay, expired/future/run-change resync; stale/expired auth closes 1008 |
| BE-13-19 | Completed | Opt-in authenticated bounded replay, isolated temporary DB, PAPER-only output, live-feed/concurrent-job exclusion and joined shutdown |
| BE-13-20 | Completed | D04: Generated REST/WS types plus actual frontend/src/api/client.ts; real Node-to-FastAPI auth/actions/CSRF/exact INR and resync integration; React scaffold remains FE-14. docs/testing/BE-13-domain-acceptance.md. |

See [operating contract](../api/dashboard-operations.md) for endpoints, security,
single-worker limits, replay lifetime and exact regeneration commands.

Original D02 verification: 367 tests passed (one existing dependency warning), Ruff lint/format,
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

Next task: FE-14-01. Backend/domain and typed frontend-client integration now pass; actual
reference/G2/G3 and managed pipeline acceptance remain Pending. Accepted API
transport/domain work must not be restarted. Build the React foundation using the
existing typed client; a client module is not a paper-trading UI.
