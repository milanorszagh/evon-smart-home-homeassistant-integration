/**
 * Blind resources for Evon Smart Home MCP Server
 */

import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { fetchBlindsWithState } from "../helpers.js";
import { RESOURCE_URIS } from "../constants.js";

export function registerBlindResources(server: McpServer): void {
  server.resource(
    RESOURCE_URIS.BLINDS,
    "All Evon blinds with current state",
    async () => {
      const blindsWithState = await fetchBlindsWithState();
      return {
        contents: [{
          uri: RESOURCE_URIS.BLINDS,
          mimeType: "application/json",
          text: JSON.stringify(blindsWithState, null, 2),
        }],
      };
    }
  );
}
