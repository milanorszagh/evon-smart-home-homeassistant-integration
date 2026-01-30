/**
 * Home state control tools for Evon Smart Home MCP Server
 */

import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import { callMethod } from "../api-client.js";
import { HOME_STATE_IDS } from "../constants.js";
import { fetchHomeStatesWithInfo } from "../helpers.js";

export function registerHomeStateTools(server: McpServer): void {
  server.tool(
    "list_home_states",
    "List all home states (At Home, Holiday, Night, Work) with current active state",
    {},
    async () => {
      const statesWithInfo = await fetchHomeStatesWithInfo();
      const activeState = statesWithInfo.find((s) => s.active);

      return {
        content: [{
          type: "text",
          text: `Current home state: ${activeState?.name || "unknown"}\n\nAvailable states:\n${JSON.stringify(statesWithInfo, null, 2)}`,
        }],
      };
    }
  );

  server.tool(
    "set_home_state",
    "Set the active home state (switches between At Home, Holiday, Night, Work modes)",
    {
      state: z
        .enum(["at_home", "holiday", "night", "work"])
        .describe("The home state to activate"),
    },
    async ({ state }) => {
      const instanceId = HOME_STATE_IDS[state];
      await callMethod(instanceId, "Activate");

      return {
        content: [{ type: "text", text: `Home state set to: ${state}` }],
      };
    }
  );
}
