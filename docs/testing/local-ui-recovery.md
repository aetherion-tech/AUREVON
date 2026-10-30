# Local dashboard recovery: 2026-10-30 D05

User-reported symptoms: Kite login did not activate the dashboard; NIFTY was
unavailable/feed stopped; wallet/history/P&L returned generic HTTP 409 conflicts.
This recovery fixes local display/account startup and the callback-origin path.
It does not authorize strategy entries or accept reference/burn-in gates.

## Root causes and changes

- The actual local database was at `0006_dashboard_api`, missing all paper wallet
  and domain tables. Normal startup had no account/runtime attachment.
- The actual backend reported Kite unauthenticated. The last recorded callback
  at 09:37:13 IST returned 400. Screenshots used `localhost:5173`; a configured
  callback can return to backend `127.0.0.1:8000`, where the initiating browser's
  host-only state cookie is absent. That origin mismatch is now handled; the
  original failed attempt cannot be retroactively attributed to it with certainty.
- OAuth grants now retain the authenticated originating dashboard origin. A
  callback on another address is relayed to that retained origin BEFORE cookie
  proof or token exchange. No caller-supplied redirect URL is accepted. Configured
  HTTPS origins account for Vite's HTTPS-to-HTTP proxy; arbitrary forwarded headers
  are not trusted. Original cookie/state/expiry, one-use and logout-revocation
  checks remain. Success returns to `/dashboard/?kite=verified` for actual UI
  origins. Old attempts need a fresh login after restart.
- `LOCAL_UI_ENABLED` is explicit, default false. With it enabled, startup attaches
  an existing flat local wallet and a display-only runtime with unavailable
  execution providers and `entries_allowed=False`. It never seeds funds during
  startup, invents quotes or activates a strategy. Existing exposure refuses this
  empty-price attachment and requires its matching recovery owner.
- The explicit `python -m app.tools.local_ui_setup --apply` operation creates a
  zero-funded simulated account only when absent, preserving existing books. A
  retry after interruption before INITIAL resumes with zero funding. It preserves
  unrelated .env settings and Windows DACL/protection during its atomic opt-in.
- Live now has **Start market data / Stop market data**. Starting requires a
  verified Kite session, uses existing audited/CSRF-protected feed endpoints and
  never authorizes entries. Stop still refuses paper exposure.
- Actual configuration has no verified Renko anchor. Explicit local UI mode can
  stream/record genuine quotes without a fabricated grid or history handoff.
  The state is `running_quotes_only_anchor_required`, with explicit chart blocker
  and a never-validated entry resume gate. Renko/indicator/reference acceptance
  remains separate; source inputs and original Pine were not changed.
- Missing account errors now explain local setup/restart rather than merely
  displaying “Conflict”.

## Actual local operation performed

The market owner lease was available, feed was stopped, lifecycle table empty,
and the old schema had no execution books/exposure. The guarded setup held its
own lock, enabled only LOCAL_UI_ENABLED, and requested the already-running
`uvicorn --reload` owner to pause via its normal graceful reload. Its replacement
child acknowledged maintenance BEFORE opening services or attaching a database.
No process was force-killed and no duplicate operator server was started.

While paused and holding the market lease:

1. Created and verified an immutable online SQLite backup, including committed WAL.
2. Applied additive migrations 0007 through **0012_operations**.
3. Saved explicit zero initial-capital settings and one INITIAL ledger row of ₹0.
4. Retained a local setup receipt, released maintenance and resumed the existing
   backend. MARKET_SERVICE_ENABLED stayed false; paper entries stayed blocked.

Local receipt, ignored by Git:
`backend/data/backups/local-ui-20261030T044455-b2a6ef6d.setup.json`.
Backup: same basename ending `.db`, with its adjacent integrity/count manifest.
The backup restored successfully into a separate temporary database. Existing
table row counts remained unchanged; audit history was retained and can grow
with subsequent requests. No market baseline was replaced with test data.

Actual read-only verification after recovery:

- Database revision: **0012_operations**; maintenance flag absent.
- Local UI opt-in true; account attached and initialized; balance **₹0.00**.
- Exactly one INITIAL row; zero paper positions/trades.
- Configured startup projects actual wallet and P&L data; entries false.
- Running backend `/api/health` responds 200.
- Kite remains **unauthenticated** until the operator completes a fresh browser
  login. Actual fresh broker authorization and live quotes are not claimed here.

## Verification

- **121** focused auth/domain/wallet/startup cases passed. Another **17**
  startup/market-owner cases passed, including interrupted zero-setup recovery and
  quote-only mode; these runs overlap. Final quote-only regression and Windows
  .env permission-preserving helper also passed separately.
- Cross-origin OAuth test proves no exchange on backend arrival, successful
  original-cookie exchange, UI return and rejected replay. Existing invalid
  cookie/state/expiry/revocation/secret-redaction tests remain accepted.
- **35 frontend tests**, production build/strict TypeScript, ESLint, Ruff lint/
  format, strict mypy and OpenAPI drift check pass.
- New feed-control browser cases pass against an isolated HTTPS fixture. Their
  verified-login/start/stop responses are deliberately mocked; they do not prove
  an actual broker session. A full 40-case run initially passed 39 with one mocked
  transport conflict; the fixture now keeps REST/socket state consistent. A later
  run passed 39 with a Settings initial-resync timeout; its helper now starts on
  Settings instead of loading unrelated 655-brick Live fixture history. No trading
  assertions were weakened or timeouts extended. The direct Settings entry also
  required an explicit prior in-app entry in its browser-back test; the deposit
  test now waits for its actual POST response before checking the result. Both
  corrected scenarios pass. Final complete built HTTPS browser run:
  **40/40 passed** (1.8 minutes).

## Operator verification

Reuse the current backend and Vite terminals; the controlled reload already
applied the fix. Open **https://localhost:5173/dashboard/** and sign in again.
Use this same address throughout the login flow.

1. Verify wallet ₹0 and readable empty History/P&L without Conflict errors.
2. Click **Log in to Kite**; complete the broker flow. Successful return should
   show **Kite: Verified**. Do not reuse the old failed callback URL or paste tokens.
3. On Live click **Start market data**. During a valid exchange session, genuine
   prices should arrive after catalog/socket setup. Without an anchor, expect the
   explicit quotes-only notice; no Renko signal chart or automated entries is
   implied. Outside a session, session-closed status is correct.
4. Paper funds are simulated and separate from broker/project cash. Use the
   explicit Add paper funds action if desired; a zero starting balance is correct.

If terminals are stopped, backend:

```powershell
cd D:\WorkSpace\AUREVON\backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log
```

Frontend:

```powershell
cd D:\WorkSpace\AUREVON\frontend
npm.cmd run dev
```

Never launch a second owner over the existing one. Built HTTPS hosting at 8443
remains supported as an alternative, with the same retained-origin callback relay.
This fix is a follow-up to accepted APIs/frontend, not another product completion.
Counts remain 234 Completed / 46 Pending. Formal sessions remain zero. Original
Pine/immutable README unchanged. Usage/cash/renewal/headroom remain Unknown;
extra paid usage INR 0, no purchase or account billing access.
