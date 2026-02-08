# Development Guide

This document provides architecture details, API reference, and development guidelines for contributors working on the Evon Smart Home integration.

For AI agents, see [AGENTS.md](AGENTS.md) which contains critical API knowledge and debugging tips.

---

## Architecture Overview

### Home Assistant Integration

```
custom_components/evon/
├── __init__.py          # Entry point, platform setup, stale entity cleanup
├── api.py               # Evon HTTP/WebSocket API client with WS-first control
├── ws_client.py         # WebSocket client for real-time updates and control
├── ws_control.py        # WebSocket control mappings (methods that work via WS)
├── ws_mappings.py       # Property mappings for WebSocket data
├── base_entity.py       # Base entity class with common functionality
├── config_flow.py       # Configuration UI flows (setup, options, reconfigure, repairs)
├── const.py             # Constants, device classes, repair identifiers
├── coordinator/         # Data update coordinator package
│   ├── __init__.py      # Main coordinator with connection failure tracking, WebSocket integration
│   └── processors/      # Device-specific data processors
│       ├── __init__.py
│       ├── lights.py
│       ├── blinds.py
│       ├── climate.py
│       ├── switches.py
│       ├── smart_meters.py
│       ├── air_quality.py
│       ├── valves.py
│       ├── home_states.py
│       ├── bathroom_radiators.py
│       ├── scenes.py
│       ├── security_doors.py
│       ├── intercoms.py
│       └── cameras.py
├── light.py             # Light platform
├── cover.py             # Cover/blind platform
├── climate.py           # Climate platform
├── sensor.py            # Sensor platform (temperature, energy, air quality)
├── switch.py            # Switch platform (relays, bathroom radiators)
├── select.py            # Select platform (home state, season mode)
├── binary_sensor.py     # Binary sensor platform (valves, security doors, intercoms)
├── button.py            # Button platform (scenes)
├── camera.py            # Camera platform (2N intercoms)
├── camera_recorder.py   # Camera recording manager (snapshot → MP4)
├── image.py             # Image platform (doorbell snapshots)
├── device_trigger.py    # Device triggers (doorbell press)
├── statistics.py        # External energy statistics import
├── diagnostics.py       # Diagnostics data export
├── strings.json         # UI strings
└── translations/        # Localization files (en.json, de.json)
```

### MCP Server

```
src/
├── index.ts             # MCP server entry point
├── api-client.ts        # Evon HTTP API client
├── ws-client.ts         # Evon WebSocket client (real-time)
├── config.ts            # Environment configuration
├── constants.ts         # Shared constants (HTTP + WS device classes)
├── helpers.ts           # Utility functions
├── types.ts             # TypeScript type definitions
├── tools/               # MCP tool implementations
│   ├── index.ts         # Tool exports and registration
│   ├── lights.ts        # Light control tools
│   ├── blinds.ts        # Blind control tools
│   ├── climate.ts       # Climate control tools
│   ├── home-state.ts    # Home state tools
│   ├── radiators.ts     # Bathroom radiator tools
│   ├── sensors.ts       # Sensor listing tools
│   └── generic.ts       # Generic helper tools
└── resources/           # MCP resource implementations
    ├── index.ts         # Resource exports and registration
    ├── lights.ts        # Light resources
    ├── blinds.ts        # Blind resources
    ├── climate.ts       # Climate resources
    ├── home-state.ts    # Home state resources
    ├── radiators.ts     # Radiator resources
    └── summary.ts       # Home summary resource
```

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         HOME ASSISTANT INTEGRATION                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────┐    ┌──────────────────────────────────────────────────┐  │
│  │  Config Flow │───►│              COORDINATOR                         │  │
│  └──────────────┘    │  • Manages device data                           │  │
│                      │  • Notifies entities on updates                  │  │
│                      │  • Tracks connection health                      │  │
│                      └──────────────────────────────────────────────────┘  │
│                                      │                                      │
│                      ┌───────────────┴───────────────┐                      │
│                      ▼                               ▼                      │
│  ┌─────────────────────────────┐   ┌─────────────────────────────┐         │
│  │      WebSocket Client       │   │       HTTP API Client       │         │
│  │  (ws_client.py)             │   │  (api.py)                   │         │
│  │                             │   │                             │         │
│  │  ┌─────────────────────┐    │   │  • Initial data fetch       │         │
│  │  │ State Updates (IN)  │◄───┼───┼─── Fallback polling (60s)   │         │
│  │  │ • ValuesChanged     │    │   │                             │         │
│  │  │ • <100ms latency    │    │   │  • Fallback control         │         │
│  │  └─────────────────────┘    │   │  • Auth & token refresh     │         │
│  │                             │   └─────────────────────────────┘         │
│  │  ┌─────────────────────┐    │                                           │
│  │  │ Device Control (OUT)│    │   ws_control.py: Method mappings          │
│  │  │ • CallMethod        │    │   ws_mappings.py: Property mappings       │
│  │  │ • <50ms response    │    │                                           │
│  │  └─────────────────────┘    │                                           │
│  └─────────────────────────────┘                                           │
│                      │                                                      │
└──────────────────────┼──────────────────────────────────────────────────────┘
                       │
                       ▼ Persistent bidirectional connection
┌──────────────────────────────────────────────────────────────────────────────┐
│                            EVON SMART HOME                                   │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐    │
│  │ Lights  │ │ Blinds  │ │ Climate │ │ Sensors │ │ Doors   │ │ Groups  │    │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘    │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Data Flow

**With WebSocket (default, recommended):**
```
STARTUP:
1. config_flow.py validates credentials with HTTP API
2. __init__.py creates API client, coordinator, and WebSocket client
3. coordinator.py fetches initial data via HTTP
4. ws_client.py connects and subscribes to all device properties
5. Platform files create entities from coordinator data

REAL-TIME UPDATES (state changes from wall switches, etc.):
6. Evon sends ValuesChanged event via WebSocket (<100ms)
7. ws_mappings.py converts WS property names to coordinator format
8. coordinator.py updates entity data and notifies listeners
9. Entity UI updates instantly

DEVICE CONTROL (user taps light in HA):
10. Entity calls api.py control method
11. api.py sends command via WebSocket (ws_control.py mapping)
12. Evon executes command (<50ms response)
13. Optimistic update shows instant UI feedback
14. WebSocket confirms actual state

FALLBACK:
• HTTP polling continues at 60s as safety net
• If WebSocket unavailable, control falls back to HTTP automatically
```

**HTTP Only (when "Use HTTP API only" is enabled):**
```
1. User adds integration via config flow
2. config_flow.py validates credentials with API
3. __init__.py creates API client and coordinator
4. coordinator.py fetches all device data periodically (30s)
5. Platform files create entities from coordinator data
6. Entities read state from coordinator.data
7. Entities call HTTP API methods for control actions
8. Optimistic updates provide instant UI feedback
```

---

## MCP Server Setup

The MCP server allows AI assistants like Claude to control Evon devices directly.

### Installation

```bash
git clone https://github.com/milanorszagh/evon-smart-home-homeassistant-integration.git
cd evon-ha
npm install
npm run build
```

### Configuration

**Option 1: Using `.env` file (recommended)**

Keep credentials in `.env` (single source of truth):

```bash
# In your .env file
EVON_HOST=http://192.168.x.x
EVON_USERNAME=your-username
EVON_PASSWORD=your-password
```

Add to `~/.claude.json` without inline credentials:

```json
{
  "mcpServers": {
    "evon": {
      "command": "/bin/bash",
      "args": ["-c", "source /path/to/evon-ha/.env && node /path/to/evon-ha/dist/index.js"]
    }
  }
}
```

**Option 2: Inline credentials**

Add credentials directly to `~/.claude.json`:

```json
{
  "mcpServers": {
    "evon": {
      "command": "node",
      "args": ["/path/to/evon-ha/dist/index.js"],
      "env": {
        "EVON_HOST": "http://192.168.x.x",
        "EVON_USERNAME": "your-username",
        "EVON_PASSWORD": "your-password"
      }
    }
  }
}
```

The server auto-detects plain text or encoded passwords.

### Available Tools

| Tool | Description |
|------|-------------|
| `list_apps` | List all available apps in the system |
| `list_instances` | List all instances (devices, sensors, logic blocks) with optional filter |
| `get_instance` | Get detailed properties of a specific instance |
| `get_property` | Get a specific property value of an instance |
| `call_method` | Call a method on an instance (use specific tools for common operations) |
| `list_lights` | List all lights with current state |
| `light_control` | Control a single light (on/off/brightness) |
| `light_control_all` | Control all lights at once |
| `list_blinds` | List all blinds with current state |
| `blind_control` | Control a single blind (position/angle/up/down/stop) |
| `blind_control_all` | Control all blinds at once |
| `list_climate` | List all climate controls with current state |
| `climate_control` | Control a single climate zone (comfort/eco/away/set_temperature) |
| `climate_control_all` | Control all climate zones at once |
| `list_home_states` | List all home states with active status |
| `set_home_state` | Set the active home state |
| `list_sensors` | List temperature and other sensors |
| `list_bathroom_radiators` | List all bathroom radiators |
| `bathroom_radiator_control` | Control a bathroom radiator (on/off/toggle) |

### Available Resources

| Resource URI | Description |
|--------------|-------------|
| `evon://lights` | All lights with current state |
| `evon://blinds` | All blinds with current state |
| `evon://climate` | All climate controls with state |
| `evon://home_state` | Current and available home states |
| `evon://bathroom_radiators` | All bathroom radiators |
| `evon://summary` | Home summary (counts, avg temp, state) |

---

## WebSocket Client

The MCP server includes a WebSocket client (`src/ws-client.ts`) for real-time communication with Evon systems.

### Architecture

```
src/
├── ws-client.ts         # WebSocket client with device helpers
└── constants.ts         # Device class constants (WS_DEVICE_CLASSES)
```

### Features

| Feature | Description |
|---------|-------------|
| **Real-time subscriptions** | Get instant notifications when device states change |
| **Lower latency** | Faster than HTTP API for device control |
| **Batch queries** | Request multiple device properties in a single call |
| **Automatic reconnection** | Handles connection drops gracefully |
| **Connection deduplication** | Concurrent connect/login calls are coalesced into a single request |
| **Parallel bulk control** | `controlAllDevices` sends commands in parallel via `Promise.all` |

### Usage

```typescript
import { getWsClient, wsGetLights, wsControlLight } from './dist/ws-client.js';

// Get singleton client
const client = getWsClient();
await client.connect();

// Get all lights
const lights = await wsGetLights();

// Control a light
await wsControlLight('SC1_M01.Light1', { on: true, brightness: 75 });

// Subscribe to real-time changes
client.registerValuesChanged([
  { Instanceid: 'SC1_M01.Light1', Properties: ['IsOn', 'Brightness'] }
], (instanceId, props) => {
  console.log(`${instanceId} changed:`, props);
});
```

### Available Methods

| Method | Description |
|--------|-------------|
| `connect()` | Connect to WebSocket server |
| `disconnect()` | Close connection |
| `getInstances(className)` | List all instances of a device class |
| `registerValuesChanged(subs, callback)` | Subscribe to property changes |
| `setValue(path, value)` | Set a device property |
| `setLightOn(id, on)` | Turn light on/off |
| `setLightBrightness(id, brightness)` | Set light brightness (0-100) |
| `setBlindPosition(id, position)` | Set blind position (0-100) |
| `setClimateTemperature(id, temp)` | Set target temperature |
| `setHomeStateActive(id, active)` | Activate home state |
| `setBathroomRadiatorOn(id, on)` | Control bathroom radiator |

### Convenience Functions

| Function | Description |
|----------|-------------|
| `wsGetLights()` | Get all lights with state |
| `wsGetBlinds()` | Get all blinds with state |
| `wsGetClimateZones()` | Get all climate zones |
| `wsGetHomeStates()` | Get all home states |
| `wsControlLight(id, opts)` | Control light with options |
| `wsControlBlind(id, opts)` | Control blind with options |

See [docs/WEBSOCKET_API.md](docs/WEBSOCKET_API.md) for detailed protocol documentation.

---

## Home Assistant WebSocket Integration

The Home Assistant integration includes a Python WebSocket client (`ws_client.py`) for real-time updates.

### Architecture

```
ws_client.py       # WebSocket client with reconnection logic
ws_mappings.py     # Property mappings (WS → coordinator format)
coordinator/       # Integrates WebSocket with data updates
```

### How It Works

1. **Connection**: HTTP login → get token → WebSocket connect with token in Cookie
2. **Subscription**: `RegisterValuesChanged` for all tracked devices
3. **Events**: `ValuesChanged` events trigger coordinator data updates
4. **Reconnection**: Exponential backoff (5s → 300s max) on disconnect
5. **Fallback**: HTTP polling resumes at normal rate when WS disconnects

### Property Mappings

| Entity Type | WebSocket Properties | Key Coordinator Mappings |
|-------------|---------------------|--------------------------|
| lights | `IsOn`, `ScaledBrightness`, `ColorTemp`, `MinColorTemperature`, `MaxColorTemperature` | `is_on`, `brightness`, `color_temp` |
| blinds | `Position`, `Angle` | `position`, `angle` |
| climates | `SetTemperature`, `ActualTemperature`, `ModeSaved`, `MainState`, `IsOn`, `Mode`, `Humidity`, `CoolingMode`, `DisableCooling`, + heating/cooling setpoints and limits | `target_temperature`, `current_temperature`, `mode_saved` (both `ModeSaved` and `MainState` map here), `humidity` |
| switches | `IsOn`, `State` | `is_on` |
| home_states | `Active` | `active` |
| bathroom_radiators | `Output`, `NextSwitchPoint` | `is_on`, `time_remaining` |
| smart_meters | `P1`, `P2`, `P3`, `IL1-3`, `UL1N-3N`, `Frequency`, `Energy`, `Energy24h`, `EnergyDataDay/Month/Year`, `FeedInEnergy`, `FeedIn24h`, `FeedInDataMonth` | `power` (computed P1+P2+P3), per-phase values, energy totals |
| air_quality | `Humidity`, `ActualTemperature`, `CO2Value` | `humidity`, `temperature`, `co2` |
| valves | `ActValue` | `position` |
| security_doors | `IsOpen`, `DoorIsOpen`, `CallInProgress`, `SavedPictures`, `CamInstanceName` | `is_open`, `door_is_open`, `call_in_progress`, `saved_pictures` |
| intercoms | `DoorBellTriggered`, `DoorOpenTriggered`, `IsDoorOpen`, `ConnectionToIntercomHasBeenLost` | `doorbell_triggered`, `is_door_open`, `connection_lost` |
| cameras | `Image`, `ImageRequest`, `Error` | `image_path` |

### Constants

```python
# WebSocket configuration
CONF_HTTP_ONLY = "http_only"
DEFAULT_HTTP_ONLY = False              # WebSocket enabled by default (recommended)
DEFAULT_WS_RECONNECT_DELAY = 5         # Initial reconnect delay (seconds)
WS_RECONNECT_JITTER = 0.25            # Jitter factor for reconnect delays (0.0 to 1.0)
WS_RECONNECT_MAX_DELAY = 300           # Max reconnect delay (seconds)
WS_PROTOCOL = "echo-protocol"          # WebSocket sub-protocol
WS_POLL_INTERVAL = 60                  # Safety net poll interval when WS connected
WS_HEARTBEAT_INTERVAL = 30             # WebSocket heartbeat/ping interval (seconds)
WS_DEFAULT_REQUEST_TIMEOUT = 10.0      # Default timeout for WS RPC requests (seconds)
WS_SUBSCRIBE_REQUEST_TIMEOUT = 30.0    # Timeout for subscription requests (many devices)
WS_LOG_MESSAGE_TRUNCATE = 500          # Max characters to log from WS messages
WS_MAX_PENDING_REQUESTS = 100          # Maximum pending WS requests before rejecting new ones

# Optimistic state and animation timing
LIGHT_IDENTIFY_ANIMATION_DELAY = 3.0   # Light identification animation timing (seconds)
OPTIMISTIC_SETTLING_PERIOD = 2.5       # Window to ignore WS updates after control action
OPTIMISTIC_SETTLING_PERIOD_SHORT = 1.0 # Shorter settling for bathroom radiators (no animation)
OPTIMISTIC_STATE_TIMEOUT = 30.0        # Clears stale optimistic state on network recovery
OPTIMISTIC_STATE_TOLERANCE = 2         # Small rounding differences tolerance
COVER_STOP_DELAY = 0.3                 # Delay after cover stop for UI update (seconds)
CAMERA_IMAGE_UPDATE_TIMEOUT = 5.0      # Wait for WS image_path update after ImageRequest (seconds)
IMAGE_FETCH_TIMEOUT = 10               # Timeout for fetching images from Evon server (seconds)
```

**Note:** The setting is inverted - `http_only = False` means WebSocket is enabled. This allows users to disable WebSocket (by checking "Use HTTP API only") if they experience connection issues, while keeping WebSocket as the recommended default.

### Implementation Notes

**Subscription Timing:** The WebSocket client must schedule resubscription as a background task after `_wait_for_connected()` returns, not inside it. This is because the message loop (`_handle_messages()`) only runs after `_wait_for_connected()` completes. If you call `_resubscribe()` synchronously inside `_wait_for_connected()`, the subscription request will timeout because there's no message loop running to process the `Callback` response.

```python
# CORRECT: Schedule resubscription in _run_loop after _wait_for_connected returns
async def _run_loop(self):
    if await self.connect():
        await self._wait_for_connected()
        if self._connected and self._subscriptions:
            asyncio.create_task(self._resubscribe())  # Background task
    await self._handle_messages()  # Now running to process responses

# WRONG: Don't resubscribe inside _wait_for_connected
async def _wait_for_connected(self):
    # ... handle Connected message ...
    await self._resubscribe()  # Will timeout! No message loop running yet
```

**Subscription Timeout:** For systems with many devices (50+), the `RegisterValuesChanged` request can take longer to process. Use a 30-second timeout instead of the default 10 seconds.

**Brightness Property:** Always subscribe to `ScaledBrightness` (0-100 percentage) instead of `Brightness` (raw internal value). Using the wrong property causes brightness mismatches between Home Assistant and the Evon UI.

### Testing

```bash
# Run WebSocket unit tests
pytest tests/test_ws_client.py -v
```

---

## Evon API Reference

### Connection Types

The Evon API supports two connection methods:

| Type | URL | Use Case |
|------|-----|----------|
| **Local** | `http://{local-ip}` | Direct LAN connection (faster, recommended) |
| **Remote** | `https://my.evon-smarthome.com` | Internet access via Evon relay server |

### Authentication

#### Local Authentication

```
POST http://{local-ip}/login
Headers:
  x-elocs-username: <username>
  x-elocs-password: <encoded-password>

Response Headers:
  x-elocs-token: <session-token>
```

#### Remote Authentication

Remote access uses a relay server that routes requests to your local Evon system.

```
POST https://my.evon-smarthome.com/login
Headers:
  x-elocs-username: <username>
  x-elocs-password: <encoded-password>
  x-elocs-relayid: <engine-id>
  x-elocs-sessionlogin: true
  X-Requested-With: XMLHttpRequest

Response Headers:
  x-elocs-token: <session-token>
```

**Key Differences from Local:**
- Login URL is at the remote host root (`/login`), NOT `/{engine-id}/login`
- Requires `x-elocs-relayid` header with your Engine ID
- Requires `x-elocs-sessionlogin: true` header for session-based auth
- Requires `X-Requested-With: XMLHttpRequest` header

**Engine ID:** Found in your Evon system settings. This identifies your installation on the relay server.
- Format: 4-12 alphanumeric characters (e.g., `985315`)
- Validated in both config flow and API client
- Used in the URL path for API requests: `https://my.evon-smarthome.com/{engine_id}/api/...`

**Password Encoding:**
```
x-elocs-password = Base64(SHA512(username + password))
```

```python
import hashlib, base64
encoded = base64.b64encode(
    hashlib.sha512((username + password).encode()).digest()
).decode()
```

Both integrations handle encoding automatically - just provide plain text passwords.

### API Endpoints

After authentication, API calls differ by connection type:

| Type | Base URL |
|------|----------|
| Local | `http://{local-ip}/api` |
| Remote | `https://my.evon-smarthome.com/{engine-id}/api` |

The remote relay server proxies all `/api/*` requests to your local Evon system.

### Endpoints

All requests require: `Cookie: token=<token>`

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/login` | POST | Authenticate and get token |
| `/api/instances` | GET | List all device instances |
| `/api/instances/{id}` | GET | Get device details |
| `/api/instances/{id}/{method}` | POST | Call method on device |
| `/api/instances/{id}/{property}` | PUT | Set property value |

### Device Classes

| Class Name | Type | Controllable |
|------------|------|--------------|
| `SmartCOM.Light.LightDim` | Dimmable light | Yes |
| `SmartCOM.Light.Light` | Relay output (processed as **switch**) | Yes |
| `SmartCOM.Light.DynamicRGBWLight` | RGBW light | Yes |
| `SmartCOM.Light.LightGroup` | Light group | Yes |
| `SmartCOM.Blind.Blind` | Blind/shutter | Yes |
| `SmartCOM.Blind.BlindGroup` | Blind group | Yes |
| `SmartCOM.Clima.ClimateControl` | Climate control | Yes |
| `Heating.ClimateControlUniversal` | Universal climate (substring match) | Yes |
| `Base.ehThermostat` | Season mode | Yes |
| `System.HomeState` | Home state | Yes |
| `Heating.BathroomRadiator` | Bathroom heater | Yes |
| `SmartCOM.Switch` | Physical button | **No** (momentary) |
| `Energy.SmartMeter*` | Smart meter | No (sensor) |
| `System.Location.AirQuality` | Air quality | No (sensor) |
| `SmartCOM.Clima.Valve` | Climate valve | No (sensor) |
| `Security.Door` | Security door | No (sensor) |
| `Security.Intercom.2N.Intercom2N` | 2N Intercom | No (sensor) |
| `Security.Intercom.2N.Intercom2NCam` | 2N Camera | Yes (image request) |
| `System.Location.Room` | Room/area | No |

### Light Methods (HTTP API)

| Method | Parameters | Description |
|--------|------------|-------------|
| `AmznTurnOn` | - | Turn light on |
| `AmznTurnOff` | - | Turn light off |
| `AmznSetBrightness` | `[brightness]` (0-100) | Set brightness |

**Important**: Read `ScaledBrightness` property for actual brightness, not `Brightness`.

### WebSocket Control Methods

The integration supports WebSocket-based control for faster response times. When WebSocket is connected, control commands use these methods:

**Lights (via WebSocket):**
| WS Method | Parameters | HTTP Equivalent | Notes |
|-----------|------------|-----------------|-------|
| `SwitchOn` | `[]` | `AmznTurnOn` | Explicit on - PREFERRED |
| `SwitchOff` | `[]` | `AmznTurnOff` | Explicit off - PREFERRED |
| `BrightnessSetScaled` | `[brightness, transition_ms]` | `AmznSetBrightness` | transition=0 for instant |
| `SetValue ColorTemp` | `value` (Kelvin) | - | Color temperature for RGBW lights |

**⚠️ Light Control Trap:** `Switch([true/false])` exists but behaves inconsistently on some devices. Always use `SwitchOn`/`SwitchOff` instead for explicit on/off control.

**RGBW Color Temperature:** DynamicRGBWLight devices support color temperature via the `ColorTemp` property (in Kelvin). The `MinColorTemperature` and `MaxColorTemperature` properties define the supported range. Home Assistant converts between Kelvin and mireds internally. *Note: This feature is untested - please report issues if you have RGBW Evon modules.*

**Blinds (via WebSocket):**
| WS Method | Parameters | HTTP Equivalent | Notes |
|-----------|------------|-----------------|-------|
| `Open` | `[]` | `Open` | Move up |
| `Close` | `[]` | `Close` | Move down |
| `Stop` | `[]` | `Stop` | Stop movement |
| `MoveToPosition` | `[angle, position]` | `AmznSetPercentage`/`SetAngle` | **Angle comes FIRST!** |

**⚠️ Blind Control Trap:** `SetValue` on `Position` property updates the value in Evon but does NOT move the physical blind. Always use `MoveToPosition` CallMethod.

**WebSocket CallMethod Format:**
```json
{"methodName":"CallWithReturn","request":{"args":["instanceId.methodName",[params]],"methodName":"CallMethod","sequenceId":N}}
```

**WebSocket SetValue Format:**
```json
{"methodName":"CallWithReturn","request":{"args":["instanceId","propertyName",value],"methodName":"SetValue","sequenceId":N}}
```

**Note:** For CallMethod, the method is appended to the instance ID with a dot (e.g., `SC1_M01.Light3.SwitchOn`).

**Climate (via WebSocket):**
| WS Method/Property | Parameters | HTTP Equivalent | Notes |
|--------------------|------------|-----------------|-------|
| `CallMethod WriteCurrentSetTemperature` | `[value]` | `WriteCurrentSetTemperature` | ✅ Verified working (NOT SetValue!) |
| `CallMethod WriteDayMode` | `[]` | `WriteDayMode` | ✅ Comfort preset |
| `CallMethod WriteNightMode` | `[]` | `WriteNightMode` | ✅ Eco preset |
| `CallMethod WriteFreezeMode` | `[]` | `WriteFreezeMode` | ✅ Away preset |

**Alternative Climate Control Methods (from Evon webapp):**
- `SetValue ModeSaved = 2/3/4` (heating) or `5/6/7` (cooling) for presets
- `CallMethod IncreaseSetTemperature([])` / `DecreaseSetTemperature([])` for ±0.5°C
- `CallMethod Base.ehThermostat.AllDayMode/AllNightMode/AllFreezeMode([])` for global preset changes

**Switches:** WebSocket CallMethod does NOT work for switches - the integration falls back to HTTP API automatically.

**Fallback:** When WebSocket control fails or is unavailable, the integration automatically falls back to HTTP API.

### Blind Methods (HTTP API)

| Method | Parameters | Description |
|--------|------------|-------------|
| `Open` | - | Move blind up |
| `Close` | - | Move blind down |
| `Stop` | - | Stop movement |
| `AmznSetPercentage` | `[position]` (0-100) | Set position |
| `SetAngle` | `[angle]` (0-100) | Set tilt angle |

**Critical**: `MoveUp` and `MoveDown` do NOT exist - use `Open` and `Close`.

**Position convention**: Evon uses 0=open, 100=closed. Home Assistant uses the opposite (0=closed, 100=open).

**Tilt/Angle convention**: Same inversion applies. Evon uses 0=open (horizontal), 100=closed (blocking). Home Assistant uses 0=closed, 100=open.

### Climate Methods

| Method | Parameters | Description |
|--------|------------|-------------|
| `WriteDayMode` | - | Set comfort preset |
| `WriteNightMode` | - | Set eco preset |
| `WriteFreezeMode` | - | Set away/protection preset |
| `WriteCurrentSetTemperature` | `[temp]` | Set target temperature |

### Climate Properties

| Property | Description |
|----------|-------------|
| `ActualTemperature` | Current room temperature |
| `SetTemperature` | Target temperature |
| `SetValueComfortHeating` | Comfort mode temperature |
| `SetValueEnergySavingHeating` | Eco mode temperature |
| `SetValueFreezeProtection` | Protection temperature |
| `ModeSaved` | Current preset (values differ by season) |
| `CoolingMode` | Whether in cooling mode |
| `IsOn` | Whether actively heating/cooling |

**ModeSaved values by Season Mode:**

| Preset | Heating | Cooling |
|--------|---------|---------|
| away | 2 | 5 |
| eco | 3 | 6 |
| comfort | 4 | 7 |

### Season Mode

Controls global heating/cooling for the entire house.

**Read:**
```
GET /api/instances/Base.ehThermostat
→ IsCool: false = heating, true = cooling
```

**Set:**
```
PUT /api/instances/Base.ehThermostat/IsCool
Content-Type: application/json
Body: {"value": false}  // HEATING
Body: {"value": true}   // COOLING
```

### Home State Methods

| Method | Parameters | Description |
|--------|------------|-------------|
| `Activate` | - | Activate this home state |

**Properties**: `Active` (bool), `Name` (string)

**State IDs**: `HomeStateAtHome`, `HomeStateNight`, `HomeStateWork`, `HomeStateHoliday`

### Bathroom Radiator

| Method | Parameters | Description |
|--------|------------|-------------|
| `Switch` | - | Toggle on/off |

**Properties**: `Output` (state), `NextSwitchPoint` (minutes remaining), `EnableForMins` (duration)

### Scene Methods

| Method | Parameters | Description |
|--------|------------|-------------|
| `Execute` | - | Execute the scene |

**Properties**: `Name` (string), `CanExecute` (bool)

**Class**: `System.SceneApp`

### Camera Methods (2N Intercom)

| Method | Parameters | Description |
|--------|------------|-------------|
| `SetValue ImageRequest` | `true` | Request new image capture |

**Properties**: `Image` (string - path to JPEG on Evon server)

**Class**: `Security.Intercom.2N.Intercom2NCam`

**2N Camera Capabilities:**
- Frame rate: 1-10 fps for streaming mode
- Resolutions: 160×120, 176×144, 320×240, 352×272, 352×288, 640×480, 1280×960
- Historical buffer: 30 seconds (`time` parameter: -30 to 0)
- Image format: JPEG

**Image Fetch:** After requesting an image via WebSocket (`ImageRequest=True`), the camera waits for the `Image` property to update via a `ValuesChanged` event (up to `CAMERA_IMAGE_UPDATE_TIMEOUT` seconds), then fetches the JPEG via HTTP with token authentication. This event-driven approach replaces the previous blind sleep and ensures the image is ready before fetching.

### Smart Meter Properties

| Property | Unit | Description |
|----------|------|-------------|
| `PowerActual` | W | Current power consumption (HTTP API); via WebSocket, computed from `P1 + P2 + P3` |
| `P1`, `P2`, `P3` | W | Active power per phase (WebSocket only, summed for total power) |
| `Energy` | kWh | Total energy consumption |
| `Energy24h` | kWh | Rolling 24-hour energy (can decrease) |
| `EnergyDataDay` | kWh | Today's consumption data |
| `EnergyDataMonth` | kWh[] | Array of daily values (rolling 31-day window, last = yesterday) |
| `EnergyDataYear` | kWh[] | Array of monthly values (rolling 12-month window, last = previous month) |
| `UL1N` | V | Voltage phase L1 |
| `UL2N` | V | Voltage phase L2 |
| `UL3N` | V | Voltage phase L3 |
| `IL1` | A | Current phase L1 |
| `IL2` | A | Current phase L2 |
| `IL3` | A | Current phase L3 |
| `Frequency` | Hz | Grid frequency |
| `FeedIn` | W | Power fed to grid (HTTP API only; no WS subscription or sensor entity) |
| `FeedInEnergy` | kWh | Total energy fed to grid |

**Note**: For HA Energy Dashboard, use `Energy` (total_increasing), not `Energy24h` which is a rolling window.

### Calculated Energy Sensors

The integration provides two calculated sensors that don't exist in the Evon API:

| Sensor | Calculation | Source |
|--------|-------------|--------|
| **Energy Today** | Sum of hourly changes from HA statistics | `statistics_during_period()` on `sensor.*_energy_total` |
| **Energy This Month** | Previous days from Evon + today from HA | `EnergyDataMonth[-N:]` + Energy Today |

**Implementation Details:**
- Calculation happens in `coordinator/_calculate_energy_today_and_month()`
- Called during each coordinator refresh cycle
- `statistics_during_period()` is a blocking call - use `async_add_executor_job()`
- Values stored as `energy_today_calculated` and `energy_this_month_calculated` in meter data
- Sensor classes read from coordinator data, return 0.0 if not yet calculated

### Air Quality Properties

| Property | Unit | Description |
|----------|------|-------------|
| `CO2Value` | ppm | CO2 concentration (-999 if no sensor) |
| `Humidity` | % | Relative humidity |
| `HealthIndex` | - | Overall air quality index |
| `CO2Index` | - | CO2 quality index |
| `HumidityIndex` | - | Humidity quality index |

**Note:** Air quality devices (`System.Location.AirQuality`) may exist without physical sensors connected. A `CO2Value` of `-999` indicates no CO2 sensor is installed. The integration only creates sensors when valid data is available.

---

## Known Limitations

### Physical Buttons (`SmartCOM.Switch` / `Base.bSwitch`)

Cannot be monitored due to API limitations:

**HTTP API:**
- `IsOn` is only `true` while physically pressed (milliseconds)
- No event history or push notifications
- Polling is ineffective

**WebSocket API:**
- Physical switches (Taster) are action triggers, not stateful devices
- When pressed, the controller executes pre-configured actions
- Button press events are NOT exposed via WebSocket
- Only static configuration is available (ID, Name, Address, Channel)
- No `Pressed`, `State`, or `Value` properties exist

**Workaround:** Detect button presses indirectly by monitoring the devices they control (e.g., watch for light state changes). See `ws-switch-listener.mjs` for a test implementation and `docs/WEBSOCKET_API.md` for details.

The integration does not create entities for these devices.

### Security Doors & Intercoms (Implemented!)

Unlike physical switches, **security doors and intercoms DO expose real-time events** via WebSocket:

| Device | Instance Example | Key Properties |
|--------|------------------|----------------|
| Entry Door | `Door7586` | `IsOpen`, `DoorIsOpen`, `CallInProgress` |
| 2N Intercom | `Intercom2N1000` | `DoorBellTriggered`, `DoorOpenTriggered`, `IsDoorOpen` |
| Doorbell Button | `Intercom2N1000.DoorSwitch` | `IsOn` (pressed state) |

These can be monitored in real-time using `RegisterValuesChanged`. See `ws-security-door.mjs` for a test implementation and `docs/WEBSOCKET_API.md` for full property documentation.

**Integration Features (v1.14.0):**
- **Security Door Sensors**: Binary sensors for door open/closed state and call in progress
- **Intercom Sensors**: Binary sensors for door state and connection status
- **Doorbell Events**: Home Assistant event `evon_doorbell` fired when doorbell is pressed *(untested)*
  - Event data: `device_id`, `name`
  - Use in automations to trigger notifications, announcements, or camera snapshots

---

## Code Quality

### Linting

```bash
# Python
ruff check custom_components/evon/
ruff format custom_components/evon/

# TypeScript
npm run lint
npm run lint:fix
```

### Pre-commit Check

```bash
ruff check custom_components/evon/ && ruff format --check custom_components/evon/ && npm run lint
```

---

## Development Guidelines

### Adding New Device Types

1. Add device class constant to `const.py`
2. Create a processor in `coordinator/processors/` (e.g., `new_device.py`)
3. Export processor from `coordinator/processors/__init__.py`
4. Call processor in `coordinator/__init__.py` `_async_update_data()`
5. Add getter method in coordinator (e.g., `get_new_device_data()`)
6. Create platform file or extend existing one
7. Register platform in `__init__.py` PLATFORMS list
8. Add API methods to `api.py` if needed
9. Add tests in `tests/test_new_device.py`

### Entity Best Practices

- Use `EntityDescription` for configuration
- Set appropriate `entity_category`
- Implement `available` property
- Use `HomeAssistantError` for service call errors
- Include `evon_id` in extra state attributes
- Implement optimistic updates for responsive UI

### Optimistic Updates Pattern

```python
# In __init__
self._optimistic_is_on: bool | None = None

# In property
@property
def is_on(self) -> bool:
    if self._optimistic_is_on is not None:
        return self._optimistic_is_on
    return self.coordinator.get_state(...)

# In action
async def async_turn_on(self, **kwargs):
    self._optimistic_is_on = True
    self.async_write_ha_state()
    await self._api.turn_on(...)
    await self.coordinator.async_request_refresh()

# In coordinator update
def _handle_coordinator_update(self):
    if self._optimistic_is_on is not None:
        actual = self.coordinator.get_state(...)
        if actual == self._optimistic_is_on:
            self._optimistic_is_on = None
    super()._handle_coordinator_update()
```

### Light Animation Timing

Evon dimmable lights use hardware-level animations for smooth transitions. This affects how the integration handles state updates:

**Fade Animation Characteristics:**
- **Fade-out duration**: ~2.2-2.3 seconds (fixed ramp rate, independent of starting brightness)
- **Fade-in duration**: Similar timing, ramping from 0% to target
- **Update frequency**: WebSocket sends brightness updates every ~200ms during animation
- **Brightness steps**: 1-3% per update

**Problem:** During fade animations, WebSocket sends intermediate brightness values (e.g., 87% → 80% → 60% → 40% → 20% → 0% during fade-out). If these updates are applied to the UI, users see:
- Jerky brightness slider animation during turn-on
- Light appearing "on" momentarily after turn-off command
- Incorrect brightness level when rapidly toggling

**Solution:** The `OPTIMISTIC_SETTLING_PERIOD` constant (2.5 seconds) defines a window after control actions during which WebSocket/coordinator updates are ignored. The UI trusts the optimistic state instead:

```python
# const.py
OPTIMISTIC_SETTLING_PERIOD = 2.5  # Covers full fade animation (~2.2-2.3s) plus buffer

# light.py - ignore updates during settling
def _handle_coordinator_update(self) -> None:
    if (
        self._optimistic_state_set_at is not None
        and time.monotonic() - self._optimistic_state_set_at < OPTIMISTIC_SETTLING_PERIOD
    ):
        super()._handle_coordinator_update()  # Maintain subscription
        return  # Don't process data

    # After settling, clear optimistic state when coordinator confirms
    ...
```

**Additional Safeguards:**
- `_last_brightness`: Remembers last known brightness for optimistic turn-on display
- Only saved when no optimistic state is active (prevents corruption from animation values)
- `OPTIMISTIC_STATE_TIMEOUT` (30s): Clears stale optimistic state on network recovery

---

## Repairs Integration

| Repair | Trigger | Severity | Auto-clear |
|--------|---------|----------|------------|
| Connection failed | 3 consecutive failures | Error | Yes |
| Stale entities | Orphaned entities removed | Warning | Dismissible |
| Config migration | Incompatible version | Error | No |

Key files: `const.py` (constants), `coordinator.py` (connection tracking), `__init__.py` (entity/migration repairs), `config_flow.py` (repair flows)

---

## Logging Guidelines

- Use `error` when the operation failed and user intervention or data loss is likely.
- Use `warning` for recoverable issues where the system will retry or fallback.
- Use `debug` for transient retries, protocol details, and high-volume state updates.
- Log exceptions with `exc_info=True` to preserve stack traces.

## WebSocket Error Handling Policy

The WebSocket loop favors availability over strict failure handling. It catches expected network
errors (timeouts, disconnects, client errors) and retries with backoff. Only `CancelledError`
terminates the loop. Keep a broad catch as a last-resort safety net, but prefer explicit exception
types for diagnostics.

---

## Testing

### Manual API Testing

```bash
# Login and get token
curl -X POST http://EVON_HOST/login \
  -H "x-elocs-username: USERNAME" \
  -H "x-elocs-password: BASE64_SHA512_HASH"

# List devices
curl http://EVON_HOST/api/instances \
  -H "Cookie: token=TOKEN"
```

### WebSocket Testing

```bash
# Test switch/button event detection (requires EVON_TOKEN in .env)
node ws-switch-listener.mjs [mode]
# Modes: lights, switches, all

# Get token from browser: Developer Tools > Application > Cookies > token
```

### Unit Tests

```bash
pip install -r requirements-test.txt
pytest -v
```

Tests are in `tests/` - some require Home Assistant installed. CI skips many tests that need a full
HA runtime or optional dependencies; that is expected unless running in a full HA dev environment.

### MCP Server Tests

```bash
npm run build
npm run test:mcp
```

These tests run against the compiled `dist/` output and mock network calls.

### Test Coverage

```bash
pytest --cov=custom_components/evon --cov-report=term-missing
```

Test files:
- `test_api.py` - API client tests
- `test_ws_client.py` - WebSocket client tests
- `test_ws_mappings.py` - WebSocket property mapping tests
- `test_config_flow.py` / `test_config_flow_unit.py` - Configuration flow tests
- `test_coordinator.py` - Coordinator and getter method tests
- `test_diagnostics.py` - Diagnostics export tests
- `test_light.py`, `test_cover.py`, `test_climate.py` - Platform tests
- `test_sensor.py`, `test_switch.py`, `test_select.py` - Entity tests
- `test_binary_sensor.py`, `test_button.py` - Additional entity tests
- `test_camera.py`, `test_image.py` - Camera and image platform tests
- `test_camera_recorder.py` - Camera recording tests (lifecycle, encoding, duration)
- `test_base_entity.py` - Base entity and optimistic state tests
- `test_constants.py` - Constants validation tests
- `test_device_trigger.py` - Device trigger tests
- `test_processors.py` - Data processor tests
- `test_services.py` - Service handler tests

Current coverage: 498 tests

---

## Deploy Workflow

### Setup

1. Copy `.env.example` to `.env` with your HA IP
2. Configure SSH on Home Assistant (Terminal & SSH add-on)
3. Add your public key to authorized_keys

### Commands

| Command | Description |
|---------|-------------|
| `./scripts/ha-deploy.sh` | Deploy integration to HA |
| `./scripts/ha-deploy.sh restart` | Deploy and restart HA |
| `./scripts/ha-logs.sh` | Fetch evon-related logs |

---

## Version Compatibility

- Home Assistant: 2024.1.0+
- Python: 3.12+
- Node.js (MCP): 18+

---

## Contributing

1. Fork the repository
2. Create feature branch
3. Follow existing code patterns
4. Run linting before committing
5. Test on actual Evon hardware if possible
6. Update documentation for API changes
7. Submit pull request

## License

MIT License - see LICENSE file
