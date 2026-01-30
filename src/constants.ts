/**
 * Constants for Evon Smart Home MCP Server
 */

export const DEVICE_CLASSES = {
  LIGHT: "SmartCOM.Light.LightDim",
  BLIND: "SmartCOM.Blind.Blind",
  CLIMATE: "SmartCOM.Clima.ClimateControl",
  CLIMATE_UNIVERSAL: "ClimateControlUniversal",
  HOME_STATE: "System.HomeState",
  BATHROOM_RADIATOR: "Heating.BathroomRadiator",
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

export const API_TIMEOUT_MS = 10000;
export const TOKEN_VALIDITY_DAYS = 27;
