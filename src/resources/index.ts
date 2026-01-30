/**
 * Resource registration for Evon Smart Home MCP Server
 */

import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { registerLightResources } from "./lights.js";
import { registerBlindResources } from "./blinds.js";
import { registerClimateResources } from "./climate.js";
import { registerHomeStateResources } from "./home-state.js";
import { registerRadiatorResources } from "./radiators.js";
import { registerSummaryResources } from "./summary.js";

export function registerAllResources(server: McpServer): void {
  registerLightResources(server);
  registerBlindResources(server);
  registerClimateResources(server);
  registerHomeStateResources(server);
  registerRadiatorResources(server);
  registerSummaryResources(server);
}
