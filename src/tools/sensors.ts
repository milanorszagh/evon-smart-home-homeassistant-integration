/**
 * Sensor listing tools for Evon Smart Home MCP Server
 */

import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import { getInstances } from "../helpers.js";

export function registerSensorTools(server: McpServer): void {
  server.tool(
    "list_sensors",
    "List sensors (temperature, humidity, motion, etc.)",
    {
      type: z.string().optional().describe("Filter by sensor type"),
    },
    async ({ type }) => {
      const instances = await getInstances();
      let sensors = instances.filter(
        (i) =>
          i.ClassName.includes("Sensor") ||
          i.ClassName.includes("Detector") ||
          i.ClassName.includes("Temperature") ||
          i.ClassName.includes("Humidity")
      );

      if (type) {
        const lowerType = type.toLowerCase();
        sensors = sensors.filter(
          (s) =>
            s.ClassName.toLowerCase().includes(lowerType) ||
            s.Name.toLowerCase().includes(lowerType)
        );
      }

      return {
        content: [{ type: "text", text: JSON.stringify(sensors, null, 2) }],
      };
    }
  );
}
