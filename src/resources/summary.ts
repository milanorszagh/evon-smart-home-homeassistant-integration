/**
 * Summary resource for Evon Smart Home MCP Server
 */

import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { apiRequest } from "../api-client.js";
import { DEVICE_CLASSES } from "../constants.js";
import {
  getInstances,
  filterByClass,
  filterClimateDevices,
  filterHomeStates,
} from "../helpers.js";
import type { LightState, BlindState, ClimateState, HomeStateState, BathroomRadiatorState } from "../types.js";

export function registerSummaryResources(server: McpServer): void {
  server.resource(
    "evon://summary",
    "Summary of all Evon devices and their current state",
    async () => {
      const instances = await getInstances();
      const lights = filterByClass(instances, DEVICE_CLASSES.LIGHT);
      const blinds = filterByClass(instances, DEVICE_CLASSES.BLIND);
      const climates = filterClimateDevices(instances);
      const homeStates = filterHomeStates(instances);
      const radiators = filterByClass(instances, DEVICE_CLASSES.BATHROOM_RADIATOR);

      // Count on lights
      let lightsOn = 0;
      for (const light of lights) {
        try {
          const details = await apiRequest<LightState>(`/instances/${light.ID}`);
          if (details.data.IsOn) lightsOn++;
        } catch {
          // Skip unresponsive devices in count
        }
      }

      // Count open blinds
      let blindsOpen = 0;
      for (const blind of blinds) {
        try {
          const details = await apiRequest<BlindState>(`/instances/${blind.ID}`);
          if ((details.data.Position ?? 0) < 50) blindsOpen++;
        } catch {
          // Skip unresponsive devices in count
        }
      }

      // Get average temperature
      let totalTemp = 0;
      let tempCount = 0;
      for (const climate of climates) {
        try {
          const details = await apiRequest<ClimateState>(`/instances/${climate.ID}`);
          if (details.data.ActualTemperature) {
            totalTemp += details.data.ActualTemperature;
            tempCount++;
          }
        } catch {
          // Skip unresponsive devices in count
        }
      }

      // Get current home state
      let currentHomeState = "unknown";
      for (const state of homeStates) {
        try {
          const details = await apiRequest<HomeStateState>(`/instances/${state.ID}`);
          if (details.data.Active) {
            currentHomeState = state.Name;
            break;
          }
        } catch {
          // Skip unresponsive devices
        }
      }

      // Count bathroom radiators on
      let radiatorsOn = 0;
      for (const radiator of radiators) {
        try {
          const details = await apiRequest<BathroomRadiatorState>(`/instances/${radiator.ID}`);
          if (details.data.Output) radiatorsOn++;
        } catch {
          // Skip unresponsive devices
        }
      }

      const summary = {
        homeState: currentHomeState,
        lights: { total: lights.length, on: lightsOn },
        blinds: { total: blinds.length, open: blindsOpen },
        climate: {
          total: climates.length,
          averageTemperature: tempCount > 0 ? Math.round((totalTemp / tempCount) * 10) / 10 : null,
        },
        bathroomRadiators: { total: radiators.length, on: radiatorsOn },
      };

      return {
        contents: [{
          uri: "evon://summary",
          mimeType: "application/json",
          text: JSON.stringify(summary, null, 2),
        }],
      };
    }
  );
}
