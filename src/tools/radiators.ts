/**
 * Bathroom radiator control tools for Evon Smart Home MCP Server
 */

import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import { apiRequest, callMethod } from "../api-client.js";
import { fetchRadiatorsWithState, sanitizeId } from "../helpers.js";
import type { BathroomRadiatorState } from "../types.js";

export function registerRadiatorTools(server: McpServer): void {
  server.tool(
    "list_bathroom_radiators",
    "List all bathroom radiators (electric heaters) with their current state",
    {},
    async () => {
      const radiatorsWithState = await fetchRadiatorsWithState();
      return {
        content: [{ type: "text", text: JSON.stringify(radiatorsWithState, null, 2) }],
      };
    }
  );

  server.tool(
    "bathroom_radiator_control",
    "Control a bathroom radiator (electric heater) - toggle on/off. When turned on, it runs for the configured duration (default 30 min).",
    {
      radiator_id: z.string().describe("The radiator instance ID (e.g., 'BathroomRadiator9506')"),
      action: z.enum(["on", "off", "toggle"]).describe("Action to perform"),
    },
    async ({ radiator_id, action }) => {
      const id = sanitizeId(radiator_id);
      // Get current state
      const details = await apiRequest<BathroomRadiatorState>(`/instances/${id}`);
      const isCurrentlyOn = details.data.Output ?? false;

      let shouldToggle = false;
      switch (action) {
        case "on":
          shouldToggle = !isCurrentlyOn;
          break;
        case "off":
          shouldToggle = isCurrentlyOn;
          break;
        case "toggle":
          shouldToggle = true;
          break;
      }

      if (shouldToggle) {
        await callMethod(id, "Switch");
      }

      const newState = action === "toggle" ? !isCurrentlyOn : (action === "on");
      const durationInfo = newState ? ` for ${details.data.EnableForMins ?? 30} minutes` : "";
      const actionDesc = shouldToggle ? `turned ${newState ? "on" : "off"}` : `already ${isCurrentlyOn ? "on" : "off"}`;

      return {
        content: [{ type: "text", text: `Bathroom radiator ${id}: ${actionDesc}${durationInfo}` }],
      };
    }
  );
}
