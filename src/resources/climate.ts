/**
 * Climate resources for Evon Smart Home MCP Server
 */

import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { fetchClimateWithState } from "../helpers.js";

export function registerClimateResources(server: McpServer): void {
  server.resource(
    "evon://climate",
    "All Evon climate controls with current state",
    async () => {
      const climatesWithState = await fetchClimateWithState();
      return {
        contents: [{
          uri: "evon://climate",
          mimeType: "application/json",
          text: JSON.stringify(climatesWithState, null, 2),
        }],
      };
    }
  );
}
