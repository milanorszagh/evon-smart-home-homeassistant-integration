#!/usr/bin/env node

/**
 * Evon Smart Home MCP Server
 *
 * Model Context Protocol server for controlling Evon Smart Home devices.
 */

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { EVON_USERNAME, EVON_PASSWORD } from "./config.js";
import { registerAllTools } from "./tools/index.js";
import { registerAllResources } from "./resources/index.js";

const server = new McpServer({
  name: "evon-smarthome",
  version: "1.0.0",
});

// Register all tools and resources
registerAllTools(server);
registerAllResources(server);

async function main() {
  if (!EVON_USERNAME || !EVON_PASSWORD) {
    console.error("Error: EVON_USERNAME and EVON_PASSWORD environment variables must be set");
    process.exit(1);
  }

  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error("Evon Smart Home MCP server running on stdio");
}

main().catch(console.error);
