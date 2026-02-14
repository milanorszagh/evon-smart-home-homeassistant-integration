/**
 * Bathroom radiator resources for Evon Smart Home MCP Server
 */

import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { fetchRadiatorsWithState } from "../helpers.js";
import { RESOURCE_URIS } from "../constants.js";

export function registerRadiatorResources(server: McpServer): void {
  server.resource(
    RESOURCE_URIS.BATHROOM_RADIATORS,
    "All Evon bathroom radiators (electric heaters) with current state",
    async () => {
      const radiatorsWithState = await fetchRadiatorsWithState();
      return {
        contents: [{
          uri: RESOURCE_URIS.BATHROOM_RADIATORS,
          mimeType: "application/json",
          text: JSON.stringify(radiatorsWithState, null, 2),
        }],
      };
    }
  );
}
