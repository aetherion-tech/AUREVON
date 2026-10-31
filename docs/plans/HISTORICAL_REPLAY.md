# Historical strategy replay - requested D06

Status: DEFERRED by explicit user request on 2026-10-31. Return to current Kite-based live paper trading. HIST-REPLAY-DATA1 input foundation remains delivered and preserved; no provider acquisition or replay UI work unless explicitly resumed. Original request dated 2026-10-31.

Choose From and To dates (example: 2025-01-01 through 2025-03-03), then execute/play the historical Renko strategy without starting live trading. Chart advances in historical order, signals drive simulated option positions, and timestamped positions/trades and P&L update during playback.

## Required behavior

- Separate Historical Replay screen with inclusive IST date range, validation, source coverage and explicit preparation/progress/errors.
- Prepare required pre-range warm-up and seed without admitting pre-range trades. Use the existing five-minute Close Renko/wick and indicator pipeline; retain original Pine and disclose remaining parity gates.
- Play/pause, playback speed, step and reset; advance a historical clock and chart without future-data leakage. Playback speed must not alter results.
- Configure replay capital and lots under the existing strategy/risk rules. Signals select historically valid strike, expiry, lot size and contract identity, then drive isolated paper execution/accounting.
- Display entry/exit timestamps in IST, signal/reason, side, strike, expiry, lots/quantity, entry/exit premiums, per-leg/current marks, charges, realized/unrealized/net P&L and wallet/equity.
- Save replay configuration, source identity, assumptions, trade history and result summary separately from operator trading history; allow result export and deterministic rerun.
- At range end explicitly report open positions and valuation policy; never invent an executable closing price.
- Missing warm-up, source/calendar, contracts or eligible prices must be visible. Missing prices are unavailable, never zero. Every decision/mark/fill uses only information available at the historical clock.
- No live sockets, broker orders, operator-wallet changes, live entry-gate changes or formal burn-in credit. Broker history acquisition, if selected, is read-only and explicit; no purchases authorized.

## Pricing decision confirmed

User confirmed on 2026-10-31: actual historical option prices only. No estimated option-price model or spot-derived option premium fallback is authorized. Missing contract identity, historical lot size, eligible prices or coverage must block affected simulated execution and leave unsupported P&L unavailable.

Historical market prices do not prove an actual broker fill: all replay positions/fills remain simulated, with explicit timing, price selection, liquidity/slippage and cost assumptions. Candle OHLC does not establish intrabar bid/ask or event ordering; never use a candle close before it is historically available.

## Data coverage finding and next gate

Official Kite documentation checked 2026-10-31: https://kite.trade/docs/connect/v3/historical/

Kite instrument master supplies live contracts, not expired contract tokens unless previously cached. Its continuous-history facility is documented for futures day candles; it does not establish expired option intraday coverage. Therefore arbitrary past-date option replay, including the example 2025 range, cannot be promised from the present broker integration. This is a documented API constraint, not proof that retained local data is absent. Inspect retained historical contract masters/quotes and supported read-only sources before selecting a data adapter. No provider, subscription or purchase is authorized.

## Existing reusable components

- backend/app/api/replay_routes.py: opt-in recording replay into temporary isolated SQLite; currently exposes event/brick counts only, not date-range strategy replay or persisted trade results.
- backend/app/market/production_replay.py: validated chronological recording replay, source hashes and isolated stream.
- Existing indicator engine, strategy planner, PaperBroker and wallet/accounting provide building blocks; end-to-end historical integration is Pending.
- frontend/src/App.tsx and existing chart/Live UI can supply navigation and reusable visual components.

## Acceptance before delivery

Meaningful tests must cover chronology/no look-ahead, warm-up exclusion, historical contract selection and lot changes, missing/stale prices, deterministic orders/fills/accounting across playback speeds and reruns, pause/step/reset, end-range exposure, data provenance, access controls and live-state isolation. Browser checks must cover date inputs, playback chart, positions, trades and exact monetary totals. Real historical data acceptance remains distinct from synthetic engineering checks.

## Next implementation batch

Pricing mode is resolved: actual historical option prices only. Inspect retained historical spot/context/derivative coverage and historical contract metadata first. Implement isolated date-range run storage and historical event/quote adapters, then connect the existing strategy/execution/accounting pipeline and playback UI. Do not substitute the development replay endpoint for this feature or mark FUT-21-05 Completed from this requirements document.

## D06 delivered input foundation

D06 HIST-REPLAY-DATA1 delivered offline actual-depth input validation, no-look-ahead quote adapter, coverage CLI and isolated durable input folders. Read-only local audit: current options expire2026-11-03 or later; retained recording has no option depth; example2025 range BLOCKED without actual option bundle.35 focused plus114 planner/execution/history tests PASS;selected Ruff/format/mypy PASS. Full replay UI/strategy execution Pending;counts241/39,formal0;usage/cash/renewal Unknown;extra paidINR0. Evidence docs/testing/HIST-REPLAY-DATA1.md/.json. Next actual historical contract/quote intake and isolated strategy/playback integration; preserve live owners/wallet/config/Pine.

## Clarification: arbitrary dates and automatic acquisition

D06 user clarification: January-March2025 was an example only. Historical Replay must accept arbitrary user-selected From/To dates, automatically discover contracts and fetch/cache available actual historical option prices; manual bundles are optional, not the intended normal workflow. Availability remains limited by provider coverage/entitlement; show supported dates and precise gaps. DATA1 depth-only adapter is one supported input, not a user requirement: actual historical option candles may support a separately tested candle-based simulated-fill policy without fabricating bid/ask depth. Next build provider coverage/download adapter plus candle replay policy and isolated playback integration. No provider purchase or account access authorized;full feature Pending;counts241/39,formal0;usage/cash/renewal Unknown;extra paidINR0.

The normal workflow is From/To -> check provider coverage and authentication -> discover historical contracts/lot metadata -> fetch missing spot/context/option prices -> cache with provenance -> warm up -> replay -> results. Return supported ranges, holidays and source gaps explicitly; do not promise market data for dates before listing, future dates or unavailable archives. Existing datasets are a cache/input option, not a requirement that the user hand-assemble each backtest.

The actual-price requirement does not require historical order-book depth for all backtests. DATA1 supports depth-based execution. A separate candle-based replay path can use recorded option OHLC with a documented conservative timing policy (for example the next eligible bar open after signal confirmation), simulated fills, declared costs/slippage and no future candle close access. It must not invent historical bid/ask, claim live liquidity validation or waive current live entry gates. Intrabar ambiguous stop/target ordering and missing contract/lot metadata require explicit handling and tests before delivery.

Official provider findings checked 2026-10-31:
- Kite: current instrument master excludes expired tokens; continuous history is futures/day specific: https://kite.trade/docs/connect/v3/historical/
- Upstox documents expired option discovery and historical candles: https://upstox.com/developer/api-documentation/expired-instruments/
- Expired candle endpoint supports minute data; documentation identifies a Plus entitlement restriction. Exact user's entitlement, cost, retention and contract/lot history remain unverified: https://upstox.com/developer/api-documentation/get-expired-historical-candle-data/

No provider selected or purchased. User asked which existing data access is available; integration engineering can proceed independently using mocked provider responses while real retrieval remains dependent on authorized authentication and coverage.

## Latest priority decision

D06 user DEFERRED historical backtesting and restored current Kite-based LIVE PAPER work as the sole active priority. Do not pursue Upstox, historical option acquisition or replay UI unless explicitly resumed. Preserve delivered DATA1 offline modules/evidence for later; no deletion or new master completion. Next UI-LIVE-B3 operator readiness/profile check, safe backend restart only when stopped/flat and observation-safe if the fix is not loaded, then Start market data and verify chart/source/as-of; actual fresh-feed/reference acceptance and G1/G2/G3 remain required before paper entries. Closed-session history is display-only, not backtesting. Counts241/39,formal0;usage/cash/headroom/renewal Unknown;extra paidINR0;no purchase authorized.
