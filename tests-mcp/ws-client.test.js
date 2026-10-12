import test from "node:test";
import assert from "node:assert/strict";

const WS_CLIENT_URL = new URL("../dist/ws-client.js", import.meta.url);

async function importFresh(url) {
  const href = url.href + `?v=${Date.now()}-${Math.random()}`;
  return import(href);
}

test("T-H2: sequenceId resets to 1 after reconnect", async () => {
  const { EvonWsClient } = await importFresh(WS_CLIENT_URL);
  const client = new EvonWsClient("http://localhost:9999");
  assert.equal(client["sequenceId"], 1, "starts at 1");
  client["sequenceId"] = 500;
  assert.equal(client["sequenceId"], 500, "incremented");
  client["resetConnectionState"]();
  assert.equal(client["sequenceId"], 1, "reset to 1 after reconnect");
});

test("T-H3: resubscribeAll builds correct subscription list from Map", async () => {
  const { EvonWsClient } = await importFresh(WS_CLIENT_URL);
  const client = new EvonWsClient("http://localhost:9999");
  const callback = () => {};
  client["subscriptions"].set("light_1", callback);
  client["subscriptions"].set("blind_2", callback);
  const calls = [];
  client["call"] = async (method, args) => { calls.push({ method, args }); return null; };
  await client["resubscribeAll"]();
  assert.equal(calls.length, 1, "one RegisterValuesChanged call");
  assert.equal(calls[0].method, "RegisterValuesChanged");
  const [enable, subs, flag1, flag2] = calls[0].args;
  assert.equal(enable, true);
  assert.equal(flag1, true);
  assert.equal(flag2, true);
  const instanceIds = subs.map(s => s.Instanceid).sort();
  assert.deepEqual(instanceIds, ["blind_2", "light_1"]);
  for (const sub of subs) { assert.deepEqual(sub.Properties, []); }
});

test("T-H3: resubscribeAll is a no-op when no subscriptions exist", async () => {
  const { EvonWsClient } = await importFresh(WS_CLIENT_URL);
  const client = new EvonWsClient("http://localhost:9999");
  let callCount = 0;
  client["call"] = async () => { callCount++; return null; };
  await client["resubscribeAll"]();
  assert.equal(callCount, 0, "no call made when no subscriptions");
});

test("T-H4: disconnect during connect rejects connectPromise", async () => {
  const { EvonWsClient } = await importFresh(WS_CLIENT_URL);
  const client = new EvonWsClient("http://localhost:9999");
  client["login"] = () => new Promise(resolve => setTimeout(() => resolve("token"), 50));
  const connectPromise = client.connect();
  client.disconnect();
  await assert.rejects(connectPromise, /aborted/i);
});

test("T-H4: disconnectRequested flag resets on next connect", async () => {
  const { EvonWsClient } = await importFresh(WS_CLIENT_URL);
  const client = new EvonWsClient("http://localhost:9999");
  client["disconnectRequested"] = true;
  let flagDuringConnect;
  client["performConnect"] = async () => {
    flagDuringConnect = client["disconnectRequested"];
    throw new Error("stop here");
  };
  try { await client.connect(); } catch { /* Expected */ }
  assert.equal(flagDuringConnect, false, "flag reset at start of connect()");
});

// ---------------------------------------------------------------------------
// Liveness: ping/pong heartbeat (issue #12)
// ---------------------------------------------------------------------------

const CONSTANTS_URL = new URL("../dist/constants.js", import.meta.url);

function fakeSocket() {
  const handlers = {};
  return {
    readyState: 1, // WebSocket.OPEN
    pings: 0,
    terminated: 0,
    on(event, cb) { handlers[event] = cb; return this; },
    ping() { this.pings++; },
    terminate() { this.terminated++; this.readyState = 3; },
    close() { this.readyState = 3; },
    removeAllListeners() {},
    emit(event, ...args) { handlers[event]?.(...args); },
  };
}

async function heartbeatFixture(t) {
  t.mock.timers.enable({ apis: ["setInterval", "setTimeout"] });
  const { EvonWsClient } = await importFresh(WS_CLIENT_URL);
  const { WS_HEARTBEAT_INTERVAL_MS, WS_PONG_TIMEOUT_MS, WS_HEARTBEAT_RECONNECT_DELAY_MS } = await import(CONSTANTS_URL.href);
  const client = new EvonWsClient("http://localhost:9999");
  const ws = fakeSocket();
  client["ws"] = ws;
  client["connected"] = true;
  return { client, ws, WS_HEARTBEAT_INTERVAL_MS, WS_PONG_TIMEOUT_MS, WS_HEARTBEAT_RECONNECT_DELAY_MS };
}

test("T-L1: heartbeat pings on every interval while connected", async (t) => {
  const { client, ws, WS_HEARTBEAT_INTERVAL_MS } = await heartbeatFixture(t);
  client["startHeartbeat"]();
  t.mock.timers.tick(WS_HEARTBEAT_INTERVAL_MS);
  assert.equal(ws.pings, 1);
  ws.emit("pong");
  t.mock.timers.tick(WS_HEARTBEAT_INTERVAL_MS);
  assert.equal(ws.pings, 2);
  client["stopHeartbeat"]();
});

test("T-L2: a missing pong terminates the socket and marks the client disconnected", async (t) => {
  const { client, ws, WS_HEARTBEAT_INTERVAL_MS, WS_PONG_TIMEOUT_MS } = await heartbeatFixture(t);
  client["startHeartbeat"]();
  t.mock.timers.tick(WS_HEARTBEAT_INTERVAL_MS);
  assert.equal(ws.terminated, 0, "no terminate before the pong grace period");
  t.mock.timers.tick(WS_PONG_TIMEOUT_MS);
  assert.equal(ws.terminated, 1, "terminated after the pong grace period");
  assert.equal(client.isConnected(), false);
  client["stopHeartbeat"]();
});

test("T-L3: a pong within the grace period keeps the connection alive", async (t) => {
  const { client, ws, WS_HEARTBEAT_INTERVAL_MS, WS_PONG_TIMEOUT_MS } = await heartbeatFixture(t);
  client["startHeartbeat"]();
  t.mock.timers.tick(WS_HEARTBEAT_INTERVAL_MS);
  ws.emit("pong");
  t.mock.timers.tick(WS_PONG_TIMEOUT_MS);
  assert.equal(ws.terminated, 0);
  assert.equal(client.isConnected(), true);
  client["stopHeartbeat"]();
});

test("T-L4: disconnect() stops the heartbeat", async (t) => {
  const { client, ws, WS_HEARTBEAT_INTERVAL_MS } = await heartbeatFixture(t);
  client["startHeartbeat"]();
  client.disconnect();
  t.mock.timers.tick(WS_HEARTBEAT_INTERVAL_MS * 3);
  assert.equal(ws.pings, 0);
});

test("T-L5: after a heartbeat failure the client reconnects once", async (t) => {
  const { client, ws, WS_HEARTBEAT_INTERVAL_MS, WS_PONG_TIMEOUT_MS, WS_HEARTBEAT_RECONNECT_DELAY_MS } = await heartbeatFixture(t);
  let reconnects = 0;
  client["connect"] = async () => { reconnects++; };
  client["startHeartbeat"]();
  // Tick step by step: node:test mock timers do not run a timer that is
  // scheduled from inside a callback nested two levels deep within one tick().
  t.mock.timers.tick(WS_HEARTBEAT_INTERVAL_MS);
  t.mock.timers.tick(WS_PONG_TIMEOUT_MS);
  assert.equal(ws.terminated, 1);
  t.mock.timers.tick(WS_HEARTBEAT_RECONNECT_DELAY_MS);
  assert.equal(reconnects, 1, "one reconnect attempt after the grace period");
});

test("T-L6: no reconnect after a heartbeat failure when disconnect() was requested", async (t) => {
  const { client, ws, WS_HEARTBEAT_INTERVAL_MS, WS_PONG_TIMEOUT_MS, WS_HEARTBEAT_RECONNECT_DELAY_MS } = await heartbeatFixture(t);
  let reconnects = 0;
  client["connect"] = async () => { reconnects++; };
  client["startHeartbeat"]();
  t.mock.timers.tick(WS_HEARTBEAT_INTERVAL_MS);
  client["disconnectRequested"] = true;
  t.mock.timers.tick(WS_PONG_TIMEOUT_MS);
  assert.equal(ws.terminated, 1, "half-open socket is still torn down");
  t.mock.timers.tick(WS_HEARTBEAT_RECONNECT_DELAY_MS);
  assert.equal(reconnects, 0, "no reconnect when disconnect was requested");
  client["stopHeartbeat"]();
});
