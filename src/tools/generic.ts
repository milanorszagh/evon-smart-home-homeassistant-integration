/**
 * Generic tools for Evon Smart Home MCP Server
 */

import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import { apiRequest, callMethod } from "../api-client.js";
import { getInstances, requireDevice, sanitizeId } from "../helpers.js";

/**
 * Allowed methods for the call_method tool. Together with the device-class check
 * below (lights, blinds, climate, bathroom radiators only) this keeps the model
 * away from door openers, alarm and logic objects. SetValue (a raw property write)
 * is deliberately not allowed.
 */
const ALLOWED_METHODS = new Set([
  "Switch",
  "SwitchOn",
  "SwitchOff",
  "GetValue",
  "Toggle",
  "Open",
  "Close",
  "Stop",
  "SetPosition",
  "SetColor",
  "SetBrightness",
  "SetTemperature",
  "SetMode",
]);

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
    "Call a method on a light, blind, climate or bathroom-radiator instance. Use specific tools (light_control, blind_control, climate_control) for common operations.",
    {
      instance_id: z.string().describe("The instance ID"),
      method: z.string().describe("The method name"),
      params: z.array(z.unknown()).optional().describe("Parameters as an array"),
    },
    async ({ instance_id, method, params }) => {
      if (!ALLOWED_METHODS.has(method)) {
        const allowed = [...ALLOWED_METHODS].sort().join(", ");
        throw new Error(
          `Method "${method}" is not allowed. Allowed methods: ${allowed}`
        );
      }
      const device = await requireDevice(instance_id, ["light", "blind", "climate", "radiator"]);
      const result = await callMethod(device.ID, sanitizeId(method), params);
      return {
        content: [{ type: "text", text: `Method ${method} called on ${instance_id}: ${result.statusText}` }],
      };
    }
  );
}
