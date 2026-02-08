/**
 * Light control tools for Evon Smart Home MCP Server
 */

import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import { apiRequest, callMethod } from "../api-client.js";
import { DEVICE_CLASSES } from "../constants.js";
import { getInstances, filterByClass, controlAllDevices, fetchLightsWithState, sanitizeId } from "../helpers.js";
import type { LightState } from "../types.js";

export function registerLightTools(server: McpServer): void {
  server.tool(
    "list_lights",
    "List all lights with their current state",
    {},
    async () => {
      const lightsWithState = await fetchLightsWithState();
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
      const id = sanitizeId(light_id);
      let method: string;
      let params: unknown[] = [];

      switch (action) {
        case "on":
          method = "AmznTurnOn";
          break;
        case "off":
          method = "AmznTurnOff";
          break;
        case "toggle": {
          const state = await apiRequest<LightState>(`/instances/${id}`);
          method = state.data.IsOn ? "AmznTurnOff" : "AmznTurnOn";
          break;
        }
        case "brightness":
          method = "AmznSetBrightness";
          params = [brightness ?? 50];
          break;
        default:
          throw new Error(`Unknown light action: ${action as string}`);
      }

      await callMethod(id, method, params);
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
}
