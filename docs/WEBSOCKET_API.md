# Evon Smart Home WebSocket API

This document describes the WebSocket API for Evon Smart Home systems, discovered through reverse engineering the web application.

## Overview

The Evon system exposes a WebSocket API that provides:
- **Real-time property subscriptions** - Get notified when device states change
- **Device control** - Set property values to control devices
- **Device discovery** - List all instances of a device type

## Connection

### Endpoint
```
ws://<evon-host>/
```

### WebSocket Protocol
```
Sec-WebSocket-Protocol: echo-protocol
```

### Authentication
Authentication uses a JWT token obtained via HTTP login:

```javascript
// 1. Get token via HTTP
const response = await fetch('http://<evon-host>/login', {
  method: 'POST',
  headers: {
    'x-elocs-username': username,
    'x-elocs-password': encodedPassword,  // Base64(SHA512(username + password))
  },
});
const token = response.headers.get('x-elocs-token');

// 2. Connect WebSocket with token in Cookie
const ws = new WebSocket('ws://<evon-host>/', 'echo-protocol', {
  headers: {
    'Origin': 'http://<evon-host>',
    'Cookie': `token=${token}; x-elocs-isrelay=false`,
  }
});
```

## Message Format

### Request Format
All requests use this structure:
```json
{
  "methodName": "CallWithReturn",
  "request": {
    "args": [...],
    "methodName": "<method>",
    "sequenceId": <number>
  }
}
```

### Response Types

#### 1. Connection Message
Received immediately after connecting:
```json
["Connected", "Connection to server on port: 80 created!", {
  "_userData": {
    "ID": "User985",
    "Name": "User",
    "ClassName": "System.User",
    "Authorization": [
      {"Selector": "#RoomWohnzimmer", "CanView": true},
      ...
    ],
    ...
  }
}]
```

#### 2. Callback (Method Response)
Response to a method call:
```json
["Callback", {
  "args": [<result>],
  "sequenceId": <matching-sequence-id>,
  "methodName": "<method>"
}]
```

#### 3. Event
Asynchronous events (property changes, etc.):
```json
["Event", {
  "methodName": "ValuesChanged",
  "args": [{
    "table": {
      "<instanceId>.<property>": {
        "key": "<instanceId>.<property>",
        "value": {
          "Value": <actual-value>,
          "Type": <type-number>,
          "SetReason": "ValueChanged",
          "SetTime": "2025-01-30T..."
        }
      }
    }
  }]
}]
```

## Available Methods

### GetInstances
List all instances of a device class.

```javascript
// Request
{
  methodName: "CallWithReturn",
  request: {
    args: ["Base.bLight"],
    methodName: "GetInstances",
    sequenceId: 1
  }
}

// Response
["Callback", {
  args: [[
    { ID: "SC1_M01.Light1", Name: "Licht Terrasse", ClassName: "SmartCOM.Light.DynamicRGBWLight", ... },
    { ID: "SC1_M01.Light2", Name: "Licht Zi1", ... },
    ...
  ]],
  sequenceId: 1,
  methodName: "GetInstances"
}]
```

### RegisterValuesChanged
Subscribe to property changes and get initial values.

```javascript
// Request
{
  methodName: "CallWithReturn",
  request: {
    args: [
      true,  // subscribe (false to unsubscribe)
      [
        { Instanceid: "SC1_M01.Light1", Properties: ["IsOn", "Brightness", "ScaledBrightness"] },
        { Instanceid: "SC1_M07.Blind1", Properties: ["Position", "Angle"] }
      ],
      true,  // include initial values
      true   // unknown
    ],
    methodName: "RegisterValuesChanged",
    sequenceId: 2
  }
}

// Initial values come via ValuesChanged event
["Event", {
  methodName: "ValuesChanged",
  args: [{
    table: {
      "SC1_M01.Light1.IsOn": { value: { Value: false, Type: 0 } },
      "SC1_M01.Light1.Brightness": { value: { Value: 82, Type: 1 } },
      ...
    }
  }]
}]
```

### SetValue
Set a property value to control a device.

```javascript
// Turn light on
{
  methodName: "CallWithReturn",
  request: {
    args: ["SC1_M01.Light1.IsOn", true],
    methodName: "SetValue",
    sequenceId: 3
  }
}

// Set brightness to 50%
{
  methodName: "CallWithReturn",
  request: {
    args: ["SC1_M01.Light1.ScaledBrightness", 50],
    methodName: "SetValue",
    sequenceId: 4
  }
}

// Set blind position
{
  methodName: "CallWithReturn",
  request: {
    args: ["SC1_M07.Blind1.Position", 75],
    methodName: "SetValue",
    sequenceId: 5
  }
}
```

### CallMethod
Call a method on an instance. **Note:** This has limited support for device control - see "Device Control" section below.

```javascript
// Open a blind
{
  methodName: "CallWithReturn",
  request: {
    args: ["SC1_M07.Blind1", "Open", []],
    methodName: "CallMethod",
    sequenceId: 6
  }
}

// Activate a scene
{
  methodName: "CallWithReturn",
  request: {
    args: ["Scene.MovieMode", "Execute", []],
    methodName: "CallMethod",
    sequenceId: 7
  }
}
```

## Device Control via WebSocket

### Overview

The Evon WebSocket API supports two mechanisms for device control:
1. **SetValue** - Set a property value directly
2. **CallMethod** - Call a method on an instance

**Important Discovery:** The Evon webapp uses `CallMethod` for all device control. Our testing verified which methods work:

| Operation | WebSocket Method | Format | HTTP Fallback |
|-----------|------------------|--------|---------------|
| Light On | ✅ `CallMethod SwitchOn` | `[instanceId.SwitchOn, []]` | `AmznTurnOn` |
| Light Off | ✅ `CallMethod SwitchOff` | `[instanceId.SwitchOff, []]` | `AmznTurnOff` |
| Light Brightness | ✅ `CallMethod BrightnessSetScaled` | `[instanceId.BrightnessSetScaled, [brightness, transition]]` | `AmznSetBrightness` |
| Blind Open/Close/Stop | ✅ `CallMethod Open/Close/Stop` | `[instanceId.Open, []]` | `Open/Close/Stop` |
| Blind Position | ✅ `CallMethod MoveToPosition` | `[instanceId.MoveToPosition, [angle, position]]` | `AmznSetPercentage` |
| Blind Tilt | ✅ `CallMethod MoveToPosition` | `[instanceId.MoveToPosition, [angle, position]]` | `SetAngle` |
| Climate Temperature | ✅ `SetValue SetTemperature` | `[instanceId, SetTemperature, value]` | `WriteCurrentSetTemperature` |
| Climate Presets | ✅ `CallMethod WriteDayMode/WriteNightMode/WriteFreezeMode` | `[instanceId.WriteDayMode, []]` | Same |
| Bathroom Radiator On | ✅ `CallMethod SwitchOneTime` | `[instanceId.SwitchOneTime, []]` | `SwitchOneTime` |
| Bathroom Radiator Off | ✅ `CallMethod Switch` | `[instanceId.Switch, []]` (toggle) | `Switch` |
| Switch On/Off | ❌ Does not work | - | ✅ `AmznTurnOn/Off` |
| Scene Activation | ✅ `CallMethod Execute` | `[instanceId.Execute, []]` | `Execute` |
| Home State | ✅ `CallMethod Activate` | `[instanceId.Activate, []]` | `Activate` |
| Smart Meter | ✅ `RegisterValuesChanged` | Subscribe to IL1-3, UL1N-3N, P1-3, Frequency | Read-only |
| Air Quality | ✅ `RegisterValuesChanged` | Subscribe to Humidity, ActualTemperature, CO2Value | Read-only |
| Valves | ✅ `RegisterValuesChanged` | Subscribe to ActValue | Read-only |

*CallMethod must use format `[instanceId.methodName, params]` (not `[instanceId, methodName, params]`)

**Summary:**
- **Lights**: Use `CallMethod SwitchOn/SwitchOff([])` and `BrightnessSetScaled([brightness, 0])`
- **Blinds**: Use `CallMethod Open/Close/Stop([])` and `MoveToPosition([angle, position])`
- **Climate**: Use `SetValue SetTemperature` and `CallMethod WriteDayMode/WriteNightMode/WriteFreezeMode`
- **Bathroom Radiators**: Use `CallMethod SwitchOneTime([])` to turn on, `Switch([])` to toggle off
- **Smart Meters**: Subscribe via `RegisterValuesChanged` for real-time power/voltage/current updates
- **Air Quality**: Subscribe via `RegisterValuesChanged` for humidity, temperature, CO2 updates
- **Valves**: Subscribe via `RegisterValuesChanged` for open/closed state updates
- **Switches**: Use HTTP API (WebSocket doesn't trigger hardware)

### Light Control (Verified Working)

The Evon webapp uses `CallMethod` with `SwitchOn`, `SwitchOff`, and `BrightnessSetScaled` methods:

**Turn On/Off:**
```javascript
// Turn light ON via CallMethod SwitchOn (explicit, no toggle)
await ws.send(JSON.stringify({
  methodName: "CallWithReturn",
  request: {
    args: ["SC1_M01.Light3.SwitchOn", []],
    methodName: "CallMethod",
    sequenceId: seq++
  }
}));

// Turn light OFF via CallMethod SwitchOff (explicit, no toggle)
await ws.send(JSON.stringify({
  methodName: "CallWithReturn",
  request: {
    args: ["SC1_M01.Light3.SwitchOff", []],
    methodName: "CallMethod",
    sequenceId: seq++
  }
}));
```

**Note:** `SwitchOn`/`SwitchOff` are preferred over `Switch([bool])` because they are explicit and don't require state tracking. `Switch([bool])` exists but has inconsistent behavior on some devices.

**Set Brightness (0-100%):**
```javascript
// Set brightness to 75% with instant transition (0ms)
await ws.send(JSON.stringify({
  methodName: "CallWithReturn",
  request: {
    args: ["SC1_M01.Light3.BrightnessSetScaled", [75, 0]],
    methodName: "CallMethod",
    sequenceId: seq++
  }
}));
```

**Parameters:**
- `SwitchOn([])` - turn light on (no params, explicit)
- `SwitchOff([])` - turn light off (no params, explicit)
- `BrightnessSetScaled([brightness, transition])` - brightness 0-100, transition time in ms (use 0 for instant)

**Alternative (also works):**
```javascript
// SetValue on IsOn property also works
await ws.send(JSON.stringify({
  methodName: "CallWithReturn",
  request: {
    args: ["SC1_M01.Light3.IsOn", true],
    methodName: "SetValue",
    sequenceId: seq++
  }
}));
```

### Test Results (January 2025)

Tested on: `SC1_M01.Light3` (Licht Zi3, SmartCOM.Light.LightDim)

| Test | Result | Details |
|------|--------|---------|
| CallMethod SwitchOn([]) | ✅ PASS | Light turns on, explicit method |
| CallMethod SwitchOff([]) | ✅ PASS | Light turns off, explicit method |
| CallMethod Switch([true/false]) | ⚠️ WORKS | Inconsistent on some devices, prefer SwitchOn/Off |
| CallMethod BrightnessSetScaled([34, 0]) | ✅ PASS | Brightness changes to 34% |
| CallMethod BrightnessSetScaled([44, 0]) | ✅ PASS | Brightness changes to 44% |
| CallMethod BrightnessSetScaled([84, 0]) | ✅ PASS | Brightness changes to 84% |
| SetValue IsOn=true | ✅ PASS | Also works for on/off |
| SetValue ScaledBrightness=X | ✅ PASS | Also works for brightness |

### Brightness Scale

The brightness scale for lights is **0-100**:
- `0` = Off (when using BrightnessSetScaled, setting to 0 turns off the light)
- `100` = Maximum brightness

**Do NOT use the raw `Brightness` property** - it uses internal scaling that doesn't match the 0-100% range shown in the Evon UI. Always use `ScaledBrightness` or `BrightnessSetScaled`.

### HTTP API Fallback

The HTTP API (`POST /api/instances/{id}/{method}`) remains available as a fallback:
- Works for all device types
- Required when WebSocket is not connected
- Required for switches (WebSocket doesn't trigger hardware)

The integration automatically falls back to HTTP when:
1. WebSocket client is not connected
2. WebSocket control fails
3. Required cache values are not available (e.g., blind angle/position not yet cached)
4. No WebSocket mapping exists for the device/method combination

### Blind Control (Fully via WebSocket)

**Key Discovery:** WebSocket `CallMethod` works for ALL blind operations, including position and tilt!

**The Format:** `CallMethod` with args `[instanceId.methodName, params]`
- Note: The method name is appended to the instance ID with a dot
- This matches the Evon web app's WebSocket protocol

**Open/Close/Stop:**
```javascript
// ✅ Open blind (move up)
await ws.send(JSON.stringify({
  methodName: "CallWithReturn",
  request: {
    args: ["SC1_M09.Blind2.Open", []],
    methodName: "CallMethod",
    sequenceId: seq++
  }
}));

// ✅ Close blind (move down)
await ws.send(JSON.stringify({
  methodName: "CallWithReturn",
  request: {
    args: ["SC1_M09.Blind2.Close", []],
    methodName: "CallMethod",
    sequenceId: seq++
  }
}));

// ✅ Stop blind
await ws.send(JSON.stringify({
  methodName: "CallWithReturn",
  request: {
    args: ["SC1_M09.Blind2.Stop", []],
    methodName: "CallMethod",
    sequenceId: seq++
  }
}));
```

**Position and Tilt Control:**
```javascript
// ✅ Move to specific position and angle
// MoveToPosition([angle, position]) - Note: ANGLE FIRST!
await ws.send(JSON.stringify({
  methodName: "CallWithReturn",
  request: {
    args: ["SC1_M09.Blind2.MoveToPosition", [30, 50]],  // angle=30, position=50
    methodName: "CallMethod",
    sequenceId: seq++
  }
}));
```

**Parameters:**
- `MoveToPosition([angle, position])` - angle is tilt (0-100), position is closure (0=open, 100=closed)
- To change position only: use `MoveToPosition([current_angle, new_position])`
- To change tilt only: use `MoveToPosition([new_angle, current_position])`

**Implementation Note:** The Home Assistant integration caches the current angle and position values so that position-only or tilt-only changes can be made via WebSocket using `MoveToPosition` with the cached counterpart value.

**What Does NOT Work:**
```javascript
// ❌ SetValue on Position - updates value but hardware doesn't move, then reverts
// ❌ Old CallMethod format [instanceId, method, params] - doesn't trigger hardware
```

**Test Results (January 2025):**

Tested on: `SC1_M09.Blind2` (Jal. Zi3 1, SmartCOM.Blind.Blind)

| Test | Result | Observation |
|------|--------|-------------|
| CallMethod `instanceId.Open` | ✅ PASS | Blind moves up |
| CallMethod `instanceId.Close` | ✅ PASS | Blind moves down |
| CallMethod `instanceId.Stop` | ✅ PASS | Blind stops immediately |
| CallMethod `MoveToPosition([angle, pos])` | ✅ PASS | Moves to exact position and tilt |
| CallMethod `MoveToPosition([new_angle, cached_pos])` | ✅ PASS | Changes tilt only |
| CallMethod `MoveToPosition([cached_angle, new_pos])` | ✅ PASS | Changes position only |
| SetValue Position | ❌ FAIL | Value updates but hardware doesn't move |
| Old CallMethod format | ❌ FAIL | Returns success but no hardware movement |

### Climate Control (Verified Working)

**Key Discovery:** Climate control works via both `SetValue` and `CallMethod` operations.

**Temperature Control:**
```javascript
// ✅ Set absolute temperature via SetValue
await ws.send(JSON.stringify({
  methodName: "CallWithReturn",
  request: {
    args: ["SC1_M06.Thermostat3", "SetTemperature", 23.5],
    methodName: "SetValue",
    sequenceId: seq++
  }
}));

// ✅ Alternative: Increment temperature by 0.5°C
await ws.send(JSON.stringify({
  methodName: "CallWithReturn",
  request: {
    args: ["SC1_M06.Thermostat3.IncreaseSetTemperature", []],
    methodName: "CallMethod",
    sequenceId: seq++
  }
}));

// ✅ Decrement temperature by 0.5°C
await ws.send(JSON.stringify({
  methodName: "CallWithReturn",
  request: {
    args: ["SC1_M06.Thermostat3.DecreaseSetTemperature", []],
    methodName: "CallMethod",
    sequenceId: seq++
  }
}));
```

**Preset Control:**
```javascript
// ✅ Set comfort preset via CallMethod WriteDayMode
await ws.send(JSON.stringify({
  methodName: "CallWithReturn",
  request: {
    args: ["SC1_M06.Thermostat3.WriteDayMode", []],
    methodName: "CallMethod",
    sequenceId: seq++
  }
}));

// ✅ Set eco preset via CallMethod WriteNightMode
await ws.send(JSON.stringify({
  methodName: "CallWithReturn",
  request: {
    args: ["SC1_M06.Thermostat3.WriteNightMode", []],
    methodName: "CallMethod",
    sequenceId: seq++
  }
}));

// ✅ Set away/protection preset via CallMethod WriteFreezeMode
await ws.send(JSON.stringify({
  methodName: "CallWithReturn",
  request: {
    args: ["SC1_M06.Thermostat3.WriteFreezeMode", []],
    methodName: "CallMethod",
    sequenceId: seq++
  }
}));

// ✅ Alternative: Set preset via ModeSaved property
// Heating: 2=away, 3=eco, 4=comfort
// Cooling: 5=away, 6=eco, 7=comfort
await ws.send(JSON.stringify({
  methodName: "CallWithReturn",
  request: {
    args: ["ClimateControlUniversal1", "ModeSaved", 3],  // eco mode in heating
    methodName: "SetValue",
    sequenceId: seq++
  }
}));
```

**Global Preset Control (All Thermostats):**
```javascript
// ✅ Set ALL thermostats to comfort mode
await ws.send(JSON.stringify({
  methodName: "CallWithReturn",
  request: {
    args: ["Base.ehThermostat.AllDayMode", []],
    methodName: "CallMethod",
    sequenceId: seq++
  }
}));

// ✅ Set ALL thermostats to eco mode
await ws.send(JSON.stringify({
  methodName: "CallWithReturn",
  request: {
    args: ["Base.ehThermostat.AllNightMode", []],
    methodName: "CallMethod",
    sequenceId: seq++
  }
}));

// ✅ Set ALL thermostats to away/protection mode
await ws.send(JSON.stringify({
  methodName: "CallWithReturn",
  request: {
    args: ["Base.ehThermostat.AllFreezeMode", []],
    methodName: "CallMethod",
    sequenceId: seq++
  }
}));
```

**Season Mode Control:**
```javascript
// ✅ Set to cooling mode (summer)
await ws.send(JSON.stringify({
  methodName: "CallWithReturn",
  request: {
    args: ["Base.ehThermostat", "IsCool", true],
    methodName: "SetValue",
    sequenceId: seq++
  }
}));

// ✅ Set to heating mode (winter)
await ws.send(JSON.stringify({
  methodName: "CallWithReturn",
  request: {
    args: ["Base.ehThermostat", "IsCool", false],
    methodName: "SetValue",
    sequenceId: seq++
  }
}));
```

**Test Results (January 2025):**

Tested on: `SC1_M06.Thermostat3` (Raumklima Zi3, SmartCOM.Clima.ClimateControl)

| Test | Result | Observation |
|------|--------|-------------|
| SetValue SetTemperature | ✅ PASS | Temperature changes immediately |
| CallMethod WriteDayMode | ✅ PASS | Preset changes to comfort |
| CallMethod WriteNightMode | ✅ PASS | Preset changes to eco |
| CallMethod WriteFreezeMode | ✅ PASS | Preset changes to away |
| SetValue ModeSaved | ✅ PASS | Alternative preset method works |
| SetValue IsCool (Base.ehThermostat) | ✅ PASS | Season mode changes globally |

### Bathroom Radiator Control (Verified Working)

**Key Discovery:** Bathroom radiators use `CallMethod` with `SwitchOneTime` for turn on, but `SwitchOff` does NOT work. Use `Switch` (toggle) for turn off with state check.

**Turn On (for configured duration):**
```javascript
// ✅ Turn on radiator via CallMethod SwitchOneTime
await ws.send(JSON.stringify({
  methodName: "CallWithReturn",
  request: {
    args: ["BathroomRadiator9506.SwitchOneTime", []],
    methodName: "CallMethod",
    sequenceId: seq++
  }
}));
```

**Turn Off (via toggle):**
```javascript
// ✅ Toggle radiator via CallMethod Switch (check state first!)
await ws.send(JSON.stringify({
  methodName: "CallWithReturn",
  request: {
    args: ["BathroomRadiator9506.Switch", []],
    methodName: "CallMethod",
    sequenceId: seq++
  }
}));
```

**Important Notes:**
- `SwitchOneTime` is idempotent - calling it when already on restarts the timer
- `SwitchOff` exists but does NOT work (server acknowledges but no hardware effect)
- `Switch` is a toggle - caller must check state first to avoid turning ON when off
- Timer duration is configured in the Evon system, not via API

**Test Results (January 2025):**

Tested on: `BathroomRadiator9506` (Heating.BathroomRadiator)

| Test | Result | Observation |
|------|--------|-------------|
| CallMethod SwitchOneTime([]) | ✅ PASS | Radiator turns on for configured duration |
| CallMethod Switch([]) | ✅ PASS | Toggles radiator state (on→off, off→on) |
| CallMethod SwitchOff([]) | ❌ FAIL | Server acknowledges but no hardware effect |

### Smart Meter Real-time Updates (Verified Working)

Smart meters (`Energy.SmartMeter`) support real-time monitoring via WebSocket subscriptions. This provides instant updates for power consumption without polling.

**Subscribe to Smart Meter:**
```javascript
// Subscribe to real-time power measurements
await ws.send(JSON.stringify({
  methodName: "CallWithReturn",
  request: {
    args: [true, [
      {
        Instanceid: "SmartMeter3006939",
        Properties: [
          "IL1", "IL2", "IL3",        // Current per phase (A)
          "UL1N", "UL2N", "UL3N",     // Voltage per phase (V)
          "Frequency",                 // Grid frequency (Hz)
          "P1", "P2", "P3"            // Active power per phase (W)
        ]
      }
    ], true, true],
    methodName: "RegisterValuesChanged",
    sequenceId: seq++
  }
}));
```

**Available Properties:**
| Property | Type | Description |
|----------|------|-------------|
| `IL1`, `IL2`, `IL3` | number | Current per phase (Amperes) |
| `UL1N`, `UL2N`, `UL3N` | number | Phase-to-neutral voltage (Volts) |
| `UL1L2`, `UL2L3`, `UL3L1` | number | Line-to-line voltage (Volts) |
| `Frequency` | number | Grid frequency (Hz) |
| `P1`, `P2`, `P3` | number | Active power per phase (Watts) |
| `Q1`, `Q2`, `Q3` | number | Reactive power per phase (VAR) |
| `S1`, `S3`, `Sges` | number | Apparent power (VA) |

**Total Power Calculation:**
The total power is computed as `P1 + P2 + P3`. The Home Assistant integration automatically calculates this from the per-phase values received via WebSocket.

**Note:** Smart meters are read-only sensors - there are no control methods available via WebSocket.

### Switch Control (HTTP Only)

**Important:** Switches (`SmartCOM.Switch`, `Base.bSwitch`) do NOT support WebSocket control. All switch commands must use the HTTP API:

```javascript
// ❌ WebSocket SetValue on IsOn - does NOT work for switches
// ❌ WebSocket CallMethod AmznTurnOn - does NOT work for switches
// ✅ Use HTTP API: POST /api/instances/Switch1/AmznTurnOn
```

This is because switches in Evon systems are typically physical relays that require the HTTP API to trigger hardware actions.

## Device Classes

### Lights
| Class | Description |
|-------|-------------|
| `Base.bLight` | Base light class (returns all lights) |
| `SmartCOM.Light.LightDim` | Dimmable lights |
| `SmartCOM.Light.DynamicRGBWLight` | RGBW lights |
| `SmartCOM.Light.LightGroup` | Light groups |

**Properties:**
| Property | Type | Description |
|----------|------|-------------|
| `ID` | string | Instance identifier |
| `Name` | string | Display name |
| `Group` | string | Room ID |
| `IsOn` | boolean | Light on/off state |
| `Brightness` | number | Raw brightness (internal value, avoid using) |
| `ScaledBrightness` | number | **Recommended** - Brightness as percentage (0-100) |

**Important:** Always use `ScaledBrightness` instead of `Brightness` for reading and setting brightness values. The raw `Brightness` property uses internal scaling that doesn't match the 0-100% range shown in the UI. Using `Brightness` instead of `ScaledBrightness` will cause mismatched values between your application and the Evon interface.
| `DirectOn` | boolean | Directly switched on (not via dimming) |
| `ColorTemp` | number | Color temperature |
| `MinColorTemperature` | number | Minimum color temp |
| `MaxColorTemperature` | number | Maximum color temp |
| `IsWarmWhite` | boolean | Warm white mode |
| `Lock` | boolean | Locked state |
| `Error` | boolean | Error state |
| `Address` | number | Hardware address |
| `Channel` | number | Hardware channel |
| `Line` | number | Hardware line |

### Blinds
| Class | Description |
|-------|-------------|
| `Base.bBlind` | Base blind class |
| `SmartCOM.Blind.Blind` | Standard blinds |
| `SmartCOM.Blind.BlindGroup` | Blind groups |

**Properties:**
| Property | Type | Description |
|----------|------|-------------|
| `ID` | string | Instance identifier |
| `Name` | string | Display name |
| `Position` | number | Position (0=closed/up, 100=open/down) |
| `Angle` | number | Slat angle (0-100) |
| `Lock` | boolean | Locked state |
| `Error` | boolean | Error state |
| `Address` | number | Hardware address |
| `Channel` | number | Hardware channel |

### Climate
| Class | Description |
|-------|-------------|
| `SmartCOM.Clima.ClimateControl` | Climate zones/thermostats |

**Properties:**
| Property | Type | Description |
|----------|------|-------------|
| `ID` | string | Instance identifier |
| `Name` | string | Display name |
| `SetTemperature` | number | Target temperature |
| `ActualTemperature` | number | Current temperature |
| `Mode` | number | Climate mode (0=off, 1=comfort, 2=eco, 3=away) |
| `Humidity` | number | Humidity (if available) |
| `Error` | boolean | Error state |

### Home States
| Class | Description |
|-------|-------------|
| `System.HomeState` | Home state presets |

**Known Instances:**
- `HomeStateAtHome` - At home
- `HomeStateHoliday` - Holiday/vacation
- `HomeStateNight` - Night mode
- `HomeStateWork` - Away at work

**Properties:**
| Property | Type | Description |
|----------|------|-------------|
| `ID` | string | Instance identifier |
| `Name` | string | Display name |
| `Active` | boolean | Currently active state |

### Bathroom Radiators
| Class | Description |
|-------|-------------|
| `Heating.BathroomRadiator` | Electric bathroom radiators |

**Properties:**
| Property | Type | Description |
|----------|------|-------------|
| `ID` | string | Instance identifier |
| `Name` | string | Display name |
| `Output` | boolean | Heater on/off |
| `EnableForMins` | number | Timer duration in minutes |
| `NextSwitchPoint` | number | Next scheduled switch time |
| `PermanentlyOn` | boolean | Permanently on mode |
| `PermanentlyOff` | boolean | Permanently off mode |
| `Deactivated` | boolean | Deactivated |

### Security Doors & Intercoms

Unlike physical switches, security doors and intercoms **DO expose real-time state** via WebSocket.

| Class | Description |
|-------|-------------|
| `Security.Door` | Entry doors with intercom integration |
| `Security.Intercom.2N.Intercom2N` | 2N branded intercoms |
| `Base.bSwitch` (Intercom.DoorSwitch) | Doorbell button on intercom |

**Security.Door Properties:**
| Property | Type | Description |
|----------|------|-------------|
| `ID` | string | Instance identifier (e.g., `Door7586`) |
| `Name` | string | Display name (e.g., "Eingangstür") |
| `IsOpen` | boolean | Door open/closed state ✅ |
| `DoorIsOpen` | boolean | Alternative door open indicator ✅ |
| `CallInProgress` | boolean | Intercom call active ✅ |
| `DoorOpenTime` | number | Time door has been open |
| `DoorBellMelodyTime` | number | Doorbell melody duration |
| `IntercomInstanceName` | string | Linked intercom instance |
| `CamInstanceName` | string | Linked camera instance |
| `SavedPictures` | array | Doorbell snapshot history |

**Intercom Properties (e.g., `Intercom2N1000`):**
| Property | Type | Description |
|----------|------|-------------|
| `DoorBellTriggered` | boolean | Doorbell ring event ✅ |
| `DoorOpenTriggered` | boolean | Door open event ✅ |
| `IsDoorOpen` | boolean | Door state from intercom ✅ |
| `ConnectionToIntercomHasBeenLost` | boolean | Connection status |
| `ErrorCode` | number | Error code (999 = OK) |
| `HasCam` | boolean | Camera available |

**Doorbell Switch Properties (e.g., `Intercom2N1000.DoorSwitch`):**
| Property | Type | Description |
|----------|------|-------------|
| `IsOn` | boolean | Button pressed state ✅ |
| `ActValue` | boolean | Actual value |
| `Error` | boolean | Error state |

**Example: Monitor Entry Door Events**
```javascript
client.registerValuesChanged([
  { Instanceid: 'Door7586', Properties: ['IsOpen', 'DoorIsOpen', 'CallInProgress'] },
  { Instanceid: 'Intercom2N1000', Properties: ['DoorBellTriggered', 'DoorOpenTriggered'] },
  { Instanceid: 'Intercom2N1000.DoorSwitch', Properties: ['IsOn'] }
], (instanceId, props) => {
  if (props.DoorBellTriggered === true) {
    console.log('🔔 Doorbell rang!');
  }
  if (props.IsOpen === true) {
    console.log('🚪 Door opened!');
  }
});
```

See `ws-security-door.mjs` for a complete test implementation.

### Physical Switches (Taster)
| Class | Description |
|-------|-------------|
| `Base.bSwitch` | Base switch class |
| `Base.bSwitchUniversal` | Universal switches/buttons |

**⚠️ Important Finding:** Physical wall switches (Taster) do NOT expose dynamic state properties. They only have static configuration:

| Property | Type | Description |
|----------|------|-------------|
| `ID` | string | Instance identifier |
| `Name` | string | Display name (e.g., "Taster Licht Zi3") |
| `Group` | string | Room ID |
| `Error` | boolean | Error state |
| `Address` | number | Hardware address |
| `Channel` | number | Hardware channel |
| `Line` | number | Hardware line |

**No `Pressed`, `State`, or `Value` properties exist.** See "Physical Switches" section below for details.

## Physical Switches (Taster) - Detailed Findings

### The Problem
Physical wall switches ("Taster" in German) in Evon systems are **action triggers**, not stateful devices. When you press a button:

1. The button sends a signal to the Evon controller
2. The controller executes the pre-configured action (toggle light, dim, etc.)
3. The target device state changes
4. **The button press itself is NOT exposed** via the WebSocket API

### Why This Happens
This is typical for KNX and building automation systems. The button-to-device mapping is configured at the controller level, and the API only exposes the resulting device states, not the input events.

### Workaround: Indirect Detection
You can detect button presses by monitoring the devices they control:

```javascript
// Monitor light state changes
client.registerValuesChanged([
  { Instanceid: 'SC1_M01.Light3', Properties: ['IsOn', 'DirectOn'] }
], (instanceId, props) => {
  if (props.IsOn !== undefined) {
    console.log(`Light changed - likely button press on "Taster Licht Zi3"`);
  }
});
```

### Switch-to-Light Mapping (Example)
| Switch ID | Switch Name | Controls |
|-----------|-------------|----------|
| `SC1_M01.Input1` | Taster Licht Terrasse | `SC1_M01.Light1` |
| `SC1_M01.Input2` | Taster Licht Zi1 | `SC1_M01.Light2` |
| `SC1_M01.Input3` | Taster Licht Zi3 | `SC1_M01.Light3` |
| `SC1_M01.Input4` | Taster Licht Bad 2 | `SC1_M01.Light4` |
| `SC1_M02.Input1` | Taster Licht WC | `SC1_M02.Light1` |
| `SC1_M02.Input2` | Taster Wandlicht Vorraum | `SC1_M02.Light2` |
| `SC1_M02.Input3` | Taster Licht Bad | `SC1_M02.Light3` |
| `SC1_M02.Input4` | Taster LED Vorraum | `SC1_M02.Light4` |

### Methods Tested (All Failed to Return Button Events)
- `RegisterValuesChanged` with various property names (`State`, `Pressed`, `Value`, `Active`, etc.)
- `GetPropertyNames` - returned nothing
- `GetMethods` - returned nothing
- `SubscribeEvents` - returned nothing
- `Subscribe` - returned nothing

### Future Investigation
- Check if there's a separate event stream for inputs
- Investigate if admin users have access to additional APIs
- Look for system-level event logs

**Note:** The doorbell switch (`Intercom2N1000.DoorSwitch`) DOES expose state - see "Security Doors & Intercoms" section above.

## Value Types
| Type | Description |
|------|-------------|
| 0 | Boolean |
| 1 | Number (integer) |
| 2 | String |
| 10 | Localized string |

## Usage Example

```javascript
import { WebSocket } from 'ws';

const ws = new WebSocket('ws://192.168.1.4/', 'echo-protocol', {
  headers: {
    'Origin': 'http://192.168.1.4',
    'Cookie': `token=${token}`,
  }
});

let seq = 1;

ws.on('open', () => {
  // Subscribe to a light
  ws.send(JSON.stringify({
    methodName: "CallWithReturn",
    request: {
      args: [true, [
        { Instanceid: 'SC1_M01.Light1', Properties: ['IsOn', 'ScaledBrightness'] }
      ], true, true],
      methodName: "RegisterValuesChanged",
      sequenceId: seq++
    }
  }));
});

ws.on('message', (data) => {
  const [type, payload] = JSON.parse(data);

  if (type === 'Event' && payload?.methodName === 'ValuesChanged') {
    const table = payload.args[0].table;
    for (const [key, entry] of Object.entries(table)) {
      console.log(`${key} = ${entry.value.Value}`);
    }
  }
});

// Turn light on
ws.send(JSON.stringify({
  methodName: "CallWithReturn",
  request: {
    args: ["SC1_M01.Light1.IsOn", true],
    methodName: "SetValue",
    sequenceId: seq++
  }
}));
```

## See Also

- `src/ws-client.ts` - TypeScript WebSocket client implementation
- `ws-switch-listener.mjs` - Test script for exploring physical switch events
- `ws-security-door.mjs` - Test script for security door and doorbell events
- `src/api-client.ts` - HTTP API client (alternative to WebSocket)
