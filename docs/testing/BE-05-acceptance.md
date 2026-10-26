# BE-05 synthetic acceptance matrix

Verified 2026-10-26 against isolated SQLite databases, synthetic broker responses,
recordings and fake clocks. These cases verify the recovery core; they do not
establish authenticated market operation, TradingView parity, automated paper
execution or a qualifying burn-in session. Original inline source fixtures and the
user's Pine script are preserved.

| Required case | Evidence in backend/tests | Acceptance checked |
| --- | --- | --- |
| Cold start | `test_warmup_plan.py::test_cold_start_completed_bars_and_context`; `test_history_renko.py::test_rebuild_orders_closes_emits_gaps_and_reversals_and_is_idempotent` | Completed-session ranges, source ordering, initial candles/bricks/checkpoint and repeat import |
| Mid-session restart | `test_market_persistence.py::test_active_candles_counters_and_renko_resume`; `test_recording_recovery.py::test_tail_replay_after_crash_and_repeated_restart` | Restore active builders/counters and replay only uncommitted events without duplicate outputs |
| Repeated recovery | `test_recovery.py::test_identical_recovery_has_no_requests_or_writes` | Identical repeat does not request or write data |
| Session/day rollover | `test_recovery.py::test_weekend_recovery_uses_sessions_and_resets_vwap`; `test_recording_recovery.py::test_tail_across_daily_files_and_same_timestamp_updates` | Calendar boundaries, no weekend fabrication, VWAP reset and recording sequence across files |
| Expired/missing valid broker session | `test_recovery_progress.py::test_expired_session_is_not_retried_or_written`; existing `test_kite_auth.py` session tests | Real broker read path rejects missing valid session once; no HTTP, source/derived writes or recovery-driven session-file mutation |
| Partial/unavailable history | `test_recovery.py::test_missing_sources_are_not_fabricated_and_quality_survives_restart`; `test_readiness.py::test_bad_history_cannot_release_handoff` | Missing data, partial/OI/VWAP flags and inconsistent derived state block eligibility |
| Atomic rollback | `test_recovery.py::test_failed_derived_write_rolls_back_sources_and_all_outputs`; `test_recovery_progress.py::test_failure_preserves_committed_watermarks_and_rolls_back` | Source/output/checkpoint rollback; no advancement of successful-source diagnostics |
| Validation/handoff failure | `test_readiness.py::test_validation_to_handoff_failure_keeps_processing_blocked` | Revision races and failed adoption writes leave queue processing and entry hold blocked |
| Interrupted reconciliation | `test_recording_recovery.py::test_crash_during_reconciliation_resumes_committed_cursor` | Second crash resumes after the last atomic cursor; old files remain intact |
| Entry hold | `test_readiness.py::test_configured_delay_boundary`; `test_readiness.py::test_managed_handoff_delay_and_new_gap` | Exact minimum/configured hold, gap revocation and no elapsed-time override of partial volume |
| Tick fidelity | `test_tick_restore.py` | Explicit completeness attestation, original same-time order, gap/seed/corruption/calendar rejection and disabled entries |

Source fixtures: `test_recovery.py` retains START/END/PRICES, candle(), broker(),
calendar/catalog and its checkpoint fixture; progress tests reuse that fixture
without rewriting source data. `test_readiness.py` retains its generated multi-day
spot/futures/VWAP fixture. `test_tick_recording.py` supplies normalized synthetic
ticks. Every test runs against temporary files/databases; no production market
book, ledger or Pine source is modified.

An expired-session test stubs the session loader to report no valid session; it
is not evidence of an actual account expiration/login. See BE-06-04/11 and the
real-data QA rows for lifecycle and external acceptance still required.
