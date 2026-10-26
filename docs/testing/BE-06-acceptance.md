# BE-06 acceptance evidence

2026-10-26: 308 tests passed; Ruff lint/format and strict mypy passed. There is one
existing FastAPI/Starlette httpx deprecation warning. All broker/socket evidence
here uses synthetic data and fake SDK calls; no real account was connected.

| Requirement | Concrete checks |
| --- | --- |
| Lifespan owner, clean disposal | `test_market_service.py::test_app_lifespan_owns_service_with_no_default_broker_calls`; `test_cancellation_joins_synchronous_work_before_disposal` |
| One worker and idempotent controls | `test_owned_cold_start_duplicate_start_stop_and_scheduler`; `test_market_calendar_replay.py::test_cross_process_lease_and_bounded_event_resync` |
| Current contract selection/change | `test_token_change_replaces_worker_with_distinct_stream`; actual cold-start code selects current catalog spot/near futures and derives separate contract/token streams |
| Expiry/re-login and recovery | `test_expiry_relogin_and_real_recovery_before_resuming`: old socket stopped, original recording reconciled, missing/partial source bars replaced, completed-source proof checked and original gap evidence archived before the next worker hold |
| Sessions/calendar | `test_calendar_holidays_special_sessions_and_unknown_year`; `test_calendar_flows_into_weekend_worker_and_candles` |
| Fresh catalog/retries | `test_catalog_transient_retry_then_freshness_gate`; stale-catalog parameter of `test_fail_closed_service_paths` |
| Jobs/reminders/restart | `test_persisted_login_reminder_is_not_duplicated_after_restart`; `test_day_rollover_requires_new_catalog_and_preserves_recordings` |
| Daily/previous/ORB context | Historical complete-source context checked by `test_owned_cold_start_duplicate_start_stop_and_scheduler`; partial ORB, missing exact previous session and durable context checked by `test_daily_context_exact_previous_and_orb_restart` |
| Health/recovery/session events | `test_catalog_transient_retry_then_freshness_gate`; bounded resync and defensive snapshot checks in `test_cross_process_lease_and_bounded_event_resync` |
| Production replay | `test_recorded_events_use_production_persistence_and_preserve_provenance`: same worker/candle/Renko persistence path, isolated stream, source hashes, gap/partial retention and repeat determinism |
| Market close/missing calendar/failure | Parameters of `test_fail_closed_service_paths` and day-rollover checks |
| Migration | `test_migration_up_down_up_isolated_database`; local additive upgrade separately verified at `0005_market_lifecycle` |

The pre-existing BE-05 acceptance matrix and source fixtures are retained. The
integration fixture now runs the actual cold and recovery pipeline against a fake
historical broker, rather than replacing those stages with a success flag.

## Calendar provenance and policy

The bundled `backend/app/market/calendars/nse_2026.json` is a versioned source
snapshot reviewed on 2026-10-26:

- [2026 annual F&O holidays](https://nsearchives.nseindia.com/content/circulars/FAOP71777.pdf).
- [January 15 trading-holiday addendum reference](https://nsearchives.nseindia.com/content/circulars/CMPT72276.pdf).
- [February 1 Budget Sunday session](https://nsearchives.nseindia.com/content/circulars/FAOP72352.pdf).
- [November 8 F&O Muhurat session](https://nsearchives.nseindia.com/content/circulars/FAOP76940.pdf) and [capital-market session](https://nsearchives.nseindia.com/content/circulars/CMTR76941.pdf).
- [NSE market timings](https://www.nseindia.com/static/market-data/market-timings).

The application processes a common spot/futures window ending at 15:30. This is
its conservative processing cutoff, not a claim that the F&O exchange closes then:
the current published F&O close is 15:40. November 8 uses a 14:20 opening and the
application's 15:30 cutoff; February 1 uses 09:15?15:30. Pre-open auctions and CAS
are outside this data-path acceptance. Special-session first-15-minute context is
not evidence of Pine ORB parity. No Pine content was changed.

Annual coverage is explicit. Missing/corrupt year data, including a prior year
needed for the history window, blocks the service. The loader does not infer an
unlisted year's holidays. Future source amendments require review/versioning; no
unattended exchange-calendar updater is installed.

## Operational boundary

`create_app` owns one `MarketService` through lifespan. Startup is opt-in via
`MARKET_SERVICE_ENABLED`; the default is false and does not call the broker. Trusted
in-process `start/stop/status` methods are available at `app.state.market_service`.
No unauthenticated HTTP control endpoint or WebSocket was added; those are later
API/authentication tasks. Use one lock file per account/service across processes.
A second owner cannot open a managed socket while that lock is held.

A single coroutine schedules preparation fifteen minutes before the declared
session, current-catalog refresh, one durable login reminder per day, warm-up/feed
start and session-close cleanup. Catalog retries and recovery retries are bounded;
repeated polls do not create scheduler jobs or duplicate workers. Synchronous work
runs off-loop and is joined on cancellation before clients/engines are disposed.
Only the actual account session loader and periodic verification supply login
state; internal generation markers are never exposed in snapshots.

Completed-source validation can retire open incident markers only after proving
all affected completed bars, source quality and derived values. The checkpoint
archives retired gaps, checked revision and exact per-token completed fences.
Unfinished state is not fabricated: fresh live buckets remain partial and entry
eligibility remains blocked while source/indicator/auth/session/risk checks fail.
No delay, market date or successful socket connection bypasses that proof.

Daily context uses committed minute bars and the exact prior exchange session;
missing prior data stays unknown. Context and reminder facts live in the new
`market_lifecycle_state` table. The bounded in-process event journal has sequence
and run identity plus resync indications; it is not a durable audit/history API.
Replay requires a new isolated stream, validates frozen source files and preserves
SHA-256 provenance. Nonempty seeds require their original baseline, rather than
silently importing missing source/output history.

Schema `0005_market_lifecycle` was applied to the local SQLite database under the
managed-worker lock; it adds the lifecycle table without replacing market data.
No worker or account was started as part of the migration. No real market session,
TradingView parity, automated paper fill/ledger or formal burn-in is claimed.
