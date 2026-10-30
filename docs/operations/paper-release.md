# Local paper release operations

2026-10-30. Code and isolated tests do not activate trading. Reference G1/G2/G3,
managed owner attachment and formal observation remain outstanding. Never use a
synthetic test database as the operator's baseline.

## Build and run

From the repository root, use process-scoped PowerShell execution policy; no
machine-wide policy change is needed:

```powershell
cd D:\WorkSpace\AUREVON
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/ops.ps1 -Action Check
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/ops.ps1 -Action Build
```

For a fresh installation only, `-Action Setup` runs `uv sync --locked` and
`npm.cmd ci`. It never writes .env, migrates a database, creates funds or starts a
service. Configure a missing dashboard password using the hidden local
`python -m app.tools.dashboard_password --save` prompt. Never paste secrets in
chat, scripts or IDE configuration. Run `npm.cmd run setup:https` from frontend
only if the local certificate is missing. Existing certificate expires 2027-10-29.

One-terminal built release:

```powershell
cd D:\WorkSpace\AUREVON\backend
.\.venv\Scripts\python.exe -m app.tools.serve
```

Open **https://127.0.0.1:8443/dashboard/**. Direct links to `/dashboard/history`,
`/dashboard/wallet` and `/dashboard/settings` load the SPA. API and WebSocket
traffic goes to this same HTTPS origin; Vite is unnecessary. The root redirects
to the dashboard. Missing assets and API paths retain genuine error responses.
The runner binds loopback, allows only localhost/127.0.0.1 Host headers, disables
proxy-header trust, and holds an OS lease. A second release runner is refused.
`.run/AUREVON HTTPS.run.xml` supplies an IntelliJ Python module configuration;
select the backend virtual environment if the IDE requests it.

Before running, identify any existing backend. Do not run a release owner beside
an observing development owner, even though the ports differ. Preserve its
observation. When safely flat and no longer observing, stop its owning terminal
with Ctrl+C and allow shutdown to complete before switching. A backend code
change requires this safe restart. Do not kill unrelated Python processes.
Ctrl+C requests Uvicorn shutdown, drains app work and releases the owner lease;
pending paper exits still need valid quotes and explicit verification.

Development remains available in separate terminals:

```powershell
cd D:\WorkSpace\AUREVON\backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log
```

```powershell
cd D:\WorkSpace\AUREVON\frontend
npm.cmd run dev
```

Development URL: https://127.0.0.1:5173/dashboard/. Reuse existing Vite. The
hardened release runner is preferred for built operation; raw development
Uvicorn does not add the runner's Host-header guard.

## Morning, recovery and close

1. Check the actual calendar/session, OS clock, dashboard login, Kite login and
   token expiry. Verify PAPER/unarmed and the intended data/configuration identity.
2. Confirm local migrations under the documented owner/backup procedure. The
   D05 local recovery already applied 0007 through 0012 with verified backup and
   owner pause. The explicit local_ui_setup command is separate from ordinary
   dependency Setup; it never enables MARKET_SERVICE_ENABLED. Do not rerun
   migrations during an observation or merely to log in.
3. Verify reference gates, explicit matching wallet/runtime/providers, fresh
   catalog/contracts/quotes, recovery completion, risk settings, capital and ledger.
   Default startup has no attached executor. The explicit local UI opt-in attaches
   the already initialized flat display account; entries remain disabled.
4. On disconnect, overflow or token expiry, keep entries blocked until recovery
   and clock checks pass. Preserve recordings/checkpoints and the original Pine.
   Re-login uses the existing owner; never start a competing socket/worker.
5. Close/kill locks entries and requests exits; a pending response is not a fill.
   Verify both legs, settlement, margin release, final trade/history totals and
   reconciliation. Keep the owner polling with fresh prices until exposure is flat.
   A feed-stop request with exposure is refused. Do not force-stop to bypass this.
6. Record the session's actual signals/trades/rejects/anomalies, or the blocking
   condition. Synthetic drills, manual Pine practice, trials and burn-in remain
   separate. G4 requires 20 qualifying exchange sessions; currently zero evidenced.

## Backups and isolated restoration

Use absolute paths. The target must be a NEW file. This example creates a named
snapshot; choose a new timestamp for each backup:

```powershell
cd D:\WorkSpace\AUREVON
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/ops.ps1 -Action Backup -Source D:\WorkSpace\AUREVON\backend\data\aurevon.db -Target D:\WorkSpace\AUREVON\backend\data\backups\manual-20261030.db
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/ops.ps1 -Action Restore -Source D:\WorkSpace\AUREVON\backend\data\backups\manual-20261030.db -Target D:\WorkSpace\AUREVON\backend\data\restore-check-20261030.db
```

SQLite's online backup API includes committed WAL data. Integrity, foreign keys,
table counts and a digest of the effective database image are retained in an
adjacent manifest. Restore validates that manifest, refuses existing targets and
compares restored counts. A separate database restoration is tested. Backups
contain private trading/accounting history: restrict access and retain an offline
copy. .env, DPAPI session and TLS keys are deliberately outside this DB backup;
retain those securely under the same Windows identity. No cloud upload is added.
Switching a restored DB into operation remains a stopped-owner recovery step;
first reconcile its book/ledger and source identity, never rename over an active DB.

`SESSION_MAINTENANCE_ENABLED=false` is the default. Opting in enables nightly
reports/backups inside the **existing desired/running leased MarketService**,
after the actual calendar close plus ten minutes (holiday fallback 15:40 IST).
There is no independent Windows task or extra scheduler. Existing paper polling
requests square-off; maintenance refuses open/pending exposure, reconciles the
wallet, then validates the copied snapshot's exact book revisions before emitting
the report. With no books, the report says NO_BOOKS. Failure propagates through
the owner's fail-closed recovery path. A stopped owner does not run maintenance.
Default destination is `backend/data/backups/YYYY-MM-DD/`. A crash leaving an
unreported snapshot requires verification and archival before retry; it is never
silently overwritten or certified as a newer snapshot. The isolated owner-loop close/quote-retry/report/restore scenario now passes
OPS-19-04. It uses synthetic providers, not actual market-session evidence.

## Retention

Logs rotate at UTC midnight, retaining 90 daily archives; this replaces size-only
rotation. Existing size archives are preserved. With no running process, rotation
does not happen in the background. Bricks, signals, orders, fills, ledger, trades,
snapshots and audit data are never deleted by these tools.

Recording compression is explicit and initially dry-run:

```powershell
cd D:\WorkSpace\AUREVON\backend
.\.venv\Scripts\python.exe -m app.tools.retention D:\WorkSpace\AUREVON\backend\data\ticks
```

Only a stopped run with `SEALED.json` containing a `sha256` mapping of relative
JSONL paths to their verified digests is eligible. The operator seals runs only
after preserving source/run/checkpoint provenance. `--apply` writes verified gzip
copies of earlier-day recordings, preserving originals. Missing/changed hashes
or corrupt archives stop the operation. Never mark an observing run as sealed.
Raw ticks and verified compressed copies are retained indefinitely as source
and recovery evidence. No raw-deletion path is installed. Automatic approval
review rejected the proposed destructive raw-deletion enhancement; preserving
originals is the chosen retention policy, so no deletion approval is needed.

Migration 0012 adds derivative `pnl_ticks`. Explicit opt-in
`PNL_TICK_RECORDING_ENABLED=false` enables no producer by default; when enabled,
the already attached runtime records exact decimal/unknown mark observations on
owner polls, separate from the ledger. The existing opt-in nightly maintenance
backs up first, then prunes only samples strictly older than 90 days. The exact
boundary and preservation of book/ledger are tested. Schema 0012 is required;
it was tested on isolated databases only. No operator migration or pruning ran.
`RECORDING_COMPRESSION_ENABLED=false` optionally invokes the same sealed-run
compressor from nightly maintenance. No extra scheduler is added. A stopped
owner performs none of this work. Inspect disk use periodically because original
recordings, compressed evidence and backups have indefinite retention.

## Windows service staging

`scripts/service.ps1 -Action Inspect` is read-only. The optional pywin32 wrapper
supports Install/Start/Stop/Restart/Remove/ConfigureRecovery, registers **manual** startup, uses the
same HTTPS runner/lease, and requests graceful shutdown from SCM Stop. Example
command format is `powershell.exe -NoProfile -ExecutionPolicy Bypass -File
scripts/service.ps1 -Action Inspect`. Install/start have not been executed.

Before installation, select an appropriate Windows identity. LocalSystem does
not inherit the operator's DPAPI credentials or current-user certificate trust.
Configure its account and private-directory permissions locally without placing
passwords on a command line. Test SCM start/stop/restart and duplicate-owner
refusal in an isolated release environment, then record evidence before enabling
automatic startup/recovery. OPS-19-03 is Pending until that verification exists.
Do not install or restart a service over a current observation.

The 2026-10-30 access probe found this session is not elevated;
`OpenSCManager(SC_MANAGER_CREATE_SERVICE)` returned Windows error 5, Access denied.
Actual service installation remains blocked. In an elevated local PowerShell,
from the repository root, use the Install action, configure the intended Windows
identity privately in Services, then test Start/Stop/Restart against an isolated
release. After successful identity/TLS/DPAPI and graceful lifecycle checks,
`-Action ConfigureRecovery` explicitly configures delayed automatic startup and
10/30/60-second restart attempts with a daily failure reset. This action was
prepared but has not been executed; do not infer working SCM recovery from it.

## Dependency and security review

```powershell
cd D:\WorkSpace\AUREVON
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/ops.ps1 -Action Audit
```

Both graphs are audited even if one has findings; JSON reports go to
`docs/testing/OPS-19-{backend,frontend}-audit.json`. Findings or unavailable
audits return a nonzero exit. No ignores or automatic force-fixes are applied.
Use `uv lock --check` and `npm.cmd outdated` for update checks; outdated's nonzero
exit can mean updates exist. Review changelogs, update targeted dependencies in
development and rerun relevant full checks before restarting an owner.

The 2026-10-30 frontend report has zero findings after the Vitest 4.1.12 update.
The backend report retains 12 advisory records (including aliases) involving
Autobahn 19.11.2 pinned by kiteconnect 5.2.2 and Twisted 26.4.0. Several Twisted
server/mail paths are not used here; the Kite client WebSocket path still requires
upstream compatibility review. Do not infer immunity or approve a release from
that scope assessment. No forced dependency override or broker compatibility
claim is made. See the acceptance report for findings and upstream links.

Security review: secure HttpOnly SameSite=Strict dashboard cookie, CSRF plus
explicit Origin checks, authenticated WSS, durable mutation audit, bounded
transport, no request-body/query/credential logging, generic exception responses,
no-store/no-referrer, nosniff and anti-framing response headers. Local build assets
are public while all private API actions retain authentication. The raw backend
is not exposed to LAN/public networks. No tunnel, reverse proxy, public webhook
or TradingView shadow feed is configured. OPS-19-08 now has an authenticated, source-fenced observation inbox and bounded
two-sided comparison/UI; actual reachable ingress and G2 evidence remain pending.
See [shadow alert operations](shadow-alerts.md). The ingress uses a dedicated
token, never dashboard/broker credentials; the original Pine is preserved.

## Troubleshooting

- Port in use: identify and reuse its owner; never spawn duplicates or kill all Python.
- TLS missing: run the local certificate setup once; never disable browser checks
  for the operator. Browser tests alone use a temporary self-signed certificate.
- Login unavailable: use the hidden local password tool, then safely restart BE.
- HTTP 409/unavailable wallet: verify matching schema/owner/runtime; do not seed
  funds or fabricate availability to dismiss the error.
- Audit exits 1: inspect both retained reports; this is expected while backend
  findings remain. A blocked network lookup is unavailable evidence, not a pass.
- Failed close/reconciliation/backup: preserve files, leave entries blocked and
  reconcile the real book. Do not reset history, loss locks or trade counters.

## Repeatable isolated drills and timing

From backend, retain a new immutable evidence file for each run:

```powershell
.\.venv\Scripts\python.exe -m app.tools.ops_drills --output ..\docs\testing\OPS-19-next-drills.json
.\.venv\Scripts\python.exe -m app.tools.ops_benchmark --output ..\docs\testing\OPS-19-next-performance.json
```

`--all-tests` on ops_drills runs the full backend suite and retains per-case
outcomes. The crash drill abruptly exits a separate process with a committed open
position, restores it in a new process and verifies one position, four fills,
unique ledger keys, exact net/balance and zero reserved margin. Partial legs and
duplicate signals use the existing exact execution regressions. This completes
QA-19-12 engineering evidence, not formal G5 acceptance or an exchange session.

The 500-tick synthetic timing baseline emitted 48 durable minute-close bricks.
Its second run measured 63.89 ms p95 on brick-emitting ticks, missing the 50 ms
target. Market persistence p95 was 23.49 ms; indicator/readback p95 was 41.69 ms.
These independently computed phase percentiles must not be summed. There is no
brick-to-order dispatch measurement or representative option fanout/warmed history;
QA-19-14 remains Pending. See retained JSON reports under docs/testing.

## Current recovered local installation

The reported missing wallet/history/P&L and callback-origin issue has a dedicated
[recovery record](../testing/local-ui-recovery.md). Operator DB revision is 0012;
original table counts/audit retained, separate backup restore verified, explicit
simulated initial capital zero. LOCAL_UI_ENABLED is now true locally; default
settings remain false. The existing reload owner paused/resumed gracefully.

Reuse the running backend/Vite and https://localhost:5173/dashboard/. Sign in,
complete fresh Kite login, then Start market data. Without a verified anchor,
local mode supplies genuine quotes only and clearly blocks chart/strategy entry
activation. No actual broker login or live quote result is inferred from tests.
The setup command need not be rerun on login. For future stopped/acknowledged
reload-owner recovery only, it is `python -m app.tools.local_ui_setup --apply`;
it refuses a market lease/exposure and retains a verified backup and receipt.
