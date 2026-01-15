#!/usr/bin/env node

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";
import { createHash } from "crypto";

// =============================================================================
// Types
// =============================================================================

interface EvonInstance {
  ID: string;
  ClassName: string;
  Name: string;
  Group: string;
}

interface ApiResponse<T> {
  statusCode: number;
  statusText: string;
  data: T;
}

interface LightState {
  IsOn?: boolean;
  ScaledBrightness?: number;
  Name?: string;
}

interface BlindState {
  Position?: number;
  Angle?: number;
  Name?: string;
  IsMoving?: boolean;
}

interface ClimateState {
  Name?: string;
  SetTemperature?: number;
  ActualTemperature?: number;
}

// =============================================================================
// Constants
// =============================================================================

const DEVICE_CLASSES = {
  LIGHT: "SmartCOM.Light.LightDim",
  BLIND: "SmartCOM.Blind.Blind",
  CLIMATE: "SmartCOM.Clima.ClimateControl",
  CLIMATE_UNIVERSAL: "ClimateControlUniversal",
} as const;

// =============================================================================
// Password Encoding
// =============================================================================

/**
 * Encode password for Evon API.
 * The x-elocs-password is computed as: Base64(SHA512(username + password))
 */
function encodePassword(username: string, password: string): string {
  const combined = username + password;
  return createHash("sha512").update(combined, "utf8").digest("base64");
}

/**
 * Check if a password looks like it's already encoded.
 * Encoded passwords are Base64-encoded SHA512 hashes (88 chars, ends with ==).
 */
function isPasswordEncoded(password: string): boolean {
  return password.length === 88 && password.endsWith("==");
}

// =============================================================================
// Configuration
// =============================================================================

const EVON_HOST = process.env.EVON_HOST || "http://192.168.1.4";
const EVON_USERNAME = process.env.EVON_USERNAME || "";
const EVON_PASSWORD_RAW = process.env.EVON_PASSWORD || "";

const EVON_PASSWORD = isPasswordEncoded(EVON_PASSWORD_RAW)
  ? EVON_PASSWORD_RAW
  : encodePassword(EVON_USERNAME, EVON_PASSWORD_RAW);

// =============================================================================
// API Client
// =============================================================================

let currentToken: string | null = null;
let tokenExpiry: number = 0;

async function login(): Promise<string> {
  if (currentToken && Date.now() < tokenExpiry - 60000) {
    return currentToken;
  }

  const response = await fetch(`${EVON_HOST}/login`, {
    method: "POST",
    headers: {
      "x-elocs-username": EVON_USERNAME,
      "x-elocs-password": EVON_PASSWORD,
    },
  });

  if (!response.ok) {
    throw new Error(`Login failed: ${response.status} ${response.statusText}`);
  }

  const token = response.headers.get("x-elocs-token");
  if (!token) {
    throw new Error("No token received from login");
  }

  currentToken = token;
  tokenExpiry = Date.now() + 27 * 24 * 60 * 60 * 1000; // 27 days

  return token;
}

async function apiRequest<T>(
  endpoint: string,
  method: "GET" | "POST" = "GET",
  body?: unknown
): Promise<ApiResponse<T>> {
  const token = await login();

  const fetchOptions: RequestInit = {
    method,
    headers: {
      Cookie: `token=${token}`,
      "Content-Type": "application/json",
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  };

  let response = await fetch(`${EVON_HOST}/api${endpoint}`, fetchOptions);

  // Handle token expiry with retry
  if (response.status === 302 || response.status === 401) {
    currentToken = null;
    const newToken = await login();
    fetchOptions.headers = {
      Cookie: `token=${newToken}`,
      "Content-Type": "application/json",
    };
    response = await fetch(`${EVON_HOST}/api${endpoint}`, fetchOptions);
  }

  if (!response.ok) {
    throw new Error(`API request failed: ${response.status}`);
  }

  return response.json();
}

async function callMethod(
  instanceId: string,
  methodName: string,
  params: unknown[] = []
): Promise<ApiResponse<unknown>> {
  return apiRequest(`/instances/${instanceId}/${methodName}`, "POST", params);
}

// =============================================================================
// Helper Functions
// =============================================================================

async function getInstances(): Promise<EvonInstance[]> {
  const result = await apiRequest<EvonInstance[]>("/instances");
  return result.data;
}

function filterByClass(instances: EvonInstance[], className: string): EvonInstance[] {
  return instances.filter(
    (i) => i.ClassName === className && i.Name && i.Name.length > 0
  );
}

function filterByClassIncludes(instances: EvonInstance[], classNamePart: string): EvonInstance[] {
  return instances.filter(
    (i) => i.ClassName.includes(classNamePart) && i.Name && i.Name.length > 0
  );
}

async function controlAllDevices(
  devices: EvonInstance[],
  method: string,
  params: unknown[] = []
): Promise<string[]> {
  const results: string[] = [];
  for (const device of devices) {
    try {
      await callMethod(device.ID, method, params);
      results.push(`${device.Name}: success`);
    } catch {
      results.push(`${device.Name}: failed`);
    }
  }
  return results;
}

// =============================================================================
// MCP Server
// =============================================================================

const server = new McpServer({
  name: "evon-smarthome",
  version: "1.0.0",
});

// -----------------------------------------------------------------------------
// Generic Tools
// -----------------------------------------------------------------------------

server.tool(
  "list_apps",
  "List all available apps in the Evon Smart Home system",
  {},
  async () => {
    const result = await apiRequest<Array<{ fullName: string; displayName?: string; autoStart: boolean }>>("/apps");
    return {
      content: [{ type: "text", text: JSON.stringify(result.data, null, 2) }],
    };
  }
);

server.tool(
  "list_instances",
  "List all instances (devices, sensors, logic blocks) in the system",
  {
    filter: z
      .string()
      .optional()
      .describe("Filter instances by class name or device name"),
  },
  async ({ filter }) => {
    let instances = await getInstances();

    if (filter) {
      const lowerFilter = filter.toLowerCase();
      instances = instances.filter(
        (i) =>
          i.ClassName.toLowerCase().includes(lowerFilter) ||
          i.Name.toLowerCase().includes(lowerFilter)
      );
    }

    return {
      content: [{ type: "text", text: JSON.stringify(instances, null, 2) }],
    };
  }
);

server.tool(
  "get_instance",
  "Get detailed information about a specific instance",
  {
    instance_id: z.string().describe("The instance ID (e.g., 'SC1_M01.Light1')"),
  },
  async ({ instance_id }) => {
    const result = await apiRequest<Record<string, unknown>>(`/instances/${instance_id}`);
    return {
      content: [{ type: "text", text: JSON.stringify(result.data, null, 2) }],
    };
  }
);

server.tool(
  "get_property",
  "Get a specific property value of an instance",
  {
    instance_id: z.string().describe("The instance ID"),
    property: z.string().describe("The property name (e.g., 'IsOn', 'ScaledBrightness', 'Position')"),
  },
  async ({ instance_id, property }) => {
    const result = await apiRequest<unknown>(`/instances/${instance_id}/${property}`);
    return {
      content: [{ type: "text", text: JSON.stringify(result.data, null, 2) }],
    };
  }
);

server.tool(
  "call_method",
  "Call a method on an instance. Use specific tools (light_control, blind_control, climate_control) for common operations.",
  {
    instance_id: z.string().describe("The instance ID"),
    method: z.string().describe("The method name"),
    params: z.array(z.unknown()).optional().describe("Parameters as an array"),
  },
  async ({ instance_id, method, params }) => {
    const result = await callMethod(instance_id, method, params);
    return {
      content: [{ type: "text", text: `Method ${method} called on ${instance_id}: ${result.statusText}` }],
    };
  }
);

// -----------------------------------------------------------------------------
// Light Tools
// -----------------------------------------------------------------------------

server.tool(
  "list_lights",
  "List all lights with their current state",
  {},
  async () => {
    const instances = await getInstances();
    const lights = filterByClass(instances, DEVICE_CLASSES.LIGHT);

    const lightsWithState = await Promise.all(
      lights.map(async (light) => {
        try {
          const details = await apiRequest<LightState>(`/instances/${light.ID}`);
          return {
            id: light.ID,
            name: details.data.Name || light.Name,
            isOn: details.data.IsOn ?? false,
            brightness: details.data.ScaledBrightness ?? 0,
          };
        } catch {
          return { id: light.ID, name: light.Name, isOn: false, brightness: 0 };
        }
      })
    );

    return {
      content: [{ type: "text", text: JSON.stringify(lightsWithState, null, 2) }],
    };
  }
);

server.tool(
  "light_control",
  "Control a light (turn on, off, toggle, or set brightness)",
  {
    light_id: z.string().describe("The light instance ID"),
    action: z.enum(["on", "off", "toggle", "brightness"]).describe("Action to perform"),
    brightness: z.number().min(0).max(100).optional().describe("Brightness level (0-100)"),
  },
  async ({ light_id, action, brightness }) => {
    let method: string;
    let params: unknown[] = [];

    switch (action) {
      case "on":
        method = "AmznTurnOn";
        break;
      case "off":
        method = "AmznTurnOff";
        break;
      case "toggle":
        const state = await apiRequest<LightState>(`/instances/${light_id}`);
        method = state.data.IsOn ? "AmznTurnOff" : "AmznTurnOn";
        break;
      case "brightness":
        method = "AmznSetBrightness";
        params = [brightness ?? 50];
        break;
    }

    await callMethod(light_id, method, params);
    return {
      content: [{ type: "text", text: `Light ${light_id}: ${action}${brightness !== undefined ? ` (${brightness}%)` : ""}` }],
    };
  }
);

server.tool(
  "light_control_all",
  "Control all lights at once",
  {
    action: z.enum(["on", "off"]).describe("Turn all lights on or off"),
  },
  async ({ action }) => {
    const instances = await getInstances();
    const lights = filterByClass(instances, DEVICE_CLASSES.LIGHT);
    const method = action === "off" ? "AmznTurnOff" : "AmznTurnOn";
    const results = await controlAllDevices(lights, method);

    return {
      content: [{ type: "text", text: `Turned ${action} ${lights.length} lights:\n${results.join("\n")}` }],
    };
  }
);

// -----------------------------------------------------------------------------
// Blind Tools
// -----------------------------------------------------------------------------

server.tool(
  "list_blinds",
  "List all blinds/shutters with their current state",
  {},
  async () => {
    const instances = await getInstances();
    const blinds = filterByClass(instances, DEVICE_CLASSES.BLIND);

    const blindsWithState = await Promise.all(
      blinds.map(async (blind) => {
        try {
          const details = await apiRequest<BlindState>(`/instances/${blind.ID}`);
          return {
            id: blind.ID,
            name: details.data.Name || blind.Name,
            position: details.data.Position ?? 0,
            angle: details.data.Angle ?? 0,
            isMoving: details.data.IsMoving ?? false,
          };
        } catch {
          return { id: blind.ID, name: blind.Name, position: 0, angle: 0, isMoving: false };
        }
      })
    );

    return {
      content: [{ type: "text", text: JSON.stringify(blindsWithState, null, 2) }],
    };
  }
);

server.tool(
  "blind_control",
  "Control a blind/shutter (move up, down, stop, set position, or set tilt angle)",
  {
    blind_id: z.string().describe("The blind instance ID"),
    action: z.enum(["up", "down", "stop", "position", "angle"]).describe("Action to perform"),
    position: z.number().min(0).max(100).optional().describe("Position (0=open, 100=closed)"),
    angle: z.number().min(0).max(100).optional().describe("Slat angle (0-100)"),
  },
  async ({ blind_id, action, position, angle }) => {
    const methodMap: Record<string, { method: string; params: unknown[] }> = {
      up: { method: "MoveUp", params: [] },
      down: { method: "MoveDown", params: [] },
      stop: { method: "Stop", params: [] },
      position: { method: "AmznSetPercentage", params: [position ?? 50] },
      angle: { method: "SetAngle", params: [angle ?? 50] },
    };

    const { method, params } = methodMap[action];
    await callMethod(blind_id, method, params);

    return {
      content: [{ type: "text", text: `Blind ${blind_id}: ${action}${params.length > 0 ? ` (${params[0]})` : ""}` }],
    };
  }
);

server.tool(
  "blind_control_all",
  "Control all blinds at once",
  {
    action: z.enum(["up", "down", "stop", "position", "angle"]).describe("Action to perform"),
    position: z.number().min(0).max(100).optional().describe("Position (0=open, 100=closed)"),
    angle: z.number().min(0).max(100).optional().describe("Slat angle (0-100)"),
  },
  async ({ action, position, angle }) => {
    const instances = await getInstances();
    const blinds = filterByClass(instances, DEVICE_CLASSES.BLIND);

    const methodMap: Record<string, { method: string; params: unknown[] }> = {
      up: { method: "MoveUp", params: [] },
      down: { method: "MoveDown", params: [] },
      stop: { method: "Stop", params: [] },
      position: { method: "AmznSetPercentage", params: [position ?? 50] },
      angle: { method: "SetAngle", params: [angle ?? 50] },
    };

    const { method, params } = methodMap[action];
    const results = await controlAllDevices(blinds, method, params);

    return {
      content: [{ type: "text", text: `Set ${blinds.length} blinds to ${action}${params.length > 0 ? ` (${params[0]})` : ""}:\n${results.join("\n")}` }],
    };
  }
);

// -----------------------------------------------------------------------------
// Climate Tools
// -----------------------------------------------------------------------------

server.tool(
  "list_climate",
  "List all climate controls with their current state",
  {},
  async () => {
    const instances = await getInstances();
    const climates = instances.filter(
      (i) =>
        (i.ClassName === DEVICE_CLASSES.CLIMATE ||
          i.ClassName.includes(DEVICE_CLASSES.CLIMATE_UNIVERSAL)) &&
        i.Name &&
        i.Name.length > 0
    );

    const climatesWithState = await Promise.all(
      climates.map(async (climate) => {
        try {
          const details = await apiRequest<ClimateState>(`/instances/${climate.ID}`);
          return {
            id: climate.ID,
            name: details.data.Name || climate.Name,
            setTemperature: details.data.SetTemperature ?? 0,
            actualTemperature: details.data.ActualTemperature ?? 0,
          };
        } catch {
          return { id: climate.ID, name: climate.Name, setTemperature: 0, actualTemperature: 0 };
        }
      })
    );

    return {
      content: [{ type: "text", text: JSON.stringify(climatesWithState, null, 2) }],
    };
  }
);

server.tool(
  "climate_control",
  "Control climate/heating for a room",
  {
    climate_id: z.string().describe("The climate control instance ID"),
    action: z.enum(["comfort", "energy_saving", "freeze_protection", "set_temperature"]).describe("Action to perform"),
    temperature: z.number().optional().describe("Target temperature (for set_temperature action)"),
  },
  async ({ climate_id, action, temperature }) => {
    const methodMap: Record<string, { method: string; params: unknown[] }> = {
      comfort: { method: "WriteDayMode", params: [] },
      energy_saving: { method: "WriteNightMode", params: [] },
      freeze_protection: { method: "WriteFreezeMode", params: [] },
      set_temperature: { method: "WriteCurrentSetTemperature", params: [temperature ?? 21] },
    };

    const { method, params } = methodMap[action];
    await callMethod(climate_id, method, params);

    return {
      content: [{ type: "text", text: `Climate ${climate_id}: ${action}${params.length > 0 ? ` (${params[0]}°C)` : ""}` }],
    };
  }
);

server.tool(
  "climate_control_all",
  "Set climate mode for all rooms at once",
  {
    action: z.enum(["comfort", "energy_saving", "freeze_protection"]).describe("Climate mode to set"),
  },
  async ({ action }) => {
    const instances = await getInstances();
    const climates = instances.filter(
      (i) =>
        (i.ClassName === DEVICE_CLASSES.CLIMATE ||
          i.ClassName.includes(DEVICE_CLASSES.CLIMATE_UNIVERSAL)) &&
        i.Name &&
        i.Name.length > 0
    );

    const methodMap: Record<string, string> = {
      comfort: "WriteDayMode",
      energy_saving: "WriteNightMode",
      freeze_protection: "WriteFreezeMode",
    };

    const results = await controlAllDevices(climates, methodMap[action]);

    return {
      content: [{ type: "text", text: `Set ${climates.length} rooms to ${action}:\n${results.join("\n")}` }],
    };
  }
);

// =============================================================================
// MCP Resources
// =============================================================================

// Resource: All lights state
server.resource(
  "evon://lights",
  "All Evon lights with current state",
  async () => {
    const instances = await getInstances();
    const lights = filterByClass(instances, DEVICE_CLASSES.LIGHT);

    const lightsWithState = await Promise.all(
      lights.map(async (light) => {
        try {
          const details = await apiRequest<LightState>(`/instances/${light.ID}`);
          return {
            id: light.ID,
            name: details.data.Name || light.Name,
            isOn: details.data.IsOn ?? false,
            brightness: details.data.ScaledBrightness ?? 0,
          };
        } catch {
          return { id: light.ID, name: light.Name, isOn: false, brightness: 0 };
        }
      })
    );

    return {
      contents: [{
        uri: "evon://lights",
        mimeType: "application/json",
        text: JSON.stringify(lightsWithState, null, 2),
      }],
    };
  }
);

// Resource: All blinds state
server.resource(
  "evon://blinds",
  "All Evon blinds with current state",
  async () => {
    const instances = await getInstances();
    const blinds = filterByClass(instances, DEVICE_CLASSES.BLIND);

    const blindsWithState = await Promise.all(
      blinds.map(async (blind) => {
        try {
          const details = await apiRequest<BlindState>(`/instances/${blind.ID}`);
          return {
            id: blind.ID,
            name: details.data.Name || blind.Name,
            position: details.data.Position ?? 0,
            angle: details.data.Angle ?? 0,
            isMoving: details.data.IsMoving ?? false,
          };
        } catch {
          return { id: blind.ID, name: blind.Name, position: 0, angle: 0, isMoving: false };
        }
      })
    );

    return {
      contents: [{
        uri: "evon://blinds",
        mimeType: "application/json",
        text: JSON.stringify(blindsWithState, null, 2),
      }],
    };
  }
);

// Resource: All climate controls state
server.resource(
  "evon://climate",
  "All Evon climate controls with current state",
  async () => {
    const instances = await getInstances();
    const climates = instances.filter(
      (i) =>
        (i.ClassName === DEVICE_CLASSES.CLIMATE ||
          i.ClassName.includes(DEVICE_CLASSES.CLIMATE_UNIVERSAL)) &&
        i.Name &&
        i.Name.length > 0
    );

    const climatesWithState = await Promise.all(
      climates.map(async (climate) => {
        try {
          const details = await apiRequest<ClimateState>(`/instances/${climate.ID}`);
          return {
            id: climate.ID,
            name: details.data.Name || climate.Name,
            setTemperature: details.data.SetTemperature ?? 0,
            actualTemperature: details.data.ActualTemperature ?? 0,
          };
        } catch {
          return { id: climate.ID, name: climate.Name, setTemperature: 0, actualTemperature: 0 };
        }
      })
    );

    return {
      contents: [{
        uri: "evon://climate",
        mimeType: "application/json",
        text: JSON.stringify(climatesWithState, null, 2),
      }],
    };
  }
);

// Resource: Home summary
server.resource(
  "evon://summary",
  "Summary of all Evon devices and their current state",
  async () => {
    const instances = await getInstances();
    const lights = filterByClass(instances, DEVICE_CLASSES.LIGHT);
    const blinds = filterByClass(instances, DEVICE_CLASSES.BLIND);
    const climates = instances.filter(
      (i) =>
        (i.ClassName === DEVICE_CLASSES.CLIMATE ||
          i.ClassName.includes(DEVICE_CLASSES.CLIMATE_UNIVERSAL)) &&
        i.Name &&
        i.Name.length > 0
    );

    // Count on lights
    let lightsOn = 0;
    for (const light of lights) {
      try {
        const details = await apiRequest<LightState>(`/instances/${light.ID}`);
        if (details.data.IsOn) lightsOn++;
      } catch {}
    }

    // Count open blinds
    let blindsOpen = 0;
    for (const blind of blinds) {
      try {
        const details = await apiRequest<BlindState>(`/instances/${blind.ID}`);
        if ((details.data.Position ?? 0) < 50) blindsOpen++;
      } catch {}
    }

    // Get average temperature
    let totalTemp = 0;
    let tempCount = 0;
    for (const climate of climates) {
      try {
        const details = await apiRequest<ClimateState>(`/instances/${climate.ID}`);
        if (details.data.ActualTemperature) {
          totalTemp += details.data.ActualTemperature;
          tempCount++;
        }
      } catch {}
    }

    const summary = {
      lights: { total: lights.length, on: lightsOn },
      blinds: { total: blinds.length, open: blindsOpen },
      climate: {
        total: climates.length,
        averageTemperature: tempCount > 0 ? Math.round((totalTemp / tempCount) * 10) / 10 : null,
      },
    };

    return {
      contents: [{
        uri: "evon://summary",
        mimeType: "application/json",
        text: JSON.stringify(summary, null, 2),
      }],
    };
  }
);

// -----------------------------------------------------------------------------
// Sensor Tools
// -----------------------------------------------------------------------------

server.tool(
  "list_sensors",
  "List sensors (temperature, humidity, motion, etc.)",
  {
    type: z.string().optional().describe("Filter by sensor type"),
  },
  async ({ type }) => {
    const instances = await getInstances();
    let sensors = instances.filter(
      (i) =>
        i.ClassName.includes("Sensor") ||
        i.ClassName.includes("Detector") ||
        i.ClassName.includes("Temperature") ||
        i.ClassName.includes("Humidity")
    );

    if (type) {
      const lowerType = type.toLowerCase();
      sensors = sensors.filter(
        (s) =>
          s.ClassName.toLowerCase().includes(lowerType) ||
          s.Name.toLowerCase().includes(lowerType)
      );
    }

    return {
      content: [{ type: "text", text: JSON.stringify(sensors, null, 2) }],
    };
  }
);

// =============================================================================
// Main
// =============================================================================

async function main() {
  if (!EVON_USERNAME || !EVON_PASSWORD) {
    console.error("Error: EVON_USERNAME and EVON_PASSWORD environment variables must be set");
    process.exit(1);
  }

  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error("Evon Smart Home MCP server running on stdio");
}

main().catch(console.error);
