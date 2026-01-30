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
├── coordinator/         # Data update coordinator package
│   ├── __init__.py      # Main coordinator with connection failure tracking
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
│       └── scenes.py
├── light.py             # Light platform
├── cover.py             # Cover/blind platform
├── climate.py           # Climate platform
├── sensor.py            # Sensor platform (temperature, energy, air quality)
├── switch.py            # Switch platform (relays, bathroom radiators)
├── select.py            # Select platform (home state, season mode)
├── binary_sensor.py     # Binary sensor platform (valves)
├── button.py            # Button platform (scenes)
├── diagnostics.py       # Diagnostics data export
├── strings.json         # UI strings
└── translations/        # Localization files (en.json, de.json)
```

### MCP Server

```
src/
├── index.ts             # MCP server entry point
├── api-client.ts        # Evon API client
├── config.ts            # Environment configuration
├── constants.ts         # Shared constants
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

### Scene Methods

| Method | Parameters | Description |
|--------|------------|-------------|
| `Execute` | - | Execute the scene |

**Properties**: `Name` (string), `CanExecute` (bool)

**Class**: `System.SceneApp`

### Smart Meter Properties

| Property | Unit | Description |
|----------|------|-------------|
| `PowerActual` | W | Current power consumption |
| `Energy` | kWh | Total energy consumption |
| `Energy24h` | kWh | Rolling 24-hour energy (can decrease) |
| `UL1N` | V | Voltage phase L1 |
| `UL2N` | V | Voltage phase L2 |
| `UL3N` | V | Voltage phase L3 |
| `IL1` | A | Current phase L1 |
| `IL2` | A | Current phase L2 |
| `IL3` | A | Current phase L3 |
| `Frequency` | Hz | Grid frequency |
| `FeedIn` | W | Power fed to grid (negative = consuming) |
| `FeedInEnergy` | kWh | Total energy fed to grid |

**Note**: For HA Energy Dashboard, use `Energy` (total_increasing), not `Energy24h` which is a rolling window.

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

### Test Coverage

```bash
pytest --cov=custom_components/evon --cov-report=term-missing
```

Test files:
- `test_api.py` - API client tests
- `test_config_flow.py` / `test_config_flow_unit.py` - Configuration flow tests
- `test_coordinator.py` - Coordinator and getter method tests
- `test_diagnostics.py` - Diagnostics export tests
- `test_light.py`, `test_cover.py`, `test_climate.py` - Platform tests
- `test_sensor.py`, `test_switch.py`, `test_select.py` - Entity tests
- `test_binary_sensor.py`, `test_button.py` - Additional entity tests

Current coverage: ~84% (130+ tests)

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
