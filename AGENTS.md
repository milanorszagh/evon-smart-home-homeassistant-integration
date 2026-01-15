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

### Blind Position Control

**DO NOT use `SetPosition`** - this may not work correctly.

**USE `AmznSetPercentage`** - this correctly sets the blind position.

Position convention in Evon:
- `0` = fully open (blind up)
- `100` = fully closed (blind down)

Note: Home Assistant uses the inverse (0=closed, 100=open), so conversion is needed.

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
- Data coordinator: `coordinator.py`
- Platforms: `light.py`, `cover.py`, `climate.py`, `sensor.py`, `switch.py`
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

## Device Class Names

When filtering devices from the API, use these class names:

| Device | Class Name |
|--------|------------|
| Dimmable Lights | `SmartCOM.Light.LightDim` |
| Switches (wall buttons) | `SmartCOM.Switch` |
| Non-dimmable Lights | `SmartCOM.Light.Light` |
| Blinds | `SmartCOM.Blind.Blind` |
| Climate | `SmartCOM.Clima.ClimateControl` |
| Climate (universal) | Contains `ClimateControlUniversal` |

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

```
EVON_HOST=http://192.168.x.x    # Evon system URL (your local IP)
EVON_USERNAME=<username>        # Your Evon username
EVON_PASSWORD=<password>        # Plain text OR encoded password (auto-detected)
```

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
- **Platforms**: Light, Cover, Climate, Sensor, Switch
- **Options Flow**: Configure poll interval (5-300 seconds)
- **Reconfigure Flow**: Change host/credentials without removing integration
- **Reload Support**: Reload without HA restart
- **Click Events**: Switches fire `evon_event` on event bus for automations
- **Entity Attributes**: Extra attributes exposed on all entities

### MCP Server
- **Tools**: Device listing and control (lights, blinds, climate)
- **Resources**: Read device state via `evon://` URIs
- **Scenes**: Pre-defined and custom scenes for whole-home control

## MCP Resources

Resources allow reading device state without calling tools:

| URI | Description |
|-----|-------------|
| `evon://lights` | All lights with state |
| `evon://blinds` | All blinds with state |
| `evon://climate` | All climate controls with state |
| `evon://summary` | Home summary with counts and averages |

## MCP Scenes

Pre-defined scenes:
- `all_off` - Turn off lights, close blinds
- `movie_mode` - Dim to 10%, close blinds
- `morning` - Open blinds, lights to 70%, comfort mode
- `night` - Lights off, energy saving mode

## Event Bus (Home Assistant)

Switches fire events on state change:

```yaml
event_type: evon_event
event_data:
  device_id: "SC1_M01.Switch1"
  device_name: "Living Room Switch"
  event_type: "double_click"  # single_click, double_click, long_press
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

## Version History

- **v1.1.3**: Fixed config flow "Unexpected error" by adding strings.json and fixing auth error handling
- **v1.1.2**: Fixed switch detection (corrected class name to `SmartCOM.Switch`)
- **v1.1.1**: Documentation and branding updates, HACS buttons
- **v1.1.0**: Added sensors, switches with click events, options flow, reconfigure flow, MCP resources and scenes
- **v1.0.0**: Initial release with lights, blinds, and climate support
