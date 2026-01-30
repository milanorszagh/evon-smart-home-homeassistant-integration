/**
 * TypeScript type definitions for Evon Smart Home MCP Server
 */

export interface EvonInstance {
  ID: string;
  ClassName: string;
  Name: string;
  Group: string;
}

export interface ApiResponse<T> {
  statusCode: number;
  statusText: string;
  data: T;
}

export interface LightState {
  IsOn?: boolean;
  ScaledBrightness?: number;
  Name?: string;
}

export interface BlindState {
  Position?: number;
  Angle?: number;
  Name?: string;
  IsMoving?: boolean;
}

export interface ClimateState {
  Name?: string;
  SetTemperature?: number;
  ActualTemperature?: number;
}

export interface HomeStateState {
  Name?: string;
  Active?: boolean;
  ActiveInstance?: string;
}

export interface BathroomRadiatorState {
  Name?: string;
  Output?: boolean;
  NextSwitchPoint?: number;
  EnableForMins?: number;
  PermanentlyOn?: boolean;
  PermanentlyOff?: boolean;
  Deactivated?: boolean;
}

// Processed device types with state
export interface LightWithState {
  id: string;
  name: string;
  isOn: boolean;
  brightness: number;
  error?: string;
}

export interface BlindWithState {
  id: string;
  name: string;
  position: number;
  angle: number;
  isMoving: boolean;
  error?: string;
}

export interface ClimateWithState {
  id: string;
  name: string;
  setTemperature: number;
  actualTemperature: number;
  error?: string;
}

export interface HomeStateWithInfo {
  id: string;
  name: string;
  active: boolean;
  error?: string;
}

export interface RadiatorWithState {
  id: string;
  name: string;
  isOn: boolean;
  timeRemaining: string | null;
  timeRemainingMins: number | null;
  durationMins: number;
  permanentlyOn?: boolean;
  permanentlyOff?: boolean;
  error?: string;
}
