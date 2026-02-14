/**
 * Summary resource for Evon Smart Home MCP Server
 */

import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { apiRequest } from "../api-client.js";
import { DEVICE_CLASSES, RESOURCE_URIS } from "../constants.js";
import {
  getInstances,
  filterByClass,
  filterClimateDevices,
  filterHomeStates,
} from "../helpers.js";
import type { LightState, BlindState, ClimateState, HomeStateState, BathroomRadiatorState } from "../types.js";

export function registerSummaryResources(server: McpServer): void {
  server.resource(
    RESOURCE_URIS.SUMMARY,
    "Summary of all Evon devices and their current state",
    async () => {
      const instances = await getInstances();
      const lights = filterByClass(instances, DEVICE_CLASSES.LIGHT);
      const blinds = filterByClass(instances, DEVICE_CLASSES.BLIND);
      const climates = filterClimateDevices(instances);
      const homeStates = filterHomeStates(instances);
      const radiators = filterByClass(instances, DEVICE_CLASSES.BATHROOM_RADIATOR);

      // Fetch all device details in parallel for performance
      const [lightDetails, blindDetails, climateDetails, homeStateDetails, radiatorDetails] = await Promise.all([
        Promise.all(lights.map((l) => apiRequest<LightState>(`/instances/${l.ID}`).catch(() => null))),
        Promise.all(blinds.map((b) => apiRequest<BlindState>(`/instances/${b.ID}`).catch(() => null))),
        Promise.all(climates.map((c) => apiRequest<ClimateState>(`/instances/${c.ID}`).catch(() => null))),
        Promise.all(homeStates.map((s) => apiRequest<HomeStateState>(`/instances/${s.ID}`).catch(() => null))),
        Promise.all(radiators.map((r) => apiRequest<BathroomRadiatorState>(`/instances/${r.ID}`).catch(() => null))),
      ]);

      // Count on lights
      let lightsOn = 0;
      for (const details of lightDetails) {
        if (details?.data.IsOn) lightsOn++;
      }

      // Count open blinds
      let blindsOpen = 0;
      for (const details of blindDetails) {
        if (details && (details.data.Position ?? 0) < 50) blindsOpen++;
      }

      // Get average temperature
      let totalTemp = 0;
      let tempCount = 0;
      for (const details of climateDetails) {
        if (details && details.data.ActualTemperature != null) {
          totalTemp += details.data.ActualTemperature;
          tempCount++;
        }
      }

      // Get current home state
      let currentHomeState = "unknown";
      for (let i = 0; i < homeStateDetails.length; i++) {
        if (homeStateDetails[i]?.data.Active) {
          currentHomeState = homeStates[i].Name;
          break;
        }
      }

      // Count bathroom radiators on
      let radiatorsOn = 0;
      for (const details of radiatorDetails) {
        if (details?.data.Output) radiatorsOn++;
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
          uri: RESOURCE_URIS.SUMMARY,
          mimeType: "application/json",
          text: JSON.stringify(summary, null, 2),
        }],
      };
    }
  );
}
