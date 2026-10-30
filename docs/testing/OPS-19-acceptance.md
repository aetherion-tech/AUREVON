# OPS-19 release work and remaining acceptance

Initial 2026-10-30 (D05) batch: six of the 18 section-19 product rows accepted;
twelve were Pending at that point. Current status is superseded by
[OPS-19-followup.md](OPS-19-followup.md): nine Completed / nine Pending. This is partial delivery of the requested full section, not paper release
or burn-in acceptance. Operator processes, .env, DB/migrations, original Pine and
market observation were not changed. No purchases or real trades were made.

| ID | Result and evidence |
| --- | --- |
| OPS-19-01 | Completed: built React assets through FastAPI; extensionless HTML navigation fallback, missing assets/API errors preserved, same-origin HTTPS API/WSS. All 36 release browser flows pass. |
| OPS-19-02 | Completed: repeatable Check/Setup/Build/Run/Backup/Restore/Audit PowerShell entrypoint, separate SCM entrypoint and shared IntelliJ run configuration. Check and Inspect exercised; PS parsed and XML validated. Setup delegates to locked dependency installers and never writes secrets/migrations. IDE execution itself was not exercised. |
| OPS-19-03 | Pending: pywin32 wrapper/manual SCM commands and OS lease implemented. Duplicate-owner/release and graceful SCM Stop request tested. Actual SCM install/start/restart, service identity/DPAPI/TLS permissions and automatic restart policy are unverified; nothing installed or activated. |
| OPS-19-04 | Pending: opt-in nightly report/reconciliation/snapshot integrated into existing desired/leased owner loop after calendar close +10 minutes; refuses exposure and checks copied book revisions. WAL backup/restoration into separate DB passes, including initialized synthetic wallet. Still needs an attached managed close/quote-retry-to-report scenario; defaults remain disabled. |
| OPS-19-05 | Pending: UTC daily log rotation with 90 archives; explicit sealed-run hash-verified gzip compression preserving originals; dry-run and tamper/idempotence checks pass. Automatic tick deletion and persisted P&L tick expiry still unimplemented (no dedicated P&L tick producer/table). No retention was applied to operator recordings. |
| OPS-19-06 | Completed review: loopback/Host guard in hardened runner, no proxy-header trust, secure HttpOnly Strict cookies, CSRF/Origin/audit, WSS auth, secret-free request logging/errors and headers reviewed against actual code and regression tests. Backend dependency findings remain an explicit release risk, not suppressed. Development raw Uvicorn lacks the runner's Host guard. |
| OPS-19-07 | Completed: repeatable both-graph audit with JSON evidence and nonzero findings/unavailable outcomes; update-check procedure documented. Frontend patched to Vitest 4.1.12, zero audit findings. Backend 12 advisory records retained/investigated below; this task's completion does not mean vulnerability-free release. |
| OPS-19-08 | Pending: authenticated TradingView ingestion, durable event comparison/mismatch UI and reachable webhook are not implemented. Actual chart/export event identity and G2 evidence are still missing; no public tunnel/service was created. |
| QA-19-09 | Completed: existing 36 Playwright flows rerun on built FastAPI HTTPS server, covering login/status, live chart, history filters/CSV, wallet, versioned settings, manual close/kill and recovery/idempotency. Temporary SQLite/TLS on 5174; no Vite proxy for this release run. Some unavailable/edge states deliberately use browser fixtures, as documented in FE evidence. |
| QA-19-10 | Pending: no actual recorded eligible day/G3 evidence. Synthetic chart publication/browser fixtures are not a recorded-day accounting reconciliation. |
| QA-19-11 | Pending formal drill: existing disconnect/overflow/token/readiness regressions pass; deliberate attached managed recovery drill evidence is absent. |
| QA-19-12 | Pending formal drill: existing restart-at-commit/partial-leg/duplicate/rollback regressions pass; actual process-crash drill with managed runtime remains absent. |
| QA-19-13 | Pending formal drill: existing loss-lock/kill/close/square-off/stale-quote/wrong-clock regressions pass; integrated owner/browser drill evidence remains absent. |
| QA-19-14 | Pending: no representative-load end-to-end tick/indicator/dispatch benchmark. No claim that 50 ms / 1 s targets are met. |
| QA-19-15 | Pending: zero qualifying formal sessions; at least 20 exchange sessions required after gates/drills. |
| QA-19-16 | Pending: no actual daily TradingView comparisons or weekly family/grade/time review. |
| QA-19-17 | Pending: G4/G5 cannot be accepted without the preceding evidence and resolved anomalies. |
| OPS-19-18 | Completed: docs/operations/paper-release.md covers safe startup/login, recovery, close, backups/isolated restore, retention, dependency/security review, staged service setup and troubleshooting, with verified/unverified boundaries explicit. |

## Validation

- Full backend regression run: **785 passed**, one existing Starlette/httpx
  deprecation warning. That collection preceded the last five release/drill cases.
- Latest focused suites: **63 passed** (8 release + 55 execution cases), including both empty and initialized
  wallet nightly snapshots, WAL backup/tamper/refused overwrite, SPA boundaries,
  sealed recording compression, duplicate owner, SCM graceful stop request, HTTPS Host guard and exposure-refusing nightly backup.
  Full regression and latest focused tests cover **790 distinct backend cases**;
  the final five cases were not part of the 785-case full invocation. Final
  collection confirms 790 tests. Latest maintenance changes passed the focused
  suite; the full invocation began before those changes.
- Strict mypy: 102 application modules; Ruff lint/format pass.
- Frontend production build/strict TypeScript, ESLint and **35 Vitest tests** pass
  after the dependency update.
- Built FastAPI HTTPS browser run: **36/36 pass**. Initial run was 34/36 with
  intermittent Settings Retry and Wallet dialog timeouts; both passed a focused
  rerun and then the full rerun. No assertions were weakened or timeouts raised.
  Windows Proactor connection-reset callbacks were observed during deliberate
  client abort/recovery cases; successful rerun retained this limitation.
- `scripts/ops.ps1 -Action Check` and `scripts/service.ps1 -Action Inspect` ran
  using process-scoped ExecutionPolicy Bypass. No service was present/installed.
- Readiness remains BLOCKED: BE-08-14, QA-09-19/20, QA-11-15/16 and actual
  owner/gate acceptance. No background notifications or account billing access.

Repeat browser checks after building:

```powershell
cd D:\WorkSpace\AUREVON\frontend
npm.cmd run build
npm.cmd run test:browser -- --config playwright.release.config.ts
```

## Dependency findings

Retained machine-readable evidence:
`OPS-19-backend-audit.json`, `OPS-19-frontend-audit.json`.

Initial frontend audit found affected Vitest/mocker and tinypool test dependencies.
Vitest upgraded from 3.2.x to 4.1.12 and its updated transitive graph audits clean.
Maintainer sources:
[Vitest mock injection](https://github.com/vitest-dev/vitest/security/advisories/GHSA-qxg6-89mg-rqv8),
[tinypool worker options](https://github.com/tinylibs/tinypool/security/advisories/GHSA-85c8-ppgw-ccpr).

Backend lock audit reports 73 audited dependencies and 12 advisory records:

- Autobahn 19.11.2 via kiteconnect 5.2.2: redirect header injection
  (GHSA-gwp7-vqr5-h33h / PYSEC-2020-25) and compressed-message size boundary
  (GHSA-hxp9-w8x3-p566 / PYSEC-2026-4027). Fix versions reported are 20.12.3
  and 26.7.1. Kite pins the old Autobahn dependency; no override was introduced.
- Twisted 26.4.0 via Autobahn: GHSA-2qrf-pqgx-qh9v, GHSA-3476-c5c2-fr73,
  GHSA-53xc-49m8-p798, GHSA-8pqf-f4m5-798g, GHSA-cwm5-jh59-mwxr,
  GHSA-jj36-9pvh-vj5r, GHSA-q7qq-6mhp-9rc4 and GHSA-vpp8-g58w-m8mp.
  Seven report 26.10.0rc1 as a fix; GHSA-8pqf-f4m5-798g reports no fix.
  The application uses the broker client path, not Twisted mail/server services;
  that is a scope observation, not a proof the dependency graph is safe.

The audit command intentionally still exits 1. Upstream broker compatibility and
the affected WebSocket handling need investigation before approving an exposed
deployment. No ignored advisories, forced prereleases or live broker probes.

## Next work and accounting

Next pending ID: OPS-19-03 isolated SCM lifecycle verification with the intended
Windows identity; independent follow-ups are OPS-19-04 managed close/report
integration, OPS-19-05 retention completion, OPS-19-08 shadow pipeline and
QA-19-14 representative performance measurement. Full-section completion also
requires actual recorded-day, drill, shadow and 20-session evidence.

Product total: 280; **231 Completed / 49 Pending**. Section 19: **6 Completed /
12 Pending**. Frontend remains 57/57 complete. Usage, spend, allowance, headroom,
renewal/reset remain Unknown; extra paid usage INR 0; cash ceiling INR 20,000.
