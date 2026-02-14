#!/usr/bin/env node

/**
 * Evon Smart Home MCP Server
 *
 * Model Context Protocol server for controlling Evon Smart Home devices.
 */

import { createRequire } from "module";
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { EVON_HOST, EVON_USERNAME, EVON_PASSWORD } from "./config.js";
import { registerAllTools } from "./tools/index.js";
import { registerAllResources } from "./resources/index.js";
import { getWsClient } from "./ws-client.js";

const require = createRequire(import.meta.url);
const { version } = require("../package.json");

const server = new McpServer({
  name: "evon-smarthome",
  version,
});

// Register all tools and resources
registerAllTools(server);
registerAllResources(server);

export function setupGracefulShutdown(): void {
  const shutdown = () => {
    try {
      getWsClient().disconnect();
    } catch {
      // Best-effort cleanup
    }
    process.exit(0);
  };
  process.on("SIGTERM", shutdown);
  process.on("SIGINT", shutdown);
}

async function main() {
  if (!EVON_HOST || !EVON_USERNAME || !EVON_PASSWORD) {
    console.error("Error: EVON_HOST, EVON_USERNAME, and EVON_PASSWORD environment variables must be set");
    process.exit(1);
  }

  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error("Evon Smart Home MCP server running on stdio");
}

main()
  .then(() => setupGracefulShutdown())
  .catch((error) => {
    console.error("Fatal error:", error);
    process.exit(1);
  });
