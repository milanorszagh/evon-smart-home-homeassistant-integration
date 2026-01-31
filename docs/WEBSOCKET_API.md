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
