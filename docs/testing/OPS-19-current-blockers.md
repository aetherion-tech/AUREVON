# OPS-19 completion review — 2026-10-30, D05

The request to complete every OPS-19 task was reviewed against the authoritative
README. Seven of nine OPS-prefixed rows are already Completed: 01, 02, 04, 05,
06, 07 and 18. They were not restarted. OPS-19-03 and OPS-19-08 remain Pending.
QA-prefixed section-19 rows retain their separate acceptance requirements.

## OPS-19-03: service activation safety

Added `app.tools.service_preflight` and `scripts/service.ps1 -Action Preflight`.
This read-only inventory opens SCM handles and closes them without creating,
starting or changing a service. It reports access errors without disclosing
service command lines, passwords, environment contents or broker credentials.

Fresh actual probe: create-service access failed with Windows error **5**;
AUREVONPaper query returned **1060**, service not installed. TLS/DPAPI identity
and SCM lifecycle remain unverified. No installation was attempted.

Installation now stages **disabled** instead of manual startup, preventing an
accidental start under the installer default LocalSystem before private account
configuration. Start/Restart/ConfigureRecovery require a readable, explicit
non-LocalSystem service identity. The identity check does not prove credentials,
TLS access, observation safety or acceptance. Stop is never gated by this check.

PowerShell parser check passed. Direct script execution encountered the existing
execution policy; the documented per-process `-ExecutionPolicy Bypass` invocation
ran Preflight successfully. Start then failed at the identity guard as expected,
before its SCM action. No global execution policy was changed.

Remaining: elevated intended identity, private account setup, isolated TLS/DPAPI
and start/stop/restart/recovery checks, single-worker/lease verification under SCM,
and a safe owner transition outside observation. No elevation or identity is
inferred from a request to finish tasks.

## OPS-19-08: external shadow acceptance

The authenticated inbox/comparison/UI implementation already exists. Acceptance
still needs an actual public HTTPS recipient authenticating TradingView, aligned
debug-copy indices/trade identities, actual delivery/retry evidence and G2.
No endpoint, account entitlement, reference export or G2 receipt was supplied in
this session. No paid tunnel, public dashboard exposure, guessed identity or
synthetic reference replacement was created. See the existing shadow operations
guide for the concrete message and ingress contract.

## Readiness and continuity

Read-only local UI readiness remains BLOCKED on BE-08-14, QA-09-19/20 and
QA-11-15/16. Frontend source/build are present. Runtime was not assessed by this
command. Formal sessions remain zero. No paper owner, operator database, .env,
original Pine, migration or market feed was changed.

Checks and fresh full-suite evidence are recorded in
`OPS-19-session-completion-check.json`: **813 passed, exit 0**. A separate focused
service/release/shadow invocation passed **21 tests**, with the existing
Starlette/httpx deprecation warning. New identity tests cover unknown,
uninstalled, unreadable, blank and system identities, plus an explicit account
without conflating it with TLS/lifecycle acceptance. Ruff lint/format and strict
mypy for the new tool pass.

Counts remain **234 Completed / 46 Pending**, section 19 **9/18 Completed**.
Extra paid usage INR 0; usage, spend, headroom and renewal facts Unknown. No
purchase or background monitoring. D05 follow-up: operator reports fresh Kite
login/Start market data done. Fresh read-only SCM probe at 11:12:51 UTC still
returns error 5 and service absent 1060. Next: OPS-19-03 in the intended elevated
service environment, preserving the running feed; OPS-19-08 needs real
ingress/reference evidence. QA-19-17 is the final paper acceptance task after
all prerequisites and at least 20 qualifying automated paper sessions.

Latest repeat check: D05 11:18:26 UTC: read-only service preflight also run outside workspace sandbox; Windows still denies create-service access (error 5), service absent (1060). No service or feed changed. OPS-19-03/08 remain Pending; 234 Completed / 46 Pending. Prior 813-pass suite retained; no implementation changes or redundant rerun.

Latest operator evidence: Operator-supplied elevated preflight at 2026-10-30T11:23:25.757431+00:00 reports create_service_access GRANTED for DESKTOP-0FJTT0S\Sanny, service NOT_INSTALLED (1060). This clears the elevated-terminal permission blocker only; coding-agent session elevation is not inferred. Identity/TLS/DPAPI/lifecycle remain unverified. OPS-19-03 stays Pending.

D05 installed-service evidence: operator Install succeeded; elevated preflight 11:25:11 UTC reports service_query OK, LocalSystem, start_type 4 (disabled), current_state 1 (stopped). Agent independently read the same service state at 11:26:01 UTC. No service start or identity change claimed. Next configure the intended operator account privately in Services while keeping startup Disabled, then repeat Preflight; TLS/DPAPI and SCM lifecycle remain pending.

D05 identity evidence: operator preflight 11:30:09 UTC and agent read-only preflight 11:30:58 UTC confirm .\Sanny, configured_non_system_identity true, disabled (4), stopped (1). Agent observed backend port 8000 and Vite 5173 still listening; no owner stopped or service started. Added service-context TLS/DPAPI read-only access guard before app creation so failed decryption preserves the saved session. Latest focused service/access/preflight tests 21 pass; Ruff lint/format and strict mypy pass. Prior 813-pass full suite predates this guard. OPS-19-03 remains Pending for actual lifecycle/TLS/DPAPI and single-worker verification.

D05 service-start failure diagnosed from screenshot, actual stopped SCM state, no listener 8443 and SCM events 7000/7009. Old .venv/pythonservice.exe help exits 0xC0000135 (missing dependency), including System32 cwd/minimal PATH. Staged host and exact Python/pywintypes/VC runtime DLLs inside .venv/Scripts; new help exits expected 2 with usage in same environment. New RepairHost action changes ONLY a stopped service binary path; retains account/startup/recovery and never starts it. Future Install uses staged host. 26 focused tests pass; Ruff/format/mypy and PS parsing pass. Evidence: docs/testing/OPS-19-service-host-repair.json. Actual SCM repair/start remains operator-admin work; port 8000 owner still running, untouched. OPS-19-03 remains Pending; counts 234/46; formal sessions zero.

The pywin32 venv layout discussion supports using Scripts for the native host:
https://github.com/mhammond/pywin32/discussions/2734
The runtime dependency requirement is also documented in the project README:
https://github.com/mhammond/pywin32#running-as-a-windows-service
