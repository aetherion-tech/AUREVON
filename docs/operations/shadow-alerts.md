# TradingView shadow observations

Implementation is observation-only and disabled by default. There is no tunnel,
public ingress or actual TradingView delivery configured on this machine.
OPS-19-08 stays Pending until reachable delivery and G2 evidence are verified.
The inbox never imports an executor, planner or wallet; it cannot place or close
trades. A match is comparison evidence only, never authority to enable entries.

## Source and messages

After operations migration 0012 is applied under a stopped-owner backup procedure,
an authenticated dashboard can read `/api/shadow/status`. `source_id` fingerprints
the configured stream, committed indicator settings and market configuration.
It changes on a source/grid/settings change. The current source must have actual
indicator and market checkpoints; missing source returns an unavailable state.

Configure `SHADOW_STREAM` to the independently verified chart stream and set a
dedicated local `SHADOW_WEBHOOK_SECRET` of at least 32 characters. Do not reuse a
dashboard password, Kite key/token or account credential. Store the token only in
ignored local configuration and the recipient ingress's secret storage; never
paste it into chat, a public webhook URL or TradingView's JSON message.
`SHADOW_INGESTION_ENABLED` remains false until the entire ingress is verified.
Changing these settings requires a safe owner restart; saving dashboard strategy
settings does not activate them.

The JSON message contract is:

```json
{
  "event_id": "unique-source-event-001",
  "source_id": "<64-character source_id from the verified local source>",
  "brick_index": 123,
  "at": "2026-10-30T10:00:00+05:30",
  "kind": "ENTRY",
  "family": "CO",
  "direction": 1,
  "trade_id": "<the actual matching Pine trade ID>"
}
```

`kind` is ENTRY or EXIT; family uses the original Pine `f_fam2` grouping:
CO = CORE, DIV = DIV/HDIV, OT = all other families. Direction is 1 or -1. A
distinct delivery ID is required per source event; retries must keep the same ID
and body. A reused ID with changed contents returns 409. Requests must be recent:
at most five minutes old and at most 30 seconds ahead of the receive clock.
Historical exports belong in parity/replay tooling rather than this live inbox.
Unknown fields, non-JSON messages, oversized/missing Content-Length and changed
source IDs are rejected. The payload limit is 8192 bytes; the durable allowance is
60 new receipts per minute per stream. Duplicate retries do not consume it.

Do not use raw TradingView bar_index as the backend index without an independently
verified origin mapping. Do not guess trade IDs or merge equal-time bricks. The
original Pine alertcondition messages alone do not contain all fields above;
an independent debug/alert copy must emit the actual state, with calibrated
index/source identity, after REF-00-04/G2 checks. Preserve the original Pine file.
Do not replace missing reference exports with synthetic messages.

## Recipient ingress requirements

TradingView documents HTTPS delivery, accepted public ports 80/443 and a roughly
three-second response limit in its
[webhook setup guide](https://www.tradingview.com/support/solutions/43000529348-how-to-configure-webhook-alerts/).
The local dashboard port 8443 is not directly eligible. No paid tunnel or hosting
purchase is authorized by this plan.

The recipient must authenticate TradingView's HTTPS client certificate using a
verified trust chain plus the documented identity, not just an untrusted header
or a matching subject string. See
[TradingView webhook authentication](https://www.tradingview.com/support/solutions/43000680459-webhook-authentication/).
Only after that authentication may the ingress inject
`Authorization: Bearer <dedicated SHADOW_WEBHOOK_SECRET>` and forward to the local
`POST /api/shadow/tv-alert`. Never accept a caller-supplied replacement token as
proof of a TradingView certificate. The backend token authenticates the recipient
ingress; backend tests do not prove an external certificate was verified.

Expose only this exact POST path through that ingress. Keep dashboard, docs,
wallet, settings, WebSocket and all other API paths private. Enforce body limits
and rate limits before forwarding, reject unexpected transfer framing, strip
untrusted forwarding/authorization headers, disable body/token logging, and do
not pass proxy-origin claims into the backend. The hardened local runner accepts
only localhost/127.0.0.1 Host; a verified ingress must forward a local Host.

The backend commits the bounded receipt and returns promptly; comparison is a
separate authenticated read. Normal mutation audit records status and route,
never the secret or alert payload. Verify timeout/retry behavior using an actual
test alert before recording any delivery as external shadow evidence.

## Comparison screen and evidence

Live now contains **TradingView shadow comparison**. Disabled, unavailable,
pending, matched and mismatch states are explicit. The authenticated comparison
endpoint accepts a window of up to 500 bricks, with a bounded 2000-event limit.
The panel displays the latest 200-brick window, counts and mismatch identifiers.

Matching requires the same kind, grouped family, direction and actual trade ID
within two aligned brick indices. Maximum one-to-one matching prevents duplicate
receipts from satisfying multiple backend events. Both window edges include the
tolerance halo; the newest unmatched events remain pending until more than two
bricks have elapsed. A changed source cannot reuse old receipts. Reads do not
alter trading state or invent missing alerts.

A clean bounded window is not 10-day G2 parity, a completed daily comparison,
or G4/G5 approval. Retain actual source/export hashes, full daily window coverage,
receipt IDs, mismatches, explanations, reconciliation and weekly reviews before
claiming QA-19-16. Receipt/audit history is kept indefinitely. No automatic
configuration changes or background user notifications are supplied.

Local synthetic checks:

```powershell
cd D:\WorkSpace\AUREVON\backend
.\.venv\Scripts\python.exe -m pytest tests/test_shadow_operations.py -q
```

Browser checks after building FE:

```powershell
cd D:\WorkSpace\AUREVON\frontend
npm.cmd run build
npm.cmd run test:browser -- --config playwright.release.config.ts --grep "shadow comparison|mocked comparison"
```

The browser mismatch scenario deliberately uses mocked responses and must not be
recorded as actual TradingView delivery.
