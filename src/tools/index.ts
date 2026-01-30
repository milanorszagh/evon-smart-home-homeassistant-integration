/**
 * Tool registration for Evon Smart Home MCP Server
 */

import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { registerGenericTools } from "./generic.js";
import { registerLightTools } from "./lights.js";
import { registerBlindTools } from "./blinds.js";
import { registerClimateTools } from "./climate.js";
import { registerHomeStateTools } from "./home-state.js";
import { registerRadiatorTools } from "./radiators.js";
import { registerSensorTools } from "./sensors.js";

export function registerAllTools(server: McpServer): void {
  registerGenericTools(server);
  registerLightTools(server);
  registerBlindTools(server);
  registerClimateTools(server);
  registerHomeStateTools(server);
  registerRadiatorTools(server);
  registerSensorTools(server);
}
