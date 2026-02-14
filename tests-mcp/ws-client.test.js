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
