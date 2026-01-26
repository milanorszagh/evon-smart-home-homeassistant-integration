# Evon Smart Home Integration

<img src="custom_components/evon/icon.png" alt="Evon Smart Home" width="128" align="right">

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/release/milanorszagh/evon-smart-home-homeassistant-integration.svg)](https://github.com/milanorszagh/evon-smart-home-homeassistant-integration/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Home Assistant custom integration for [Evon Smart Home](https://www.evon-smarthome.com/) systems.

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=milanorszagh&repository=evon-smart-home-homeassistant-integration&category=integration)

## Supported Devices

| Device Type | Features |
|-------------|----------|
| **Lights** | On/off, brightness control |
| **Blinds/Covers** | Open/close/stop, position, tilt angle |
| **Climate** | Temperature, presets (comfort, eco, away), heating/cooling status |
| **Season Mode** | Global heating/cooling switch for the whole house |
| **Home State** | Switch between home modes (At Home, Night, Work, Holiday) |
| **Smart Meter** | Power consumption, energy usage, voltage per phase |
| **Air Quality** | CO2 levels, humidity (if available) |
| **Valves** | Climate valve open/closed state |
| **Temperature Sensors** | Room temperature readings |
| **Switches** | Controllable relay outputs |
| **Bathroom Radiators** | Electric heater control with timer |

## Known Limitations

### Physical Buttons

Physical wall buttons cannot be monitored by Home Assistant due to Evon API limitations. They only report momentary state (pressed/not pressed) with no event history. The buttons still work normally within the Evon system - they just can't trigger Home Assistant automations.

### Controllable Switches

The integration supports controllable relay outputs (`SmartCOM.Light.Light`). If your Evon system doesn't have these configured, the switch platform will be empty.

---

## Installation

### Via HACS (Recommended)

1. Make sure [HACS](https://hacs.xyz/) is installed
2. Click the button below to add the repository:

   [![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=milanorszagh&repository=evon-smart-home-homeassistant-integration&category=integration)

   Or manually: **HACS** → **Integrations** → **⋮** → **Custom repositories** → Add `https://github.com/milanorszagh/evon-smart-home-homeassistant-integration` as **Integration**

3. Click **Download** and restart Home Assistant
4. Add the integration:

   [![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=evon)

   Or: **Settings** → **Devices & Services** → **Add Integration** → Search "Evon Smart Home"

5. Enter your Evon system URL (e.g., `http://192.168.x.x`), username, and password

### Manual Installation

1. Copy `custom_components/evon` to your Home Assistant's `custom_components` directory
2. Restart Home Assistant
3. Add the integration via Settings → Devices & Services

---

## Configuration

### Options

After installation, configure via **Settings** → **Devices & Services** → **Evon Smart Home** → **Configure**:

| Option | Description |
|--------|-------------|
| **Poll interval** | How often to fetch device states (5-300 seconds, default: 30) |
| **Sync areas from Evon** | Automatically assign devices to HA areas based on Evon room assignments |
| **Non-dimmable lights** | Select lights that should be on/off only (useful for LED strips with PWM controllers) |

To change connection credentials, use **Reconfigure** from the integration menu.

### Repairs

The integration creates repair issues in **Settings** → **System** → **Repairs** for:

| Issue | Description |
|-------|-------------|
| **Connection failed** | Alerts after 3 consecutive API failures. Auto-clears when connection restores. |
| **Stale entities cleaned** | Notice when orphaned entities are removed (dismissible). |
| **Config migration failed** | Error if configuration was created with a newer incompatible version. |

### Translations

Supported languages:
- English (default)
- German (Deutsch) - for DACH region customers

---

## Supported Platforms

### Lights

- Turn on/off
- Brightness control (0-100%)
- Non-dimmable lights can be configured to show as simple on/off switches

### Covers (Blinds)

- Open, close, stop
- Position control (0-100%)
- Tilt angle control (0-100%)

### Climate

- Temperature control with min/max limits
- HVAC modes: Heat, Cool (if supported), Off
- Current activity display: Heating, Cooling, or Idle
- Presets:
  - **Comfort** - Normal comfortable temperature
  - **Eco** - Energy saving mode
  - **Away** - Protection mode (freeze protection in winter, heat protection in summer)

### Season Mode

Global switch that controls whether the house is in heating (winter) or cooling (summer) mode. Changing this affects all climate devices simultaneously.

Options:
- **Heating (Winter)** - House in heating mode
- **Cooling (Summer)** - House in cooling mode

### Home State

Switch between home-wide modes defined in your Evon system:

- **At Home** - Normal home operation
- **Night** - Night mode
- **Work** - Away at work
- **Holiday** - Vacation mode

These states can trigger automations configured in the Evon system.

### Sensors

- Temperature sensors from climate devices
- Smart meter: Power (W), Energy (kWh), Daily energy, Voltage per phase
- Air quality: CO2 (ppm), Humidity (%)

### Binary Sensors

- Climate valve state (open/closed)

### Switches

- Controllable relay outputs (on/off)
- Bathroom radiators with timer (turns off automatically after configured duration)

---

## MCP Server

An MCP (Model Context Protocol) server is included for AI assistant integration (e.g., Claude). This allows AI assistants to control your Evon devices directly.

See [DEVELOPMENT.md](DEVELOPMENT.md) for setup instructions and available tools.

---

## Version History

| Version | Changes |
|---------|---------|
| **1.10.0** | Non-dimmable lights option, Repairs integration, improved translations, hub device hierarchy, HA 2025.12.0 compatibility |
| **1.9.0** | Season Mode for global heating/cooling, climate activity display (heating/cooling/idle) |
| **1.8.2** | Fixed blind optimistic state for group actions |
| **1.8.0** | Optimistic updates for all entities, improved preset icons |
| **1.7.0** | Bathroom radiator support with timer |
| **1.6.0** | Automatic stale entity cleanup |
| **1.5.0** | Home State selector |
| **1.4.1** | Removed non-functional button entities |
| **1.3.0** | Smart meter, air quality, valve sensors, diagnostics |
| **1.2.0** | Area sync feature, German translations |
| **1.1.0** | Sensors, switches, options flow, reconfigure flow |
| **1.0.0** | Initial release |

---

## Contributing

Contributions are welcome! See [DEVELOPMENT.md](DEVELOPMENT.md) for architecture details, API reference, and development guidelines.

## License

MIT License - see [LICENSE](LICENSE) file.

## Disclaimer

This project is not affiliated with or endorsed by Evon Smart Home. Use at your own risk.
