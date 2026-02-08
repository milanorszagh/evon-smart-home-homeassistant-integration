/**
 * Climate control tools for Evon Smart Home MCP Server
 */

import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import { callMethod } from "../api-client.js";
import { CLIMATE_METHODS } from "../constants.js";
import { getInstances, filterClimateDevices, controlAllDevices, fetchClimateWithState, sanitizeId } from "../helpers.js";

export function registerClimateTools(server: McpServer): void {
  server.tool(
    "list_climate",
    "List all climate controls with their current state",
    {},
    async () => {
      const climatesWithState = await fetchClimateWithState();
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
      action: z.enum(["comfort", "eco", "away", "set_temperature"]).describe("Climate action: comfort, eco (energy saving), away (protection), or set_temperature"),
      temperature: z.number().min(5).max(40).optional().describe("Target temperature in °C, 5-40 (for set_temperature action)"),
    },
    async ({ climate_id, action, temperature }) => {
      const id = sanitizeId(climate_id);
      const method = CLIMATE_METHODS[action];
      if (action === "set_temperature" && temperature == null) {
        throw new Error("temperature parameter is required for set_temperature action");
      }
      const params: unknown[] = action === "set_temperature" ? [temperature] : [];

      await callMethod(id, method, params);

      return {
        content: [{ type: "text", text: `Climate ${climate_id}: ${action}${params.length > 0 ? ` (${params[0]}°C)` : ""}` }],
      };
    }
  );

  server.tool(
    "climate_control_all",
    "Set climate mode for all rooms at once",
    {
      action: z.enum(["comfort", "eco", "away"]).describe("Climate mode: comfort, eco (energy saving), or away (protection)"),
    },
    async ({ action }) => {
      const instances = await getInstances();
      const climates = filterClimateDevices(instances);
      const results = await controlAllDevices(climates, CLIMATE_METHODS[action]);

      return {
        content: [{ type: "text", text: `Set ${climates.length} rooms to ${action}:\n${results.join("\n")}` }],
      };
    }
  );
}
