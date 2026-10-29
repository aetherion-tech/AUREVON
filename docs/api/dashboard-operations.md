# Dashboard API operation (paper only)

Run one application worker on 127.0.0.1. Dashboard sessions, the public event
journal and replay jobs are process-local; restarting requires login and a fresh
snapshot. Lockout counters, audit intents/outcomes and alerts are persisted.
No market worker or real account is started by the API contract exporter.

## Authentication and migrations

Apply `uv run alembic upgrade head` from backend before using dashboard mutations.
Migration 0006 adds lockout, audit and alert tables without changing market data.
Migration tests cover fresh upgrade, repeat upgrade, downgrade/upgrade and metadata
agreement. Missing dashboard storage returns 503; mutations fail closed.

Set the dashboard hash using the local interactive tool described in
[BE-13-02 evidence](../testing/BE-13-02-acceptance.md). Actual `.env` is unchanged.
Login accepts JSON at POST `/api/auth/dashboard/login`. Read `X-CSRF-Token` from
the login response or authenticated GET `/api/auth/dashboard/status`; send it
with the session cookie for every subsequent API mutation, including logout.
Cookies are Secure, HttpOnly, SameSite=Strict. Use HTTPS/WSS.

Five failed passwords lock the single operator for 900 seconds by default;
the fifth attempt and requests during lockout return 429 with Retry-After.
Restart does not clear the lock. A successful password after expiry clears the
failure count. Missing/invalid credentials never become a configured session.

Kite login initiation also requires dashboard authentication. Its callback uses
the existing one-time state and Lax state cookie plus a bounded server-side
delegation to the initiating dashboard session. This accommodates the cross-site
return where the Strict dashboard cookie is absent. Dashboard logout, login
rotation or expiry revokes the delegation. Broker tokens never enter client JSON.

Audit stores request ID, timestamp, actor, known route template and HTTP outcome.
It excludes bodies, query strings, passwords, tokens and arbitrary paths. An audit
intent commits before each API mutation (and Kite login/callback); a pending/null
outcome after interruption requires inspection before retry. Audit completion
failure returns 503 and does not claim the operation rolled back. Domain financial actions now use durable command intents plus wallet/decision/
settings idempotency keys; lost replies are recovered without duplicate effects.
They require an explicitly attached owner service and remain unavailable normally.

## Development proxy and production origin

Use an HTTPS development server on https://localhost:5173 (or the explicit
127.0.0.1 origin). Proxy `/api` and `/ws` from that server to the backend so the
browser uses one host. Do not call a different site's backend directly with a
Strict cookie. An example Vite server configuration is:

```ts
import { readFileSync } from "node:fs";
export default {
  server: {
    host: "127.0.0.1", port: 5173,
    https: {
      key: readFileSync(process.env.LOCAL_TLS_KEY!),
      cert: readFileSync(process.env.LOCAL_TLS_CERT!),
    },
    proxy: {
      "/api": { target: "http://127.0.0.1:8000", changeOrigin: false },
      "/ws": { target: "ws://127.0.0.1:8000", ws: true, changeOrigin: false },
    },
  },
};
```

The certificate/key stay on the developer's PC; do not commit or expose them.
Frontend setup remains FE-14 work. CORS accepts only explicit
`DASHBOARD_ORIGINS`, with credential and CSRF-header support, never a wildcard.
Production can set `DASHBOARD_ORIGINS=[]` and `DASHBOARD_FRONTEND_DIR` to a built
frontend directory containing index.html. The app serves it at `/dashboard/`,
alongside `/api` and `/ws` on the same HTTPS origin. No client environment file
contains a broker secret or dashboard hash. Remote deployment is outside this plan.

## Snapshots, history and transport

- GET `/api/live/snapshot` and `/api/market/service/status` require authentication.
  They project the actual managed worker, selected exact contract, data quality,
  recovery/context, normalized ticks and last brick. Entries remain disabled;
  unattached domains are explicitly unavailable. A bound paper owner projects actual
  wallet/P&L/positions and persisted replay signals; no fake zero balances.
- Authenticated, CSRF-protected POST `/api/market/service/start` / `stop` delegate
  to the existing owner-locked service. Default service-enabled setting stays false.
- GET `/api/bricks` and `/api/candles` use a required stream and bounded keyset
  cursors. Responses identify checkpoint revision and configuration hash; send
  the revision on later pages and reload on 409. Candles require a matching source
  token. Brick history now has typed replay overlays after explicit validated
  source publication, availability/missing-index status and an indicator source
  fingerprint. Start brick paging with `after=-1` (default, includes index 0).
  Send `revision` and `indicator_source` on later brick pages; reload on 409.
  Candle pages stay independent of Renko overlays. Normal startup does not
  publish or activate indicators. See [BE-13-06 operation/evidence](../testing/BE-13-06-acceptance.md).
- `/ws/live` requires a valid cookie and an allowed Origin. A new connection
  receives `{type:"snapshot", snapshot:...}` at journal sequence S. Apply only
  events with a higher sequence in that run. Resume with `run_id` and `after=S`.
  Typed batches are ordered; status refreshes at least every five seconds.
- One public journal retains 256 events. Spot ticks are coalesced to at most four
  per second; snapshots also retain the latest futures price. All persisted bricks
  are emitted, including multi-brick closes. Signal/trade/position payload types
  are transport-ready; their producers remain unimplemented in BE-09/11/12.
- The cursor never silently skips a reliable event: an expired/future cursor or
  changed run requires snapshot/history resync. A slow send times out in two
  seconds and closes 1013; overflow sends `resync_required` then closes 1013.
  Reauthenticate after close 1008. Refresh the REST snapshot/history after 1013;
  do not continue applying a stale run. Reload the current snapshot and paged
  signals/history/alerts using the completed domain APIs.
- GET `/api/alerts` pages durable alerts; POST `/api/alerts/{id}/ack` is idempotent
  and audited. Real recovery/source-quality, paper risk rejects and reconciliation
  producers now retain/emit public alerts; BE-13-14 code is complete.
- GET/POST `/api/mode` is PAPER/unarmed only. LIVE returns 403, arming returns 409,
  and no real-order path exists. Entry status reflects an explicitly attached owner
  capability; normal startup stays disabled and actual reference/operational gates
  remain Pending.

## Isolated development replay

`DEVELOPMENT_REPLAY_ENABLED=false` by default. When explicitly enabled,
POST `/api/dev/replay` accepts a recorded run ID, sorted ISO-date JSONL filenames,
spot/future tokens, box and anchor. It returns 202 with a job ID; authenticated
GET `/api/dev/replay/{id}` reports running/completed/failed. Only the latest job is
retained in process memory; save its response for development notes if needed.

The service limits input bytes/files, rejects traversal/symlink escapes, copies
bounded inputs, validates sourced calendar coverage and reuses production replay
and persistence in a separate temporary SQLite database. The temporary database
is disposed after the summary; it never changes the market DB or recording files.
Only one job runs; concurrent managed-feed start/replay is rejected. Shutdown joins
the job before disposal. No arming or LIVE state can be entered in this release.
Replay is development evidence, never market observation or formal burn-in.

## Generated contracts

From backend, `uv run python -m app.tools.export_api` writes the actual versioned
REST and WebSocket schemas to `docs/api/openapi.v1.json`; `--check` detects drift.
From tools/api-contracts, run `npm.cmd ci`, `npm.cmd run generate`, then
`npm.cmd run check`. Locked openapi-typescript generates `docs/api/api-v1.d.ts`;
TypeScript checks REST login, frame narrowing and rejection of live-mode types.
The framework-independent frontend/src/api/client.ts imports these generated
types and is verified against a real isolated test backend. BE-13-20 contract
integration is complete; React scaffold/browser wiring remains FE-14. See
[domain API operation and boundaries](../testing/BE-13-domain-acceptance.md).
