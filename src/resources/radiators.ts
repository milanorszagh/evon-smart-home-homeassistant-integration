/**
 * Bathroom radiator resources for Evon Smart Home MCP Server
 */

import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { fetchRadiatorsWithState } from "../helpers.js";

export function registerRadiatorResources(server: McpServer): void {
  server.resource(
    "evon://bathroom_radiators",
    "All Evon bathroom radiators (electric heaters) with current state",
    async () => {
      const radiatorsWithState = await fetchRadiatorsWithState();
      return {
        contents: [{
          uri: "evon://bathroom_radiators",
          mimeType: "application/json",
          text: JSON.stringify(radiatorsWithState, null, 2),
        }],
      };
    }
  );
}
