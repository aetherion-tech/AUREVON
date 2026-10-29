# Local paper-trading UI: readiness and usage

Updated 2026-10-29, D04. **Not ready for paper trading from the browser.**
BE-12 accounting and all 20 BE-13 API/client tasks are code accepted. A typed
frontend/src/api/client.ts exists, but there is no React scaffold,
`frontend/package.json` or built dashboard yet. Normal startup does not attach
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
| Local UI | FE-14 login/shell/client/socket/kill controls; FE-15 chart/signals/open spread/manual close/results/alerts; FE-17 wallet; FE-18 strategy/risk/preview controls and validation. No browser trading feature is delivered by BE-12 alone. |
| Data and paper gates | Actual chart settings/exports, BE-08-14, QA-09-19/20, QA-11-15/16, recorded end-to-end reconciliation and manual strike checks. Replay tests are not those actual exports. |
| Operator verification | An actual local HTTPS run; login; PAPER/unarmed; valid calendar/clock/session; fresh catalog/feed/recovery; known risk/cost configuration; reconciled wallet; browser close/kill/error/reconnect tests. |

Optional history deletion, sounds and other polish need not delay an explicitly
accepted first paper UI slice. The report currently tracks a conservative full
UI milestone. Any smaller first slice must retain working controls, error states,
accounting and browser evidence before being described as usable for paper trades.
Next task: FE-14-01 React scaffold, integrating the existing typed API client.
Client source is not a screen and does not enable trading. A first paper UI slice
may be accepted before optional polish only with all required controls/gates. A shell or screenshot alone will not be reported
as paper-trading ready.

## Startup steps to publish when the UI is actually ready

The exact frontend run/build commands, URL, TLS certificate paths and activation
procedure will be verified and added here when that frontend exists. Do not run
invented `npm` commands against a nonexistent frontend or enable execution by
editing flags now. Existing HTTPS/same-origin requirements are described in
[dashboard operations](../api/dashboard-operations.md).

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
