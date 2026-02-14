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
