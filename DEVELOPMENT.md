# Development Guide

This document provides architecture details, API findings, and development guidelines for contributors and AI agents working on the Evon Smart Home integration.

## Architecture Overview

### Home Assistant Integration (`custom_components/evon/`)

```
custom_components/evon/
├── __init__.py          # Entry point, platform setup
├── api.py               # Evon API client
├── base_entity.py       # Base entity class with common functionality
├── config_flow.py       # Configuration UI flows
├── const.py             # Constants and device classes
├── coordinator.py       # Data update coordinator
├── light.py             # Light platform
├── cover.py             # Cover/blind platform
├── climate.py           # Climate platform
├── sensor.py            # Sensor platform (temperature, energy, air quality)
├── switch.py            # Switch platform (controllable relays, bathroom radiators)
├── select.py            # Select platform (home states, season mode)
├── binary_sensor.py     # Binary sensor platform (valves)
├── diagnostics.py       # Diagnostics data export
├── strings.json         # UI strings
└── translations/        # Localization files
```

### MCP Server (`src/`)

```
src/
├── index.ts             # MCP server entry point, tools, and resources
└── ... (compiled to dist/)
```

## Data Flow

```
1. User adds integration via UI
2. config_flow.py validates credentials
3. __init__.py creates API client and coordinator
4. coordinator.py fetches all device data periodically
5. Platform files (light.py, cover.py, etc.) create entities
6. Entities read state from coordinator.data
7. Entities call api methods for control actions
```

## Evon API Details

### Authentication Flow

```
1. POST /login
   Headers:
     x-elocs-username: <username>
     x-elocs-password: Base64(SHA512(username + password))

2. Response includes:
     x-elocs-token: <session-token>

3. All subsequent requests:
     Cookie: token=<session-token>
```

### Key Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/login` | POST | Authenticate and get token |
| `/api/instances` | GET | List all device instances |
| `/api/instances/{id}` | GET | Get device details |
| `/api/instances/{id}/{method}` | POST | Call method on device |

### Device Classes

| Class | Type | Controllable | Notes |
|-------|------|--------------|-------|
| `SmartCOM.Light.LightDim` | Dimmable light | Yes | Use `ScaledBrightness` not `Brightness`. Can be marked non-dimmable in options. |
| `SmartCOM.Light.Light` | Relay output | Yes | Non-dimmable, on/off only |
| `SmartCOM.Blind.Blind` | Blind/shutter | Yes | Use `Open`/`Close`, NOT `MoveUp`/`MoveDown` |
| `SmartCOM.Clima.ClimateControl` | Climate | Yes | Preset via `ModeSaved` (values differ by season) |
| `*ClimateControlUniversal*` | Climate | Yes | Match by substring |
| `Base.ehThermostat` | Season mode | Yes | Global heating/cooling via `IsCool` property |
| `System.HomeState` | Home mode | Yes | Use `Activate` method to switch |
| `Heating.BathroomRadiator` | Bathroom heater | Yes | Toggle with `Switch` method |
| `SmartCOM.Switch` | Physical button | **No** | Read-only, momentary state |
| `Energy.SmartMeter*` | Smart meter | No | Sensor only |
| `System.Location.AirQuality` | Air quality | No | Sensor only |
| `SmartCOM.Clima.Valve` | Valve | No | Sensor only |
| `System.Location.Room` | Room/area | No | Used for area sync |

### Control Methods by Device Type

#### Lights (`SmartCOM.Light.LightDim` and `SmartCOM.Light.Light`)

| Method | Parameters | Description |
|--------|------------|-------------|
| `AmznTurnOn` | - | Turn on |
| `AmznTurnOff` | - | Turn off |
| `AmznSetBrightness` | `[brightness]` (0-100) | Set brightness (dimmable only) |

**Important**: Read `ScaledBrightness` property for actual brightness percentage, not `Brightness` (internal value).

**Optimistic Brightness**: When turning on without specifying brightness, the integration uses the last known brightness for optimistic display. This prevents the UI from showing 0% while waiting for Evon to report the actual brightness.

#### Blinds (`SmartCOM.Blind.Blind`)

| Method | Parameters | Description |
|--------|------------|-------------|
| `Open` | - | Move blind up |
| `Close` | - | Move blind down |
| `Stop` | - | Stop movement |
| `AmznSetPercentage` | `[position]` (0-100) | Set position |
| `SetAngle` | `[angle]` (0-100) | Set tilt angle |

**Critical**: `MoveUp` and `MoveDown` methods do NOT exist. Always use `Open` and `Close`.

**Position convention**: In Evon, 0 = fully open, 100 = fully closed. Home Assistant uses the opposite (0 = closed, 100 = open). The integration converts between them.

#### Climate (`SmartCOM.Clima.ClimateControl`)

| Method | Parameters | Description |
|--------|------------|-------------|
| `WriteDayMode` | - | Set comfort preset |
| `WriteNightMode` | - | Set eco preset |
| `WriteFreezeMode` | - | Set away/protection preset |
| `WriteCurrentSetTemperature` | `[temperature]` | Set target temperature |

**Preset values differ by Season Mode:**
| Preset | Heating Mode | Cooling Mode |
|--------|--------------|--------------|
| away | 2 | 5 |
| eco | 3 | 6 |
| comfort | 4 | 7 |

#### Season Mode (`Base.ehThermostat`)

Season Mode controls whether the entire house is in heating (winter) or cooling (summer) mode.

**Reading:**
```
GET /api/instances/Base.ehThermostat
→ IsCool: false = heating, true = cooling
```

**Setting:**
```
PUT /api/instances/Base.ehThermostat/IsCool
Content-Type: application/json
Body: {"value": false}  // HEATING (winter)
Body: {"value": true}   // COOLING (summer)
```

When changed, ALL climate devices switch simultaneously and their preset `ModeSaved` values shift accordingly.

#### Bathroom Radiator (`Heating.BathroomRadiator`)

| Method | Parameters | Description |
|--------|------------|-------------|
| `Switch` | - | Toggle on/off (timer-based) |

**Properties:**
| Property | Description |
|----------|-------------|
| `Output` | Current on/off state |
| `NextSwitchPoint` | Minutes remaining until auto-off |
| `EnableForMins` | Configured run duration |

#### Home State (`System.HomeState`)

| Method | Parameters | Description |
|--------|------------|-------------|
| `Activate` | - | Activate this home state |

**Properties:**
| Property | Description |
|----------|-------------|
| `Active` | `true` if this state is currently active |
| `ActiveInstance` | ID of the currently active home state |
| `Name` | Display name of the state |

**Available states:**
| ID | German Name | English |
|----|-------------|---------|
| `HomeStateAtHome` | Daheim | At Home |
| `HomeStateHoliday` | Urlaub | Holiday |
| `HomeStateNight` | Nacht | Night |
| `HomeStateWork` | Arbeit | Work |

**Important**: Skip instances where ID starts with `System.` - these are templates.

**Display Order**: Home states are sorted in preferred order: At Home, Night, Work, Holiday. Unknown states appear at the end. See `HOME_STATE_ORDER` in `select.py`.

## Known Limitations

### Physical Buttons (`SmartCOM.Switch`)

Physical wall buttons **cannot be monitored** by Home Assistant:

1. **Momentary state only**: `IsOn` property is `true` only while button is physically pressed
2. **No event history**: No `LastClickType` or click log
3. **No push notifications**: Evon API has no WebSocket or event streaming
4. **Polling ineffective**: Button presses (milliseconds) are missed between polls

**Investigation conducted**:
- Tested 100ms polling intervals - still couldn't catch button presses
- Checked for WebSocket endpoints - none exist
- Looked for event log APIs - none available
- Tested all potential methods (Press, Click, Trigger, etc.) - all return 404

**Conclusion**: These buttons work within Evon's internal system but cannot be observed externally. The integration does not create entities for `SmartCOM.Switch` devices.

### Controllable Switches vs Input Buttons

- `SmartCOM.Light.Light` = Controllable relay outputs (supported as switches)
- `SmartCOM.Switch` = Physical input buttons (not supported - see above)

## Repairs Integration

The integration uses Home Assistant's Repairs system to notify users of issues:

### Connection Failed
- **Trigger**: 3 consecutive API failures
- **Severity**: Error
- **Auto-clears**: Yes, when connection restores
- **Implementation**: `coordinator.py` tracks `_consecutive_failures`

### Stale Entities Cleaned
- **Trigger**: Orphaned entities removed during reload
- **Severity**: Warning
- **Fixable**: Yes (dismissible)
- **Implementation**: `__init__.py` `_async_cleanup_stale_entities()` with `RepairsFlow` in `config_flow.py`

### Config Migration Failed
- **Trigger**: Config entry version newer than supported
- **Severity**: Error
- **Fixable**: No
- **Implementation**: `__init__.py` `async_migrate_entry()`

### Key Files
- `const.py`: `REPAIR_*` constants, `CONNECTION_FAILURE_THRESHOLD`
- `coordinator.py`: Connection failure tracking and repair creation/deletion
- `__init__.py`: Stale entity and migration repairs
- `config_flow.py`: `EvonStaleEntitiesRepairFlow`, `async_create_fix_flow()`
- `translations/*.json`: `issues` section for repair messages

## Code Quality

### Linting

Always run linting before committing changes:

**Python (ruff):**
```bash
pip install ruff
ruff check custom_components/evon/      # Check for issues
ruff check custom_components/evon/ --fix  # Auto-fix issues
ruff format custom_components/evon/     # Format code
```

**TypeScript (eslint):**
```bash
npm run lint       # Check for issues
npm run lint:fix   # Auto-fix issues
```

CI runs these checks automatically on pull requests.

## Development Guidelines

### Adding New Device Types

1. Add device class constant to `const.py`
2. Add processing method to `coordinator.py`
3. Create platform file or add to existing one
4. Register platform in `__init__.py` PLATFORMS list
5. Add API methods to `api.py` if needed

### Entity Best Practices

- Use `EntityDescription` for entity configuration
- Set appropriate `entity_category` (None for primary, DIAGNOSTIC for info-only)
- Implement `available` property checking coordinator data
- Use `HomeAssistantError` for error handling in service calls
- Include `evon_id` in extra state attributes for debugging

### Coordinator Pattern

```python
# Reading data from coordinator
data = self.coordinator.get_entity_data("lights", self._instance_id)
if data:
    return data.get("is_on", False)

# Triggering update after control action
await self.coordinator.async_request_refresh()
```

### API Error Handling

```python
try:
    await self.api.call_method(instance_id, method)
except EvonApiError as err:
    raise HomeAssistantError(f"Failed to control device: {err}") from err
```

## Testing

### Manual API Testing

```bash
# Test authentication
curl -X POST http://EVON_HOST/login \
  -H "x-elocs-username: USERNAME" \
  -H "x-elocs-password: BASE64_SHA512_HASH"

# List all devices
curl http://EVON_HOST/api/instances \
  -H "Cookie: token=TOKEN"

# Get device details
curl http://EVON_HOST/api/instances/DEVICE_ID \
  -H "Cookie: token=TOKEN"

# Call method on device
curl -X POST http://EVON_HOST/api/instances/DEVICE_ID/METHOD \
  -H "Cookie: token=TOKEN" \
  -H "Content-Type: application/json" \
  -d '[]'
```

### Testing with MCP Server

```bash
cd /path/to/evon-ha
npm install
npm run build
```

Configure credentials in `~/.claude.json` (see README), then use Claude Code to test tools.

### Home Assistant Development

```bash
# Copy to HA config
cp -r custom_components/evon /config/custom_components/

# Or for development, symlink
ln -s /path/to/evon-ha/custom_components/evon /config/custom_components/evon

# Restart HA or reload integration
```

## Troubleshooting

### 404 Errors on Control

1. Check device class - might be read-only (`SmartCOM.Switch`)
2. Verify method name exists for that device type
3. Check API token hasn't expired

### Devices Not Appearing

1. Check `ClassName` matches expected pattern
2. Verify device has `Name` property set
3. Check coordinator logs for processing errors

### State Not Updating

1. Verify polling interval in options
2. Check coordinator is running (`_LOGGER.debug` in `_async_update_data`)
3. Confirm API responses contain expected data

## MCP Server Tools

| Tool | Description |
|------|-------------|
| `list_lights` | List all lights with state |
| `light_control` | Control single light |
| `light_control_all` | Control all lights |
| `list_blinds` | List all blinds with state |
| `blind_control` | Control single blind |
| `blind_control_all` | Control all blinds |
| `list_climate` | List climate devices |
| `climate_control` | Control single climate (comfort/eco/away/set_temperature) |
| `climate_control_all` | Control all climate (comfort/eco/away) |
| `list_home_states` | List home states with active status |
| `set_home_state` | Set active home state (at_home/holiday/night/work) |
| `list_bathroom_radiators` | List all bathroom radiators with state |
| `bathroom_radiator_control` | Control a bathroom radiator (on/off/toggle) |
| `list_sensors` | List temperature sensors |
| `list_scenes` | List available scenes |
| `activate_scene` | Activate a scene |
| `create_scene` | Create custom scene |

## Resources (MCP)

| URI | Description |
|-----|-------------|
| `evon://lights` | All lights with state |
| `evon://blinds` | All blinds with state |
| `evon://climate` | All climate devices with season mode |
| `evon://home_state` | Current home state and available states |
| `evon://bathroom_radiators` | All bathroom radiators with state |
| `evon://summary` | Home summary (counts, avg temp, home state) |

## Version Compatibility

- Home Assistant: 2023.1+ (uses modern async patterns)
- Python: 3.11+
- Node.js (MCP): 18+

## Contributing

1. Fork the repository
2. Create feature branch
3. Follow existing code patterns
4. Test on actual Evon hardware if possible
5. Update documentation for API changes
6. Submit pull request

## License

MIT License - see LICENSE file
