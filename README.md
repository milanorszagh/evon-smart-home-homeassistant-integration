# Evon Smart Home Integration

<img src="icon.png" alt="Evon Smart Home" width="128" align="right">

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/release/milanorszagh/evon-smart-home-homeassistant-integration.svg)](https://github.com/milanorszagh/evon-smart-home-homeassistant-integration/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Home Assistant custom integration and MCP server for [Evon Smart Home](https://www.evon-smarthome.com/) systems.

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=milanorszagh&repository=evon-smart-home-homeassistant-integration&category=integration)

## Supported Devices

| Device Type | Features |
|-------------|----------|
| **Lights** | On/off, brightness (0-100%) |
| **Switches** | On/off, click events (single, double, long press), device triggers |
| **Blinds** | Open/close/stop, position (0-100%), tilt angle (0-100%) |
| **Climate** | Temperature control, preset modes (comfort, energy saving, freeze protection) |
| **Smart Meter** | Power consumption, total energy, daily energy, voltage per phase |
| **Air Quality** | CO2 levels, humidity (if available) |
| **Valves** | Climate valve open/closed state |
| **Sensors** | Temperature sensors from climate devices |

---

## Home Assistant Integration

### Installation via HACS (Recommended)

1. Make sure [HACS](https://hacs.xyz/) is installed in your Home Assistant
2. Click the button below to add the repository:

   [![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=milanorszagh&repository=evon-smart-home-homeassistant-integration&category=integration)

   Or manually add the repository:
   - Go to **HACS** → **Integrations** → **⋮** (menu) → **Custom repositories**
   - Add URL: `https://github.com/milanorszagh/evon-smart-home-homeassistant-integration`
   - Category: **Integration**
3. Click **Download**
4. Restart Home Assistant
5. Click the button below to add the integration:

   [![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=evon)

   Or manually add:
   - Go to **Settings** → **Devices & Services** → **Add Integration**
   - Search for "Evon Smart Home"
6. Enter your connection details:
   - **Host URL**: Your Evon system URL (e.g., `http://192.168.x.x`)
   - **Username**: Your Evon username
   - **Password**: Your Evon password (plain text)

### Manual Installation

1. Copy the `custom_components/evon` folder to your Home Assistant's `custom_components` directory:
   ```bash
   cp -r custom_components/evon /config/custom_components/
   ```
2. Restart Home Assistant
3. Follow steps 5-7 above

### Configuration Options

After installation, you can configure the integration via **Settings** → **Devices & Services** → **Evon Smart Home** → **Configure**:

- **Poll interval**: How often to fetch device states (5-300 seconds, default: 30)
- **Sync areas from Evon**: Automatically assign devices to Home Assistant areas based on their room assignment in the Evon system (default: off)

To change your connection credentials, use the **Reconfigure** option from the integration menu.

### Translations

The integration supports the following languages:
- English (default)
- German (Deutsch) - for DACH region customers

### Supported Platforms

#### Light
- Turn on/off
- Brightness control (0-100%)
- Attributes: `brightness_pct`, `evon_id`

#### Switch
- Turn on/off
- Click event detection (fires `evon_event` on the event bus)
  - `single_click`
  - `double_click`
  - `long_press`
- Attributes: `last_click_type`, `evon_id`

#### Cover (Blinds)
- Open/close/stop
- Position control (0-100%)
- Tilt angle control (0-100%)
- Attributes: `evon_position`, `tilt_angle`, `evon_id`

#### Climate
- Temperature control
- Preset modes:
  - `comfort` - Day mode, normal heating
  - `energy_saving` - Night mode, reduced heating
  - `freeze_protection` - Minimum heating to prevent freezing
- Attributes: `comfort_temperature`, `energy_saving_temperature`, `freeze_protection_temperature`, `evon_id`

#### Sensor
- Temperature sensors from climate devices
- Attributes: `target_temperature`, `evon_id`

#### Smart Meter (Energy)
- Power consumption (W)
- Total energy consumption (kWh)
- Daily energy consumption (kWh)
- Voltage per phase (L1, L2, L3)
- Attributes: `feed_in`, `frequency`, `evon_id`

#### Air Quality
- CO2 levels (ppm) - if sensor available
- Humidity (%) - if sensor available
- Attributes: `health_index`, `co2_index`, `humidity_index`, `evon_id`

#### Binary Sensor (Valves)
- Climate valve open/closed state
- Attributes: `valve_type`, `evon_id`

### Device Triggers

Switches support device triggers for automations. You can create automations using the UI:
1. Go to **Settings** → **Automations & Scenes** → **Create Automation**
2. Select **Device** as trigger type
3. Choose your Evon switch
4. Select trigger: **Single click**, **Double click**, or **Long press**

### Logbook

Switch click events are automatically logged in the Home Assistant logbook with human-readable descriptions:
- "Living Room Switch **was clicked**"
- "Bedroom Switch **was double-clicked**"
- "Kitchen Switch **was long-pressed**"

### Automations with Click Events

Listen for switch click events in automations:

```yaml
automation:
  - alias: "Double click - movie mode"
    trigger:
      - platform: event
        event_type: evon_event
        event_data:
          event_type: double_click
          device_name: "Living Room Switch"
    action:
      - service: scene.turn_on
        target:
          entity_id: scene.movie_mode
```

---

## MCP Server (for AI Assistants)

The MCP server allows AI assistants like Claude to control your Evon Smart Home devices directly.

### Installation

```bash
git clone https://github.com/milanorszagh/evon-smart-home-homeassistant-integration.git
cd evon-ha
npm install
npm run build
```

### Configuration

Add to your Claude Code configuration (`.claude.json`):

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

**Note**: You can use either your plain text password or the encoded `x-elocs-password`. The server automatically detects and handles both formats.

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
| `climate_control` | Control a single climate zone |
| `climate_control_all` | Control all climate zones at once |
| `list_sensors` | List temperature and other sensors |
| `list_scenes` | List available scenes |
| `activate_scene` | Activate a scene (all_off, movie_mode, morning, night) |
| `create_scene` | Create a custom scene |

### Available Resources

Resources allow Claude to read device state without calling tools:

| Resource URI | Description |
|--------------|-------------|
| `evon://lights` | All lights with current state |
| `evon://blinds` | All blinds with current state |
| `evon://climate` | All climate controls with current state |
| `evon://summary` | Home summary (device counts, average temp) |

### Pre-defined Scenes

| Scene | Description |
|-------|-------------|
| `all_off` | Turn off all lights and close all blinds |
| `movie_mode` | Dim lights to 10% and close blinds |
| `morning` | Open blinds, set lights to 70%, comfort mode |
| `night` | Turn off lights, set climate to energy saving |

---

## Development

### Running Tests

```bash
pip install -r requirements-test.txt
pytest
```

### Building MCP Server

```bash
npm run build
```

---

## Evon API Reference

### Authentication

```
POST /login
Headers:
  x-elocs-username: <username>
  x-elocs-password: <encoded-password>

Response Headers:
  x-elocs-token: <token>
```

#### Password Encoding

The `x-elocs-password` is NOT the plain text password. It's encoded as:

```
x-elocs-password = Base64(SHA512(username + password))
```

**Example (Python):**
```python
import hashlib, base64
encoded = base64.b64encode(
    hashlib.sha512((username + password).encode()).digest()
).decode()
```

**Example (JavaScript/Node.js):**
```javascript
import { createHash } from "crypto";
const encoded = createHash("sha512")
    .update(username + password, "utf8")
    .digest("base64");
```

Both the MCP server and Home Assistant integration handle this encoding automatically - just provide your plain text password.

### API Endpoints

All API requests require the token in a cookie:
```
Cookie: token=<token>
```

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/instances` | GET | List all device instances |
| `/api/instances/{id}` | GET | Get device details |
| `/api/instances/{id}/{method}` | POST | Call a method on a device |

### Device Classes

| Class Name | Type |
|------------|------|
| `SmartCOM.Light.LightDim` | Dimmable light |
| `SmartCOM.Light.Light` | Non-dimmable light/switch |
| `SmartCOM.Blind.Blind` | Blind/shutter |
| `SmartCOM.Clima.ClimateControl` | Climate control |
| `*ClimateControlUniversal*` | Universal climate control |

### Light Methods

| Method | Parameters | Description |
|--------|------------|-------------|
| `AmznTurnOn` | - | Turn light on |
| `AmznTurnOff` | - | Turn light off |
| `AmznSetBrightness` | `[brightness]` (0-100) | Set brightness |

**Important**: Use `ScaledBrightness` property to read actual brightness, not `Brightness` (internal value).

### Blind Methods

| Method | Parameters | Description |
|--------|------------|-------------|
| `MoveUp` | - | Open blind |
| `MoveDown` | - | Close blind |
| `Stop` | - | Stop movement |
| `AmznSetPercentage` | `[position]` (0-100) | Set position (0=open, 100=closed) |
| `SetAngle` | `[angle]` (0-100) | Set tilt angle |

### Climate Methods

| Method | Parameters | Description |
|--------|------------|-------------|
| `WriteDayMode` | - | Set comfort/day mode |
| `WriteNightMode` | - | Set energy saving/night mode |
| `WriteFreezeMode` | - | Set freeze protection mode |
| `WriteCurrentSetTemperature` | `[temperature]` | Set target temperature |

### Climate Properties

| Property | Description |
|----------|-------------|
| `ActualTemperature` | Current room temperature |
| `SetTemperature` | Target temperature |
| `SetValueComfortHeating` | Comfort mode temperature |
| `SetValueEnergySavingHeating` | Energy saving mode temperature |
| `SetValueFreezeProtection` | Freeze protection temperature |
| `MinSetValueHeat` | Minimum allowed temperature |
| `MaxSetValueHeat` | Maximum allowed temperature |

---

## Version History

| Version | Changes |
|---------|---------|
| **1.3.2** | Added logbook integration for switch click events |
| **1.3.1** | Best practices: Entity categories for diagnostic sensors, availability detection, HomeAssistantError exceptions, EntityDescription refactoring |
| **1.3.0** | Added smart meter, air quality, and valve sensors. Added device triggers for switches. Added diagnostics support. |
| **1.2.1** | Added German translations for DACH region customers |
| **1.2.0** | Added optional area sync feature (sync Evon rooms to HA areas) |
| **1.1.5** | Fixed AbortFlow exception handling |
| **1.1.4** | Improved error handling in API client |
| **1.1.3** | Fixed config flow errors, added host URL normalization |
| **1.1.2** | Fixed switch detection |
| **1.1.1** | Documentation and branding updates |
| **1.1.0** | Added sensors, switches, options flow, reconfigure flow, MCP resources and scenes |
| **1.0.0** | Initial release with lights, blinds, and climate support |

---

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Disclaimer

This project is not affiliated with or endorsed by Evon Smart Home. Use at your own risk.
