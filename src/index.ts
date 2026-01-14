#!/usr/bin/env node

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";

// Configuration from environment
const EVON_HOST = process.env.EVON_HOST || "http://192.168.1.4";
const EVON_USERNAME = process.env.EVON_USERNAME || "";
const EVON_PASSWORD = process.env.EVON_PASSWORD || "";

// Token management
let currentToken: string | null = null;
let tokenExpiry: number = 0;

async function login(): Promise<string> {
  // Check if we have a valid token
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
  // Token valid for ~28 days, refresh after 27 days
  tokenExpiry = Date.now() + 27 * 24 * 60 * 60 * 1000;

  return token;
}

async function apiRequest(
  endpoint: string,
  method: "GET" | "POST" = "GET",
  body?: unknown
): Promise<unknown> {
  const token = await login();

  const response = await fetch(`${EVON_HOST}/api${endpoint}`, {
    method,
    headers: {
      Cookie: `token=${token}`,
      "Content-Type": "application/json",
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (!response.ok) {
    // Token might be expired, try re-login
    if (response.status === 302 || response.status === 401) {
      currentToken = null;
      const newToken = await login();
      const retryResponse = await fetch(`${EVON_HOST}/api${endpoint}`, {
        method,
        headers: {
          Cookie: `token=${newToken}`,
          "Content-Type": "application/json",
        },
        body: body !== undefined ? JSON.stringify(body) : undefined,
      });
      if (!retryResponse.ok) {
        throw new Error(`API request failed: ${retryResponse.status}`);
      }
      return retryResponse.json();
    }
    throw new Error(`API request failed: ${response.status}`);
  }

  return response.json();
}

// Helper to call instance methods with parameters as JSON array
async function callInstanceMethod(
  instanceId: string,
  methodName: string,
  params?: unknown[]
): Promise<{ statusCode: number; statusText: string }> {
  return apiRequest(
    `/instances/${instanceId}/${methodName}`,
    "POST",
    params ?? []
  ) as Promise<{ statusCode: number; statusText: string }>;
}

// Create MCP Server
const server = new McpServer({
  name: "evon-smarthome",
  version: "1.0.0",
});

// List all apps
server.tool(
  "list_apps",
  "List all available apps in the Evon Smart Home system",
  {},
  async () => {
    const result = (await apiRequest("/apps")) as {
      statusCode: number;
      data: Array<{ fullName: string; displayName?: string; autoStart: boolean }>;
    };
    return {
      content: [{ type: "text", text: JSON.stringify(result.data, null, 2) }],
    };
  }
);

// List all instances
server.tool(
  "list_instances",
  "List all instances (devices, sensors, logic blocks) in the system",
  {
    filter: z
      .string()
      .optional()
      .describe("Filter instances by class name (e.g., 'Light', 'Blind', 'Sensor')"),
  },
  async ({ filter }) => {
    const result = (await apiRequest("/instances")) as {
      statusCode: number;
      data: Array<{ ID: string; ClassName: string; Name: string; Group: string }>;
    };

    let instances = result.data;
    if (filter) {
      instances = instances.filter(
        (i) =>
          i.ClassName.toLowerCase().includes(filter.toLowerCase()) ||
          i.Name.toLowerCase().includes(filter.toLowerCase())
      );
    }

    return {
      content: [{ type: "text", text: JSON.stringify(instances, null, 2) }],
    };
  }
);

// Get instance details
server.tool(
  "get_instance",
  "Get detailed information about a specific instance",
  {
    instance_id: z.string().describe("The instance ID (e.g., 'SC1_M01.Light1')"),
  },
  async ({ instance_id }) => {
    const result = (await apiRequest(`/instances/${instance_id}`)) as {
      statusCode: number;
      data: Record<string, unknown>;
    };
    return {
      content: [{ type: "text", text: JSON.stringify(result.data, null, 2) }],
    };
  }
);

// Get instance property
server.tool(
  "get_property",
  "Get a specific property value of an instance",
  {
    instance_id: z.string().describe("The instance ID"),
    property: z.string().describe("The property name (e.g., 'IsOn', 'Brightness', 'Position')"),
  },
  async ({ instance_id, property }) => {
    const result = (await apiRequest(`/instances/${instance_id}/${property}`)) as {
      statusCode: number;
      data: unknown;
    };
    return {
      content: [{ type: "text", text: JSON.stringify(result.data, null, 2) }],
    };
  }
);

// Call instance method
server.tool(
  "call_method",
  "Call a method on an instance (e.g., turn on/off lights, move blinds). Parameters must be passed as an array in the correct order.",
  {
    instance_id: z.string().describe("The instance ID"),
    method: z.string().describe("The method name (e.g., 'AmznTurnOn', 'AmznTurnOff', 'BrightnessSetInternal', 'MoveUp', 'MoveDown', 'Stop')"),
    params: z.array(z.unknown()).optional().describe("Optional parameters for the method as an array (e.g., [50] for brightness)"),
  },
  async ({ instance_id, method, params }) => {
    const result = await callInstanceMethod(instance_id, method, params);

    return {
      content: [
        {
          type: "text",
          text: `Method ${method} called on ${instance_id}: ${result.statusText}`,
        },
      ],
    };
  }
);

// Light control
server.tool(
  "light_control",
  "Control a light (turn on, off, toggle, set brightness)",
  {
    light_id: z.string().describe("The light instance ID"),
    action: z
      .enum(["on", "off", "toggle", "brightness"])
      .describe("Action to perform"),
    brightness: z
      .number()
      .min(0)
      .max(100)
      .optional()
      .describe("Brightness level (0-100), required for 'brightness' action"),
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
        // Toggle by checking current state and switching
        const stateResult = (await apiRequest(`/instances/${light_id}`)) as {
          data: { IsOn?: boolean };
        };
        method = stateResult.data.IsOn ? "AmznTurnOff" : "AmznTurnOn";
        break;
      case "brightness":
        method = "AmznSetBrightness";
        params = [brightness ?? 50];
        break;
    }

    const result = await callInstanceMethod(light_id, method, params);

    return {
      content: [
        {
          type: "text",
          text: `Light ${light_id}: ${action} - ${result.statusText}`,
        },
      ],
    };
  }
);

// Light control for all lights
server.tool(
  "light_control_all",
  "Control all lights at once (turn off all, or turn on all)",
  {
    action: z
      .enum(["off", "on"])
      .describe("Action: 'off' to turn all lights off, 'on' to turn all lights on"),
  },
  async ({ action }) => {
    // Get all light instances
    const result = (await apiRequest("/instances")) as {
      statusCode: number;
      data: Array<{ ID: string; ClassName: string; Name: string }>;
    };

    // Filter to actual dimmable lights with names
    const lights = result.data.filter(
      (i) =>
        i.ClassName === "SmartCOM.Light.LightDim" &&
        i.Name &&
        i.Name.length > 0
    );

    const method = action === "off" ? "AmznTurnOff" : "AmznTurnOn";

    // Apply to all lights
    const results: string[] = [];
    for (const light of lights) {
      try {
        await callInstanceMethod(light.ID, method, []);
        results.push(`${light.Name}: success`);
      } catch (err) {
        results.push(`${light.Name}: failed`);
      }
    }

    return {
      content: [
        {
          type: "text",
          text: `Turned ${action} ${lights.length} lights:\n${results.join("\n")}`,
        },
      ],
    };
  }
);

// Blind control
server.tool(
  "blind_control",
  "Control a blind/shutter (move up, down, stop, set position, set angle/tilt)",
  {
    blind_id: z.string().describe("The blind instance ID"),
    action: z
      .enum(["up", "down", "stop", "position", "angle"])
      .describe("Action to perform"),
    position: z
      .number()
      .min(0)
      .max(100)
      .optional()
      .describe("Position (0=open, 100=closed), required for 'position' action"),
    angle: z
      .number()
      .min(0)
      .max(100)
      .optional()
      .describe("Slat angle (0-100), required for 'angle' action"),
  },
  async ({ blind_id, action, position, angle }) => {
    let method: string;
    let params: unknown[] = [];

    switch (action) {
      case "up":
        method = "MoveUp";
        break;
      case "down":
        method = "MoveDown";
        break;
      case "stop":
        method = "Stop";
        break;
      case "position":
        method = "AmznSetPercentage";
        params = [position ?? 50];
        break;
      case "angle":
        method = "SetAngle";
        params = [angle ?? 50];
        break;
    }

    const result = await callInstanceMethod(blind_id, method, params);

    return {
      content: [
        {
          type: "text",
          text: `Blind ${blind_id}: ${action} - ${result.statusText}`,
        },
      ],
    };
  }
);

// Blind control for all blinds
server.tool(
  "blind_control_all",
  "Control all blinds at once (set position or angle)",
  {
    action: z
      .enum(["up", "down", "stop", "position", "angle"])
      .describe("Action: 'up', 'down', 'stop', 'position' (set all to same position), or 'angle' (set all to same angle)"),
    position: z
      .number()
      .min(0)
      .max(100)
      .optional()
      .describe("Position (0=open, 100=closed), required for 'position' action"),
    angle: z
      .number()
      .min(0)
      .max(100)
      .optional()
      .describe("Slat angle (0-100), required for 'angle' action"),
  },
  async ({ action, position, angle }) => {
    // Get all blind instances
    const result = (await apiRequest("/instances")) as {
      statusCode: number;
      data: Array<{ ID: string; ClassName: string; Name: string }>;
    };

    // Filter to actual blinds with names
    const blinds = result.data.filter(
      (i) =>
        i.ClassName === "SmartCOM.Blind.Blind" &&
        i.Name &&
        i.Name.length > 0
    );

    let method: string;
    let params: unknown[] = [];

    switch (action) {
      case "up":
        method = "MoveUp";
        break;
      case "down":
        method = "MoveDown";
        break;
      case "stop":
        method = "Stop";
        break;
      case "position":
        method = "AmznSetPercentage";
        params = [position ?? 50];
        break;
      case "angle":
        method = "SetAngle";
        params = [angle ?? 50];
        break;
    }

    // Apply to all blinds
    const results: string[] = [];
    for (const blind of blinds) {
      try {
        await callInstanceMethod(blind.ID, method, params);
        results.push(`${blind.Name}: success`);
      } catch (err) {
        results.push(`${blind.Name}: failed`);
      }
    }

    return {
      content: [
        {
          type: "text",
          text: `Set ${blinds.length} blinds to ${action}${params.length > 0 ? ` (${params[0]})` : ""}:\n${results.join("\n")}`,
        },
      ],
    };
  }
);

// List lights
server.tool(
  "list_lights",
  "List all lights in the system with their current state",
  {},
  async () => {
    const result = (await apiRequest("/instances")) as {
      statusCode: number;
      data: Array<{ ID: string; ClassName: string; Name: string; Group: string }>;
    };

    const lights = result.data.filter(
      (i) =>
        i.ClassName.includes("Light") &&
        !i.ClassName.includes("LightCOM") &&
        !i.ClassName.includes("StairLight") &&
        !i.ID.includes(".LightCOM")
    );

    // Get detailed info for each light
    const lightsWithState = await Promise.all(
      lights.slice(0, 50).map(async (light) => {
        try {
          const details = (await apiRequest(`/instances/${light.ID}`)) as {
            data: { IsOn?: boolean; ScaledBrightness?: number; Name?: string };
          };
          return {
            id: light.ID,
            name: details.data.Name || light.Name,
            isOn: details.data.IsOn ?? false,
            brightness: details.data.ScaledBrightness ?? 0,
          };
        } catch {
          return {
            id: light.ID,
            name: light.Name,
            isOn: false,
            brightness: 0,
          };
        }
      })
    );

    return {
      content: [{ type: "text", text: JSON.stringify(lightsWithState, null, 2) }],
    };
  }
);

// List blinds
server.tool(
  "list_blinds",
  "List all blinds/shutters in the system with their current state",
  {},
  async () => {
    const result = (await apiRequest("/instances")) as {
      statusCode: number;
      data: Array<{ ID: string; ClassName: string; Name: string; Group: string }>;
    };

    const blinds = result.data.filter(
      (i) =>
        i.ClassName.includes("Blind") &&
        !i.ClassName.includes("BlindGroup") &&
        !i.ID.includes("bBlind") &&
        !i.ID.includes("ehBlind")
    );

    // Get detailed info for each blind
    const blindsWithState = await Promise.all(
      blinds.slice(0, 50).map(async (blind) => {
        try {
          const details = (await apiRequest(`/instances/${blind.ID}`)) as {
            data: { Position?: number; Name?: string; IsMoving?: boolean };
          };
          return {
            id: blind.ID,
            name: details.data.Name || blind.Name,
            position: details.data.Position ?? 0,
            isMoving: details.data.IsMoving ?? false,
          };
        } catch {
          return {
            id: blind.ID,
            name: blind.Name,
            position: 0,
            isMoving: false,
          };
        }
      })
    );

    return {
      content: [{ type: "text", text: JSON.stringify(blindsWithState, null, 2) }],
    };
  }
);

// Get sensors
server.tool(
  "list_sensors",
  "List sensors (temperature, humidity, etc.) with their current values",
  {
    type: z
      .string()
      .optional()
      .describe("Filter by sensor type (e.g., 'Temperature', 'Humidity', 'Motion')"),
  },
  async ({ type }) => {
    const result = (await apiRequest("/instances")) as {
      statusCode: number;
      data: Array<{ ID: string; ClassName: string; Name: string; Group: string }>;
    };

    let sensors = result.data.filter(
      (i) =>
        i.ClassName.includes("Sensor") ||
        i.ClassName.includes("Detector") ||
        i.ClassName.includes("Temperature") ||
        i.ClassName.includes("Humidity")
    );

    if (type) {
      sensors = sensors.filter(
        (s) =>
          s.ClassName.toLowerCase().includes(type.toLowerCase()) ||
          s.Name.toLowerCase().includes(type.toLowerCase())
      );
    }

    return {
      content: [{ type: "text", text: JSON.stringify(sensors, null, 2) }],
    };
  }
);

// List climate controls
server.tool(
  "list_climate",
  "List all climate control (heating/cooling) instances with their current state",
  {},
  async () => {
    const result = (await apiRequest("/instances")) as {
      statusCode: number;
      data: Array<{ ID: string; ClassName: string; Name: string; Group: string }>;
    };

    const climates = result.data.filter(
      (i) =>
        i.ClassName.includes("Climate") ||
        i.ClassName.includes("Thermostat")
    );

    // Get detailed info for each climate control
    const climatesWithState = await Promise.all(
      climates.slice(0, 20).map(async (climate) => {
        try {
          const details = (await apiRequest(`/instances/${climate.ID}`)) as {
            data: {
              Name?: string;
              SetTemperature?: number;
              ActualTemperature?: number;
              Mode?: number;
            };
          };
          return {
            id: climate.ID,
            name: details.data.Name || climate.Name,
            setTemperature: details.data.SetTemperature ?? 0,
            actualTemperature: details.data.ActualTemperature ?? 0,
          };
        } catch {
          return {
            id: climate.ID,
            name: climate.Name,
            setTemperature: 0,
            actualTemperature: 0,
          };
        }
      })
    );

    return {
      content: [{ type: "text", text: JSON.stringify(climatesWithState, null, 2) }],
    };
  }
);

// Climate control
server.tool(
  "climate_control",
  "Control climate/heating for a room (set mode or temperature)",
  {
    climate_id: z.string().describe("The climate control instance ID"),
    action: z
      .enum(["comfort", "energy_saving", "freeze_protection", "set_temperature"])
      .describe("Action: 'comfort' (day mode), 'energy_saving' (night mode), 'freeze_protection', or 'set_temperature'"),
    temperature: z
      .number()
      .optional()
      .describe("Target temperature, required for 'set_temperature' action"),
  },
  async ({ climate_id, action, temperature }) => {
    let method: string;
    let params: unknown[] = [];

    switch (action) {
      case "comfort":
        method = "WriteDayMode";
        break;
      case "energy_saving":
        method = "WriteNightMode";
        break;
      case "freeze_protection":
        method = "WriteFreezeMode";
        break;
      case "set_temperature":
        method = "WriteCurrentSetTemperature";
        params = [temperature ?? 21];
        break;
    }

    const result = await callInstanceMethod(climate_id, method, params);

    return {
      content: [
        {
          type: "text",
          text: `Climate ${climate_id}: ${action} - ${result.statusText}`,
        },
      ],
    };
  }
);

// Climate control for all rooms
server.tool(
  "climate_control_all",
  "Set climate mode for all rooms at once",
  {
    action: z
      .enum(["comfort", "energy_saving", "freeze_protection"])
      .describe("Action: 'comfort' (day mode), 'energy_saving' (night mode), or 'freeze_protection'"),
  },
  async ({ action }) => {
    // Get all climate control instances
    const result = (await apiRequest("/instances")) as {
      statusCode: number;
      data: Array<{ ID: string; ClassName: string; Name: string }>;
    };

    // Filter to actual room climate controls (exclude base classes and templates)
    const climates = result.data.filter(
      (i) =>
        (i.ClassName === "SmartCOM.Clima.ClimateControl" ||
          i.ClassName.includes("ClimateControlUniversal")) &&
        i.Name &&
        i.Name.length > 0
    );

    let method: string;
    switch (action) {
      case "comfort":
        method = "WriteDayMode";
        break;
      case "energy_saving":
        method = "WriteNightMode";
        break;
      case "freeze_protection":
        method = "WriteFreezeMode";
        break;
    }

    // Apply to all climate controls
    const results: string[] = [];
    for (const climate of climates) {
      try {
        await callInstanceMethod(climate.ID, method, []);
        results.push(`${climate.Name}: success`);
      } catch (err) {
        results.push(`${climate.Name}: failed`);
      }
    }

    return {
      content: [
        {
          type: "text",
          text: `Set ${climates.length} rooms to ${action}:\n${results.join("\n")}`,
        },
      ],
    };
  }
);

// Start the server
async function main() {
  if (!EVON_USERNAME || !EVON_PASSWORD) {
    console.error(
      "Error: EVON_USERNAME and EVON_PASSWORD environment variables must be set"
    );
    process.exit(1);
  }

  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error("Evon Smart Home MCP server running on stdio");
}

main().catch(console.error);
