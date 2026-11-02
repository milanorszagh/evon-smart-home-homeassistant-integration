/**
 * Helper functions for Evon Smart Home MCP Server
 */

import { apiRequest, callMethod } from "./api-client.js";
import { DEVICE_CLASSES } from "./constants.js";
import type {
  EvonInstance,
  LightState,
  BlindState,
  ClimateState,
  HomeStateState,
  BathroomRadiatorState,
  LightWithState,
  BlindWithState,
  ClimateWithState,
  HomeStateWithInfo,
  RadiatorWithState,
} from "./types.js";

const ID_SEGMENT = /^[A-Za-z0-9_-]+$/;

/**
 * Validate an instance ID (or property/method name) before it goes into a URL path.
 *
 * Dot-separated segments of letters, digits, "_" and "-" (the same charset as the
 * HA integration). Every segment must be non-empty, so "", ".", ".." and "a..b"
 * are rejected: fetch() normalises a literal ".." path segment, which would let
 * `/instances/${id}` reach other endpoints on the controller.
 */
export function sanitizeId(id: string): string {
  if (typeof id !== "string" || id.length === 0 || id.length > 128 || !id.split(".").every((s) => ID_SEGMENT.test(s))) {
    throw new Error(`Invalid instance ID: ${JSON.stringify(id)}`);
  }
  return id;
}

/** Device families the control tools may act on. */
export type DeviceKind = "light" | "blind" | "climate" | "radiator";

export function deviceKindOf(className: string): DeviceKind | null {
  switch (className) {
    case DEVICE_CLASSES.LIGHT_DIM:
    case DEVICE_CLASSES.LIGHT_RELAY:
    case DEVICE_CLASSES.LIGHT_RGBW:
    case DEVICE_CLASSES.LIGHT_GROUP:
      return "light";
    case DEVICE_CLASSES.BLIND:
    case DEVICE_CLASSES.BLIND_GROUP:
      return "blind";
    case DEVICE_CLASSES.CLIMATE:
    case DEVICE_CLASSES.CLIMATE_UNIVERSAL:
      return "climate";
    case DEVICE_CLASSES.BATHROOM_RADIATOR:
      return "radiator";
    default:
      return className.endsWith(`.${DEVICE_CLASSES.CLIMATE_UNIVERSAL}`) ? "climate" : null;
  }
}

/**
 * Resolve a model-supplied instance ID to a device of one of the given kinds.
 *
 * The control tools send methods such as SwitchOn or Switch. Without this check a
 * confused or prompt-injected model could send them to any instance, e.g. an
 * intercom's door-relay sub-instance or a security/logic object.
 */
export async function requireDevice(id: string, kinds: readonly DeviceKind[]): Promise<EvonInstance> {
  const safeId = sanitizeId(id);
  // Unnamed instances are class templates, not devices.
  const instance = (await getInstances()).find((i) => i.ID === safeId && i.Name);
  if (!instance) {
    throw new Error(`Unknown instance: ${safeId}`);
  }
  const kind = deviceKindOf(instance.ClassName);
  if (kind === null || !kinds.includes(kind)) {
    throw new Error(`Instance ${safeId} (${instance.ClassName}) is not a ${kinds.join(" or ")} and cannot be controlled with this tool`);
  }
  return instance;
}

// Short-lived cache for getInstances() to avoid redundant API calls
// when multiple fetchXxxWithState helpers run in sequence.
const INSTANCES_CACHE_TTL_MS = 5000;
let instancesCache: EvonInstance[] | null = null;
let instancesCacheTime = 0;

export async function getInstances(): Promise<EvonInstance[]> {
  const now = Date.now();
  if (instancesCache && now - instancesCacheTime < INSTANCES_CACHE_TTL_MS) {
    return instancesCache;
  }
  const result = await apiRequest<EvonInstance[]>("/instances");
  instancesCache = result.data;
  instancesCacheTime = now;
  return instancesCache;
}

export function filterByClass(instances: EvonInstance[], className: string): EvonInstance[] {
  return instances.filter(
    (i) => i.ClassName === className && i.Name && i.Name.length > 0
  );
}

/** Filter all light instances regardless of sub-type (dimmable, relay, RGBW, group). */
export function filterLightDevices(instances: EvonInstance[]): EvonInstance[] {
  return instances.filter(
    (i) =>
      (i.ClassName === DEVICE_CLASSES.LIGHT_DIM ||
        i.ClassName === DEVICE_CLASSES.LIGHT_RELAY ||
        i.ClassName === DEVICE_CLASSES.LIGHT_RGBW ||
        i.ClassName === DEVICE_CLASSES.LIGHT_GROUP) &&
      i.Name &&
      i.Name.length > 0
  );
}

export function filterClimateDevices(instances: EvonInstance[]): EvonInstance[] {
  return instances.filter(
    (i) =>
      (i.ClassName === DEVICE_CLASSES.CLIMATE ||
        i.ClassName === DEVICE_CLASSES.CLIMATE_UNIVERSAL ||
        i.ClassName.endsWith(`.${DEVICE_CLASSES.CLIMATE_UNIVERSAL}`)) &&
      i.Name &&
      i.Name.length > 0
  );
}

export function filterHomeStates(instances: EvonInstance[]): EvonInstance[] {
  return instances.filter(
    (i) =>
      i.ClassName === DEVICE_CLASSES.HOME_STATE &&
      i.ID &&
      !i.ID.startsWith("System.") &&
      i.Name &&
      i.Name.length > 0
  );
}

export async function controlAllDevices(
  devices: EvonInstance[],
  method: string,
  params: unknown[] = []
): Promise<string[]> {
  return Promise.all(
    devices.map(async (device) => {
      try {
        await callMethod(device.ID, method, params);
        return `${device.Name}: success`;
      } catch (error: unknown) {
        const errorMsg = error instanceof Error ? error.message : String(error);
        return `${device.Name}: failed (${errorMsg})`;
      }
    })
  );
}

// Fetch functions with state

export async function fetchLightsWithState(): Promise<LightWithState[]> {
  const instances = await getInstances();
  const lights = filterLightDevices(instances);

  return Promise.all(
    lights.map(async (light) => {
      try {
        const details = await apiRequest<LightState>(`/instances/${sanitizeId(light.ID)}`);
        return {
          id: light.ID,
          name: details.data.Name || light.Name,
          isOn: details.data.IsOn ?? false,
          brightness: details.data.ScaledBrightness ?? 0,
        };
      } catch (error: unknown) {
        const errorMsg = error instanceof Error ? error.message : String(error);
        return { id: light.ID, name: light.Name, isOn: false, brightness: 0, error: errorMsg };
      }
    })
  );
}

export async function fetchBlindsWithState(): Promise<BlindWithState[]> {
  const instances = await getInstances();
  const blinds = filterByClass(instances, DEVICE_CLASSES.BLIND);

  return Promise.all(
    blinds.map(async (blind) => {
      try {
        const details = await apiRequest<BlindState>(`/instances/${sanitizeId(blind.ID)}`);
        return {
          id: blind.ID,
          name: details.data.Name || blind.Name,
          position: details.data.Position ?? 0,
          angle: details.data.Angle ?? 0,
          isMoving: details.data.IsMoving ?? false,
        };
      } catch (error: unknown) {
        const errorMsg = error instanceof Error ? error.message : String(error);
        return { id: blind.ID, name: blind.Name, position: 0, angle: 0, isMoving: false, error: errorMsg };
      }
    })
  );
}

export async function fetchClimateWithState(): Promise<ClimateWithState[]> {
  const instances = await getInstances();
  const climates = filterClimateDevices(instances);

  return Promise.all(
    climates.map(async (climate) => {
      try {
        const details = await apiRequest<ClimateState>(`/instances/${sanitizeId(climate.ID)}`);
        return {
          id: climate.ID,
          name: details.data.Name || climate.Name,
          setTemperature: details.data.SetTemperature ?? 0,
          actualTemperature: details.data.ActualTemperature ?? 0,
        };
      } catch (error: unknown) {
        const errorMsg = error instanceof Error ? error.message : String(error);
        return { id: climate.ID, name: climate.Name, setTemperature: 0, actualTemperature: 0, error: errorMsg };
      }
    })
  );
}

export async function fetchHomeStatesWithInfo(): Promise<HomeStateWithInfo[]> {
  const instances = await getInstances();
  const homeStates = filterHomeStates(instances);

  return Promise.all(
    homeStates.map(async (state) => {
      try {
        const details = await apiRequest<HomeStateState>(`/instances/${sanitizeId(state.ID)}`);
        return {
          id: state.ID,
          name: state.Name,
          active: details.data.Active ?? false,
        };
      } catch (error: unknown) {
        const errorMsg = error instanceof Error ? error.message : String(error);
        return { id: state.ID, name: state.Name, active: false, error: errorMsg };
      }
    })
  );
}

export async function fetchRadiatorsWithState(): Promise<RadiatorWithState[]> {
  const instances = await getInstances();
  const radiators = filterByClass(instances, DEVICE_CLASSES.BATHROOM_RADIATOR);

  return Promise.all(
    radiators.map(async (radiator) => {
      try {
        const details = await apiRequest<BathroomRadiatorState>(`/instances/${sanitizeId(radiator.ID)}`);
        // NextSwitchPoint is in hours-and-fraction format (e.g. 1.5 = 1 hour 30 minutes)
        const hoursRemaining = details.data.NextSwitchPoint ?? -1;
        return {
          id: radiator.ID,
          name: details.data.Name || radiator.Name,
          isOn: details.data.Output ?? false,
          timeRemaining: hoursRemaining > 0 ? `${Math.floor(hoursRemaining)}:${Math.floor((hoursRemaining % 1) * 60).toString().padStart(2, '0')}` : null,
          timeRemainingMins: hoursRemaining > 0 ? Math.round(hoursRemaining * 10) / 10 : null,
          durationMins: details.data.EnableForMins ?? 30,
          permanentlyOn: details.data.PermanentlyOn ?? false,
          permanentlyOff: details.data.PermanentlyOff ?? false,
        };
      } catch (error: unknown) {
        const errorMsg = error instanceof Error ? error.message : String(error);
        return {
          id: radiator.ID,
          name: radiator.Name,
          isOn: false,
          timeRemaining: null,
          timeRemainingMins: null,
          durationMins: 30,
          permanentlyOn: false,
          permanentlyOff: false,
          error: errorMsg,
        };
      }
    })
  );
}
