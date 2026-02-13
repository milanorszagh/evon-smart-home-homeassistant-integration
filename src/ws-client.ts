/**
 * WebSocket client for Evon Smart Home
 *
 * Provides real-time communication with the Evon system via WebSocket.
 * Can be used alongside or instead of the HTTP API for:
 * - Real-time property value subscriptions
 * - Faster device control
 * - Batch property queries
 *
 * Discovered Device Types:
 * - Lights: SmartCOM.Light.DynamicRGBWLight, SmartCOM.Light.LightDim, Base.bLight
 * - Blinds: SmartCOM.Blind.Blind, Base.ehBlind, Base.bBlind
 * - Blind Groups: SmartCOM.Blind.BlindGroup
 * - Climate: SmartCOM.Clima.ClimateControl
 * - Home States: System.HomeState
 * - Bathroom Radiators: Heating.BathroomRadiator
 * - Switches/Inputs: Base.bSwitchUniversal, Base.bSwitch
 */

import { WebSocket } from "ws";
import { EVON_HOST, EVON_USERNAME, EVON_PASSWORD, validateConfig } from "./config.js";
import { API_TIMEOUT_MS, WS_DEVICE_CLASSES } from "./constants.js";

// Re-export for convenience
export { WS_DEVICE_CLASSES };

// Property lists for each device type
export const WS_DEVICE_PROPERTIES = {
  LIGHT: [
    "ID", "Name", "Group", "Error", "IsOn", "Brightness", "ScaledBrightness",
    "DirectOn", "ColorTemp", "MinColorTemperature", "MaxColorTemperature",
    "IsWarmWhite", "Lock", "LightGroups", "Address", "Channel", "Line",
    "IsPowerSavingOn", "UseSwitchOnForTime", "LastingTimeSwitchOnFor", "PowerSavingLasting"
  ],
  BLIND: [
    "ID", "Name", "Group", "Error", "Position", "Angle", "Lock",
    "Address", "Channel", "OpenTime", "CloseTime", "TiltTime"
  ],
  CLIMATE: [
    "ID", "Name", "Group", "Error", "SetTemperature", "ActualTemperature",
    "Mode", "Humidity", "HeatingActive", "CoolingActive"
  ],
  HOME_STATE: ["ID", "Name", "Active", "Description"],
  BATHROOM_RADIATOR: [
    "ID", "Name", "Group", "Error", "Output", "NextSwitchPoint",
    "EnableForMins", "PermanentlyOn", "PermanentlyOff", "Deactivated"
  ],
  SWITCH: ["ID", "Name", "Group", "Error", "State", "Value"],
} as const;

// ============================================================================
// Types
// ============================================================================

export interface WsMessage {
  methodName: "CallWithReturn" | "Call";
  request: {
    args: unknown[];
    methodName: string;
    sequenceId: number;
    instanceId?: string;
  };
}

export interface WsResponse {
  type: "Connected" | "Event" | "Callback";
  payload: unknown;
  userData?: WsUserData;
}

export interface WsUserData {
  ID: string;
  Name: string;
  ClassName: string;
  Authorization: Array<{ Selector: string; CanView: boolean }>;
}

export interface PropertyValue {
  key: string;
  value: {
    Hidden: boolean;
    Name: string;
    Type: number;
    Value: unknown;
    IsStatic: boolean;
    SetReason: string;
    SetTime: string;
  };
}

export interface ValuesChangedTable {
  [key: string]: PropertyValue;
}

export interface DeviceInstance {
  ID: string;
  Name: string;
  ClassName?: string;
  Containername?: string;
  FullPath?: string;
  Group?: string;
}

export interface PropertySubscription {
  Instanceid: string;
  Properties: string[];
}

export type ValuesChangedCallback = (
  instanceId: string,
  properties: Record<string, unknown>
) => void;

// ============================================================================
// WebSocket Client Class
// ============================================================================

export class EvonWsClient {
  private ws: WebSocket | null = null;
  private token: string | null = null;
  private sequenceId = 1;
  private pendingRequests = new Map<
    number,
    { resolve: (value: unknown) => void; reject: (error: Error) => void; timeout: NodeJS.Timeout }
  >();
  private subscriptions = new Map<string, ValuesChangedCallback>();
  private connected = false;
  private userData: WsUserData | null = null;

  private host: string;
  private wsHost: string;

  constructor(host?: string) {
    if (!host) validateConfig();
    this.host = host || EVON_HOST;
    this.wsHost = this.host.replace("http://", "ws://").replace("https://", "wss://");
  }

  // --------------------------------------------------------------------------
  // Connection Management
  // --------------------------------------------------------------------------

  /**
   * Connect to the Evon WebSocket server.
   * Automatically logs in via HTTP first to get a token.
   */
  private connectPromise: Promise<void> | null = null;

  async connect(): Promise<void> {
    if (this.connected && this.ws?.readyState === WebSocket.OPEN) {
      return;
    }

    // Deduplicate concurrent connect calls
    if (this.connectPromise) {
      return this.connectPromise;
    }

    this.connectPromise = this.performConnect();
    try {
      await this.connectPromise;
    } finally {
      this.connectPromise = null;
    }
  }

  private async performConnect(): Promise<void> {
    // Get token via HTTP login
    this.token = await this.login();

    return new Promise((resolve, reject) => {
      this.ws = new WebSocket(this.wsHost, "echo-protocol", {
        headers: {
          Origin: this.host,
          Cookie: `token=${this.token}; x-elocs-isrelay=false; x-elocs-token_in_cookie_only=0`,
        },
      });

      const timeout = setTimeout(() => {
        this.ws?.close();
        reject(new Error("WebSocket connection timeout"));
      }, API_TIMEOUT_MS);

      this.ws.on("open", () => {
        // Wait for Connected message
      });

      this.ws.on("message", (data) => {
        this.handleMessage(data.toString());

        // Resolve on first Connected message
        if (!this.connected) {
          this.connected = true;
          clearTimeout(timeout);

          // Replace connection-phase error handler with runtime handler
          const ws = this.ws;
          if (ws) {
            ws.removeAllListeners("error");
            ws.on("error", (error) => {
              console.error("WebSocket error:", error.message);
              this.connected = false;
              this.rejectAllPending(error);
            });
          }

          resolve();
        }
      });

      this.ws.on("error", (error) => {
        clearTimeout(timeout);
        reject(error);
      });

      this.ws.on("close", () => {
        this.connected = false;
        this.rejectAllPending(new Error("WebSocket closed"));
      });
    });
  }

  /**
   * Close the WebSocket connection.
   */
  disconnect(): void {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this.connected = false;
    this.token = null;
    this.subscriptions.clear();
  }

  /**
   * Check if connected.
   */
  isConnected(): boolean {
    return this.connected && this.ws?.readyState === WebSocket.OPEN;
  }

  /**
   * Get user data from connection.
   */
  getUserData(): WsUserData | null {
    return this.userData;
  }

  // --------------------------------------------------------------------------
  // Core Methods
  // --------------------------------------------------------------------------

  /**
   * Get all instances of a device class.
   */
  async getInstances(className: string): Promise<DeviceInstance[]> {
    const result = await this.call<DeviceInstance[]>("GetInstances", [className]);
    return result || [];
  }

  /**
   * Subscribe to property changes and get initial values.
   * Returns the initial values.
   */
  async registerValuesChanged(
    subscriptions: PropertySubscription[],
    callback?: ValuesChangedCallback
  ): Promise<Record<string, Record<string, unknown>>> {
    // Register callbacks
    if (callback) {
      for (const sub of subscriptions) {
        this.subscriptions.set(sub.Instanceid, callback);
      }
    }

    // Make the call - initial values come via ValuesChanged event
    await this.call("RegisterValuesChanged", [true, subscriptions, true, true]);

    // Return empty - values come via event
    return {};
  }

  /**
   * Unsubscribe from property changes.
   */
  async unregisterValuesChanged(instanceIds: string[]): Promise<void> {
    const subscriptions = instanceIds.map((id) => ({ Instanceid: id, Properties: [] }));
    await this.call("RegisterValuesChanged", [false, subscriptions, false, false]);

    for (const id of instanceIds) {
      this.subscriptions.delete(id);
    }
  }

  /**
   * Set a property value on a device.
   */
  async setValue(instanceId: string, property: string, value: unknown): Promise<void> {
    await this.call("SetValue", [`${instanceId}.${property}`, value]);
  }

  /**
   * Get property values for multiple devices in a single call.
   * Returns values via the ValuesChanged event mechanism.
   */
  async getPropertyValues(
    subscriptions: PropertySubscription[]
  ): Promise<Record<string, Record<string, unknown>>> {
    return new Promise((resolve, reject) => {
      const results: Record<string, Record<string, unknown>> = {};
      const expectedIds = new Set(subscriptions.map((s) => s.Instanceid));

      // Save original callbacks so we can restore them on cleanup
      const originalCallbacks = new Map<string, ValuesChangedCallback | undefined>();
      for (const sub of subscriptions) {
        originalCallbacks.set(sub.Instanceid, this.subscriptions.get(sub.Instanceid));
      }

      const cleanup = () => {
        // Restore original callbacks or remove temp ones
        for (const [id, original] of originalCallbacks) {
          if (original) {
            this.subscriptions.set(id, original);
          } else {
            this.subscriptions.delete(id);
          }
        }
        // Unsubscribe server-side for IDs that had no prior subscription
        const idsToUnsub = [...originalCallbacks.entries()]
          .filter(([, original]) => !original)
          .map(([id]) => id);
        if (idsToUnsub.length > 0) {
          this.unregisterValuesChanged(idsToUnsub).catch(() => {});
        }
      };

      const timeout = setTimeout(() => {
        cleanup();
        reject(new Error("getPropertyValues timeout"));
      }, API_TIMEOUT_MS);

      // Temporary callback to capture values
      const tempCallback: ValuesChangedCallback = (instanceId, properties) => {
        results[instanceId] = { ...results[instanceId], ...properties };

        // Check if we have all expected instances
        if ([...expectedIds].every((id) => id in results)) {
          clearTimeout(timeout);
          cleanup();
          resolve(results);
        }
      };

      // Register temp callbacks (chain with existing if any)
      for (const sub of subscriptions) {
        const existing = originalCallbacks.get(sub.Instanceid);
        this.subscriptions.set(sub.Instanceid, (id, props) => {
          tempCallback(id, props);
          if (existing) existing(id, props);
        });
      }

      // Make the call
      this.call("RegisterValuesChanged", [true, subscriptions, true, true]).catch((err) => {
        clearTimeout(timeout);
        cleanup();
        reject(err);
      });
    });
  }

  // --------------------------------------------------------------------------
  // Device-Specific Helpers
  // --------------------------------------------------------------------------

  /**
   * Turn a light on or off.
   */
  async setLightOn(instanceId: string, on: boolean): Promise<void> {
    await this.setValue(instanceId, "IsOn", on);
  }

  /**
   * Set light brightness (0-100).
   */
  async setLightBrightness(instanceId: string, brightness: number): Promise<void> {
    await this.setValue(instanceId, "ScaledBrightness", Math.max(0, Math.min(100, brightness)));
  }

  /**
   * Set blind position (0-100, where 0 is closed/up).
   */
  async setBlindPosition(instanceId: string, position: number): Promise<void> {
    await this.setValue(instanceId, "Position", Math.max(0, Math.min(100, position)));
  }

  /**
   * Set blind angle (0-100).
   */
  async setBlindAngle(instanceId: string, angle: number): Promise<void> {
    await this.setValue(instanceId, "Angle", Math.max(0, Math.min(100, angle)));
  }

  /**
   * Set climate target temperature.
   */
  async setClimateTemperature(instanceId: string, temperature: number): Promise<void> {
    await this.setValue(instanceId, "SetTemperature", temperature);
  }

  /**
   * Set climate mode (0=off, 1=comfort, 2=eco, 3=away).
   */
  async setClimateMode(instanceId: string, mode: number): Promise<void> {
    await this.setValue(instanceId, "Mode", mode);
  }

  /**
   * Activate a home state.
   */
  async setHomeStateActive(instanceId: string, active: boolean): Promise<void> {
    await this.setValue(instanceId, "Active", active);
  }

  /**
   * Control bathroom radiator.
   */
  async setBathroomRadiatorOn(instanceId: string, on: boolean): Promise<void> {
    await this.setValue(instanceId, "Output", on);
  }

  /**
   * Set bathroom radiator timer (minutes).
   */
  async setBathroomRadiatorTimer(instanceId: string, minutes: number): Promise<void> {
    await this.setValue(instanceId, "EnableForMins", minutes);
  }

  // --------------------------------------------------------------------------
  // Internal Methods
  // --------------------------------------------------------------------------

  private rejectAllPending(error: Error): void {
    this.pendingRequests.forEach(({ reject, timeout }) => {
      clearTimeout(timeout);
      reject(error);
    });
    this.pendingRequests.clear();
  }

  private async login(): Promise<string> {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), API_TIMEOUT_MS);

    try {
      const response = await fetch(`${this.host}/login`, {
        method: "POST",
        headers: {
          "x-elocs-username": EVON_USERNAME,
          "x-elocs-password": EVON_PASSWORD,
        },
        signal: controller.signal,
      });

      if (!response.ok) {
        throw new Error(`Login failed: ${response.status} ${response.statusText}`);
      }

      const token = response.headers.get("x-elocs-token");
      if (!token) {
        throw new Error("No token received from login");
      }

      return token;
    } catch (error: unknown) {
      if (error instanceof Error && error.name === "AbortError") {
        throw new Error(`WS login timeout after ${API_TIMEOUT_MS}ms`);
      }
      throw error;
    } finally {
      clearTimeout(timeoutId);
    }
  }

  private async call<T>(methodName: string, args: unknown[]): Promise<T | null> {
    if (!this.isConnected()) {
      await this.connect();
    }

    if (!this.isConnected()) {
      throw new Error("WebSocket not connected after connect");
    }

    try {
      return await this.callWithReturn<T>(methodName, args);
    } catch (error) {
      if (error instanceof Error && error.message === "WebSocket not connected") {
        this.connected = false;
        await this.connect();
        if (!this.isConnected()) {
          throw new Error("WebSocket not connected after reconnect");
        }
        return this.callWithReturn<T>(methodName, args);
      }
      throw error;
    }
  }

  private callWithReturn<T>(methodName: string, args: unknown[]): Promise<T | null> {
    return new Promise((resolve, reject) => {
      const seq = this.sequenceId++;
      const timeout = setTimeout(() => {
        this.pendingRequests.delete(seq);
        reject(new Error(`WebSocket call timeout: ${methodName}`));
      }, API_TIMEOUT_MS);

      this.pendingRequests.set(seq, {
        resolve: resolve as (value: unknown) => void,
        reject,
        timeout,
      });

      const message: WsMessage = {
        methodName: "CallWithReturn",
        request: {
          args,
          methodName,
          sequenceId: seq,
        },
      };

      if (!this.ws) {
        clearTimeout(timeout);
        this.pendingRequests.delete(seq);
        reject(new Error("WebSocket not connected"));
        return;
      }
      this.ws.send(JSON.stringify(message));
    });
  }

  private handleMessage(data: string): void {
    try {
      const msg = JSON.parse(data);
      const [type, payload, extra] = msg as [string, unknown, unknown];

      if (type === "Connected") {
        // Extract user data
        const userData = (extra as { _userData?: WsUserData })?._userData;
        if (userData) {
          this.userData = userData;
        }
        return;
      }

      if (type === "Event") {
        const event = payload as { methodName: string; args: unknown[] };
        if (event.methodName === "ValuesChanged") {
          this.handleValuesChanged(event.args[0] as { table: ValuesChangedTable });
        }
        return;
      }

      if (type === "Callback") {
        const callback = payload as { sequenceId: number; methodName: string; args: unknown[] };
        const pending = this.pendingRequests.get(callback.sequenceId);
        if (pending) {
          clearTimeout(pending.timeout);
          this.pendingRequests.delete(callback.sequenceId);
          pending.resolve(callback.args?.[0] ?? null);
        }
        return;
      }
    } catch (error) {
      console.error("Error parsing WebSocket message:", error);
    }
  }

  private handleValuesChanged(data: { table: ValuesChangedTable }): void {
    if (!data?.table) return;

    // Group values by instance ID
    const grouped: Record<string, Record<string, unknown>> = {};

    for (const [key, entry] of Object.entries(data.table)) {
      const parts = key.split(".");
      const property = parts.pop();
      if (!property) {
        continue;
      }
      const instanceId = parts.join(".");

      if (!grouped[instanceId]) {
        grouped[instanceId] = {};
      }
      grouped[instanceId][property] = entry.value?.Value;
    }

    // Notify subscribers
    for (const [instanceId, properties] of Object.entries(grouped)) {
      const callback = this.subscriptions.get(instanceId);
      if (callback) {
        callback(instanceId, properties);
      }
    }
  }
}

// ============================================================================
// Singleton Instance
// ============================================================================

let wsClientInstance: EvonWsClient | null = null;

/**
 * Get the singleton WebSocket client instance.
 */
export function getWsClient(): EvonWsClient {
  if (!wsClientInstance) {
    wsClientInstance = new EvonWsClient();
  }
  return wsClientInstance;
}

// ============================================================================
// Convenience Functions
// ============================================================================

/**
 * Get all lights via WebSocket.
 */
export async function wsGetLights(): Promise<DeviceInstance[]> {
  const client = getWsClient();
  await client.connect();
  return client.getInstances("Base.bLight");
}

/**
 * Get all blinds via WebSocket.
 */
export async function wsGetBlinds(): Promise<DeviceInstance[]> {
  const client = getWsClient();
  await client.connect();
  return client.getInstances("Base.bBlind");
}

/**
 * Get light state via WebSocket.
 */
export async function wsGetLightState(
  instanceId: string
): Promise<{ isOn: boolean; brightness: number; name: string }> {
  const client = getWsClient();
  await client.connect();

  const values = await client.getPropertyValues([
    { Instanceid: instanceId, Properties: ["Name", "IsOn", "ScaledBrightness"] },
  ]);

  const props = values[instanceId] || {};
  return {
    name: (props.Name as string) || instanceId,
    isOn: (props.IsOn as boolean) ?? false,
    brightness: (props.ScaledBrightness as number) ?? 0,
  };
}

/**
 * Get blind state via WebSocket.
 */
export async function wsGetBlindState(
  instanceId: string
): Promise<{ position: number; angle: number; name: string }> {
  const client = getWsClient();
  await client.connect();

  const values = await client.getPropertyValues([
    { Instanceid: instanceId, Properties: ["Name", "Position", "Angle"] },
  ]);

  const props = values[instanceId] || {};
  return {
    name: (props.Name as string) || instanceId,
    position: (props.Position as number) ?? 0,
    angle: (props.Angle as number) ?? 0,
  };
}

/**
 * Control a light via WebSocket.
 */
export async function wsControlLight(
  instanceId: string,
  options: { on?: boolean; brightness?: number }
): Promise<void> {
  const client = getWsClient();
  await client.connect();

  if (options.on !== undefined) {
    await client.setLightOn(instanceId, options.on);
  }
  if (options.brightness !== undefined) {
    await client.setLightBrightness(instanceId, options.brightness);
  }
}

/**
 * Control a blind via WebSocket.
 */
export async function wsControlBlind(
  instanceId: string,
  options: { position?: number; angle?: number }
): Promise<void> {
  const client = getWsClient();
  await client.connect();

  if (options.position !== undefined) {
    await client.setBlindPosition(instanceId, options.position);
  }
  if (options.angle !== undefined) {
    await client.setBlindAngle(instanceId, options.angle);
  }
}

/**
 * Get all climate zones via WebSocket.
 */
export async function wsGetClimateZones(): Promise<DeviceInstance[]> {
  const client = getWsClient();
  await client.connect();
  return client.getInstances(WS_DEVICE_CLASSES.CLIMATE);
}

/**
 * Get climate state via WebSocket.
 */
export async function wsGetClimateState(
  instanceId: string
): Promise<{ name: string; setTemperature: number; actualTemperature: number; mode: number }> {
  const client = getWsClient();
  await client.connect();

  const values = await client.getPropertyValues([
    { Instanceid: instanceId, Properties: ["Name", "SetTemperature", "ActualTemperature", "Mode"] },
  ]);

  const props = values[instanceId] || {};
  return {
    name: (props.Name as string) || instanceId,
    setTemperature: (props.SetTemperature as number) ?? 0,
    actualTemperature: (props.ActualTemperature as number) ?? 0,
    mode: (props.Mode as number) ?? 0,
  };
}

/**
 * Control climate via WebSocket.
 */
export async function wsControlClimate(
  instanceId: string,
  options: { temperature?: number; mode?: number }
): Promise<void> {
  const client = getWsClient();
  await client.connect();

  if (options.temperature !== undefined) {
    await client.setClimateTemperature(instanceId, options.temperature);
  }
  if (options.mode !== undefined) {
    await client.setClimateMode(instanceId, options.mode);
  }
}

/**
 * Get all home states via WebSocket.
 */
export async function wsGetHomeStates(): Promise<DeviceInstance[]> {
  const client = getWsClient();
  await client.connect();
  return client.getInstances(WS_DEVICE_CLASSES.HOME_STATE);
}

/**
 * Get home state status via WebSocket.
 */
export async function wsGetHomeStateStatus(
  instanceId: string
): Promise<{ name: string; active: boolean }> {
  const client = getWsClient();
  await client.connect();

  const values = await client.getPropertyValues([
    { Instanceid: instanceId, Properties: ["Name", "Active"] },
  ]);

  const props = values[instanceId] || {};
  return {
    name: (props.Name as string) || instanceId,
    active: (props.Active as boolean) ?? false,
  };
}

/**
 * Activate a home state via WebSocket.
 */
export async function wsActivateHomeState(instanceId: string): Promise<void> {
  const client = getWsClient();
  await client.connect();
  await client.setHomeStateActive(instanceId, true);
}

/**
 * Get all bathroom radiators via WebSocket.
 */
export async function wsGetBathroomRadiators(): Promise<DeviceInstance[]> {
  const client = getWsClient();
  await client.connect();
  return client.getInstances(WS_DEVICE_CLASSES.BATHROOM_RADIATOR);
}

/**
 * Get bathroom radiator state via WebSocket.
 */
export async function wsGetBathroomRadiatorState(
  instanceId: string
): Promise<{
  name: string;
  isOn: boolean;
  timerMinutes: number;
  permanentlyOn: boolean;
  permanentlyOff: boolean;
}> {
  const client = getWsClient();
  await client.connect();

  const values = await client.getPropertyValues([
    {
      Instanceid: instanceId,
      Properties: ["Name", "Output", "EnableForMins", "PermanentlyOn", "PermanentlyOff"],
    },
  ]);

  const props = values[instanceId] || {};
  return {
    name: (props.Name as string) || instanceId,
    isOn: (props.Output as boolean) ?? false,
    timerMinutes: (props.EnableForMins as number) ?? 0,
    permanentlyOn: (props.PermanentlyOn as boolean) ?? false,
    permanentlyOff: (props.PermanentlyOff as boolean) ?? false,
  };
}

/**
 * Control bathroom radiator via WebSocket.
 */
export async function wsControlBathroomRadiator(
  instanceId: string,
  options: { on?: boolean; timerMinutes?: number }
): Promise<void> {
  const client = getWsClient();
  await client.connect();

  if (options.on !== undefined) {
    await client.setBathroomRadiatorOn(instanceId, options.on);
  }
  if (options.timerMinutes !== undefined) {
    await client.setBathroomRadiatorTimer(instanceId, options.timerMinutes);
  }
}
