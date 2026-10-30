# Local paper-trading UI: readiness and usage

Updated 2026-10-30, D05. **Not ready for paper trading from the browser.**
BE-12 accounting, all 20 BE-13 API/client tasks, all 15 FE-14 foundation tasks and
all 15 FE-15 Live tasks, all 8 FE-16 History tasks, all 8 FE-17 Wallet tasks and
all 11 FE-18 Settings tasks are code accepted. React provides sign-in/navigation,
Kite/feed status, exact paper balance/deposit, kill/socket recovery, a source-bound
Renko chart/overlays, direction, spreads/close, results, signals and durable alerts.
History includes summaries/charts/period tables, URL filters, server-sorted pages,
trade details/timeline/chart and matching CSV. Wallet provides exact balances, shared financial dialogs, ledger and top-up status.
Settings provides Pine/strategy/risk/fill/data forms, guarded versioned saves,
JSON import/export, display preferences and read-only strike preview.
See docs/testing/FE-18-acceptance.md and docs/testing/OPS-19-followup.md.
Live also has an observation-only TradingView shadow comparison panel; it remains
disabled until verified ingress/source configuration. This adds no trading action.
Normal startup does not attach
an executor or enable entries. `/docs` is an API explorer, not the trading UI.
Starting the backend does not start taking paper trades.

## Check progress locally

From PowerShell:

```powershell
Set-Location D:\WorkSpace\AUREVON\backend
.\.venv\Scripts\python.exe -m app.tools.local_ui_readiness
```

This reads README task statuses and frontend files; it does not open an account,
connect a feed, change a database or activate trading. It reports the pending
wallet, domain API, frontend and reference/gate IDs. `runtime: NOT_CHECKED` means
no live operational readiness has been verified. Even after all code milestones
pass, `READY_FOR_OPERATOR_CHECK` requires the checks below; the command never
asserts that a running trading session is ready.

The coding agent should run this check and report changes at each future active
implementation session. There is no background monitoring or automatic message
while you are away. No dependable activation date can be given while reference
exports, G2/G3 and runtime integration remain outstanding.

## What must be ready before your first UI paper trade

| Area | Remaining acceptance |
| --- | --- |
| Backend accounting | BE-12-01 through 12 and BE-13-09/10/11 are complete with exact accounting/API integration. Actual runtime/observation acceptance remains separate. |
| Public execution path | All BE-13 APIs and typed-client integration are complete. Explicit owner runtime/providers and clock/poll hooks are tested; normal startup remains detached. Actual managed indicator/strategy generation, reference/operational readiness and browser workflow still need acceptance. Unattached actions return 409. |
| Local UI | FE-14/15/16/17/18 complete with isolated HTTPS browser evidence. Built frontend hosting (OPS-19-01) is accepted; integrated operational acceptance remains. No real-session or managed trial acceptance is implied. |
| Data and paper gates | Actual chart settings/exports, BE-08-14, QA-09-19/20, QA-11-15/16, recorded end-to-end reconciliation and manual strike checks. Replay tests are not those actual exports. |
| Operator verification | An actual local HTTPS run; login; PAPER/unarmed; valid calendar/clock/session; fresh catalog/feed/recovery; known risk/cost configuration; reconciled wallet; browser close/kill/error/reconnect tests. |

Optional history deletion, sounds and other polish need not delay an explicitly
accepted first paper UI slice. The report currently tracks a conservative full
UI milestone. Any smaller first slice must retain working controls, error states,
accounting and browser evidence before being described as usable for paper trades.
Next task: OPS-19-03 isolated Windows SCM verification. Built hosting is accepted;
see [release operations](paper-release.md) for the HTTPS single-origin runner,
backup/restore, staged service and remaining gates.
The foundation does not enable trading. A first paper UI slice
may be accepted before optional polish only with all required controls/gates. A shell or screenshot alone will not be reported
as paper-trading ready.

## Built release option

After building frontend, safely stop the previous backend owner only when not
observing and after verifying exposure/settlement. From backend run
`.\.venv\Scripts\python.exe -m app.tools.serve` and open
**https://127.0.0.1:8443/dashboard/**. This serves SPA/API/WSS on one origin;
no separate FE server is required. Never start it beside an observing owner.
Normal startup remains detached/unarmed. See [paper release operations](paper-release.md).
The development commands below remain supported.

## Verified foundation start/build workflow

Use Node and the installed backend development environment. From PowerShell:

```powershell
Set-Location D:\WorkSpace\AUREVON\frontend
npm.cmd ci
npm.cmd run build
npm.cmd run lint
npm.cmd test
```

`build` runs strict TypeScript checking and generates `frontend/dist` with base
`/dashboard/`. `npm.cmd` avoids the PC's PowerShell npm.ps1 execution restriction.
For an actual local operator run, start the existing backend on 127.0.0.1:8000
using its documented setup. Keep it PAPER/unarmed and preserve observation data;
do not apply pending migrations outside the owner/backup procedure. Set up local
HTTPS once from the frontend directory:

```powershell
npm.cmd run setup:https
npm.cmd run dev
```

Open **https://127.0.0.1:5173/dashboard/** (or https://localhost:5173/dashboard/).
Setup generates an exact local server certificate covering localhost, 127.0.0.1
and ::1, and trusts that certificate in `Cert:\CurrentUser\Root`. It is not a
certificate authority and cannot sign other certificates. It requires no paid
tool or system-wide trust installation. Windows may show its trust confirmation.
The setup script's execution-policy option applies only to that process.

Vite automatically uses `frontend/.local-tls/localhost-key.pem` and
`localhost-cert.pem`; no environment variables are needed. The directory is Git
ignored and its permissions are restricted to this Windows user and SYSTEM.
Keep its private key on this PC. Re-running setup reuses the matching unexpired
pair. To use an existing certificate instead, set both `LOCAL_TLS_KEY` and
`LOCAL_TLS_CERT` to its absolute paths. Vite fails closed without certificate
files and proxies `/api` and `/ws` to the backend, retaining the browser's origin
and Secure cookies. Never put passwords, hashes or broker secrets in Vite variables.
The server-only `LOCAL_API_TARGET` can select an isolated backend; it is not a
browser cross-origin API base.

Local setup verified 2026-10-29: certificate thumbprint
`5532F5F6C4B5337ECF1F473E456EB8BF1CE94D9E`, expires 2027-10-29 17:25:53 IST.
Both URLs return HTTP 200 with normal Windows certificate validation. Chromium
opens the dashboard sign-in screen using TLS 1.3 with **no certificate bypass**.
The existing backend on port 8000 was left running; no sign-in, migration or
market/trading action was performed. Restart the browser if an existing window
retains an earlier certificate error. No renewal automation is installed.

Trust can be removed specifically for this certificate when no longer needed:

```powershell
Remove-Item -LiteralPath 'Cert:\CurrentUser\Root\5532F5F6C4B5337ECF1F473E456EB8BF1CE94D9E'
```

Windows import mechanism: [Microsoft Import-Certificate documentation](https://learn.microsoft.com/en-us/powershell/module/pki/import-certificate).

The automated workflow **was verified** at that HTTPS URL against an isolated
FastAPI server on 18765 at **https://127.0.0.1:5174/dashboard/**, with a temporary test-only self-signed certificate and
Chromium's test-scoped certificate override:

```powershell
npx.cmd playwright install chromium
npm.cmd run test:browser
```

This test command starts its own temporary SQLite schema and dummy wallet,
uses a fixture password, and never loads the actual `.env` or enables the market
feed. Ports 5174/18765 must be free; operator ports 5173/8000 are left alone.
It verifies real secure-cookie login, deposit, kill, logout, keyboard dialogs,
session expiry, reconnect, mobile navigation, lost-reply financial recovery and
the FE-15 Live, FE-16 History and FE-17 Wallet workflows. The temporary DB holds 655 real
stored synthetic replay bricks with published indicator results. Kite status
variants, spread/result scenarios and network failures are test
fixtures; there was no broker login or actual market session. See
[FE-14 evidence](../testing/FE-14-acceptance.md).

If sign-in says the service is unavailable, check whether a dashboard password
is configured. Generating a hash without saving it does not configure the server.
The sign-in screen now shows setup instructions when configured=false. From
PowerShell in the backend directory, run:

```powershell
cd D:\WorkSpace\AUREVON\backend
.\.venv\Scripts\python.exe -m app.tools.dashboard_password --save
```

Choose and confirm a password of at least 12 characters in the hidden local
prompts. The command saves its hash directly to the ignored `.env`; it prints
neither password nor hash and preserves other settings. Stop the existing backend
with Ctrl+C at a safe owner boundary, then restart it using the documented command.
Refresh the dashboard and use the password you chose. Never send it in chat.
The running process reads the hash at startup, so saving alone needs a restart.

In the normal shell, sign in with the existing local dashboard password. Use the
official Kite link only when configured; its secrets remain on the server. Missing
wallet ownership remains unavailable/409. A kill with pending closures requires
fresh quotes and settlement verification. Retry an ambiguous deposit from the same
tab to reuse its saved action; review the ledger before deliberately discarding it.
The Live, History, Wallet and Settings routes are implemented; integrated
operational acceptance remains pending. Open https://127.0.0.1:5173/dashboard/history to inspect FE-16 progress.
Fixed-period summaries are account-wide PAPER; family/direction/result/grade
filters scope the table and all-page CSV. Date-range charts are labelled
separately. Missing data/owners remain unavailable, rather than fabricated zeroes.
Stop the existing backend safely with Ctrl+C before rerunning the backend command
at the top of NEXT_SESSION.md to load new history sorting/metadata/extrema views.
Reuse an existing frontend on 5173 and refresh, instead of starting a duplicate.
Every future task completion must provide the exact BE/FE commands and URL, per
the standing user instruction saved at the top of NEXT_SESSION.md.
See [FE-16 evidence](../testing/FE-16-acceptance.md).
The operator backend was not restarted in FE-15. Its next safe owner restart
loads optional plan stop/target, closed-time and dated loss projections plus the
HTTP integer history-filter fix. No new migration was introduced; never apply
the earlier pending migrations during a running observation baseline. See
[FE-15 evidence](../testing/FE-15-acceptance.md).
Existing owner/security requirements remain in
[dashboard operations](../api/dashboard-operations.md).

## Operator trading workflow still awaiting acceptance

The verified operator workflow must then be:

1. Use the delivered Windows setup/run instructions on this PC, with an isolated
   trial database first. Back up the application DB and apply pending migrations
   under the owner procedure; never migrate a running observation baseline.
2. Start one local backend owner and its verified HTTPS frontend/proxy. Open the
   documented dashboard URL. Sign in with the locally configured dashboard
   password, then use the official Kite login action if market data is needed.
3. Confirm PAPER and unarmed mode, actual feed/catalog/session/recovery readiness,
   and the expected wallet balance. Initialize the chosen dummy capital once;
   deposits are paper funds and are separate from your project cash budget.
4. Review lots, strategy, risk limits, entry window, square-off, slippage and the
   effective paper cost schedule. Preview a spread. A preview never places it.
5. Start the explicitly enabled paper trial through the delivered control. Check
   the accepted/rejected decision, both fills, blocked margin and active spread.
   Missing or rejected readiness must leave entries blocked with visible reasons.
6. Test manual close and kill in the trial. A pending response is not flat: wait
   for both closing fills, released margin, realized P&L, costs and history to
   agree. Stale quotes may leave a safe pending closure requiring operator review.
7. Check the end-of-day reconciliation result and record the actual observation.
   A formal burn-in session counts only after G1/G2/G3, drills and shadow setup;
   at least 20 qualifying exchange sessions remain required.

These are future acceptance steps, not a claim that steps 2–6 work today. Until
the missing UI and integration are delivered, use isolated development tests or
the separately documented manual Pine practice; neither is a browser paper trial.

## Accepted Wallet screen (FE-17)

Open https://127.0.0.1:5173/dashboard/wallet after sign-in. An attached initialized
PAPER wallet is required; unavailable balances are never invented. Review total,
free and blocked capital, then use Deposit paper funds (or top-bar Add paper
funds), Withdraw paper funds, or the explicitly confirmed Reset paper wallet.
Use only your intended paper account, outside an observation baseline when
changing funding. Reset requires a flat book and preserves all records/risk locks.
History deletion is disabled because no API exists. The effective auto-top-up
setting is read-only here; funding is not profit. Ledger pages show authoritative
running balances. Ambiguous requests retain the same key/body across reopen or
reload; review the ledger before discarding them. Trade/position events refresh
wallet/top bar/ledger together. These controls do not attach an owner or enable
entries. See [FE-17 evidence](../testing/FE-17-acceptance.md). No backend changes
or new migration were required for FE-17; reuse the frontend and refresh.

## Settings screen (FE-18 accepted)

Open https://127.0.0.1:5173/dashboard/settings after signing in. Expand a group,
edit values and select **Review and save**. Review each old/new value and confirm.
Pine/grid changes also require a separate rebuild acknowledgement. Saving records
a desired revision only; the displayed owner activation/rebuild state does not
start a rebuild or enable entries. Existing exposure/feed conflicts remain server
rejections. Never stop an observation to force a settings save.

Restore defaults and validated version 1 JSON imports stage local edits. Export
returns saved server values. Navigation/reload warns about unsaved edits. After a
lost reply, retry the same saved request/key; check the server outcome before
explicitly discarding a pending request. A newer server revision blocks overwrite.

Use read-only strike preview after saving/discarding edits. It uses current server
strategy/catalog/quotes and shows explicit rejection if unavailable. Optional
capital is a hypothetical assumption; no wallet balance or order is created.
Browser layer/palette preferences persist locally. Sounds and notification
permissions require a user click; notifications run only in the open signed-in
browser. Saved display sounds do not grant browser audio/notification permission.

FE-18 verification: 35 frontend tests, 101 distinct targeted backend cases,
35 full plus 10 focused HTTPS browser flows (36 distinct), build/TypeScript/ESLint,
manifest parity and focused Ruff pass. Temporary synthetic DB/TLS only; this does
not prove real-session paper readiness. No backend implementation change or new
migration in FE-18, so no backend restart is needed for this batch.
