/**
 * Blind/shutter control tools for Evon Smart Home MCP Server
 */

import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import { callMethod } from "../api-client.js";
import { DEVICE_CLASSES, BLIND_METHODS } from "../constants.js";
import { getInstances, filterByClass, controlAllDevices, fetchBlindsWithState, sanitizeId } from "../helpers.js";

export function registerBlindTools(server: McpServer): void {
  server.tool(
    "list_blinds",
    "List all blinds/shutters with their current state",
    {},
    async () => {
      const blindsWithState = await fetchBlindsWithState();
      return {
        content: [{ type: "text", text: JSON.stringify(blindsWithState, null, 2) }],
      };
    }
  );

  server.tool(
    "blind_control",
    "Control a blind/shutter (move up, down, stop, set position, or set tilt angle)",
    {
      blind_id: z.string().describe("The blind instance ID"),
      action: z.enum(["up", "down", "stop", "position", "angle"]).describe("Action to perform"),
      position: z.number().min(0).max(100).optional().describe("Position (0=open, 100=closed)"),
      angle: z.number().min(0).max(100).optional().describe("Slat angle (0-100)"),
    },
    async ({ blind_id, action, position, angle }) => {
      const id = sanitizeId(blind_id);
      if (action === "position" && position == null) throw new Error("position parameter is required for position action");
      if (action === "angle" && angle == null) throw new Error("angle parameter is required for angle action");

      const methodMap: Record<string, { method: string; params: unknown[] }> = {
        ...BLIND_METHODS,
        position: { method: "SetPosition", params: [position ?? 0] },
        angle: { method: "SetAngle", params: [angle ?? 0] },
      };

      const { method, params } = methodMap[action];
      await callMethod(id, method, params);

      return {
        content: [{ type: "text", text: `Blind ${blind_id}: ${action}${params.length > 0 ? ` (${params[0]})` : ""}` }],
      };
    }
  );

  server.tool(
    "blind_control_all",
    "Control all blinds at once",
    {
      action: z.enum(["up", "down", "stop", "position", "angle"]).describe("Action to perform"),
      position: z.number().min(0).max(100).optional().describe("Position (0=open, 100=closed)"),
      angle: z.number().min(0).max(100).optional().describe("Slat angle (0-100)"),
    },
    async ({ action, position, angle }) => {
      const instances = await getInstances();
      const blinds = filterByClass(instances, DEVICE_CLASSES.BLIND);

      if (action === "position" && position == null) throw new Error("position parameter is required for position action");
      if (action === "angle" && angle == null) throw new Error("angle parameter is required for angle action");

      const methodMap: Record<string, { method: string; params: unknown[] }> = {
        ...BLIND_METHODS,
        position: { method: "SetPosition", params: [position ?? 0] },
        angle: { method: "SetAngle", params: [angle ?? 0] },
      };

      const { method, params } = methodMap[action];
      const results = await controlAllDevices(blinds, method, params);

      return {
        content: [{ type: "text", text: `Set ${blinds.length} blinds to ${action}${params.length > 0 ? ` (${params[0]})` : ""}:\n${results.join("\n")}` }],
      };
    }
  );
}
