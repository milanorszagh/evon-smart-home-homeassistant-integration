import test from "node:test";
import assert from "node:assert/strict";

const CONFIG_URL = new URL("../dist/config.js", import.meta.url);
const API_CLIENT_URL = new URL("../dist/api-client.js", import.meta.url);

async function importFresh(url) {
  const href = url.href + `?v=${Date.now()}-${Math.random()}`;
  return import(href);
}

test("encodePassword produces base64 hash and isPasswordEncoded detects it", async () => {
  const { encodePassword, isPasswordEncoded } = await importFresh(CONFIG_URL);
  const encoded = encodePassword("user", "pass");
  assert.equal(encoded.length, 88);
  assert.ok(isPasswordEncoded(encoded));
});

test("login caches token until expiry", async () => {
  process.env.EVON_HOST = "http://example.com";
  process.env.EVON_USERNAME = "user";
  process.env.EVON_PASSWORD = "pass";

  const originalFetch = global.fetch;
  let fetchCalls = 0;
  global.fetch = async () => {
    fetchCalls += 1;
    return new Response("", {
      status: 200,
      headers: { "x-elocs-token": "token-1" },
    });
  };

  try {
    const { login } = await importFresh(API_CLIENT_URL);
    const first = await login();
    const second = await login();
    assert.equal(first, "token-1");
    assert.equal(second, "token-1");
    assert.equal(fetchCalls, 1);
  } finally {
    global.fetch = originalFetch;
  }
});

test("apiRequest retries once after auth failure", async () => {
  process.env.EVON_HOST = "http://example.com";
  process.env.EVON_USERNAME = "user";
  process.env.EVON_PASSWORD = "pass";

  const originalFetch = global.fetch;
  let apiCalls = 0;
  global.fetch = async (url) => {
    if (url.endsWith("/login")) {
      return new Response("", {
        status: 200,
        headers: { "x-elocs-token": "token-2" },
      });
    }

    apiCalls += 1;
    if (apiCalls === 1) {
      return new Response("", { status: 401 });
    }

    return new Response(JSON.stringify({ ok: true }), {
      status: 200,
      headers: { "content-type": "application/json" },
    });
  };

  try {
    const { apiRequest } = await importFresh(API_CLIENT_URL);
    const result = await apiRequest("/instances/TestDevice");
    assert.deepEqual(result, { ok: true });
    assert.equal(apiCalls, 2);
  } finally {
    global.fetch = originalFetch;
  }
});
