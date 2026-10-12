# AGENTS.md - AI Agent Guidelines for Evon Smart Home

**IMPORTANT FOR CLAUDE:** This is the primary reference document. Always check this file first when working with this codebase. The Evon MCP server is available for direct API queries - prefer using it over writing scripts.

**Commit messages:** Do not add Co-Authored-By lines to commit messages.

**Before committing:** Always run `ruff check custom_components/evon/ tests/ && ruff format --check custom_components/evon/ tests/` to catch linting/formatting issues before they fail CI. Use `--fix` and `ruff format` to auto-fix.

**GitHub Releases:** Do NOT include the version number in the release title. HACS automatically prepends the tag name (e.g., `v1.19.2 - `), so including it in the title creates duplication like `v1.19.2 - v1.19.2 — Fix ...`. Use only a descriptive title, e.g., `--title "Fix double-click detection"`.

This document provides critical information for AI agents working with this codebase.

## Project Overview

This repository contains two integrations for Evon Smart Home systems. **Branding note (October 2026):** evon Smart Home was taken over by Schrack Technik; `evon-smarthome.com` now redirects to `building.schrack.at` and the product/app is being renamed *Schrack Smart Building*. Do NOT rename the integration domain (`evon`), entity IDs, `manufacturer="Evon"`, or the repository because of this — only user-facing links/descriptions mention Schrack. The remote relay `my.evon-smarthome.com` is still live (verified 2026-10-12); every remote URL (API base, WS host, Origin, login) derives from `EVON_REMOTE_HOST` in `const.py` — a source-inspection test (`test_no_relay_url_literals_in_ws_client`) keeps it that way, so a future relay move is a one-line change.

Integrations:
- **MCP Server** (`src/index.ts`) - TypeScript-based Model Context Protocol server
- **Home Assistant Integration** (`custom_components/evon/`) - Python-based HA custom component

## Documentation Structure

**IMPORTANT**: When updating documentation, put content in the correct file based on audience:

| File | Audience | Content |
|------|----------|---------|
| **README.md** | End users | Installation, features, configuration, platform descriptions (user-friendly, no internal details), one-line version highlights |
| **CHANGELOG.md** | Everyone | The detailed version history in [Keep a Changelog](https://keepachangelog.com/) format: one section per version with Breaking / Added / Changed / Fixed / Project bullets |
| **DEVELOPMENT.md** | Developers | Architecture, API reference, device classes, methods, code patterns, testing, MCP server setup |
| **AGENTS.md** | AI agents | Critical API knowledge, debugging tips, gotchas, implementation patterns |

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
| Version history (one line per version) | README.md |
| Version history (detailed, per version) | CHANGELOG.md |

### Guidelines

1. **README.md should be user-friendly** - No internal implementation details, no API property names, no code examples
2. **DEVELOPMENT.md is for developers** - Technical details, API reference, code patterns
3. **AGENTS.md is for AI agents** - Critical knowledge that prevents mistakes, debugging tips, gotchas
4. **Keep formatting consistent** - Use tables for structured data, code blocks for examples
5. **Update version history** - One line in README.md, the detailed section in CHANGELOG.md (never a blob of prose: bullets under Breaking / Added / Changed / Fixed / Project)
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

**USE `BrightnessSetScaled`** (canonical name) - this is the correct method that controls the actual physical brightness. The HTTP fallback translates this to `AmznSetBrightness` automatically.

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
- **USE `SetPosition`** (canonical name) - sets blind position (0-100). The HTTP fallback translates this to `AmznSetPercentage` automatically.
- **USE `SetAngle`** - sets tilt angle (0-100)

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
5. **HA select options are lowercase keys, not the Evon IDs** (since v1.23.0): the `home_state` select exposes `at_home`, `night`, `work`, `holiday` — the keys of `HOME_STATE_MAP` in `const.py` — because hassfest requires translation keys to match `[a-z0-9-_]+`. `select.py` maps keys ↔ Evon IDs (`home_state_option_for_id()` derives a key for unknown IDs, e.g. `HomeStateMyParty` → `my_party`). The raw Evon IDs are still accepted with a deprecation warning — but only via the `async_handle_select_option` override (the `select.select_option` service entry point): HA validates the option against `options` there, *before* `async_select_option` runs, so a shim inside `async_select_option` is unreachable (review finding, Oct 2026). Planned removal of the shim: v1.25.0. Do not "fix" the select back to raw IDs.

```javascript
// Example: Switch to night mode
await callMethod("HomeStateNight", "Activate");
```

### Physical Buttons (SmartCOM.Switch) - WebSocket Event Entities

Physical wall buttons (`SmartCOM.Switch` class) are exposed as **HA event entities** with press type detection:

1. **WebSocket events**: Buttons fire `ValuesChanged` events with `IsOn` property (`True` on press, `False` on release)
2. **Press type detection**: The standalone `ButtonPressDetector` class (`coordinator/button_press.py`) detects single press, double press, and long press based on timing
3. **WebSocket-only**: No HTTP polling fallback — buttons only work when WebSocket is connected
4. **Configurable double-click delay**: Users can adjust the detection window (0.2–1.4s, default 0.8s) via integration options

**What this means for agents:**
- Button entities are created by `EvonButtonEvent` in `event.py` with `_entity_type = ENTITY_TYPE_BUTTON_EVENTS`
- The processor (`process_button_events`) creates entities from the `/instances` list — no HTTP detail fetch needed
- `ButtonPressDetector` is a standalone class with no HA dependencies, initialized lazily via `_get_button_detector()`
- The detector uses `on_press`, `schedule_timer`, and `on_timeout` callbacks for decoupled integration
- Press detection flows: coordinator `_handle_button_press()` → detector → `_fire_button_event()` (on_press) / `_button_press_timeout()` (on_timeout)
- Bus event `evon_button_press` is fired with `device_id`, `name`, and `press_type`
- Device triggers are available for automation (single/double/long press per button)
- `SmartCOM.Light.Light` (relay outputs) are now exposed as HA light entities with `ColorMode.ONOFF` (not switches)

**Testing confirmed (February 2026):**
- Button instances fire WebSocket events reliably
- Single press ~190ms, double press detection within configurable delay window (default 0.8s), long press >1.5s
- The Evon controller sends 4 different WS patterns for double-press: `True,True,False` (coalesced release), `True,False,False` (coalesced press), `True,False,True,False` (standard 4-event), and `False,True,False` (swallowed first True — controller drops the first press-down). All 4 patterns are handled by the detector.

### Method Naming Convention

The codebase uses **WS-native method names as canonical names** everywhere. The HTTP API uses "Amzn"-prefixed equivalents, but the translation is handled automatically by `get_http_method_name()` (Python) and `CANONICAL_TO_HTTP_METHOD` (TypeScript).

| Canonical (WS-native) | HTTP API Equivalent | Used For |
|---|---|---|
| `SwitchOn` | `AmznTurnOn` | Lights |
| `SwitchOff` | `AmznTurnOff` | Lights |
| `BrightnessSetScaled` | `AmznSetBrightness` | Light brightness |
| `SetPosition` | `AmznSetPercentage` | Blind position |
| `SetAngle` | `SetAngle` | Blind tilt |

Relay outputs (`SmartCOM.Light.Light`) are now light entities and use the same `SwitchOn`/`SwitchOff` WS control as dimmable lights.

## WebSocket Control - CRITICAL FINDINGS (January 2026)

The integration now supports WebSocket-based device control for faster, more responsive operation. **However, there are important traps to avoid.**

### What Works via WebSocket

| Device | Method | WebSocket Call | Notes |
|--------|--------|----------------|-------|
| Light On | `SwitchOn` | `CallMethod [instanceId.SwitchOn, []]` | ✅ Explicit on - PREFERRED |
| Light Off | `SwitchOff` | `CallMethod [instanceId.SwitchOff, []]` | ✅ Explicit off - PREFERRED |
| Light Brightness | `BrightnessSetScaled` | `CallMethod [instanceId.BrightnessSetScaled, [brightness, transition]]` | ✅ transition=0 for instant |
| Blind Open/Close/Stop | `Open/Close/Stop` | `CallMethod [instanceId.Open, []]` | ✅ Verified |
| Blind Position+Tilt | `MoveToPosition` | `CallMethod [instanceId.MoveToPosition, [angle, position]]` | ✅ Angle comes FIRST! |
| Climate Temperature | `WriteCurrentSetTemperature` | `CallMethod [instanceId.WriteCurrentSetTemperature, [value]]` | ✅ Verified working |
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

### Note #4: Relay Output Control

Relay outputs (`SmartCOM.Light.Light`) are now exposed as **light entities** with `ColorMode.ONOFF` (no dimming). They use `SwitchOn`/`SwitchOff` via WebSocket CallMethod, same as dimmable lights. HTTP fallback translates to `AmznTurnOn`/`AmznTurnOff`.

**Important naming distinction:** `SmartCOM.Switch` is NOT a relay — it's the Evon class for physical wall buttons (Tasters), exposed as event entities. Relay outputs use class `SmartCOM.Light.Light` and appear as on/off lights in HA.
```
// WebSocket (preferred):
CallMethod instanceId.SwitchOn([])
// HTTP fallback:
POST /api/instances/{relay_id}/AmznTurnOn
```

### TRAP #5: Non-Dimmable Lights in Light Groups

When a non-dimmable light (e.g., Evon relay controlling power for a combined light with Govee) is part of a light group:
- Brightness changes trigger `turn_on()` on all group members
- The non-dimmable light receives `turn_on()` WITHOUT brightness parameter
- The integration skips the API call if the light is already on (avoids unnecessary traffic)

This is handled automatically in `light.py` - non-dimmable lights that are already on will not receive WebSocket commands when brightness changes on the group.

### Implementation Details

The codebase uses WS-native names as canonical method names everywhere. When the HTTP fallback is needed, `ws_control.get_http_method_name()` (Python) or `CANONICAL_TO_HTTP_METHOD` (TypeScript) translates them to HTTP names automatically.

See `custom_components/evon/ws_control.py` for the mapping configuration and `api.py` for the `_try_ws_control()` method that handles WebSocket-first control with HTTP fallback.

Tests documenting these findings are in `tests/test_ws_client.py` under `TestWebSocketControlFindings`.

## File Locations

### MCP Server
- Entry point: `src/index.ts`
- API client: `src/api-client.ts`
- Authentication: `src/auth.ts`
- WebSocket client: `src/ws-client.ts`
- Helpers: `src/helpers.ts`
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
  - Button press detector: `coordinator/button_press.py` (standalone state machine, no HA dependencies)
  - Device processors: `coordinator/processors/` (lights, blinds, climate, switches, smart_meters, air_quality, valves, home_states, bathroom_radiators, scenes, security_doors, intercoms, cameras, button_events)
- Platforms: `light.py`, `cover.py`, `climate.py`, `sensor.py`, `switch.py`, `select.py`, `binary_sensor.py` (valves, security doors, intercoms), `button.py`, `camera.py`, `camera_recorder.py` (snapshot→MP4 recording), `image.py` (doorbell snapshots)
- Config flow: `config_flow.py` (includes options and reconfigure flows)
- Repairs: `repairs.py` (`async_create_fix_flow` for the fixable stale-entities / relay-migrated issues — HA discovers fix flows only from this `<domain>/repairs.py` module, not from `config_flow.py`)
- WebSocket: `ws_client.py` (WebSocket client), `ws_control.py` (WebSocket control mappings), `ws_mappings.py` (WebSocket property mappings)
- Utilities: `statistics.py` (long-term energy statistics), `device_trigger.py` (device automation triggers), `diagnostics.py` (integration diagnostics), `recordings_view.py` (authenticated HTTP view serving camera recordings)

## Testing Changes

### MCP Server
```bash
npm run build
# Restart Claude Code to reload the MCP server
```

### Home Assistant Integration
```bash
# Run unit tests — Python 3.14 required (the HA 2026.x test harness needs it)
python3.14 -m venv .venv && source .venv/bin/activate
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

**Log gotchas (HAOS):** `ha core logs` returns only its last 100 journal lines unless you pass `-n`; with `custom_components.evon: debug` enabled that is seconds of history, so always pass `-n 300000` (the script does). The journal is one stream per *host* boot, not per HA core restart, so `-b` does not separate core restarts — split by timestamp instead. Lines carry ANSI colour codes; strip them before grepping. When comparing before/after a deploy, note the exact restart time first: the previous process's shutdown noise (e.g. `Session is closed and no session factory available`, `cannot schedule new futures after shutdown`) lands right next to the new process's startup lines.

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
| `list_climate` | List all climate devices with current state |
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
| Relay Outputs (On/Off Lights) | `SmartCOM.Light.Light` | Yes |
| RGBW Lights | `SmartCOM.Light.DynamicRGBWLight` | Yes |
| Light Groups | `SmartCOM.Light.LightGroup` | Yes |
| Blinds | `SmartCOM.Blind.Blind` | Yes |
| Blind Groups | `SmartCOM.Blind.BlindGroup` | Yes |
| Climate | `SmartCOM.Clima.ClimateControl` | Yes |
| Climate (universal) | Contains `ClimateControlUniversal` | Yes |
| Bathroom Radiator | `Heating.BathroomRadiator` | Yes (use `Switch` method to toggle) |
| Home State | `System.HomeState` | Yes (use `Activate` method) |
| Scene | `System.SceneApp` | Yes (use `Execute` method) |
| Physical Buttons | `SmartCOM.Switch` | No (event entity, WS-only) |
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
- Engine ID redacted in diagnostics export — including `entry.title` (which embeds the host or Engine ID), not just `data`/`options`
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

### Camera Recordings
- Served through an authenticated `HomeAssistantView` (`recordings_view.py`, `requires_auth=True`) at `/evon/recordings/{filename}`, **not** a static path. Static paths registered via `async_register_static_paths` bypass HA auth (like `www/`), which would let anyone who can reach the HA HTTP port download footage — including over a Nabu Casa remote URL or reverse proxy.
- The Lovelace card plays recordings inline via `auth/sign_path` signed URLs, which the authenticated view validates; the media browser (`media_source`) is likewise auth-gated.
- Filenames are validated (no `/`, `\`, or dot-segments) and the resolved path is confined to the recordings directory before serving.

## Optimistic Updates

All controllable entities implement optimistic updates to prevent UI flicker when changing state. When a user triggers an action (turn on light, change preset, etc.), the UI immediately shows the expected state without waiting for the coordinator to poll Evon.

**How it works (v1.22+):**
1. User triggers action (e.g., turn on light)
2. Entity sets optimistic state, records `_optimistic_state_set_at`, calls `async_write_ha_state()`
3. API call is made to Evon (WS preferred, HTTP fallback)
4. Entity calls `self._schedule_post_command_recheck()` — arms a 5s `async_call_later` that will call `coordinator.async_request_refresh()` if no WS event arrives. Replaces the v1.21 pattern of an immediate refresh after every command.
5. WS event for this entity arrives: `_cancel_post_command_recheck_if_data_changed()` cancels the pending recheck (WS is alive — no manual poll needed). Cancellation keys off the coordinator's per-entity WS-update timestamp advancing, **not** dict identity — so a stale in-flight HTTP poll rebuilding the entity dict during the quiesce window does not defeat the recheck safety net (RV-D1). Selects override the snapshot/compare to use their coordinator state value.
6. In `_handle_coordinator_update()`: the comparison-clear logic runs ALWAYS (even during quiesce) — optimistic is cleared when actual matches expected. The `POST_COMMAND_QUIESCE_PERIOD` (5s) only gates whether `super().async_write_ha_state()` runs, suppressing attribute flicker during fade animations.
7. Backstop: `OPTIMISTIC_STATE_TIMEOUT` (30s) clears stuck optimistic state if neither a confirming WS event nor the recheck ever resolves it.

**Entities with optimistic updates:**
| Entity | Optimistic Properties |
|--------|----------------------|
| Light | `is_on`, `brightness`, `color_temp` |
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
    self._set_optimistic_timestamp()
    self.async_write_ha_state()
    await self._api.turn_on(...)
    self._schedule_post_command_recheck()  # 5s self-healing fallback

# In coordinator update handler
def _handle_coordinator_update(self):
    self._cancel_post_command_recheck_if_data_changed()

    # Comparison-clear ALWAYS runs (so matching WS clears optimistic ASAP)
    if self._optimistic_is_on is not None:
        actual = self.coordinator.get_entity_data(...)
        if actual == self._optimistic_is_on:
            self._optimistic_is_on = None
            self._optimistic_state_set_at = None

    # Suppress async_write_ha_state only while optimistic is still active
    # (prevents attribute flicker during Evon's fade animation).
    if (
        self._optimistic_state_set_at is not None
        and time.monotonic() - self._optimistic_state_set_at < POST_COMMAND_QUIESCE_PERIOD
    ):
        return
    super()._handle_coordinator_update()

# In async_will_remove_from_hass
async def async_will_remove_from_hass(self):
    self._cleanup_post_command_recheck()
    await super().async_will_remove_from_hass()
```

**Select entity override:** `EvonHomeStateSelect` and `EvonSeasonModeSelect` read state from `coordinator.get_active_home_state()` / `get_season_mode()` rather than `_get_data()`. They override `_recheck_snapshot()` and `_recheck_data_changed()` on `EvonEntity` so the cancel-on-WS mechanism uses value equality against the right coordinator method. Selects don't apply the quiesce drop — they have no animation.

## Common Pitfalls

1. **Empty device names**: Skip instances where `Name` is empty - these are templates/base classes
2. **Token expiry**: Tokens expire; implement retry logic with re-authentication
3. **Brightness values**: Evon uses 0-100, Home Assistant uses 0-255 — convert with `round()` in both directions for consistency. Minimum brightness is clamped to 1% (Evon) to prevent HA brightness=1 mapping to 0%.
4. **Position inversion**: Evon and HA have opposite conventions for cover position

## Architecture Decisions (Do Not Change)

These are intentional design choices. Do NOT flag them as bugs or attempt to "fix" them during code reviews:

1. **Scenes not in `CLASS_TO_TYPE` (ws_mappings.py)**: `EVON_CLASS_SCENE` is intentionally omitted. Scenes are fire-and-forget button entities (`button.py`) with no observable state — they don't need WebSocket subscriptions.

2. **HVAC COOL and HEAT both call comfort mode (climate.py)**: Correct behavior. The heating/cooling distinction is controlled by the global Season Mode (per-system `Base.ehThermostat.IsCool`), not per-room HVAC mode. Setting any non-OFF mode restores the comfort preset.

3. **`ENTITY_TYPE_SWITCHES` entries in `SUBSCRIBE_PROPERTIES`/`PROPERTY_MAPPINGS` (ws_mappings.py)**: Retained for future switch classes but currently unreachable — no class in `CLASS_TO_TYPE` maps to this entity type. `Base.bSwitch` sub-instances (intercom door relays, template objects) are silently skipped by `get_entity_type()` — they were never processed into entities even when mapped. `SmartCOM.Light.Light` relay outputs are on the light platform.

4. **Duplicate WebSocket status sensors (binary_sensor.py + sensor.py)**: Intentional — the binary sensor provides simple on/off for automations, while the text sensor provides rich diagnostics (uptime, latency, reconnect count). Both serve different use cases.

5. **`energy_today` treating missing data as 0 kWh (coordinator)**: Intentional. Changing this would alter behavior for existing users' energy dashboards. The current behavior is the safer default.

6. **`_sequence_id` growing unbounded (ws_client.py)**: Safe. Python handles arbitrary-precision integers. The counter resets to 1 on every reconnect. Only relevant for connections lasting months without a single reconnect — unrealistic.

7. **Quiesce drop not on all entity types**: The `POST_COMMAND_QUIESCE_PERIOD` early-return that suppresses `async_write_ha_state` is applied to lights, switches, climate, and covers — entities where intermediate WebSocket states cause visible UI flicker. Selects participate in the scheduled-recheck mechanism (via their `_recheck_snapshot` override) but skip the drop — they have no animation. Binary sensors and event entities don't need either because they have no optimistic state.

8. **`cover.py` uses `asyncio.sleep(COVER_STOP_DELAY)` inline**: Intentional 0.3s anti-flicker delay for toggle-style blind control. The `if self.hass is not None` guard after sleep is sufficient — the sleep is too short for CancelledError to be a practical concern.

9. **`_extract_instance_id_from_unique_id` is a 123-line reverse parser (__init__.py)**: Intentional — changing the unique_id format would break existing installations. The function handles all known formats correctly.

10. **Login logic duplicated between `EvonApi.login()` and `EvonWsClient._login()`**: The two paths have subtle differences (WS accepts token on 302 redirect, different header handling for remote connections). Unifying them risks breaking authentication.

11. **Climate substring match `EVON_CLASS_CLIMATE_UNIVERSAL not in class_name`**: Intentionally lenient to handle potential Evon subclass variants (e.g., `Heating.ClimateControlUniversal.V2`).

12. **Source-inspection tests using `ast.parse()` (test_processors.py)**: Camera/recorder code can't be imported in the test environment due to missing HA dependencies. Source inspection is the accepted tradeoff.

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
6. Set `_entity_type` class attribute and use `_get_data()` in entity
7. Create new platform file (e.g., `sensor.py`)
8. Add platform to `PLATFORMS` list in `__init__.py`
9. Add tests in `tests/test_new_device.py`
10. Update `manifest.json` if needed

## Integration Features

### Home Assistant
- **Platforms**: Light, Cover, Climate, Sensor, Switch, Select, Binary Sensor, Button, Camera, Image, Event
- **Select Entities**: Season mode (heating/cooling), Home state (At Home, Holiday, Night, Work)
- **Switch Entity**: Bathroom radiators with timer functionality
- **Climate**: Heating/cooling modes, preset modes (comfort, eco, away), season mode
- **Options Flow**: Configure poll interval (5-300 seconds), area sync, non-dimmable lights, HTTP-only mode toggle, debug logging, camera recording settings, button double-click delay
- **Non-dimmable Lights**: Mark lights as on/off only (useful for LED strips with PWM controllers)
- **Reconfigure Flow**: Change host/credentials without removing integration
- **Reload Support**: Reload without HA restart
- **Stale Entity Cleanup**: Automatic removal of orphaned entities on reload
- **Repairs**: Connection failure alerts, WebSocket disconnect warnings, stale entity notifications, relay migration notices, config migration warnings
- **Reauth Flow**: Automatic re-authentication prompt when credentials become invalid (`ConfigEntryAuthFailed`)
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
ruff check custom_components/evon/ tests/ && ruff format --check custom_components/evon/ tests/ && npm run lint
```

## Unit Tests

Tests are in the `tests/` directory (1322 tests):

**Platform tests:**
- `test_light.py` - Light entity tests
- `test_cover.py` - Cover/blind entity tests
- `test_climate.py` - Climate entity tests
- `test_sensor.py` - Sensor entity tests
- `test_switch.py` - Switch entity tests
- `test_select.py` - Select entity tests (home state, season mode)
- `test_binary_sensor.py` - Binary sensor tests (valves)
- `test_button.py` - Button entity tests (scenes)
- `test_button_events.py` - Physical button event entity and press detection tests
- `test_camera.py` - Camera entity tests (including snapshot fetch, error handling)
- `test_camera_recorder.py` - Camera recording tests (lifecycle, encoding, duration)
- `test_event.py` - Event entity tests (doorbell ring detection)
- `test_image.py` - Image entity tests (including fetch errors, snapshot handling)

**Unit tests (no HA dependency):**
- `test_diagnostics_unit.py` - Diagnostics unit tests
- `test_cover_unit.py` - Cover entity unit tests
- `test_binary_sensor_unit.py` - Binary sensor unit tests
- `test_select_unit.py` - Select entity unit tests
- `test_sensor_unit.py` - Sensor entity unit tests

**Core tests:**
- `test_api.py` - API client tests (mocks homeassistant, works without HA installed)
- `test_brightness_edges.py` - Brightness edge case tests
- `test_bulk_service_failures.py` - Bulk service failure handling tests
- `test_camera_mp4.py` - Camera MP4 recording tests
- `test_concurrent_updates.py` - Concurrent WS + HTTP update tests
- `test_config_flow.py` / `test_config_flow_unit.py` - Config and options flow tests
- `test_coordinator.py` - Data coordinator tests
- `test_coordinator_energy.py` - Energy statistics coordinator tests
- `test_coordinator_ws_cow.py` - WS copy-on-write coordinator tests
- `test_diagnostics.py` - Diagnostics export tests
- `test_base_entity.py` - Base entity class tests
- `test_constants.py` - Constants validation tests
- `test_energy_rollover.py` - Energy meter rollover tests
- `test_optimistic_state.py` - Optimistic state update tests
- `test_options_flow.py` - Options flow integration tests
- `test_options_flow_handler.py` - Options flow handler unit tests
- `test_reconnect_delay.py` - WebSocket reconnect delay tests
- `test_recording_services.py` - Recording service tests
- `test_services.py` - Service handler tests
- `test_service_invalid_params.py` - Service invalid parameter tests
- `test_stale_entities.py` - Stale entity cleanup tests
- `test_processors.py` - Data processor tests
- `test_ws_client.py` - WebSocket client tests (periodic cleanup, sequenceId validation, fire-and-forget)
- `test_ws_control.py` - WebSocket control mappings tests (method translation, HTTP fallback)
- `test_ws_mappings.py` - WebSocket property mapping tests (all device types, edge cases)
- `test_ws_reconnect.py` - WebSocket reconnect tests
- `test_device_trigger.py` - Device trigger tests
- `test_statistics.py` - Energy statistics import tests (daily, monthly, rate limiting, edge cases)
- `test_instance_id_extraction.py` - Instance ID extraction from unique_id tests
- `test_translations.py` - strings.json ↔ translations/*.json parity, selector/enum-state translatability (no HA needed)

### Test Architecture

**CI runs both linting and pytest.** Tests that require homeassistant use `requires_ha_test_framework` skip markers and are skipped in environments without HA installed.

Tests are split by dependency:
| Test File | Requires HA | How It Works |
|-----------|-------------|--------------|
| `test_api.py` | No | Mocks `homeassistant` module, uses `importlib` to load `api.py` directly |
| `test_*_unit.py` | No | Unit tests that mock all HA dependencies |
| `test_config_flow.py` | Yes | Uses `requires_ha_test_framework` skip marker |
| `test_coordinator.py` | Yes | Uses `requires_ha_test_framework` skip marker |

**Why this matters for agents:**
- When importing from `custom_components.evon.*`, Python executes `__init__.py` which imports from `homeassistant`
- To test without HA, mock the homeassistant module before importing (like `test_api.py` and the `*_unit.py` tests)

### Running Tests

```bash
# Install test dependencies (Python 3.14 required — an older interpreter fails with
# "No matching distribution found for pytest-homeassistant-custom-component")
pip install -r requirements-test.txt

# Run all tests (HA-dependent tests will be skipped if HA not installed)
pytest

# Run with verbose output
pytest -v
```

### CI Checks

The CI workflow (`.github/workflows/ci.yml`) runs:
1. `ruff check` - Python linting (custom_components/evon/ and tests/)
2. `ruff format --check` - Python formatting
3. `mypy` - Python type checking
4. `npm run lint` - TypeScript linting
5. `npm run build` - TypeScript compilation
6. `npm run test:mcp` - MCP server tests
7. `npm audit` - npm security audit (fails the build at `--audit-level=high`)
8. `pip-audit` - Python dependency audit (advisory-only; HA hard-pins its deps, so
   findings there are usually not fixable downstream)
9. `pytest` - Python tests (matrix: Python 3.14, Ubuntu + macOS) with Codecov upload
10. HACS validation - Custom component structure check
11. hassfest - Home Assistant's own integration validator (manifest keys and ordering, declared
    `dependencies`/`after_dependencies` for every imported component, translation key format
    `[a-z0-9-_]+`, services, config flow). Also runs on `v*` tags. Run it locally before pushing:
    `docker run --rm --platform linux/amd64 -v "$PWD"://github/workspace ghcr.io/home-assistant/hassfest`

Additional workflows:
- **CodeQL** (`.github/workflows/codeql.yml`) - Security scanning for Python and JavaScript/TypeScript on push, PRs, and weekly schedule. Results in the repo's Security tab.
- **Renovate** (`renovate.json`) - Automated dependency updates. Runs weekly (Monday, Europe/Vienna). Groups updates by ecosystem (npm deps, npm devDeps, pip, GitHub Actions). Patch updates automerge when CI passes. **Note (2026-10):** the config has never produced an onboarding PR, dependency dashboard or update PR, so the Mend Renovate GitHub App is evidently not installed on the repository — until it is, dependency drift (and `npm audit` CI failures) must be checked by hand.

### Pending Home Assistant Deprecations

Known upcoming HA changes that touch this integration but are not actionable yet (the replacement API is newer than the supported HA floor):

| HA change | Affects | Warns from | Removed in | Action |
|-----------|---------|------------|------------|--------|
| Climate `native_*` temperature properties (`_attr_native_temperature_unit`, `native_target_temperature`, `native_current_temperature`) | `climate.py` (`_attr_temperature_unit`, `target_temperature`, `current_temperature`) | 2026.11 | 2027.11 | Rename once the HA floor is ≥ 2026.11 |
| Standard button event types (`ButtonEventType`) | `event.py` (`single_press`/`double_press`/`long_press`) | — (optional) | — | Optional; custom event types stay valid |
| *(own deprecation)* legacy raw Evon IDs accepted by the home-state select's `async_handle_select_option` | `select.py` | v1.23.0 (warning) | v1.25.0 (planned) | Remove the shim and its tests |

Already handled (v1.23.0): `via_device` → `via_device_id`, `DeviceEntry.config_entries` → `DeviceEntry.config_entry_id`, `CONCENTRATION_PARTS_PER_MILLION` → `UnitOfRatio.PARTS_PER_MILLION`, `async_update_reload_and_abort` with an update listener → `async_update_entry` + listener-driven reload. The autouse fixture `fail_on_ha_deprecation_report` (tests/conftest.py) turns any new HA deprecation report into a test failure, so new ones surface as soon as the harness moves to the HA release that introduces them.

**Before committing, always run:**
```bash
ruff check custom_components/evon/ tests/
ruff format custom_components/evon/ tests/
npm run lint
```

## Pre-Commit Checklist

**IMPORTANT**: Before every commit, ensure documentation is updated:

1. **Update ALL documentation files** if the changes affect them:
   - `README.md` - User-facing features, installation, configuration
   - `DEVELOPMENT.md` - Architecture, API reference, code patterns
   - `AGENTS.md` - AI agent guidelines, debugging tips, gotchas
   - `docs/*.md` - Detailed technical documentation (e.g., BLIND_TILT_BEHAVIOR.md)

2. **Run linting** before committing:
   ```bash
   ruff check custom_components/evon/ tests/ && ruff format --check custom_components/evon/ tests/ && npm run lint
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
   - `AGENTS.md` - AI guidelines, debugging tips
   - `docs/*.md` - Detailed technical docs

3. **Version history** - Add entry to:
   - `CHANGELOG.md` (detailed: one `## [X.Y.Z] - YYYY-MM-DD` section, bullets grouped under Breaking changes / Added / Changed / Fixed / Project; set the date when tagging)
   - `README.md` (one table row: version, date, highlights)

4. **Linting** - Run all CI checks:
   ```bash
   ruff check custom_components/evon/ tests/ && ruff format --check custom_components/evon/ tests/ && npm run lint
   ```

5. **Build TypeScript** - Ensure MCP server compiles:
   ```bash
   npm run build
   ```

**Common mistake**: `package.json` version was not updated from v1.4.1 to v1.11.0 across multiple releases. Always check all four version files match!

**Dependency updates**: Renovate is configured to open weekly dependency update PRs (see `renovate.json`). Patch updates automerge when CI passes. Review and merge minor/major update PRs manually.

## Version History

The detailed version history lives in **[CHANGELOG.md](CHANGELOG.md)** (Keep a Changelog
format, one section per version). README.md keeps a one-line highlights table.

**IMPORTANT**: Before adding an entry, check the latest version section in CHANGELOG.md.
Never rewrite the section of an already-released version — create the next version's
section instead (marked `Unreleased` until it is tagged, when the date is filled in).
Keep entries as short bullets under *Breaking changes / Added / Changed / Fixed /
Project*; technical detail that agents need (property names, traps, method names) belongs
in the topic sections of this file, not in the changelog.
