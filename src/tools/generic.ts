/**
 * Generic tools for Evon Smart Home MCP Server
 */

import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import { apiRequest, callMethod } from "../api-client.js";
import { getInstances } from "../helpers.js";

// Validate instance_id to prevent path traversal (must be alphanumeric with dots/underscores)
function sanitizeId(id: string): string {
  if (!/^[\w.]+$/.test(id)) {
    throw new Error(`Invalid instance ID: ${id}`);
  }
  return id;
}

export function registerGenericTools(server: McpServer): void {
  server.tool(
    "list_apps",
    "List all available apps in the Evon Smart Home system",
    {},
    async () => {
      const result = await apiRequest<Array<{ fullName: string; displayName?: string; autoStart: boolean }>>("/apps");
      return {
        content: [{ type: "text", text: JSON.stringify(result.data, null, 2) }],
      };
    }
  );

  server.tool(
    "list_instances",
    "List all instances (devices, sensors, logic blocks) in the system",
    {
      filter: z
        .string()
        .optional()
        .describe("Filter instances by class name or device name"),
    },
    async ({ filter }) => {
      let instances = await getInstances();

      if (filter) {
        const lowerFilter = filter.toLowerCase();
        instances = instances.filter(
          (i) =>
            i.ClassName.toLowerCase().includes(lowerFilter) ||
            i.Name.toLowerCase().includes(lowerFilter)
        );
      }

      return {
        content: [{ type: "text", text: JSON.stringify(instances, null, 2) }],
      };
    }
  );

  server.tool(
    "get_instance",
    "Get detailed information about a specific instance",
    {
      instance_id: z.string().describe("The instance ID (e.g., 'SC1_M01.Light1')"),
    },
    async ({ instance_id }) => {
      const result = await apiRequest<Record<string, unknown>>(`/instances/${sanitizeId(instance_id)}`);
      return {
        content: [{ type: "text", text: JSON.stringify(result.data, null, 2) }],
      };
    }
  );

  server.tool(
    "get_property",
    "Get a specific property value of an instance",
    {
      instance_id: z.string().describe("The instance ID"),
      property: z.string().describe("The property name (e.g., 'IsOn', 'ScaledBrightness', 'Position')"),
    },
    async ({ instance_id, property }) => {
      const result = await apiRequest<unknown>(`/instances/${sanitizeId(instance_id)}/${sanitizeId(property)}`);
      return {
        content: [{ type: "text", text: JSON.stringify(result.data, null, 2) }],
      };
    }
  );

  server.tool(
    "call_method",
    "Call a method on an instance. Use specific tools (light_control, blind_control, climate_control) for common operations.",
    {
      instance_id: z.string().describe("The instance ID"),
      method: z.string().describe("The method name"),
      params: z.array(z.unknown()).optional().describe("Parameters as an array"),
    },
    async ({ instance_id, method, params }) => {
      const result = await callMethod(sanitizeId(instance_id), sanitizeId(method), params);
      return {
        content: [{ type: "text", text: `Method ${method} called on ${instance_id}: ${result.statusText}` }],
      };
    }
  );
}
