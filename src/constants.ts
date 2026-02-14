/**
 * Constants for Evon Smart Home MCP Server
 */

// HTTP API device classes (used by api-client.ts)
export const DEVICE_CLASSES = {
  LIGHT: "SmartCOM.Light.LightDim",
  BLIND: "SmartCOM.Blind.Blind",
  CLIMATE: "SmartCOM.Clima.ClimateControl",
  CLIMATE_UNIVERSAL: "ClimateControlUniversal",
  HOME_STATE: "System.HomeState",
  BATHROOM_RADIATOR: "Heating.BathroomRadiator",
} as const;

// WebSocket API device classes (used by ws-client.ts)
// These may differ slightly from HTTP API classes
export const WS_DEVICE_CLASSES = {
  // Lights
  LIGHT: "Base.bLight",
  LIGHT_DIM: "SmartCOM.Light.LightDim",
  LIGHT_RGBW: "SmartCOM.Light.DynamicRGBWLight",
  LIGHT_GROUP: "SmartCOM.Light.LightGroup",

  // Blinds
  BLIND: "Base.bBlind",
  BLIND_SMARTCOM: "SmartCOM.Blind.Blind",
  BLIND_GROUP: "SmartCOM.Blind.BlindGroup",

  // Climate
  CLIMATE: "SmartCOM.Clima.ClimateControl",

  // Home State
  HOME_STATE: "System.HomeState",

  // Heating
  BATHROOM_RADIATOR: "Heating.BathroomRadiator",

  // Inputs
  SWITCH: "Base.bSwitch",
  SWITCH_UNIVERSAL: "Base.bSwitchUniversal",

  // Rooms/Areas
  ROOM: "System.Room",
  AREA: "System.Area",
} as const;

export const BLIND_METHODS = {
  up: { method: "Open", params: [] as unknown[] },
  down: { method: "Close", params: [] as unknown[] },
  stop: { method: "Stop", params: [] as unknown[] },
} as const;

export const CLIMATE_METHODS = {
  comfort: "WriteDayMode",
  eco: "WriteNightMode",
  away: "WriteFreezeMode",
  set_temperature: "WriteCurrentSetTemperature",
} as const;

export const HOME_STATE_IDS = {
  at_home: "HomeStateAtHome",
  holiday: "HomeStateHoliday",
  night: "HomeStateNight",
  work: "HomeStateWork",
} as const;

/**
 * Canonical (WS-native) method names → HTTP API method names.
 * Only the 4 names that differ between WS and HTTP are listed.
 */
export const CANONICAL_TO_HTTP_METHOD: Record<string, string> = {
  SwitchOn: "AmznTurnOn",
  SwitchOff: "AmznTurnOff",
  BrightnessSetScaled: "AmznSetBrightness",
  SetPosition: "AmznSetPercentage",
} as const;

// Resource URIs for MCP resource registration
export const RESOURCE_URIS = {
  LIGHTS: "evon://lights",
  BLINDS: "evon://blinds",
  CLIMATE: "evon://climate",
  HOME_STATE: "evon://home_state",
  BATHROOM_RADIATORS: "evon://bathroom_radiators",
  SUMMARY: "evon://summary",
} as const;

export const API_TIMEOUT_MS = 10000;
// MCP server uses a longer TTL (27 days) since it starts fresh each session.
// The HA integration uses 1 hour (see api.py TOKEN_TTL_SECONDS) because it
// maintains a persistent connection and can re-login cheaply.
export const TOKEN_VALIDITY_DAYS = 27;
