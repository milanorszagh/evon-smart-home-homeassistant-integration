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
    args: ["SC1_M07.Blind1.Open", []],
    methodName: "CallMethod",
    sequenceId: 6
  }
}

// Activate a scene
{
  methodName: "CallWithReturn",
  request: {
    args: ["Scene.MovieMode.Execute", []],
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
| Climate Temperature | ✅ `CallMethod WriteCurrentSetTemperature` | `[instanceId.WriteCurrentSetTemperature, [temp]]` | Same |
| Climate Presets | ✅ `CallMethod WriteDayMode/WriteNightMode/WriteFreezeMode` | `[instanceId.WriteDayMode, []]` (fire-and-forget*) | Same |
| Bathroom Radiator On | ✅ `CallMethod SwitchOneTime` | `[instanceId.SwitchOneTime, []]` | `SwitchOneTime` |
| Bathroom Radiator Off | ✅ `CallMethod Switch` | `[instanceId.Switch, []]` (toggle) | `Switch` |
| Switch On/Off | ❌ Does not work | - | ✅ `AmznTurnOn/Off` |
| Scene Activation | ✅ `CallMethod Execute` | `[instanceId.Execute, []]` | `Execute` |
| Home State | ✅ `CallMethod Activate` | `[instanceId.Activate, []]` | `Activate` |
| Smart Meter | ✅ `RegisterValuesChanged` | Subscribe to IL1-3, UL1N-3N, P1-3, Frequency | Read-only |
| Air Quality | ✅ `RegisterValuesChanged` | Subscribe to Humidity, ActualTemperature, CO2Value | Read-only |
| Valves | ✅ `RegisterValuesChanged` | Subscribe to ActValue | Read-only |

*CallMethod must use format `[instanceId.methodName, params]` (not `[instanceId, methodName, params]`)
*Fire-and-forget: Climate methods don't send MethodReturn response - send and assume success

**Summary:**
- **Lights**: Use `CallMethod SwitchOn/SwitchOff([])` and `BrightnessSetScaled([brightness, 0])`
- **Blinds**: Use `CallMethod Open/Close/Stop([])` and `MoveToPosition([angle, position])`
- **Climate**: Use `CallMethod WriteCurrentSetTemperature([temp])` for temperature, `WriteDayMode/WriteNightMode/WriteFreezeMode` for presets (fire-and-forget)
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

### Test Results (January 2026)

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

**Test Results (January 2026):**

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

**Group Commands (Verified Working - February 2026):**

Blind group commands operate on `Base.bBlind` and control all blinds simultaneously:

```javascript
// ✅ Open all blinds
await ws.send(JSON.stringify({
  methodName: "CallWithReturn",
  request: {
    args: ["Base.bBlind.OpenAll", [null]],
    methodName: "CallMethod",
    sequenceId: seq++
  }
}));

// ✅ Close all blinds
// Base.bBlind.CloseAll([null])

// ✅ Stop all blinds
// Base.bBlind.StopAll([null])
```

**Note:** Group commands use `fire_and_forget` mode - they execute immediately but don't return a `MethodReturn` response. Position feedback comes via WebSocket subscriptions. Measured latency: ~1-2ms via WebSocket vs ~22 seconds via HTTP fallback.

### Climate Control (Verified Working - February 2026)

**Key Discovery:** Climate control requires understanding the READ vs CHANGE distinction:

- **READ (Properties):** `ModeSaved` (ClimateControlUniversal) or `MainState` (ClimateControl) - READ the current mode
- **CHANGE (Methods):** `WriteDayMode`, `WriteNightMode`, `WriteFreezeMode` - CHANGE the preset AND recall its temperature

**⚠️ CRITICAL TRAP:** Using `SetValue` on `ModeSaved` or `MainState` only updates the UI number - it does NOT actually change the preset or target temperature! Always use the CallMethod variants.

**Thermostat Types:**
- `Heating.ClimateControlUniversal` - Bathrooms, uses `ModeSaved` property
- `SmartCOM.Clima.ClimateControl` - Other rooms, uses `MainState` property

**Mode Values:**
- Heating: 2=away, 3=eco, 4=comfort
- Cooling: 5=away, 6=eco, 7=comfort

**Fire-and-Forget Behavior:**
Climate CallMethod operations (`WriteDayMode`, `WriteNightMode`, `WriteFreezeMode`, `WriteCurrentSetTemperature`) do NOT send a `MethodReturn` response. Send the command and assume success - waiting for a response will timeout. The Home Assistant integration uses fire-and-forget mode for these.

**Timing Notes:**
- WebSocket property updates arrive in **~0.8-1.5 seconds** after command
- HTTP API polling is much slower (~5-7 seconds) and can return stale data
- Always prefer WebSocket subscriptions over HTTP polling for state updates

**Home Assistant Integration Notes:**
- Use **optimistic state** for immediate UI feedback (preset changes shown instantly)
- **Do NOT trigger HTTP refresh** after WebSocket commands - it causes race conditions where stale HTTP data overwrites correct WebSocket state
- Subscribe to both `ModeSaved` AND `MainState` properties (different thermostat types use different properties)
- Temperature recall works automatically when switching presets via WebSocket CallMethod

**Temperature Control:**
```javascript
// ✅ Set target temperature for CURRENT preset via CallMethod (fire-and-forget)
await ws.send(JSON.stringify({
  methodName: "CallWithReturn",
  request: {
    args: ["SC1_M06.Thermostat3.WriteCurrentSetTemperature", [23.5]],
    methodName: "CallMethod",
    sequenceId: seq++
  }
}));
// Note: Don't wait for MethodReturn - it won't come

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

**Preset Control (fire-and-forget):**
```javascript
// ✅ Set comfort preset - also recalls comfort temperature
await ws.send(JSON.stringify({
  methodName: "CallWithReturn",
  request: {
    args: ["SC1_M06.Thermostat3.WriteDayMode", []],
    methodName: "CallMethod",
    sequenceId: seq++
  }
}));
// Note: Don't wait for MethodReturn - it won't come

// ✅ Set eco preset - also recalls eco temperature
await ws.send(JSON.stringify({
  methodName: "CallWithReturn",
  request: {
    args: ["SC1_M06.Thermostat3.WriteNightMode", []],
    methodName: "CallMethod",
    sequenceId: seq++
  }
}));

// ✅ Set away/protection preset - also recalls away temperature
await ws.send(JSON.stringify({
  methodName: "CallWithReturn",
  request: {
    args: ["SC1_M06.Thermostat3.WriteFreezeMode", []],
    methodName: "CallMethod",
    sequenceId: seq++
  }
}));

// ❌ TRAP: SetValue on ModeSaved/MainState - DON'T USE FOR CONTROL
// This only updates the UI number, does NOT change preset or temperature!
// await ws.send(JSON.stringify({
//   methodName: "CallWithReturn",
//   request: {
//     args: ["ClimateControlUniversal1.ModeSaved", 3],
//     methodName: "SetValue",
//     sequenceId: seq++
//   }
// }));
```

**Temperature Recall Behavior:**
Each preset remembers its own target temperature. When switching presets:
1. `WriteDayMode` → recalls saved comfort temperature
2. `WriteNightMode` → recalls saved eco temperature
3. `WriteFreezeMode` → recalls saved away/protection temperature
4. `WriteCurrentSetTemperature([temp])` → sets temperature for the CURRENT preset only

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
    args: ["Base.ehThermostat.IsCool", true],
    methodName: "SetValue",
    sequenceId: seq++
  }
}));

// ✅ Set to heating mode (winter)
await ws.send(JSON.stringify({
  methodName: "CallWithReturn",
  request: {
    args: ["Base.ehThermostat.IsCool", false],
    methodName: "SetValue",
    sequenceId: seq++
  }
}));
```

**Test Results (February 2026):**

Tested on:
- `SC1_M05.Thermostat1` (Raumklima WZ, SmartCOM.Clima.ClimateControl) - uses `MainState`
- `ClimateControlUniversal1` (Raumklima Bad 1, Heating.ClimateControlUniversal) - uses `ModeSaved`

| Test | Result | Timing | Observation |
|------|--------|--------|-------------|
| Service call (preset change) | ✅ PASS | 0.01s | Instant with optimistic state |
| WebSocket temp update | ✅ PASS | ~0.8s | Push notification from server |
| CallMethod WriteDayMode | ✅ PASS | fire-and-forget | Preset → comfort + recalls saved temp |
| CallMethod WriteNightMode | ✅ PASS | fire-and-forget | Preset → eco + recalls saved temp |
| CallMethod WriteFreezeMode | ✅ PASS | fire-and-forget | Preset → away + recalls saved temp |
| CallMethod WriteCurrentSetTemperature | ✅ PASS | fire-and-forget | Sets temp for current preset |
| Temperature recall (Living Room) | ✅ PASS | 0.62s | SmartCOM.Clima.ClimateControl |
| Temperature recall (Bathroom) | ✅ PASS | 0.79s | ClimateControlUniversal |
| Global preset (all 6 thermostats) | ✅ PASS | instant | All switch simultaneously |
| SetValue ModeSaved | ❌ TRAP | - | Only updates UI, does NOT change preset! |
| SetValue SetTemperature | ❌ TRAP | - | Only updates UI, does NOT change target! |

**Property Availability by Thermostat Type:**
| Property | SmartCOM.Clima.ClimateControl | Heating.ClimateControlUniversal |
|----------|------------------------------|--------------------------------|
| `MainState` | ✅ Present | ❌ Not present |
| `ModeSaved` | ❌ Not present | ✅ Present |
| `SetTemperature` | ✅ Present | ✅ Present |

**Temperature Range:**
- All thermostats have min_temp=18°C (includes freeze protection range)
- max_temp varies by room and season mode

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

**Test Results (January 2026):**

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
| `S1`, `S2`, `S3`, `Sges` | number | Apparent power (VA) |

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
| `Position` | number | Position (0=open/up, 100=closed/down) |
| `Angle` | number | Slat angle (0-100) |
| `Lock` | boolean | Locked state |
| `Error` | boolean | Error state |
| `Address` | number | Hardware address |
| `Channel` | number | Hardware channel |

### Climate
| Class | Description |
|-------|-------------|
| `SmartCOM.Clima.ClimateControl` | Standard thermostats (uses `MainState` for mode) |
| `Heating.ClimateControlUniversal` | Bathroom thermostats (uses `ModeSaved` for mode) |

**Properties:**
| Property | Type | Description |
|----------|------|-------------|
| `ID` | string | Instance identifier |
| `Name` | string | Display name |
| `SetTemperature` | number | Target temperature (READ ONLY - use WriteCurrentSetTemperature to change) |
| `ActualTemperature` | number | Current temperature |
| `ModeSaved` | number | Current mode for ClimateControlUniversal (READ ONLY) |
| `MainState` | number | Current mode for ClimateControl (READ ONLY) |
| `Humidity` | number | Humidity (if available) |
| `Error` | boolean | Error state |
| `MinSetValueHeat` | number | Min temp for heating mode |
| `MaxSetValueHeat` | number | Max temp for heating mode |
| `MinSetValueCool` | number | Min temp for cooling mode |
| `MaxSetValueCool` | number | Max temp for cooling mode |
| `SetValueFreezeProtection` | number | Away/protection preset temperature |
| `SetValueComfortHeating` | number | Comfort preset temperature (heating) |
| `SetValueEnergySavingHeating` | number | Eco preset temperature (heating) |

**Mode Values (ModeSaved/MainState):**
| Value | Heating | Cooling |
|-------|---------|---------|
| 2 | away | - |
| 3 | eco | - |
| 4 | comfort | - |
| 5 | - | away |
| 6 | - | eco |
| 7 | - | comfort |

**⚠️ Important:** `ModeSaved`, `MainState`, and `SetTemperature` are for READING state only. To CHANGE presets or temperature, use CallMethod with `WriteDayMode`, `WriteNightMode`, `WriteFreezeMode`, or `WriteCurrentSetTemperature`. See "Climate Control" section above.

#### Climate Module Architecture (SmartCOM C1144/C1244)

Evon uses SmartCOM C1144v40 (or C1244) modules for room climate control. Each module supports **4 independent thermostat zones**, but not all zones need to be active. The instance naming follows a fixed pattern:

| Instance Pattern | Zone | Description |
|-----------------|------|-------------|
| `SC1_M{nn}.Thermostat1` | Zone 1 | First thermostat on the module |
| `SC1_M{nn}.Thermostat2` | Zone 2 | Second thermostat (may be unused) |
| `SC1_M{nn}.Thermostat3` | Zone 3 | Third thermostat on the module |
| `SC1_M{nn}.Thermostat4` | Zone 4 | Fourth thermostat (may be unused) |

**Unused zones** have an empty `Name` property and report zero/default values for temperature. The integration correctly ignores these by filtering out instances with empty names during discovery. However, the Evon controller still sends WebSocket `ValuesChanged` events for unused zones — these appear as "unknown instance" in logs and are safely ignored.

Each climate module also has associated input instances:

| Instance Pattern | Class | Description |
|-----------------|-------|-------------|
| `SC1_M{nn}.Input1/3` | `SmartCOM.Clima.RoomControlUnit` | Room control panels (wall-mounted thermostat displays with temperature sensor) |
| `SC1_M{nn}.Input2/4` | `SmartCOM.Digital.DigitalInput` | Lock contacts ("Sperrkontakt") — window/door contact sensors that can disable heating when open |

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

Physical wall buttons ("Taster" in German) use the `SmartCOM.Switch` class. These are the physical push-buttons mounted on walls for controlling lights and blinds.

| Class | Description |
|-------|-------------|
| `SmartCOM.Switch` | Physical wall buttons (light buttons, blind buttons) |
| `Base.bSwitch` | Base switch class |
| `Base.bSwitchUniversal` | Universal switches/buttons |

#### Key Properties (from API)

| Property | Type | Description |
|----------|------|-------------|
| `ID` | string | Instance identifier (e.g., `SC1_M01.Input1`) |
| `Name` | string | Display name (e.g., "Taster Licht Zi3") |
| `ClassName` | string | Always `SmartCOM.Switch` for physical buttons |
| `IsOn` | boolean | Current pressed state |
| `ActValue` | number | Analog value (0 or 1) |
| `Address` | number | Hardware address |
| `Channel` | number | Hardware channel |
| `Line` | number | Hardware line |
| `Group` | string | Room ID |
| `Error` | boolean | Error state |
| `MinLongclick` | number | Long-press threshold in ms (default: 1500) |
| `MaxDblClick` | number | Double-click window in ms (default: 300) |

#### Instance ID Naming Conventions

- **Light buttons**: `SC1_M{nn}.Input{1-4}` — 4 buttons per module
- **Blind buttons**: `SC1_M{nn}.Switch{1-2}Up` / `SC1_M{nn}.Switch{1-2}Down` — paired up/down per blind
- Modules M01-M04 are light modules, M07-M10 are blind modules

#### Button Press Types

Evon hardware supports three press types at the controller level:
- **Single press**: Standard toggle
- **Double press**: Detected within `MaxDblClick` window (default 300ms)
- **Long press**: Detected after `MinLongclick` threshold (default 1500ms)

#### Button Instance ID Patterns

Button instances follow these naming conventions:

| Type | Pattern | Example |
|------|---------|---------|
| Light buttons | `SC1_M{nn}.Input{1-4}` | `SC1_M01.Input1` |
| Blind buttons (up) | `SC1_M{nn}.Switch{1-2}Up` | `SC1_M07.Switch1Up` |
| Blind buttons (down) | `SC1_M{nn}.Switch{1-2}Down` | `SC1_M07.Switch1Down` |

Each SmartCOM module has up to 4 button inputs. Light modules use `Input{1-4}`, blind modules use paired `Switch{n}Up`/`Switch{n}Down`. The number of buttons varies by installation.

### WebSocket Behavior for Physical Switches

#### Confirmed Working (February 2026)

**Physical buttons DO fire WebSocket `ValuesChanged` events.** Subscribing to `IsOn` and `ActValue` properties on button instances reliably detects all button presses.

**How it works:**
- `IsOn = True` when the button is **pressed down**
- `IsOn = False` when the button is **released**
- `ActValue` mirrors `IsOn` (redundant — only `IsOn` is needed)
- Button events arrive **~2 seconds before** the controlled device (light/blind) changes state

**Press type detection via timing:**

| Press Type | Pattern | Duration |
|-----------|---------|----------|
| **Single press** | One True→False cycle | ~190ms |
| **Double press** | See WS patterns below | ~400ms total |
| **Long press** | One True→False cycle | >1500ms (matches `MinLongclick` default) |

**Example events from a single button press:**
```
[17:28:31.680] SC1_M01.Input3.IsOn = True    ← button pressed
[17:28:31.878] SC1_M01.Input3.IsOn = False   ← button released (198ms later)
```

**Double-press WS patterns (Evon controller behavior):**

The Evon controller does **not** always send a clean True→False→True→False sequence for double-press. Testing reveals **3 different patterns**, all of which must be handled:

| Pattern | WS Events | Frequency |
|---------|-----------|-----------|
| **Coalesced release** | True, True, False | ~40% |
| **Coalesced press** | True, False, False | ~40% |
| **Standard 4-event** | True, False, True, False | ~20% |

**Pattern 1: True, True, False** (second True without intervening False):
```
[17:28:37.691] SC1_M01.Input3.IsOn = True    ← press 1
[17:28:37.888] SC1_M01.Input3.IsOn = True    ← press 2 (first release coalesced)
[17:28:38.093] SC1_M01.Input3.IsOn = False   ← final release
```

**Pattern 2: True, False, False** (second False without intervening True):
```
[17:30:03.617] SC1_M01.Input3.IsOn = True    ← press 1
[17:30:03.819] SC1_M01.Input3.IsOn = False   ← release 1
[17:30:04.020] SC1_M01.Input3.IsOn = False   ← release 2 (second press coalesced)
```

**Pattern 3: True, False, True, False** (standard — rare):
```
[17:29:55.989] SC1_M01.Input3.IsOn = True    ← press 1
[17:29:56.196] SC1_M01.Input3.IsOn = False   ← release 1
[17:29:56.391] SC1_M01.Input3.IsOn = True    ← press 2
[17:29:56.590] SC1_M01.Input3.IsOn = False   ← release 2
```

**Example events from a long press:**
```
[17:28:31.680] SC1_M01.Input3.IsOn = True    ← button held down
[17:28:34.080] SC1_M01.Input3.IsOn = False   ← released after ~2400ms
```

**Implementation note:** Because of the coalesced patterns, button press detection must process **every** WS event (not just state changes). A second True while already pressed implies the first release was coalesced. A second False with an active double-click timer implies the second press was coalesced.

**Subscription example:**
```javascript
client.registerValuesChanged([
  { Instanceid: 'SC1_M01.Input1', Properties: ['IsOn'] },
  { Instanceid: 'SC1_M04.Input3', Properties: ['IsOn'] },
], (instanceId, props) => {
  // Implement press type detection — handle ALL 3 WS patterns:
  // - Single: one press+release, no second event within double-click delay (default 0.8s)
  // - Double: two presses within double-click delay (watch for coalesced patterns!)
  // - Long: held >1500ms before release
});
```

**HA integration implementation:** The `ButtonPressDetector` class (`coordinator/button_press.py`) implements this press type detection as a standalone state machine. The double-click delay is user-configurable (0.2–1.4s, default 0.8s) via integration options.

#### Note on Earlier Testing
Initial testing reported 0 events from buttons, likely due to subscribing to incorrect properties (`State`, `Pressed`, `Value`) rather than `IsOn`/`ActValue`. Subscribing to `IsOn` reliably detects all button presses.

#### Alternative: Indirect Detection
You can also detect button presses indirectly by monitoring the devices they control. This is less precise (no press type detection, ~2s delay) but doesn't require subscribing to button instances:

```javascript
client.registerValuesChanged([
  { Instanceid: 'SC1_M01.Light3', Properties: ['IsOn', 'DirectOn'] }
], (instanceId, props) => {
  if (props.IsOn !== undefined) {
    console.log(`Light changed - likely button press`);
  }
});
```

### Other Input Types on Climate Modules (Not Buttons)

Climate modules also have Input instances, but these are **not** physical wall buttons:

| Class | Description |
|-------|-------------|
| `SmartCOM.Clima.RoomControlUnit` | Room control panels (wall-mounted thermostat displays) |
| `SmartCOM.Digital.DigitalInput` | Lock contacts ("Sperrkontakt") — e.g., window contact sensors |

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

## Camera Control (2N Intercom) - Verified Working (February 2026)

The 2N intercom cameras support live feed via WebSocket. The mechanism works by triggering image capture and fetching the result.

### Camera Properties

| Property | Type | Description |
|----------|------|-------------|
| `Image` | string | Path to current image (e.g., `/temp/Intercom2N1000.Cam_img.jpg?rng=...`) |
| `ImageRequest` | boolean | Set to `true` to trigger image capture |
| `Error` | boolean | Connection error status |
| `IPAddress` | string | Camera IP address (internal network) |
| `JPEGUrl` | string | Direct camera URL (requires camera credentials) |
| `Username` | string | Camera username |
| `Password` | string | Camera password |

### Live Feed Flow

1. **Subscribe to camera properties:**
```javascript
await ws.send(JSON.stringify({
  methodName: "CallWithReturn",
  request: {
    args: [true, [{
      Instanceid: "Intercom2N1000.Cam",
      Properties: ["Image", "ImageRequest", "Error"]
    }], false, false],
    methodName: "RegisterValuesChanged",
    sequenceId: 1
  }
}));
```

2. **Trigger image capture:**
```javascript
await ws.send(JSON.stringify({
  methodName: "CallWithReturn",
  request: {
    args: ["Intercom2N1000.Cam.ImageRequest", true],
    methodName: "SetValue",
    sequenceId: 2
  }
}));
```

3. **Wait for `Image` property update** - The `Image` path changes with a new random cache buster (`?rng=...`)

4. **Fetch the image via HTTP:**
```javascript
const imageUrl = `http://${evonHost}${imagePath}`;
const response = await fetch(imageUrl, { cookies: { token } });
const jpeg = await response.blob();
```

### Image Capture Cycle

When `ImageRequest` is set to `true`:
1. Evon fetches a frame from the 2N camera (using stored credentials)
2. Saves it to `/temp/Intercom2N1000.Cam_img.jpg`
3. Updates the `Image` property with a new `?rng=` cache buster
4. Resets `ImageRequest` to `false`

The Evon webapp creates a "live feed" by rapidly repeating this cycle.

### Saved Pictures (Door Entity)

Historical doorbell snapshots are available via the Door entity:

```javascript
// Subscribe to Door entity for saved pictures
await ws.send(JSON.stringify({
  methodName: "CallWithReturn",
  request: {
    args: [true, [{
      Instanceid: "Door7586",
      Properties: ["SavedPictures", "CamInstanceName"]
    }], false, false],
    methodName: "RegisterValuesChanged",
    sequenceId: 1
  }
}));
```

**SavedPictures format:**
```json
[
  {
    "datetime": 1765913625935,
    "imageUrlServer": "./Project/useruploads/snapshots/door/Door7586_xxx_img.jpg",
    "imageUrlClient": "/images/project/snapshots/door/Door7586_xxx_img.jpg"
  },
  ...
]
```

Fetch saved pictures via: `http://{evon-host}{imageUrlClient}` with token cookie.

## See Also

**Home Assistant Integration Files:**
- `custom_components/evon/ws_client.py` - WebSocket client implementation
- `custom_components/evon/ws_control.py` - WebSocket control mappings (canonical WS-native names → WS call format, plus `get_http_method_name()` for HTTP fallback translation)
- `custom_components/evon/ws_mappings.py` - Property subscriptions and data mapping
- `custom_components/evon/api.py` - API client with WebSocket-preferred control, HTTP fallback
- `custom_components/evon/climate.py` - Climate entity with optimistic state

**Test Scripts:**
- `scripts/test-evon-ws-temp-recall.py` - Temperature recall test via WebSocket
- `scripts/test-ha-temp-recall.py` - End-to-end HA climate test
