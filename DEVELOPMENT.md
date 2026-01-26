# Development Guide

This document provides architecture details, API reference, and development guidelines for contributors working on the Evon Smart Home integration.

For AI agents, see [AGENTS.md](AGENTS.md) which contains critical API knowledge and debugging tips.

---

## Architecture Overview

### Home Assistant Integration

```
custom_components/evon/
├── __init__.py          # Entry point, platform setup, stale entity cleanup
├── api.py               # Evon API client
├── base_entity.py       # Base entity class with common functionality
├── config_flow.py       # Configuration UI flows (setup, options, reconfigure, repairs)
├── const.py             # Constants, device classes, repair identifiers
├── coordinator.py       # Data update coordinator with connection failure tracking
├── light.py             # Light platform
├── cover.py             # Cover/blind platform
├── climate.py           # Climate platform
├── sensor.py            # Sensor platform (temperature, energy, air quality)
├── switch.py            # Switch platform (relays, bathroom radiators)
├── select.py            # Select platform (home state, season mode)
├── binary_sensor.py     # Binary sensor platform (valves)
├── diagnostics.py       # Diagnostics data export
├── strings.json         # UI strings
└── translations/        # Localization files (en.json, de.json)
```

### MCP Server

```
src/
├── index.ts             # MCP server entry point, tools, and resources
└── ... (compiled to dist/)
```

### Data Flow

```
1. User adds integration via config flow
2. config_flow.py validates credentials with API
3. __init__.py creates API client and coordinator
4. coordinator.py fetches all device data periodically
5. Platform files create entities from coordinator data
6. Entities read state from coordinator.data
7. Entities call API methods for control actions
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

Add to your Claude Code configuration (`~/.claude.json`):

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
| `list_scenes` | List available scenes |
| `activate_scene` | Activate a scene |
| `create_scene` | Create a custom scene |

### Available Resources

| Resource URI | Description |
|--------------|-------------|
| `evon://lights` | All lights with current state |
| `evon://blinds` | All blinds with current state |
| `evon://climate` | All climate controls with state |
| `evon://home_state` | Current and available home states |
| `evon://bathroom_radiators` | All bathroom radiators |
| `evon://summary` | Home summary (counts, avg temp, state) |

### Pre-defined Scenes

| Scene | Description |
|-------|-------------|
| `all_off` | Turn off all lights and close all blinds |
| `movie_mode` | Dim lights to 10% and close blinds |
| `morning` | Open blinds, set lights to 70%, comfort mode |
| `night` | Turn off lights, set climate to eco mode |

---

## Evon API Reference

### Authentication

```
POST /login
Headers:
  x-elocs-username: <username>
  x-elocs-password: <encoded-password>

Response Headers:
  x-elocs-token: <session-token>
```

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
| `SmartCOM.Light.Light` | Relay output | Yes |
| `SmartCOM.Blind.Blind` | Blind/shutter | Yes |
| `SmartCOM.Clima.ClimateControl` | Climate control | Yes |
| `*ClimateControlUniversal*` | Universal climate | Yes |
| `Base.ehThermostat` | Season mode | Yes |
| `System.HomeState` | Home state | Yes |
| `Heating.BathroomRadiator` | Bathroom heater | Yes |
| `SmartCOM.Switch` | Physical button | **No** (momentary) |
| `Energy.SmartMeter*` | Smart meter | No (sensor) |
| `System.Location.AirQuality` | Air quality | No (sensor) |
| `SmartCOM.Clima.Valve` | Climate valve | No (sensor) |
| `System.Location.Room` | Room/area | No |

### Light Methods

| Method | Parameters | Description |
|--------|------------|-------------|
| `AmznTurnOn` | - | Turn light on |
| `AmznTurnOff` | - | Turn light off |
| `AmznSetBrightness` | `[brightness]` (0-100) | Set brightness |

**Important**: Read `ScaledBrightness` property for actual brightness, not `Brightness`.

### Blind Methods

| Method | Parameters | Description |
|--------|------------|-------------|
| `Open` | - | Move blind up |
| `Close` | - | Move blind down |
| `Stop` | - | Stop movement |
| `AmznSetPercentage` | `[position]` (0-100) | Set position |
| `SetAngle` | `[angle]` (0-100) | Set tilt angle |

**Critical**: `MoveUp` and `MoveDown` do NOT exist - use `Open` and `Close`.

**Position convention**: Evon uses 0=open, 100=closed. Home Assistant uses the opposite.

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

---

## Known Limitations

### Physical Buttons (`SmartCOM.Switch`)

Cannot be monitored due to API limitations:
- `IsOn` is only `true` while physically pressed (milliseconds)
- No event history or push notifications
- Polling is ineffective

The integration does not create entities for these devices.

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
2. Add processing logic to `coordinator.py`
3. Create platform file or extend existing one
4. Register platform in `__init__.py` PLATFORMS list
5. Add API methods to `api.py` if needed

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

---

## Repairs Integration

| Repair | Trigger | Severity | Auto-clear |
|--------|---------|----------|------------|
| Connection failed | 3 consecutive failures | Error | Yes |
| Stale entities | Orphaned entities removed | Warning | Dismissible |
| Config migration | Incompatible version | Error | No |

Key files: `const.py` (constants), `coordinator.py` (connection tracking), `__init__.py` (entity/migration repairs), `config_flow.py` (repair flows)

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

### Unit Tests

```bash
pip install -r requirements-test.txt
pytest -v
```

Tests are in `tests/` - some require Home Assistant installed.

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
- Python: 3.11+
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
