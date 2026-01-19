# AGENTS.md - AI Agent Guidelines for Evon Smart Home

**IMPORTANT FOR CLAUDE:** This is the primary reference document. Always check this file first when working with this codebase. The Evon MCP server is available for direct API queries - prefer using it over writing scripts.

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
| Bathroom Radiator | `is_on` |
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
3. Add filtering logic to `coordinator.py` in `_async_update_data()`
4. Create new platform file (e.g., `sensor.py`)
5. Add platform to `PLATFORMS` list in `__init__.py`
6. Update `manifest.json` if needed

## Integration Features

### Home Assistant
- **Platforms**: Light, Cover, Climate, Sensor, Switch, Select, Binary Sensor
- **Select Entities**: Season mode (heating/cooling), Home state (At Home, Holiday, Night, Work)
- **Switch Entity**: Bathroom radiators with timer functionality
- **Climate**: Heating/cooling modes, preset modes (comfort, eco, away), season mode
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

Tests are in the `tests/` directory:
- `test_standalone.py` - Standalone tests (no HA dependency, reads files directly)
- `test_api.py` - API client tests (mocks homeassistant, works without HA installed)
- `test_config_flow.py` - Config and options flow tests (requires homeassistant)
- `test_coordinator.py` - Data coordinator tests (requires homeassistant)

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

4. **Linting** - Run all CI checks before committing:
   ```bash
   ruff check custom_components/evon/ && ruff format --check custom_components/evon/ && npm run lint
   ```

**Important**: Always document new API findings (properties, methods, behaviors) in both README.md (API Reference section) and AGENTS.md (relevant sections). This helps future debugging and development.

## Version History

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
