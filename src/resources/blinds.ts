/**
 * Blind resources for Evon Smart Home MCP Server
 */

import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { fetchBlindsWithState } from "../helpers.js";

export function registerBlindResources(server: McpServer): void {
  server.resource(
    "evon://blinds",
    "All Evon blinds with current state",
    async () => {
      const blindsWithState = await fetchBlindsWithState();
      return {
        contents: [{
          uri: "evon://blinds",
          mimeType: "application/json",
          text: JSON.stringify(blindsWithState, null, 2),
        }],
      };
    }
  );
}
