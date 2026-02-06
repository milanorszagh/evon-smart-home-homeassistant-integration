import test from "node:test";
import assert from "node:assert/strict";

const TOOLS_URL = new URL("../dist/tools/index.js", import.meta.url);
const RESOURCES_URL = new URL("../dist/resources/index.js", import.meta.url);

async function importFresh(url) {
  const href = url.href + `?v=${Date.now()}-${Math.random()}`;
  return import(href);
}

class FakeServer {
  constructor() {
    this.tools = new Map();
    this.resources = new Map();
  }

  tool(name, description, schema, handler) {
    this.tools.set(name, { description, schema, handler });
  }

  resource(uri, description, handler) {
    this.resources.set(uri, { description, handler });
  }
}

const EXPECTED_TOOLS = [
  "bathroom_radiator_control",
  "blind_control",
  "blind_control_all",
  "call_method",
  "climate_control",
  "climate_control_all",
  "get_instance",
  "get_property",
  "light_control",
  "light_control_all",
  "list_apps",
  "list_bathroom_radiators",
  "list_blinds",
  "list_climate",
  "list_home_states",
  "list_instances",
  "list_lights",
  "list_sensors",
  "set_home_state",
];

const EXPECTED_RESOURCES = [
  "evon://bathroom_radiators",
  "evon://blinds",
  "evon://climate",
  "evon://home_state",
  "evon://lights",
  "evon://summary",
];

test("registerAllTools registers expected tool names", async () => {
  const { registerAllTools } = await importFresh(TOOLS_URL);
  const server = new FakeServer();
  registerAllTools(server);

  for (const name of EXPECTED_TOOLS) {
    assert.ok(server.tools.has(name), `missing tool: ${name}`);
  }

  assert.ok(server.tools.size >= EXPECTED_TOOLS.length);
});

test("registerAllResources registers expected resource URIs", async () => {
  const { registerAllResources } = await importFresh(RESOURCES_URL);
  const server = new FakeServer();
  registerAllResources(server);

  for (const uri of EXPECTED_RESOURCES) {
    assert.ok(server.resources.has(uri), `missing resource: ${uri}`);
  }

  assert.ok(server.resources.size >= EXPECTED_RESOURCES.length);
});
