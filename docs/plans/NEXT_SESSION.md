# Next session - budgeted delivery plan v2

Updated: 2026-10-26. README is authoritative.

- Product tasks: 280 total; 82 Completed; 198 Pending. Latest: 328 tests,
  Ruff lint/format and strict mypy passed. One existing dependency warning.
- BE-05 complete (17/17); BE-06 complete (11/11), verified early on D01.
  Evidence: docs/testing/BE-05-acceptance.md and BE-06-acceptance.md.
- Next dependency-ready code: BE-13-02 (dashboard auth, distinct from Kite login).
  REF-00-04 separate Pine debug copy remains independent. Preserve original Pine.
- D01 Pending only for REF-00-03 actual TradingView settings (already requested;
  do not repeat/invent them). D02 Pending REF-00-04. D03/D05 code batches Completed
  early; D04 Completed early with BE-13-01. D06 code complete; real market recording/observation
  not supplied, so its daily observation acceptance remains Pending.
- BE-13-01 Completed: shared DTOs, safe error envelope/request IDs, pagination,
  aware IST dates/times, exact INR strings, typed events and API v1 compatibility.
  Existing response shapes/OpenAPI aligned; docs/api/contracts.md. No public worker
  control/auth/WS route activated. BE-13-02/03 supply dashboard auth/protection next.
- Managed service: lifespan-owned app.state.market_service; in-process start/stop/
  status only. Default MARKET_SERVICE_ENABLED=false; .env unchanged. No public
  control route/WS before API/auth work. No real broker socket was started.
- One owned worker/OS lease and one scheduler; current-day catalog and exact
  contract required. Login/token changes stop old socket and require recovery.
  Blocking jobs are joined on cancellation before disposal. Local additive migration
  0005_market_lifecycle applied under owner lock; existing market data retained.
- Calendar: sourced nse_2026.json includes Budget/Muhurat overrides. Unknown years
  (including needed prior-year history) block. 15:30 is the common application
  cutoff, distinct from published 15:40 F&O close. Source notes are in BE-06 evidence.
- Recovery proves source/derived coverage before retiring completed gap prefixes;
  original gaps/revision/fences are archived. Fresh unfinished live volume remains
  partial and entries blocked. Keep all original recording run files for restart.
- Isolated replay uses production candle/Renko persistence and file-hash provenance.
  Tick restore requires explicit complete recorded ordering; missing/gapped order
  or minute seeds require rebuild. No tick parity or enabled trading is claimed.
- Single coding agent, existing model/Standard speed; no extra agents or paid API.
  H checkpoint: 90k input + 20k output, soft only, not an account quota. Exact
  tokens/allowance unavailable: Unknown. Use included allowance; extra cash INR 0.
- Project ceiling INR 20,000 including fees; target INR 10,000. Historical spend,
  current plan/price, renewal/expiry/reset and headroom UNVERIFIED, not zero or an
  available INR 20,000 balance. No purchase/recharge initiated or authorized.
- Already-requested account inputs remain outstanding: receipts/total spent,
  Codex plan and INR renewal price/date, allowance/reset, Kite/TradingView access.
  Missing readings do not block included independent coding. Ledgers: spend-ledger,
  daily-log and paper-journal CSVs. Blank actuals remain Unknown.
- Paper: zero qualifying sessions; D01 journal is development BLOCKED, not an
  observation/trade. Manual practice not reported; no fills/P&L invented. Preserve
  any market-hour baseline; develop using replay/test DB. Check actual feed/paper
  state before coding when a real session is in progress.
- Targets remain conditional: automated trial D24-D30, candidate D45, D60 review
  only with gates and 20 qualifying sessions. Live-money work stays outside plan.
- In-session alerts: renewal within 3 days, allowance <=20%, cash thresholds and
  missing account facts. No billing meter or background renewal notification exists.
- On next turn read this, current daily row and relevant README/code only. Update
  evidence/counts/daily rows/handoff together. README.v1.md remains immutable.
