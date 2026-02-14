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

    return new Response(JSON.stringify({ statusCode: 200, statusText: "OK", data: { ok: true } }), {
      status: 200,
      headers: { "content-type": "application/json" },
    });
  };

  try {
    const { apiRequest } = await importFresh(API_CLIENT_URL);
    const result = await apiRequest("/instances/TestDevice");
    assert.deepEqual(result, { statusCode: 200, statusText: "OK", data: { ok: true } });
    assert.equal(apiCalls, 2);
  } finally {
    global.fetch = originalFetch;
  }
});

test("login deduplicates concurrent calls into single fetch", async () => {
  process.env.EVON_HOST = "http://example.com";
  process.env.EVON_USERNAME = "user";
  process.env.EVON_PASSWORD = "pass";

  const originalFetch = global.fetch;
  let loginCalls = 0;
  global.fetch = async () => {
    loginCalls += 1;
    // Small delay to simulate network latency
    await new Promise((r) => setTimeout(r, 10));
    return new Response("", {
      status: 200,
      headers: { "x-elocs-token": "dedup-token" },
    });
  };

  try {
    const { login } = await importFresh(API_CLIENT_URL);
    // Fire 3 concurrent login calls
    const [t1, t2, t3] = await Promise.all([login(), login(), login()]);
    assert.equal(t1, "dedup-token");
    assert.equal(t2, "dedup-token");
    assert.equal(t3, "dedup-token");
    // Only one actual fetch should have been made
    assert.equal(loginCalls, 1);
  } finally {
    global.fetch = originalFetch;
  }
});

test("apiRequest throws on invalid JSON response", async () => {
  process.env.EVON_HOST = "http://example.com";
  process.env.EVON_USERNAME = "user";
  process.env.EVON_PASSWORD = "pass";

  const originalFetch = global.fetch;
  global.fetch = async (url) => {
    if (url.endsWith("/login")) {
      return new Response("", {
        status: 200,
        headers: { "x-elocs-token": "token-json" },
      });
    }
    // Return non-JSON response
    return new Response("not json", { status: 200 });
  };

  try {
    const { apiRequest } = await importFresh(API_CLIENT_URL);
    await assert.rejects(
      () => apiRequest("/bad-endpoint"),
      (err) => {
        assert.ok(err.message.includes("Invalid JSON response"));
        assert.ok(err.message.includes("/bad-endpoint"));
        return true;
      }
    );
  } finally {
    global.fetch = originalFetch;
  }
});

test("callMethod wraps error with instance and method context", async () => {
  process.env.EVON_HOST = "http://example.com";
  process.env.EVON_USERNAME = "user";
  process.env.EVON_PASSWORD = "pass";

  const originalFetch = global.fetch;
  global.fetch = async (url) => {
    if (url.endsWith("/login")) {
      return new Response("", {
        status: 200,
        headers: { "x-elocs-token": "token-err" },
      });
    }
    return new Response("", { status: 500 });
  };

  try {
    const { callMethod } = await importFresh(API_CLIENT_URL);
    await assert.rejects(
      () => callMethod("SC1_M01.Light1", "SwitchOn", []),
      (err) => {
        assert.ok(err.message.includes("SwitchOn"));
        assert.ok(err.message.includes("SC1_M01.Light1"));
        return true;
      }
    );
  } finally {
    global.fetch = originalFetch;
  }
});
