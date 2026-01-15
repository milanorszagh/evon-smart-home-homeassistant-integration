# AGENTS.md - AI Agent Guidelines for Evon Smart Home

This document provides critical information for AI agents working with this codebase.

## Project Overview

This repository contains two integrations for Evon Smart Home systems:
- **MCP Server** (`src/index.ts`) - TypeScript-based Model Context Protocol server
- **Home Assistant Integration** (`custom_components/evon/`) - Python-based HA custom component

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

### Climate Preset Mode - IMPORTANT

Climate devices use different properties depending on type:

| Device Type | Class Name | Preset Property |
|-------------|------------|-----------------|
| ClimateControlUniversal | Contains `ClimateControlUniversal` | `ModeSaved` |
| ClimateControl/Thermostat | `SmartCOM.Clima.ClimateControl` | `MainState` |

Both properties use the same value mapping:
- `2` = freeze_protection
- `3` = energy_saving
- `4` = comfort

**Code should check `ModeSaved` first, then fall back to `MainState`:**
```python
mode_saved = details.get("ModeSaved", details.get("MainState", 4))
```

**DO NOT use the `Mode` property** for preset detection - it indicates heating vs cooling mode (0=heating, 1=cooling), not the preset.

**Note**: The heating/cooling mode (`Mode`/`CoolingMode`) is typically read-only. Most Evon installations have `CoolingModeWriteable: false`, meaning the mode is controlled by seasonal schedules in Evon and cannot be changed via the API.

To set preset modes, use these methods:
- `WriteDayMode` - sets comfort mode
- `WriteNightMode` - sets energy saving mode
- `WriteFreezeMode` - sets freeze protection mode

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

### Physical Buttons (SmartCOM.Switch) - CANNOT BE MONITORED

**CRITICAL**: Physical wall buttons (`SmartCOM.Switch` class) **cannot be reliably monitored** by external systems:

1. **Momentary state only**: The `IsOn` property is `true` ONLY while the button is physically pressed (milliseconds)
2. **No event history**: There is NO `LastClickType`, click log, or event history
3. **No push notifications**: Evon API has NO WebSocket or event streaming support
4. **Polling is ineffective**: Even 100ms polling intervals miss button presses

**What this means for agents:**
- Do NOT create event entities, binary sensors, or triggers for `SmartCOM.Switch` devices
- Do NOT attempt to implement button press detection - it will not work
- The buttons work within Evon's internal system but cannot be observed externally
- Only `SmartCOM.Light.Light` (controllable relay outputs) should be exposed as switches

### Method Naming Pattern

Evon uses "Amzn" prefix for methods that were designed for Alexa integration. These are the reliable methods for device control:
- `AmznTurnOn` / `AmznTurnOff` - lights and switches
- `AmznSetBrightness` - light brightness
- `AmznSetPercentage` - blind position

## File Locations

### MCP Server
- Source: `src/index.ts`
- Compiled: `dist/index.js`
- Build: `npm run build`

### Home Assistant Integration
- All files in: `custom_components/evon/`
- Entry point: `__init__.py`
- API client: `api.py`
- Base entity: `base_entity.py`
- Data coordinator: `coordinator.py`
- Platforms: `light.py`, `cover.py`, `climate.py`, `sensor.py`, `switch.py`, `select.py`, `binary_sensor.py`
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

For live testing:
1. Copy files to HA's `custom_components/evon/`
2. Restart Home Assistant (or use reload from integration menu)
3. Check logs at Settings → System → Logs

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
   - `ModeSaved` - Found to change: 2=freeze, 3=energy_saving, 4=comfort

3. **Test by changing preset in Evon** and re-querying to see which property changes

4. **Verify HA integration** correctly reads the identified property

This approach helped discover that `ModeSaved` (not `Mode`) indicates the preset mode.

## Device Class Names

When filtering devices from the API, use these class names:

| Device | Class Name | Controllable |
|--------|------------|--------------|
| Dimmable Lights | `SmartCOM.Light.LightDim` | Yes |
| Relay Outputs (Switches) | `SmartCOM.Light.Light` | Yes |
| Blinds | `SmartCOM.Blind.Blind` | Yes |
| Climate | `SmartCOM.Clima.ClimateControl` | Yes |
| Climate (universal) | Contains `ClimateControlUniversal` | Yes |
| Bathroom Radiator | `Heating.BathroomRadiator` | Yes (use `Switch` method to toggle) |
| Home State | `System.HomeState` | Yes (use `Activate` method) |
| Physical Buttons | `SmartCOM.Switch` | **NO** (read-only, unusable) |
| Smart Meter | Contains `Energy.SmartMeter` | No (sensor only) |
| Air Quality | `System.Location.AirQuality` | No (sensor only) |
| Climate Valve | `SmartCOM.Clima.Valve` | No (sensor only) |
| Room/Area | `System.Location.Room` | No (used for area sync) |

## API Authentication Flow

1. POST to `/login` with headers `x-elocs-username` and `x-elocs-password`
2. Get token from response header `x-elocs-token`
3. Use token in cookie for all subsequent requests: `Cookie: token=<token>`
4. On 302 or 401 response, re-authenticate and retry

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
3. Add filtering logic to `coordinator.py` in `_async_update_data()`
4. Create new platform file (e.g., `sensor.py`)
5. Add platform to `PLATFORMS` list in `__init__.py`
6. Update `manifest.json` if needed

## Integration Features

### Home Assistant
- **Platforms**: Light, Cover, Climate, Sensor, Switch, Select, Binary Sensor
- **Select Entity**: Home state selector (At Home, Holiday, Night, Work)
- **Switch Entity**: Bathroom radiators with timer functionality
- **Climate**: Heating/cooling modes, preset modes (comfort, energy_saving, freeze_protection)
- **Options Flow**: Configure poll interval (5-300 seconds), area sync
- **Reconfigure Flow**: Change host/credentials without removing integration
- **Reload Support**: Reload without HA restart
- **Stale Entity Cleanup**: Automatic removal of orphaned entities on reload
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
- `night` - Lights off, energy saving mode

## Linting

### Python (ruff)
```bash
# Install ruff
pip install ruff

# Check for issues
ruff check custom_components/evon/

# Auto-fix issues
ruff check custom_components/evon/ --fix

# Format code
ruff format custom_components/evon/
```

### TypeScript (eslint)
```bash
# Install dependencies
npm install

# Check for issues
npm run lint

# Auto-fix issues
npm run lint:fix
```

## Unit Tests

Tests are in the `tests/` directory:
- `test_standalone.py` - Standalone tests (no HA dependency)
- `test_api.py` - API client and password encoding tests
- `test_config_flow.py` - Config and options flow tests
- `test_coordinator.py` - Data coordinator tests

Test constants are defined in `tests/conftest.py`:
```python
TEST_HOST = "http://192.168.1.100"
TEST_USERNAME = "testuser"
TEST_PASSWORD = "testpass"
```

Run standalone tests (no HA required):
```bash
python3 tests/test_standalone.py
```

Run all tests with pytest:
```bash
pip install -r requirements-test.txt
pytest
```

## Release Process

Before creating a release, ensure the following are up to date:

1. **Version numbers** - Update in all three files:
   - `package.json`
   - `pyproject.toml`
   - `custom_components/evon/manifest.json`

2. **Documentation** - Update these files with any new findings:
   - `README.md` - User-facing documentation, supported devices, API reference
   - `AGENTS.md` - AI agent guidelines, debugging tips, API discoveries

3. **Version history** - Add entry to both README.md and AGENTS.md

4. **Linting** - Run linters before committing:
   ```bash
   python3 -m ruff check custom_components/evon/
   npm run lint
   ```

**Important**: Always document new API findings (properties, methods, behaviors) in both README.md (API Reference section) and AGENTS.md (relevant sections). This helps future debugging and development.

## Version History

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
