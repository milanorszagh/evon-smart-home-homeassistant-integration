import test from "node:test";
import assert from "node:assert/strict";

const INDEX_URL = new URL("../dist/index.js", import.meta.url);

async function importFresh(url) {
  const href = url.href + `?v=${Date.now()}-${Math.random()}`;
  return import(href);
}

test("setupGracefulShutdown is exported and is a function", async () => {
  // Stub env vars so the module can load without errors
  process.env.EVON_HOST = "http://example.com";
  process.env.EVON_USERNAME = "user";
  process.env.EVON_PASSWORD = "pass";

  const mod = await importFresh(INDEX_URL);
  assert.equal(typeof mod.setupGracefulShutdown, "function");

  // Force exit after test since importing index.js starts the MCP server
  // which keeps the event loop alive via stdio transport
  setTimeout(() => process.exit(0), 100).unref();
});
