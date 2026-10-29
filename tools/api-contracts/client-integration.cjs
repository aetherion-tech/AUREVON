"use strict";
// Test-only cookie transport: no browser stores or real accounts are involved.
const assert = require("node:assert/strict");
const { ApiClient, ApiError, LiveCursor } = require(process.argv[2]);
const origin = process.argv[3];
const index = Number(process.argv[4]);
const ordinal = Number(process.argv[5]);
let cookie = "";
let calls = 0;
const transport = async (url, options) => {
  calls++;
  const headers = new Headers(options.headers);
  if (cookie) headers.set("Cookie", cookie);
  const response = await fetch(url, { ...options, headers });
  const value = response.headers.get("set-cookie");
  if (value) cookie = value.split(";", 1)[0];
  return response;
};

async function main() {
  const client = new ApiClient(origin, transport);
  await assert.rejects(client.get("/api/wallet"), e => e instanceof ApiError && e.status === 401);
  await client.login("fixture-password-only");
  const initial = await client.get("/api/wallet");
  assert.equal(initial.balance, "100000.00");
  const deposited = await client.post("/api/wallet/deposit", { amount: "12.34" }, { key: "node-deposit" });
  assert.equal(deposited.balance, "100012.34");
  assert.deepEqual(await client.post("/api/wallet/deposit", { amount: "12.34" }, { key: "node-deposit" }), deposited);
  await assert.rejects(client.post("/api/wallet/deposit", { amount: "99.00" }, { key: "node-deposit" }), e => e.status === 409);
  await assert.rejects(client.post("/api/wallet/deposit", { amount: 1.1 }, { key: "node-bad-money" }), e => e.status === 422);
  const newClient = new ApiClient(origin, transport);
  await assert.rejects(newClient.post("/api/wallet/withdraw", { amount: "5.00" }, { key: "node-withdraw" }), e => e.status === 401);
  await newClient.session();
  assert.equal((await newClient.post("/api/wallet/withdraw", { amount: "5.00" }, { key: "node-withdraw" })).balance, "100007.34");

  const signalPage = await client.get("/api/signals", { stream: "api-test", accepted: true });
  const entry = signalPage.items.find(s => s.index === index && s.entry_event_ordinal === ordinal);
  assert.equal(entry.signal_id, `api-test:${index}:${ordinal}`);
  const prepared = await client.post("/api/decisions/prepare", { stream: entry.stream, index: entry.index, event_ordinal: entry.entry_event_ordinal }, { key: "node-prepare" });
  assert.equal(prepared.accepted, true);
  assert.equal(prepared.executable, false);
  const confirmed = await client.post("/api/decisions/{identity}/confirm", {}, { key: "node-confirm", params: { identity: prepared.decision_id } });
  assert.equal(confirmed.accepted, true);
  assert.equal(confirmed.state, "ENTERING");
  assert.deepEqual(await client.post("/api/decisions/{identity}/confirm", {}, { key: "node-confirm", params: { identity: prepared.decision_id } }), confirmed);
  assert.equal((await client.get("/api/positions/open"))[0].trade_id, confirmed.trade_id);
  assert.equal((await client.get("/api/wallet")).reserved, "9116.25");
  const close = await client.post("/api/trades/{trade_id}/close", {}, { key: "node-close", params: { trade_id: confirmed.trade_id } });
  assert.equal(close.pending_closures, 1);
  assert.equal((await client.post("/api/kill", {}, { key: "node-kill" })).entries_locked, true);
  assert.match(await client.exportTrades(), /^trade_id,/);

  const cursor = new LiveCursor();
  const snapshot = await client.get("/api/live/snapshot");
  assert.equal(snapshot.wallet.balance, "100007.34");
  assert.equal(snapshot.positions.length, 1);
  cursor.reset(snapshot);
  const event = { run_id: cursor.run, sequence: cursor.sequence + 1, at: snapshot.at, kind: "signal", payload: snapshot.signals[0] };
  const batch = { type: "events", run_id: cursor.run, sequence: event.sequence, events: [event] };
  assert.equal(cursor.accept(batch).events.length, 1);
  assert.equal(cursor.accept(batch).events.length, 0);
  const sequence = cursor.sequence;
  assert.equal(cursor.accept({ ...batch, sequence: sequence + 2, events: [{ ...event, sequence: sequence + 2 }] }).resync, true);
  assert.equal(cursor.sequence, sequence);
  assert.equal(cursor.accept({ type: "resync_required", run_id: cursor.run, sequence, reason: "cursor_expired" }).resync, true);
  cursor.reset(await client.get("/api/live/snapshot"));
  assert.equal(cursor.accept({ type: "heartbeat", run_id: "different-process", sequence: 0 }).resync, true);
  assert.equal(cursor.accept({ type: "heartbeat", run_id: cursor.run, sequence: cursor.sequence + 99 }).resync, false);
  assert.match(new ApiClient("https://localhost:5173").liveUrl(cursor), /^wss:\/\/localhost:5173\/ws\/live\?/);
  assert.throws(() => client.liveUrl(cursor), /HTTPS/);

  await client.logout("node-logout");
  await assert.rejects(newClient.get("/api/wallet"), e => e.status === 401);
  const before = calls;
  await assert.rejects(newClient.post("/api/wallet/deposit", { amount: "1.00" }, { key: "expired" }), e => e.status === 401);
  assert.equal(calls, before);
  console.log(JSON.stringify({ result: "passed", transportCalls: calls }));
}
main().catch(error => { console.error(error); process.exitCode = 1; });
