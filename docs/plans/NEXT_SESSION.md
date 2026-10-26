# Next session - budgeted delivery plan v2

Updated: 2026-10-26. This file is a short handoff; README is authoritative.

- Product tasks: 280 total; 64 Completed; 216 Pending. D01 checks: 241 tests,
  Ruff lint/format and strict mypy passed (2026-10-26).
- Version 1: `docs/plans/README.v1.md` (immutable; SHA-256 beside it).
- Kickoff: 2026-10-26 IST (D01). BE-05-10/11 Completed; D01 stays Pending for
  REF-00-03 actual TradingView settings. Template: `docs/pine/chart_reference.md`.
  User has been asked for the real settings; do not repeat/invent them.
- Next ready code: BE-05-12 then BE-05-13 (D02 batch may start early); REF-00-04
  debug Pine copy is also independent. Honor dependencies; leave external rows Pending.
- New behavior: `recover_missing_history(..., correct_partial=True)` explicitly
  replaces completed partial bars, audits former source payloads and atomically
  rebuilds VWAP/Renko. Default remains missing-only. Read-only recovery requests
  now retry classified transient failures under configured attempts/backoff.
- Mode: one coding agent, existing model at Standard speed; no paid API/credits
  or extra agents by default. Risky logic gets a focused review, not weaker checks.
- Next coding profile: H (90k input + 20k output soft checkpoint; not an account quota).
  Included usage first. Extra cash default INR 0; exception ceiling INR 150,
  only after actual billing/allowance data, remaining-budget arithmetic and an
  explicit user purchase decision. No purchase has been made by this plan.
- Total project cap: INR 20,000 inclusive of taxes/fees. Target INR 10,000.
  Historical spend, current plan, price, expiry/reset dates and renewal dates:
  UNVERIFIED. Do not infer an available balance of INR 20,000 or a zero baseline.
- Outstanding user input (already requested): existing project receipts/total spent; Codex plan and INR
  renewal price/date; allowance/reset reading; Kite/TradingView entitlements.
  Missing billing data does not block already-included coding work.
- Money: `spend-ledger.csv`; day actuals: `daily-log.csv`; paper observations:
  `paper-journal.csv`. Blank usage/spend means unknown, never zero.
- Last usage: exact tokens/allowance/cash readings unavailable; recorded Unknown.
  No purchase/recharge initiated. Do not infer consumption is free or cash balance is zero.
- Paper: zero qualified sessions evidenced. D01 journal is a BLOCKED development
  status, not a live market observation or trade. Manual practice was not reported.
- Morning: record/check feed and paper status before coding. Manual practice
  can use the user's original Pine chart from Day 1; it is not automated paper
  execution or formal burn-in. Never invent fills or force a trade without a signal.
- Targets: automated paper trial around D24-D30 if checks pass; application
  candidate D45; acceptance review D60 conditional on 20 qualifying paper sessions.
  Live-money tasks and extensions stay Pending outside this funded milestone.
- Alerts: report renewal due within 3 days, allowance remaining <=20%, paid-spend
  thresholds and missing account data at the next active session. No background
  notification, billing access or token-meter integration is currently installed.
- Read README's v2 operating rules once; on later sessions read this handoff,
  current daily row, relevant master rows/code/Pine and ledger changes only.
  End each batch by updating those records and this handoff with real evidence.
