/**
 * Light resources for Evon Smart Home MCP Server
 */

import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { fetchLightsWithState } from "../helpers.js";

export function registerLightResources(server: McpServer): void {
  server.resource(
    "evon://lights",
    "All Evon lights with current state",
    async () => {
      const lightsWithState = await fetchLightsWithState();
      return {
        contents: [{
          uri: "evon://lights",
          mimeType: "application/json",
          text: JSON.stringify(lightsWithState, null, 2),
        }],
      };
    }
  );
}
