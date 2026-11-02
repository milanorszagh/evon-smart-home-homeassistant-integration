// Input validation used by the MCP tools before IDs reach URLs and control calls.
import test from "node:test";
import assert from "node:assert/strict";

const HELPERS_URL = new URL("../dist/helpers.js", import.meta.url);

test("sanitizeId accepts real Evon IDs", async () => {
  const { sanitizeId } = await import(HELPERS_URL);
  for (const id of ["SC1_M01.Light3", "Intercom2N1000.Cam", "BathroomRadiator9506", "Base.ehThermostat", "a-b_c.D9"]) {
    assert.equal(sanitizeId(id), id);
  }
});

test("sanitizeId rejects traversal and URL metacharacters", async () => {
  const { sanitizeId } = await import(HELPERS_URL);
  for (const id of ["", ".", "..", "...", "a..b", ".a", "a.", "../apps", "a/b", "a%2e", "a?b", "a#b", "a b", "x".repeat(129)]) {
    assert.throws(() => sanitizeId(id), /Invalid instance ID/, `expected ${JSON.stringify(id)} to be rejected`);
  }
});

test("deviceKindOf maps controllable classes and nothing else", async () => {
  const { deviceKindOf } = await import(HELPERS_URL);
  assert.equal(deviceKindOf("SmartCOM.Light.LightDim"), "light");
  assert.equal(deviceKindOf("SmartCOM.Light.Light"), "light");
  assert.equal(deviceKindOf("SmartCOM.Blind.BlindGroup"), "blind");
  assert.equal(deviceKindOf("Heating.ClimateControlUniversal"), "climate");
  assert.equal(deviceKindOf("Heating.BathroomRadiator"), "radiator");
  for (const cls of ["Base.bSwitch", "Security.Intercom.2N.Intercom2N", "Security.Door", "System.HomeState", "Logic.Timer"]) {
    assert.equal(deviceKindOf(cls), null, cls);
  }
});

test("requireDevice refuses door relays, wrong kinds, templates and unknown IDs", async () => {
  process.env.EVON_HOST = "http://example.com";
  process.env.EVON_USERNAME = "user";
  process.env.EVON_PASSWORD = "pass";
  const instances = [
    { ID: "SC1_M01.Light3", ClassName: "SmartCOM.Light.LightDim", Name: "Kitchen", Group: "" },
    { ID: "Intercom2N1000.DoorSwitch", ClassName: "Base.bSwitch", Name: "Door", Group: "" },
    { ID: "SmartCOM.Light.LightDim", ClassName: "SmartCOM.Light.LightDim", Name: "", Group: "" },
  ];
  const originalFetch = global.fetch;
  global.fetch = async (url) => {
    if (String(url).endsWith("/login")) {
      return new Response("", { status: 200, headers: { "x-elocs-token": "t" } });
    }
    return new Response(JSON.stringify({ statusCode: 200, statusText: "OK", data: instances }), {
      status: 200,
      headers: { "content-type": "application/json" },
    });
  };
  try {
    const { requireDevice } = await import(HELPERS_URL + `?v=${Date.now()}`);
    assert.equal((await requireDevice("SC1_M01.Light3", ["light"])).ID, "SC1_M01.Light3");
    await assert.rejects(requireDevice("Intercom2N1000.DoorSwitch", ["light", "blind", "climate", "radiator"]), /cannot be controlled/);
    await assert.rejects(requireDevice("SC1_M01.Light3", ["radiator"]), /cannot be controlled/);
    await assert.rejects(requireDevice("SmartCOM.Light.LightDim", ["light"]), /Unknown instance/);
    await assert.rejects(requireDevice("Nope", ["light"]), /Unknown instance/);
    await assert.rejects(requireDevice("..", ["light"]), /Invalid instance ID/);
  } finally {
    global.fetch = originalFetch;
  }
});
