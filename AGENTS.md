# AGENTS.md - AI Agent Guidelines for Evon Smart Home

**IMPORTANT FOR CLAUDE:** This is the primary reference document. Always check this file first when working with this codebase. The Evon MCP server is available for direct API queries - prefer using it over writing scripts.

**Commit messages:** Do not add Co-Authored-By lines to commit messages.

This document provides critical information for AI agents working with this codebase.

## Project Overview

This repository contains two integrations for Evon Smart Home systems:
- **MCP Server** (`src/index.ts`) - TypeScript-based Model Context Protocol server
- **Home Assistant Integration** (`custom_components/evon/`) - Python-based HA custom component

## Documentation Structure

**IMPORTANT**: When updating documentation, put content in the correct file based on audience:

| File | Audience | Content |
|------|----------|---------|
| **README.md** | End users | Installation, features, configuration, platform descriptions (user-friendly, no internal details), version history |
| **DEVELOPMENT.md** | Developers | Architecture, API reference, device classes, methods, code patterns, testing, MCP server setup |
| **AGENTS.md** | AI agents | Critical API knowledge, debugging tips, gotchas, implementation patterns, version history (detailed) |
| **info.md** | HACS | Brief feature summary for HACS integration page |

### What Goes Where

| Content Type | File |
|--------------|------|
| How to install/configure | README.md |
| What features are supported | README.md |
| API endpoints and methods | DEVELOPMENT.md |
| Internal property values (e.g., ModeSaved) | DEVELOPMENT.md, AGENTS.md |
| Password encoding details | DEVELOPMENT.md |
| Debugging tips and gotchas | AGENTS.md |
| Code patterns and examples | DEVELOPMENT.md, AGENTS.md |
| MCP tools/resources tables | DEVELOPMENT.md |
| Version history (brief) | README.md |
| Version history (detailed) | AGENTS.md |

### Guidelines

1. **README.md should be user-friendly** - No internal implementation details, no API property names, no code examples
2. **DEVELOPMENT.md is for developers** - Technical details, API reference, code patterns
3. **AGENTS.md is for AI agents** - Critical knowledge that prevents mistakes, debugging tips, gotchas
4. **Keep formatting consistent** - Use tables for structured data, code blocks for examples
5. **Update version history** - Brief in README.md, detailed in AGENTS.md
6. **Don't duplicate** - Link to other docs instead of copying content

## Remote Access API - CRITICAL

The Evon API supports both local and remote access. **Remote access has different authentication requirements.**

### Connection Types

| Type | Base URL | Use Case |
|------|----------|----------|
| **Local** | `http://{local-ip}` | Direct LAN connection (faster, recommended) |
| **Remote** | `https://my.evon-smarthome.com` | Internet access via relay server |

### Remote Login - IMPORTANT DIFFERENCES

**Local login:**
```
POST http://{local-ip}/login
Headers:
  x-elocs-username: <username>
  x-elocs-password: <encoded-password>
```

**Remote login:**
```
POST https://my.evon-smarthome.com/login   ← Note: /login at ROOT, NOT /{engine-id}/login
Headers:
  x-elocs-username: <username>
  x-elocs-password: <encoded-password>
  x-elocs-relayid: <engine-id>              ← REQUIRED for remote
  x-elocs-sessionlogin: true                ← REQUIRED for remote
  X-Requested-With: XMLHttpRequest          ← REQUIRED for remote
```

**Critical gotcha:** The remote login URL is `https://my.evon-smarthome.com/login` (at root), NOT `https://my.evon-smarthome.com/{engine-id}/login`. The engine ID goes in the `x-elocs-relayid` header only.

### Remote API Calls

After login, API calls use different base URLs:

| Type | API Base URL |
|------|--------------|
| Local | `http://{local-ip}/api/instances/...` |
| Remote | `https://my.evon-smarthome.com/{engine-id}/api/instances/...` |

The actual API methods (get instances, turn on/off, etc.) are identical - the relay server proxies requests to the local Evon system.

### Engine ID

The Engine ID is found in your Evon system settings. It identifies your installation on the relay server (e.g., `985315`).

---

## Critical API Knowledge

### Brightness Control - IMPORTANT

**DO NOT use `BrightnessSetInternal`** - this sets an internal value but does not change the physical light brightness.

**USE `AmznSetBrightness`** - this is the correct method that controls the actual physical brightness.

Similarly, when **reading** brightness:
- `Brightness` property = internal value (incorrect)
- `ScaledBrightness` property = actual physical brightness (correct)

### Blind Control Methods - CRITICAL

**Movement methods:**
- **USE `Open`** - moves blind up (opens)
- **USE `Close`** - moves blind down (closes)
- **USE `Stop`** - stops movement
- **DO NOT use `MoveUp` or `MoveDown`** - these methods DO NOT EXIST and will return 404

**Position control:**
- **USE `AmznSetPercentage`** - sets blind position (0-100)
- **USE `SetAngle`** - sets tilt angle (0-100)
- **DO NOT use `SetPosition`** - may not work correctly

Position convention in Evon:
- `0` = fully open (blind up)
- `100` = fully closed (blind down)

Note: Home Assistant uses the inverse (0=closed, 100=open), so conversion is needed.

### Climate Control - Three Distinct Concepts

**IMPORTANT**: Climate control involves THREE separate concepts that must not be confused:

| Concept | Name in HA | Scope | Writable | API Property |
|---------|------------|-------|----------|--------------|
| **Season Mode** | `select` entity | Whole house | Yes | `Base.ehThermostat.IsCool` |
| **Preset** | `preset_mode` | Per room | Yes | `ModeSaved` / `MainState` |
| **Climate Status** | `hvac_action` | Per room | **No** | Read-only |

---

### Season Mode (Global Heating/Cooling) - VERIFIED

The **Season Mode** controls whether the entire house is in heating (winter) or cooling (summer) mode.

**API Endpoint:**
```
PUT /api/instances/Base.ehThermostat/IsCool
Content-Type: application/json
Body: {"value": false}  // HEATING (winter)
Body: {"value": true}   // COOLING (summer)
```

**Reading current state:**
```
GET /api/instances/Base.ehThermostat
→ IsCool: false = heating, true = cooling
```

**How it works:**
1. Setting `IsCool` switches ALL climate devices simultaneously
2. Each device's `CoolingMode` property reflects the global setting
3. Changes propagate immediately
4. **Preset values change** when season mode changes (see below)

---

### Preset (Per-Room Temperature Mode)

Each room can be set to one of three presets: **comfort**, **eco**, or **away**.

These preset names match Home Assistant's built-in presets for better UI icons. The actual behavior depends on the current Season Mode.

**CRITICAL**: Preset values in `ModeSaved` differ based on Season Mode!

| Preset | HEATING Mode | COOLING Mode | Description |
|--------|--------------|--------------|-------------|
| **comfort** | `4` | `7` | Normal comfortable temperature |
| **eco** | `3` | `6` | Energy saving (slightly less comfortable) |
| **away** | `2` | `5` | Protection mode (see below) |

**Temperature targets by preset:**
| Preset | Heating (Winter) | Cooling (Summer) |
|--------|------------------|------------------|
| comfort | 24°C | 25.5°C |
| eco | 22.5°C | 24.9°C |
| away | 18°C | 29°C |

**About the `away` preset:**
The `away` preset provides protection appropriate to the current season:
- **Heating mode**: Freeze protection - maintains minimum 18°C to prevent pipes from freezing
- **Cooling mode**: Heat protection - maintains maximum 29°C to prevent overheating

This is the same preset in both seasons, but Evon automatically adjusts its behavior based on what protection is needed.

**API - Setting presets** (works in both modes):
- `WriteDayMode` → sets comfort
- `WriteNightMode` → sets eco
- `WriteFreezeMode` → sets away/protection

**API - Reading preset:**
```python
# Check ModeSaved first, fall back to MainState
mode_saved = details.get("ModeSaved", details.get("MainState", 4))

# Map to preset name (must account for season mode!)
if is_cooling_mode:
    preset_map = {5: "away", 6: "eco", 7: "comfort"}
else:
    preset_map = {2: "away", 3: "eco", 4: "comfort"}
```

**Device type differences:**
| Device Type | Class Name | Preset Property |
|-------------|------------|-----------------|
| ClimateControlUniversal | Contains `ClimateControlUniversal` | `ModeSaved` |
| ClimateControl/Thermostat | `SmartCOM.Clima.ClimateControl` | `MainState` |

---

### Climate Status (Per-Room Activity) - READ-ONLY

The **Climate Status** indicates what the room's climate system is currently doing. This is **read-only** and cannot be changed directly.

| Status | Meaning |
|--------|---------|
| `heating` | Actively heating the room |
| `cooling` | Actively cooling the room |
| `idle` | Target temperature reached, not actively heating/cooling |

**Note**: The exact API property for reading this status needs verification. It may be derived from valve state or a dedicated property.

### Bathroom Radiators - TOGGLE CONTROL

Bathroom radiators (`Heating.BathroomRadiator`) are electric heaters with timer functionality:

1. **Control method**: Use `Switch` method to toggle on/off
2. **No separate on/off methods**: Only toggle is available
3. **Timer-based**: When turned on, runs for `EnableForMins` duration (default 30 minutes)
4. **State properties**:
   - `Output` - current on/off state
   - `NextSwitchPoint` - minutes remaining until auto-off
   - `EnableForMins` - configured duration

```javascript
// Toggle bathroom radiator
await callMethod("BathroomRadiator1", "Switch");
```

### Home State Control - SIMPLE AND RELIABLE

The `System.HomeState` class controls home-wide modes. Key points:

1. **Finding states**: Filter by `ClassName === "System.HomeState"` and skip IDs starting with `System.`
2. **Reading active state**: Check the `Active` property on each state instance
3. **Changing state**: Call `Activate` method on the desired state instance
4. **State IDs are fixed**: `HomeStateAtHome`, `HomeStateHoliday`, `HomeStateNight`, `HomeStateWork`

```javascript
// Example: Switch to night mode
await callMethod("HomeStateNight", "Activate");
```

### Physical Buttons (SmartCOM.Switch) - HARDWARE LEVEL ONLY

**CRITICAL**: Physical wall buttons (`SmartCOM.Switch` class) **operate at the hardware level and do NOT fire WebSocket events**:

1. **Hardware-level operation**: Buttons directly signal their associated actuators (blind motors, light relays) without going through the software layer
2. **No WebSocket events**: Testing confirmed 0 ValuesChanged events even with active subscriptions
3. **By design**: This ensures physical buttons work even if the software layer has issues

**What this means for agents:**
- Do NOT create event entities, binary sensors, or triggers for `SmartCOM.Switch` devices
- Do NOT attempt to implement button press detection - it will not work
- The buttons work within Evon's internal system but cannot be observed externally
- Only `SmartCOM.Light.Light` (controllable relay outputs) should be exposed as switches
- Device state changes from button presses ARE visible (e.g., light turns on), but the button press itself is not

**Testing performed (February 2025):**
- Tested SC1_M08.Switch1Up (Taster Jal. WZ 3 Öffnen) - 0 events
- Tested SC1_M07.Switch1Up (Taster Jal. WZ 1 Öffnen) - 0 events
- Tested SC1_M04.Input3 (Taster Licht Esstisch) - 0 events

### Method Naming Pattern

Evon uses "Amzn" prefix for methods that were designed for Alexa integration. These work via HTTP API:
- `AmznTurnOn` / `AmznTurnOff` - lights and switches
- `AmznSetBrightness` - light brightness
- `AmznSetPercentage` - blind position

## WebSocket Control - CRITICAL FINDINGS (January 2025)

The integration now supports WebSocket-based device control for faster, more responsive operation. **However, there are important traps to avoid.**

### What Works via WebSocket

| Device | Method | WebSocket Call | Notes |
|--------|--------|----------------|-------|
| Light On | `SwitchOn` | `CallMethod [instanceId.SwitchOn, []]` | ✅ Explicit on - PREFERRED |
| Light Off | `SwitchOff` | `CallMethod [instanceId.SwitchOff, []]` | ✅ Explicit off - PREFERRED |
| Light Brightness | `BrightnessSetScaled` | `CallMethod [instanceId.BrightnessSetScaled, [brightness, transition]]` | ✅ transition=0 for instant |
| Blind Open/Close/Stop | `Open/Close/Stop` | `CallMethod [instanceId.Open, []]` | ✅ Verified |
| Blind Position+Tilt | `MoveToPosition` | `CallMethod [instanceId.MoveToPosition, [angle, position]]` | ✅ Angle comes FIRST! |
| Climate Temperature | `SetTemperature` | `SetValue [instanceId, "SetTemperature", value]` | ✅ Verified working |
| Climate Comfort | `WriteDayMode` | `CallMethod [instanceId.WriteDayMode, []]` | ✅ Verified working |
| Climate Eco | `WriteNightMode` | `CallMethod [instanceId.WriteNightMode, []]` | ✅ Verified working |
| Climate Away | `WriteFreezeMode` | `CallMethod [instanceId.WriteFreezeMode, []]` | ✅ Verified working |
| Season Mode | `IsCool` | `SetValue [Base.ehThermostat, "IsCool", bool]` | ✅ true=cooling, false=heating |

### What Does NOT Work via WebSocket

| Device | Trap | What Happens |
|--------|------|--------------|
| **Switch** | `SetValue` or `CallMethod` | Returns success but hardware doesn't respond |
| **Blind Position** | `SetValue Position` | Updates UI value but hardware doesn't move, then reverts |
| **Light** | `CallMethod AmznTurnOn/Off` | Returns success but hardware doesn't respond |
| **Light** | `Switch([true/false])` | Inconsistent - may toggle instead of set state on some devices |

### TRAP #1: CallMethod Format

**WRONG format (looks correct but doesn't trigger hardware):**
```json
{"args": ["SC1_M09.Blind2", "Open", []], "methodName": "CallMethod"}
```

**CORRECT format (method appended to instance ID with dot):**
```json
{"args": ["SC1_M09.Blind2.Open", []], "methodName": "CallMethod"}
```

### TRAP #2: Light Control Methods - Use SwitchOn/SwitchOff

The Evon webapp exposes multiple light control methods, but only some work reliably:

**WRONG (inconsistent behavior, may toggle instead of setting state):**
```json
{"args": ["SC1_M01.Light3.Switch", [true]], "methodName": "CallMethod"}
```

**WRONG (doesn't trigger hardware via WebSocket):**
```json
{"args": ["SC1_M01.Light3.AmznTurnOn", []], "methodName": "CallMethod"}
```

**CORRECT (explicit on/off, no ambiguity):**
```json
{"args": ["SC1_M01.Light3.SwitchOn", []], "methodName": "CallMethod"}
{"args": ["SC1_M01.Light3.SwitchOff", []], "methodName": "CallMethod"}
{"args": ["SC1_M01.Light3.BrightnessSetScaled", [75, 0]], "methodName": "CallMethod"}
```

### TRAP #3: Blind MoveToPosition Parameters

**IMPORTANT: Angle comes FIRST, then position!**
```json
{"args": ["SC1_M09.Blind2.MoveToPosition", [angle, position]], "methodName": "CallMethod"}
```

The integration caches angle and position separately so:
- Position changes → `MoveToPosition([cached_angle, new_position])`
- Tilt changes → `MoveToPosition([new_angle, cached_position])`

### TRAP #4: Switches Must Use HTTP

Switches (`SmartCOM.Switch`, `Base.bSwitch`) do NOT respond to WebSocket control at all. The HTTP API must be used:
```
POST /api/instances/{switch_id}/AmznTurnOn
```

### TRAP #5: Non-Dimmable Lights in Light Groups

When a non-dimmable light (e.g., Evon relay controlling power for a combined light with Govee) is part of a light group:
- Brightness changes trigger `turn_on()` on all group members
- The non-dimmable light receives `turn_on()` WITHOUT brightness parameter
- The integration skips the API call if the light is already on (avoids unnecessary traffic)

This is handled automatically in `light.py` - non-dimmable lights that are already on will not receive WebSocket commands when brightness changes on the group.

### Implementation Details

See `custom_components/evon/ws_control.py` for the mapping configuration and `api.py` for the `_try_ws_control()` method that handles WebSocket-first control with HTTP fallback.

Tests documenting these findings are in `tests/test_ws_client.py` under `TestWebSocketControlFindings`.

## File Locations

### MCP Server
- Entry point: `src/index.ts`
- API client: `src/api-client.ts`
- Configuration: `src/config.ts`, `src/constants.ts`, `src/types.ts`
- Tools: `src/tools/` (lights, blinds, climate, home-state, radiators, sensors, generic)
- Resources: `src/resources/` (lights, blinds, climate, home-state, radiators, summary)
- Compiled: `dist/`
- Build: `npm run build`

### Home Assistant Integration
- All files in: `custom_components/evon/`
- Entry point: `__init__.py`
- API client: `api.py`
- Base entity: `base_entity.py`
- Data coordinator: `coordinator/` package
  - Main coordinator: `coordinator/__init__.py`
  - Device processors: `coordinator/processors/` (lights, blinds, climate, switches, smart_meters, air_quality, valves, home_states, bathroom_radiators, scenes, security_doors, intercoms, cameras)
- Platforms: `light.py`, `cover.py`, `climate.py`, `sensor.py`, `switch.py`, `select.py`, `binary_sensor.py` (valves, security doors, intercoms), `button.py`, `camera.py`, `image.py` (doorbell snapshots)
- Config flow: `config_flow.py` (includes options and reconfigure flows)

## Testing Changes

### MCP Server
```bash
npm run build
# Restart Claude Code to reload the MCP server
```

### Home Assistant Integration
```bash
# Run unit tests
pip install -r requirements-test.txt
pytest
```

For live testing, use the deploy scripts (see Deploy Workflow below).

## Deploy Workflow (Home Assistant Integration)

SSH access to Home Assistant enables quick deployment and log checking.

### Initial Setup

1. **Copy `.env.example` to `.env`** and fill in your values:
   ```bash
   cp .env.example .env
   # Edit .env with your HA IP and user
   ```

2. **Configure SSH on Home Assistant:**
   - Install "Terminal & SSH" add-on
   - Add your public key to authorized_keys in the add-on configuration
   - Start the add-on

3. **Verify connection:**
   ```bash
   ssh root@192.168.1.x  # Replace with your HA IP
   ```

### Deploy Scripts

| Command | Description |
|---------|-------------|
| `./scripts/ha-deploy.sh` | Deploy integration to HA |
| `./scripts/ha-deploy.sh restart` | Deploy and restart HA |
| `./scripts/ha-logs.sh` | Fetch evon-related logs (last 100 lines) |
| `./scripts/ha-logs.sh 50` | Fetch last 50 lines |
| `./scripts/ha-logs.sh 100 error` | Fetch lines containing "error" |

### Typical Development Session

```bash
# 1. Make code changes
# ... edit files in custom_components/evon/

# 2. Deploy to HA
./scripts/ha-deploy.sh

# 3. Reload integration in HA UI (or restart HA)
# Settings → Devices & Services → Evon → ⋮ → Reload

# 4. Check logs for errors
./scripts/ha-logs.sh

# 5. Run linting before committing
ruff check custom_components/evon/ && ruff format custom_components/evon/
```

### Security Notes

- **`.env` is in `.gitignore`** - credentials are never committed
- **Never hardcode IP addresses or credentials** in scripts
- The `.env.example` file shows required variables without actual values

## Using Evon MCP Server for Debugging

The Evon MCP server can be used to directly query the Evon API for debugging and verification. This is useful for:
- **Discovering properties**: See all available properties on a device instance
- **Verifying HA changes**: Check if changes made in Home Assistant are reflected in Evon
- **Debugging issues**: Compare what HA shows vs what Evon actually reports
- **Testing API methods**: Call methods directly to understand their behavior

### MCP Server Configuration

The Evon MCP server is configured in `.claude.json`:

```json
{
  "mcpServers": {
    "evon": {
      "command": "node",
      "args": ["/path/to/evon-ha/dist/index.js"],
      "env": {
        "EVON_HOST": "http://192.168.x.x",
        "EVON_USERNAME": "<username>",
        "EVON_PASSWORD": "<password>"
      }
    }
  }
}
```

### Useful MCP Tools for Debugging

| Tool | Purpose |
|------|---------|
| `get_instance` | Get all properties of a specific device instance |
| `get_property` | Get a specific property value |
| `call_method` | Call any method on an instance to test behavior |
| `list_climates` | List all climate devices with current state |
| `list_lights` | List all lights with current state |

### Direct API Queries via Bash

If the MCP server is not available, you can query the Evon API directly:

```bash
# Generate password hash
PASS_HASH=$(node -e "
const crypto = require('crypto');
const hash = crypto.createHash('sha512').update('username' + 'password').digest('base64');
console.log(hash);
")

# Login and get token
TOKEN=$(curl -s -X POST "http://192.168.x.x/login" \
  -H "x-elocs-username: username" \
  -H "x-elocs-password: $PASS_HASH" \
  -D - 2>/dev/null | grep -i "x-elocs-token" | cut -d' ' -f2 | tr -d '\r\n')

# Query an instance (e.g., climate device)
curl -s "http://192.168.x.x/api/instances/ClimateControlUniversal1" \
  -H "Cookie: token=$TOKEN" | python3 -m json.tool
```

### Example: Debugging Climate Preset Mode

When investigating why climate preset wasn't showing correctly:

1. **Query the device** to see all properties:
   ```
   get_instance instance_id=ClimateControlUniversal1
   ```

2. **Look for relevant properties**:
   - `Mode` - Found to be 0 for all presets (heating/cooling mode, NOT preset!)
   - `ModeSaved` - Found to change: 2=away, 3=eco, 4=comfort (in heating mode)

3. **Test by changing preset in Evon** and re-querying to see which property changes

4. **Verify HA integration** correctly reads the identified property

This approach helped discover that `ModeSaved` (not `Mode`) indicates the preset mode.

## Device Class Names

When filtering devices from the API, use these class names:

| Device | Class Name | Controllable |
|--------|------------|--------------|
| Dimmable Lights | `SmartCOM.Light.LightDim` | Yes |
| Relay Outputs (Switches) | `SmartCOM.Light.Light` | Yes |
| RGBW Lights | `SmartCOM.Light.DynamicRGBWLight` | Yes |
| Light Groups | `SmartCOM.Light.LightGroup` | Yes |
| Blinds | `SmartCOM.Blind.Blind` | Yes |
| Blind Groups | `SmartCOM.Blind.BlindGroup` | Yes |
| Climate | `SmartCOM.Clima.ClimateControl` | Yes |
| Climate (universal) | Contains `ClimateControlUniversal` | Yes |
| Bathroom Radiator | `Heating.BathroomRadiator` | Yes (use `Switch` method to toggle) |
| Home State | `System.HomeState` | Yes (use `Activate` method) |
| Scene | `System.SceneApp` | Yes (use `Execute` method) |
| Physical Buttons | `SmartCOM.Switch` | **NO** (read-only, unusable) |
| Smart Meter | Contains `Energy.SmartMeter` | No (sensor only) |
| Security Door | `Security.Door` | No (sensor only, stores SavedPictures) |
| Intercom (2N) | `Security.Intercom.2N.Intercom2N` | No (sensor only) |
| Camera (2N) | `Security.Intercom.2N.Intercom2NCam` | Yes (trigger image capture) |

### Smart Meter Energy Sensors - IMPORTANT

Evon smart meters expose two energy values:

| Sensor | Evon Property | Description | HA Energy Dashboard |
|--------|---------------|-------------|---------------------|
| **Energy Total** | `Energy` | Cumulative total, always increasing | ✅ **Use this** |
| **Energy (24h Rolling)** | `Energy24h` | Rolling 24-hour window | ❌ Don't use |

**CRITICAL**: The `Energy24h` property is a **rolling 24-hour window**, not a daily reset. It can **decrease** during the day as high-consumption hours from yesterday roll off. Using this in HA's Energy Dashboard will produce **negative values**.

Always configure HA's Energy Dashboard to use `sensor.*_energy_total` instead.

| Air Quality | `System.Location.AirQuality` | No (sensor only, CO2=-999 means no sensor) |
| Climate Valve | `SmartCOM.Clima.Valve` | No (sensor only) |
| Room/Area | `System.Location.Room` | No (used for area sync) |

## API Authentication Flow

1. POST to `/login` with headers `x-elocs-username` and `x-elocs-password`
2. Get token from response header `x-elocs-token`
3. Use token in cookie for all subsequent requests: `Cookie: token=<token>`
4. On 302 or 401 response, re-authenticate and retry

## Security Implementation

The API client implements several security measures:

### SSL/TLS
- Explicit SSL context using `ssl.create_default_context()` for all HTTPS connections
- System certificate store used for verification
- Applied via `aiohttp.TCPConnector` for remote connections
- Connection limits: 10 total, 5 per host

### Credential Protection
- Sensitive headers redacted from debug logs (`x-elocs-token`, `x-elocs-password`, `cookie`, etc.)
- Password hashed client-side before transmission (SHA-512 of username+password, Base64 encoded)
- No credentials in error messages or exceptions
- Engine ID redacted in diagnostics export
- Login redirect URLs sanitized in logs (only path shown)

### Input Validation
- Instance IDs validated against pattern `^[a-zA-Z0-9._-]+$` (prevents path traversal)
- Method names validated against pattern `^[a-zA-Z][a-zA-Z0-9]*$`
- Engine ID validated: 4-12 alphanumeric characters (validated in both config flow and API)
- Username must be non-empty (whitespace stripped)
- Password must be non-empty
- Host port validated: 1-65535

### Token Management
- Token TTL tracking (1 hour default)
- Automatic refresh when expired
- `asyncio.Lock` prevents race conditions in concurrent token access
- Token cleared on 401/302 responses with retry
- Token cleared from memory on session close

### HTTP Security
- Content-Type validation - raises error if response is not JSON
- Specific error handling for 400 (bad request), 403 (forbidden), 404, 429 (rate limit), 5xx errors
- Response reason included in all error messages for debugging
- Accepts 200, 201, 204 as success codes
- Unexpected redirects rejected (not logged with full URL)
- Session creation error handling

## Optimistic Updates

All controllable entities implement optimistic updates to prevent UI flicker when changing state. When a user triggers an action (turn on light, change preset, etc.), the UI immediately shows the expected state without waiting for the coordinator to poll Evon.

**How it works:**
1. User triggers action (e.g., turn on light)
2. Entity sets optimistic state and calls `async_write_ha_state()`
3. API call is made to Evon
4. Coordinator refreshes data from Evon
5. In `_handle_coordinator_update()`, optimistic state is cleared only when actual state matches expected

**Entities with optimistic updates:**
| Entity | Optimistic Properties |
|--------|----------------------|
| Light | `is_on`, `brightness` |
| Cover | `position`, `tilt_position`, `is_moving` |
| Climate | `preset_mode`, `target_temperature`, `hvac_mode` |
| Switch | `is_on` |
| Bathroom Radiator | `is_on`, `time_remaining_mins` |
| Home State Select | `current_option` |
| Season Mode Select | `current_option` |

**Implementation pattern:**
```python
# In __init__
self._optimistic_is_on: bool | None = None

# In property
@property
def is_on(self) -> bool:
    if self._optimistic_is_on is not None:
        return self._optimistic_is_on
    # ... get from coordinator

# In action method
async def async_turn_on(self, **kwargs):
    self._optimistic_is_on = True
    self.async_write_ha_state()
    await self._api.turn_on(...)
    await self.coordinator.async_request_refresh()

# In coordinator update handler
def _handle_coordinator_update(self):
    if self._optimistic_is_on is not None:
        actual = self.coordinator.get_entity_data(...)
        if actual == self._optimistic_is_on:
            self._optimistic_is_on = None
    super()._handle_coordinator_update()
```

## Common Pitfalls

1. **Empty device names**: Skip instances where `Name` is empty - these are templates/base classes
2. **Token expiry**: Tokens expire; implement retry logic with re-authentication
3. **Brightness values**: Evon uses 0-100, Home Assistant uses 0-255 - convert appropriately
4. **Position inversion**: Evon and HA have opposite conventions for cover position

## Environment Variables (MCP Server)

Configure via Claude Code's `~/.claude.json`:

```json
{
  "mcpServers": {
    "evon": {
      "command": "node",
      "args": ["/path/to/evon-ha/dist/index.js"],
      "env": {
        "EVON_HOST": "http://192.168.x.x",
        "EVON_USERNAME": "<username>",
        "EVON_PASSWORD": "<password>"
      }
    }
  }
}
```

**Required variables:**
- `EVON_HOST` - Evon system URL (your local IP)
- `EVON_USERNAME` - Your Evon username
- `EVON_PASSWORD` - Plain text OR encoded password (auto-detected)

**Security**: `.claude.json` is in `.gitignore` - never commit credentials.

## Password Encoding

The Evon API requires `x-elocs-password` which is NOT plain text. The encoding is:

```
x-elocs-password = Base64(SHA512(username + password))
```

**Both integrations now handle this automatically:**
- MCP Server: Auto-detects if password is already encoded (88 chars ending with `==`)
- Home Assistant: Encodes plain text password in the `EvonApi` class

**To manually encode (if needed):**
```python
import hashlib, base64
encoded = base64.b64encode(hashlib.sha512((username + password).encode()).digest()).decode()
```

## Adding New Device Types

1. Find the device class name in `/api/instances` response
2. Add class name constant to `const.py`
3. Create a processor in `coordinator/processors/` (e.g., `new_device.py`)
4. Export processor from `coordinator/processors/__init__.py`
5. Call processor in `coordinator/__init__.py` `_async_update_data()`
6. Add getter method in coordinator (e.g., `get_new_device_data()`)
7. Create new platform file (e.g., `sensor.py`)
8. Add platform to `PLATFORMS` list in `__init__.py`
9. Add tests in `tests/test_new_device.py`
10. Update `manifest.json` if needed

## Integration Features

### Home Assistant
- **Platforms**: Light, Cover, Climate, Sensor, Switch, Select, Binary Sensor, Button, Camera, Image
- **Select Entities**: Season mode (heating/cooling), Home state (At Home, Holiday, Night, Work)
- **Switch Entity**: Bathroom radiators with timer functionality
- **Climate**: Heating/cooling modes, preset modes (comfort, eco, away), season mode
- **Options Flow**: Configure poll interval (5-300 seconds), area sync, non-dimmable lights
- **Non-dimmable Lights**: Mark lights as on/off only (useful for LED strips with PWM controllers)
- **Reconfigure Flow**: Change host/credentials without removing integration
- **Reload Support**: Reload without HA restart
- **Stale Entity Cleanup**: Automatic removal of orphaned entities on reload
- **Repairs**: Connection failure alerts, stale entity notifications, config migration warnings
- **Diagnostics**: Export diagnostic data for troubleshooting
- **Entity Attributes**: Extra attributes exposed on all entities
- **Energy Sensors**: Smart meter power, energy, voltage sensors
- **Air Quality**: CO2 and humidity sensors (if available)
- **Valve Sensors**: Binary sensors for climate valve state

### MCP Server
- **Tools**: Device listing and control (lights, blinds, climate, home states, bathroom radiators)
- **Resources**: Read device state via `evon://` URIs
- **Scenes**: Pre-defined and custom scenes for whole-home control
- **Home State**: Read and change home modes (at_home, holiday, night, work)
- **Bathroom Radiators**: List and toggle electric heaters

## MCP Resources

Resources allow reading device state without calling tools:

| URI | Description |
|-----|-------------|
| `evon://lights` | All lights with state |
| `evon://blinds` | All blinds with state |
| `evon://climate` | All climate controls with state |
| `evon://home_state` | Current home state and available states |
| `evon://bathroom_radiators` | All bathroom radiators with state |
| `evon://summary` | Home summary (counts, averages, home state) |

## MCP Scenes

Pre-defined scenes:
- `all_off` - Turn off lights, close blinds
- `movie_mode` - Dim to 10%, close blinds
- `morning` - Open blinds, lights to 70%, comfort mode
- `night` - Lights off, eco mode

## Linting

**IMPORTANT**: CI runs both `ruff check` AND `ruff format --check`. Code must pass both.

### Python (ruff)
```bash
# Check for linting issues
ruff check custom_components/evon/

# Auto-fix linting issues
ruff check custom_components/evon/ --fix

# Check formatting (what CI runs)
ruff format --check custom_components/evon/

# Auto-fix formatting
ruff format custom_components/evon/
```

### TypeScript (eslint)
```bash
# Check for issues
npm run lint

# Auto-fix issues
npm run lint:fix
```

### Quick CI Check (run before committing)
```bash
ruff check custom_components/evon/ && ruff format --check custom_components/evon/ && npm run lint
```

## Unit Tests

Tests are in the `tests/` directory (130+ tests, ~84% coverage):

**Platform tests:**
- `test_light.py` - Light entity tests
- `test_cover.py` - Cover/blind entity tests
- `test_climate.py` - Climate entity tests
- `test_sensor.py` - Sensor entity tests
- `test_switch.py` - Switch entity tests
- `test_select.py` - Select entity tests (home state, season mode)
- `test_binary_sensor.py` - Binary sensor tests (valves)
- `test_button.py` - Button entity tests (scenes)

**Core tests:**
- `test_api.py` - API client tests (mocks homeassistant, works without HA installed)
- `test_config_flow.py` / `test_config_flow_unit.py` - Config and options flow tests
- `test_coordinator.py` - Data coordinator and getter method tests
- `test_diagnostics.py` - Diagnostics export tests

### Test Architecture

**The CI only runs linting, NOT pytest.** This is because many tests require homeassistant which is a heavy dependency.

Tests are split by dependency:
| Test File | Requires HA | How It Works |
|-----------|-------------|--------------|
| `test_standalone.py` | No | Reads files directly, no imports from custom_components |
| `test_api.py` | No | Mocks `homeassistant` module, uses `importlib` to load `api.py` directly |
| `test_config_flow.py` | Yes | Uses `@requires_homeassistant` skip marker |
| `test_coordinator.py` | Yes | Uses `@requires_homeassistant` skip marker |

**Why this matters for agents:**
- When importing from `custom_components.evon.*`, Python executes `__init__.py` which imports from `homeassistant`
- To test without HA, either read files directly (like `test_standalone.py`) or mock the homeassistant module before importing (like `test_api.py`)

### Running Tests

```bash
# Install test dependencies
pip install -r requirements-test.txt

# Run all tests (HA-dependent tests will be skipped if HA not installed)
pytest

# Run only standalone tests (always works)
python3 tests/test_standalone.py

# Run with verbose output
pytest -v
```

### CI Checks

The CI workflow (`.github/workflows/ci.yml`) runs:
1. `ruff check` - Python linting
2. `ruff format --check` - Python formatting
3. `npm run lint` - TypeScript linting
4. `npm run build` - TypeScript compilation

**Before committing, always run:**
```bash
ruff check custom_components/evon/
ruff format custom_components/evon/
npm run lint
```

## Pre-Commit Checklist

**IMPORTANT**: Before every commit, ensure documentation is updated:

1. **Update ALL documentation files** if the changes affect them:
   - `README.md` - User-facing features, installation, configuration
   - `DEVELOPMENT.md` - Architecture, API reference, code patterns
   - `AGENTS.md` - AI agent guidelines, debugging tips, gotchas
   - `info.md` - HACS integration page summary
   - `docs/*.md` - Detailed technical documentation (e.g., BLIND_TILT_BEHAVIOR.md)

2. **Run linting** before committing:
   ```bash
   ruff check custom_components/evon/ && ruff format --check custom_components/evon/ && npm run lint
   ```

3. **Check for undocumented API discoveries** - Any new properties, methods, or behaviors found during development should be documented.

---

## Release Process

Before creating a release, ensure the following are up to date:

1. **Version numbers** - Update in ALL FOUR files (they must match!):
   - `package.json`
   - `package-lock.json` ← Run `npm install --package-lock-only` to sync
   - `pyproject.toml`
   - `custom_components/evon/manifest.json`

2. **Documentation** - Review and update ALL docs:
   - `README.md` - User-facing documentation, supported devices
   - `DEVELOPMENT.md` - API reference, code patterns
   - `AGENTS.md` - AI guidelines, debugging tips, version history
   - `info.md` - HACS summary
   - `docs/*.md` - Detailed technical docs

3. **Version history** - Add entry to:
   - `README.md` (brief, user-friendly)
   - `AGENTS.md` (detailed, technical)

4. **Linting** - Run all CI checks:
   ```bash
   ruff check custom_components/evon/ && ruff format --check custom_components/evon/ && npm run lint
   ```

5. **Build TypeScript** - Ensure MCP server compiles:
   ```bash
   npm run build
   ```

**Common mistake**: `package.json` version was not updated from v1.4.1 to v1.11.0 across multiple releases. Always check all three version files match!

## Version History

**IMPORTANT**: Before updating version history, always check the existing entries to identify the current/latest version. Do not overwrite an already-released version with new features - create a new version number instead.

- **v1.15.0**: Camera support for 2N intercom cameras and doorbell snapshot image entities. **Camera**: Live feed via WebSocket using `SetValue ImageRequest=true` to trigger capture, then fetching JPEG from `/temp/` path. **Doorbell Snapshots**: Image entities (`image.py`) for up to 10 historical snapshots from `SavedPictures` property on Security Door. Each snapshot includes timestamp in attributes. **Class name fixes**: Security Door is `Security.Door` (not `SmartCOM.Security.SecurityDoor`), Intercom 2N is `Security.Intercom.2N.Intercom2N` (not `SmartCOM.Intercom.Intercom2N`). **Physical buttons (Taster)**: Verified they operate at hardware level and do NOT fire WebSocket events (tested SC1_M08.Switch1Up, SC1_M07.Switch1Up, SC1_M04.Input3 with 0 events received). **Security Door entities**: Door open/closed state (`IsOpen`/`DoorIsOpen`) and call in progress indicator (`CallInProgress`). **Intercom entities**: Doorbell events, door open events, connection status.
- **v1.14.0**: WebSocket-based device control for lights and blinds. Lights use `CallMethod SwitchOn/SwitchOff` for explicit on/off (not `Switch([bool])` which is inconsistent) and `BrightnessSetScaled([brightness, transition])` for dimming. Blinds use `CallMethod MoveToPosition([angle, position])` for position and tilt control with cached values. Non-dimmable lights in light groups skip API calls when already on (for combined lights with Govee). Falls back to HTTP when WebSocket unavailable. Added security doors and intercoms with doorbell events (`evon_doorbell`), RGBW light color temperature support (untested), light/blind group classes, and climate humidity display.
- **v1.13.0**: Added WebSocket support for real-time state updates (read-only).
- **v1.12.0**: Remote access via `my.evon-smarthome.com` relay server. Reconfigure flow now allows switching between local and remote connection types. Security improvements: explicit SSL context with connection limits, header redaction, token TTL with auto-refresh and memory cleanup on close, comprehensive input validation (instance IDs, method names, Engine ID, username, password, host port), asyncio.Lock for token access, HTTP status handling (400/403/404/429/5xx with response.reason), Content-Type validation, Engine ID redaction in diagnostics.
- **v1.11.0**: Added scene support - Evon scenes appear as button entities that can be pressed to execute. Also includes smart meter current sensors (L1/L2/L3), frequency sensor, and feed-in energy sensor from 1.10.3 branch.
- **v1.10.1**: Added optimistic time display for bathroom radiators. Fixed smart meter "Energy Today" sensor - renamed to "Energy (24h Rolling)" with `state_class: measurement` to prevent incorrect negative values in HA Energy Dashboard. The rolling 24h window from Evon can decrease during the day.
- **v1.10.0**: Added configurable non-dimmable lights option, Home Assistant Repairs integration (connection failure alerts after 3 failures, stale entity notifications, config migration warnings), improved home state translations using HA's translation system (proper German/English), hub device for device hierarchy, and fixed `via_device` warnings for HA 2025.12.0 compatibility. Config entry version bumped to 2 with migration support. Added 9 new tests (29 total).
- **v1.9.0**: Added Season Mode select entity for global heating/cooling control via `Base.ehThermostat.IsCool`. Climate presets now correctly map to season-specific `ModeSaved` values (2-4 for heating, 5-7 for cooling). Added `hvac_action` property to climate entities showing current activity (heating/cooling/idle).
- **v1.8.2**: Fixed blind cover optimistic state for group actions. Added `is_moving` optimistic tracking so group open/close buttons work correctly when clicking twice to stop.
- **v1.8.1**: Added optimistic updates for all entities and improved preset icons.
- **v1.8.0**: Added optimistic updates for all controllable entities (lights, covers, climate, switches, select). Changed climate preset names to use HA built-in presets for better UI icons (`eco` instead of `energy_saving`, `away` instead of `freeze_protection`).
- **v1.7.4**: Added optimistic updates for climate target temperature when changing presets.
- **v1.7.3**: Added optimistic updates for climate preset mode to prevent UI flicker.
- **v1.7.2**: Fixed climate preset detection for Thermostat devices (uses `MainState` fallback when `ModeSaved` not present).
- **v1.7.1**: Fixed climate preset mode detection (uses `ModeSaved` property instead of `Mode`), added cooling/heating mode display.
- **v1.7.0**: Added bathroom radiator (electric heater) support with timer functionality. Added MCP tools (`list_bathroom_radiators`, `bathroom_radiator_control`) and resource (`evon://bathroom_radiators`).
- **v1.6.0**: Added automatic cleanup of stale/orphaned entities on integration reload.
- **v1.5.2**: Fixed reconfigure flow 500 error with modern HA config flow patterns.
- **v1.5.0**: Added Home State selector (select entity) for switching between home modes. Added MCP tools (`list_home_states`, `set_home_state`) and resource (`evon://home_state`).
- **v1.4.1**: Removed button event entities (not functional due to Evon API limitations)
- **v1.4.0**: Added event entities for physical buttons (later removed in 1.4.1)
- **v1.3.3**: Fixed blind control - use `Open`/`Close` instead of `MoveUp`/`MoveDown`
- **v1.3.2**: Added logbook integration for switch click events
- **v1.3.1**: Best practices: Entity categories, availability detection, HomeAssistantError exceptions, EntityDescription refactoring
- **v1.3.0**: Added smart meter, air quality, and valve sensors. Added diagnostics support.
- **v1.2.1**: Added German translations for DACH region customers
- **v1.2.0**: Added optional area sync feature (sync Evon rooms to HA areas)
- **v1.1.5**: Fixed AbortFlow exception handling (was causing "Unexpected error" for already configured)
- **v1.1.4**: Improved error handling in API client (JSON decode, unexpected errors)
- **v1.1.3**: Fixed config flow "Unexpected error" by adding strings.json and fixing auth error handling
- **v1.1.2**: Fixed switch detection (corrected class name to `SmartCOM.Switch`)
- **v1.1.1**: Documentation and branding updates, HACS buttons
- **v1.1.0**: Added sensors, switches, options flow, reconfigure flow, MCP resources and scenes
- **v1.0.0**: Initial release with lights, blinds, and climate support
