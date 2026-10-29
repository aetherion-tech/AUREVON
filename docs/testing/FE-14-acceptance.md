# FE-14 frontend foundation acceptance

Accepted 2026-10-29 (D04): FE-14-01 through FE-14-15, all 15 code tasks.
This is a local paper dashboard foundation, not an accepted trading application.
Live, History, Wallet and Settings detail screens remain FE-15 through FE-18.

| IDs | Delivered evidence |
| --- | --- |
| 01–03 | Locked React/TypeScript/Vite project; persistent responsive navigation, guarded deep links and not-found route; dark color/spacing tokens, shared native button/input styles, cards, accessible modal dialogs and skip link. |
| 04–06 | BigInt-based exact INR formatting, Indian grouping, IST dates and percentages; generated REST/WS types, abort signals, HTTPS same-origin proxy; React Query server cache, separate local display preferences and pending-command recovery. |
| 07–09 | Dashboard sign-in/logout, session-expiry guard and private-cache clearing; official server-owned Kite login link, configured/verified/expired states; actual snapshot price/feed chips, explicit missing market state, stale prices and isolated IST clock. |
| 10–11 | Actual paper wallet/free-cash chip and bounded exact deposit; PAPER/unarmed display; global kill with duplicate-click guard, waiting/result/error states and explicit pending closure count. No client enables LIVE or submits quotes/readiness. |
| 12–14 | One socket hook with cleanup, capped backoff/jitter, REST snapshot/domain refresh on reconnect, authentication close handling, run/sequence cursor fencing; immutable typed tick/brick/status/signal/position projections and ID deduplication; tick updates preserve unrelated chart/domain references; explicit loading, empty, missing, stale, disconnected, unauthorized and retry states. |
| 15 | Unit/component checks, real Chromium HTTPS integration, desktop/mobile layout, guarded routes, keyboard focus wrapping/Escape/opener restoration; build/typecheck/lint scripts. |

Verification from `frontend`:

```powershell
npm.cmd ci
npm.cmd run build
npm.cmd run lint
npm.cmd test
npm.cmd run test:browser
```

- Production build (includes strict TypeScript check) and ESLint pass.
- 8 unit/component tests pass: exact money/storage boundary/IST, invalid deposits,
  atomic cursor gaps/duplicates, stable projection references, signal deduplication,
  pending-intent recovery, same-key retry and duplicate kill clicks/pending result.
- 6 Chromium browser flows pass on `https://127.0.0.1:5173/dashboard/`, using the
  actual Vite HTTPS proxy and isolated FastAPI backend on port 18765. They cover
  Secure cookie login, route reload, real exact deposit/kill/logout, native dialog
  keyboard behavior, session expiry, socket reconnect, mobile navigation, Kite
  status variants, unavailable wallet/retry and socket authentication close.
- The lost-reply test lets a real deposit commit, drops the response, reloads the
  page, retries the retained key/body, and verifies that funds increased only once.
- 94 targeted existing backend regressions pass in `test_domain_api.py`,
  `test_dashboard_auth.py`, `test_dashboard_api.py`, `test_api_contracts.py`.
  This includes the prior real Node client integration. One existing
  Starlette/httpx deprecation warning remains. Previous full backend result is
  768; this batch does not claim a fresh full backend-suite run.
- Python browser harness passes Ruff lint/format. Desktop screenshot inspected;
  mobile test checks horizontal overflow. Screenshots/reports are ignored artifacts.

Browser evidence is synthetic: temporary SQLite schemas, generated test-only TLS
certificate, fixture password and explicitly attached dummy paper wallet. It does
not use broker credentials, connect market data, enable entries, change `.env`,
migrate the local database or count as a formal session. Kite status variants and
forced network/auth errors are visibly test fixtures; broker login itself was not
performed. No production certificate trust or normal runtime activation is claimed.

Financial commands never retry automatically. An ambiguous result keeps its
original amount/key across dialog recreation and reload in the same tab using
session storage. If storage is unavailable, only in-memory recovery remains;
keep the page open and reconcile before another action. A deliberate discard
requires the operator's explicit ledger/position-review acknowledgment. A kill
reply with pending closures does not mean both legs filled or accounting settled.

The browser-only fetch binding defect found in the existing transport is fixed.
Query errors and socket authentication failures clear private UI state and require
explicit sign-in before returning to the shell. Secrets stay server-side.

Next: FE-15-01 live layout/snapshot readiness, then the remaining chart, signal,
position and close controls. Actual reference/G2/G3, managed-runtime ownership and
operator acceptance still block paper trading. Qualifying formal sessions: 0.
