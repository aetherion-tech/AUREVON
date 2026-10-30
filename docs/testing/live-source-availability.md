# Live chart and signals availability repair

2026-10-30, D05. User screenshot showed raw Not Found panels for Renko chart and
Signal feed, with indicators/signals listed as unavailable. Read-only local
configuration check found `renko_anchor=None`, `renko_mode=minute_close`, local
UI enabled and default market service disabled. No secret values were printed.

## Result

- Explicit quote-only mode now explains the verified-anchor requirement and
  omits chart requests that cannot succeed in that mode. No anchor is guessed.
- Signals marked unavailable by the snapshot show a clear waiting state and
  do not fetch the missing indicator signal resource. Cached old signals are
  hidden until that source becomes available again.
- A stopped source returning chart 404 shows a missing-history explanation
  instead of the raw error/Retry loop. It does not create empty bricks or claim
  chart history exists. Chart data and cached direction are hidden for this
  missing resource. Genuine 500 errors remain visible and retryable.
- Valid archived charts remain readable when the live worker is stopped.
  `latest_brick=null` is not treated as proof that stored history is absent.
  Managed indicator-domain availability is also distinct from valid published
  replay overlays. Direction retains the existing matching configuration/source
  checks, with explicit quote-only/chart-404 guards for stale cached values.
- Source availability transitions resume normal chart/signal loading. Paging,
  incremental tick/brick rendering, revision fencing and entry gates remain.

This repairs the UI's handling of unavailable data. It does not generate real
Renko history, activate the indicator engine, accept references or enable entries.
Actual REF-00-03 anchor/settings and later reference gates remain outstanding.

## Validation

Frontend unit tests: 35 pass. Production build/TypeScript and ESLint pass.
Final selected built HTTPS run: **12/12 pass**, covering new availability
transitions/error states plus the existing Live and feed suites. Final results are retained in
`live-source-final-browser-checks.json`. New scenarios use mocked availability
and errors against the isolated browser harness, not the operator account.
The fixture uses port 5174 and temporary DB/TLS; operator state was untouched.

Earlier failed runs are retained separately:

- `live-source-initial-browser-checks.json`: 6 pass / 5 fail. An overly broad
  latest-brick guard initially suppressed valid archived charts.
- `live-source-second-browser-checks.json`: 11 pass / 1 fail. The indicator
  availability guard initially suppressed valid replay direction. Corrected
  source semantics; no tests or existing chart guarantees were removed.

Existing Windows Proactor connection-reset callbacks occurred during synthetic
browser disconnects. They are not evidence of broker/feed recovery failure.

No backend application, operator DB, .env, original Pine, market feed, account,
service or actual trading acceptance changed. Product counts remain 237 Completed
/ 43 Pending; formal sessions zero. Original Pine and immutable README v1 hashes
remain checked. Next engineering task remains QA-19-14.

## Operator check

Reuse the existing development backend and Vite owner; no backend restart is
needed for this frontend-only change. Hard-refresh
https://localhost:5173/dashboard/ and inspect Renko chart/Signal feed. In quote-only
mode expect anchor/history guidance, not a fabricated chart or trading signals.
If Vite is not running, `npm.cmd run dev` from frontend starts it. The built
frontend was also updated; service port 8443 remains a separate unresolved track.

Budget/usage: no purchase, extra paid usage INR 0; account usage, cash/headroom
and renewal/reset remain Unknown. No background monitoring or alerts claimed.
