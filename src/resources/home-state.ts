/**
 * Home state resources for Evon Smart Home MCP Server
 */

import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { fetchHomeStatesWithInfo } from "../helpers.js";

export function registerHomeStateResources(server: McpServer): void {
  server.resource(
    "evon://home_state",
    "Current home state (At Home, Holiday, Night, Work)",
    async () => {
      const statesWithInfo = await fetchHomeStatesWithInfo();
      const activeState = statesWithInfo.find((s) => s.active);

      return {
        contents: [{
          uri: "evon://home_state",
          mimeType: "application/json",
          text: JSON.stringify({
            current: activeState?.name || "unknown",
            currentId: activeState?.id || null,
            available: statesWithInfo,
          }, null, 2),
        }],
      };
    }
  );
}
