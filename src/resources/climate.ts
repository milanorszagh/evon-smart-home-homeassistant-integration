/**
 * Climate resources for Evon Smart Home MCP Server
 */

import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { fetchClimateWithState } from "../helpers.js";
import { RESOURCE_URIS } from "../constants.js";

export function registerClimateResources(server: McpServer): void {
  server.resource(
    RESOURCE_URIS.CLIMATE,
    "All Evon climate controls with current state",
    async () => {
      const climatesWithState = await fetchClimateWithState();
      return {
        contents: [{
          uri: RESOURCE_URIS.CLIMATE,
          mimeType: "application/json",
          text: JSON.stringify(climatesWithState, null, 2),
        }],
      };
    }
  );
}
