/**
 * Light resources for Evon Smart Home MCP Server
 */

import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { fetchLightsWithState } from "../helpers.js";
import { RESOURCE_URIS } from "../constants.js";

export function registerLightResources(server: McpServer): void {
  server.resource(
    RESOURCE_URIS.LIGHTS,
    "All Evon lights with current state",
    async () => {
      const lightsWithState = await fetchLightsWithState();
      return {
        contents: [{
          uri: RESOURCE_URIS.LIGHTS,
          mimeType: "application/json",
          text: JSON.stringify(lightsWithState, null, 2),
        }],
      };
    }
  );
}
