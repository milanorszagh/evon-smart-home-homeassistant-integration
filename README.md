# Evon Smart Home Integration

This repository contains two integrations for [Evon Smart Home](https://www.evon-smarthome.com/) systems:

1. **MCP Server** - A Model Context Protocol server for AI assistants (Claude, etc.)
2. **Home Assistant Custom Integration** - Native Home Assistant integration

## Supported Devices

| Device Type | Features |
|-------------|----------|
| **Lights** | On/off, brightness (0-100%) |
| **Blinds** | Open/close/stop, position (0-100%), tilt angle (0-100%) |
| **Climate** | Temperature control, preset modes (comfort, energy saving, freeze protection) |

## MCP Server

The MCP server allows AI assistants to control your Evon Smart Home devices directly.

### Installation

```bash
# Install dependencies
npm install

# Build
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
        "EVON_HOST": "http://192.168.1.4",
        "EVON_USERNAME": "User",
        "EVON_PASSWORD": "your-encrypted-password"
      }
    }
  }
}
```

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

## Home Assistant Custom Integration

Native Home Assistant integration for Evon Smart Home.

### Installation

1. Copy the `custom_components/evon` folder to your Home Assistant's `custom_components` directory:
   ```bash
   cp -r custom_components/evon /config/custom_components/
   ```

2. Restart Home Assistant

3. Go to **Settings** → **Devices & Services** → **Add Integration**

4. Search for "Evon Smart Home"

5. Enter your connection details:
   - **Host URL**: Your Evon system URL (e.g., `http://192.168.1.4`)
   - **Username**: Your Evon username
   - **Password**: Your Evon password

### Supported Platforms

#### Light (`light.py`)
- Turn on/off
- Set brightness (0-255, converted from Evon's 0-100)
- Reports current brightness state

#### Cover (`cover.py`)
- Open/close/stop blinds
- Set position (0-100%, inverted from Evon's convention)
- Set tilt position (0-100%)
- Reports current position and tilt

#### Climate (`climate.py`)
- Set target temperature
- Preset modes:
  - `comfort` - Day mode, normal heating
  - `energy_saving` - Night mode, reduced heating
  - `freeze_protection` - Minimum heating to prevent freezing
- Reports current and target temperature

## Evon API Reference

### Authentication

```
POST /login
Headers:
  x-elocs-username: <username>
  x-elocs-password: <password>

Response Headers:
  x-elocs-token: <token>
```

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

## Project Structure

```
evon-ha/
├── src/
│   └── index.ts          # MCP server source
├── dist/
│   └── index.js          # Compiled MCP server
├── custom_components/
│   └── evon/
│       ├── manifest.json # HA integration manifest
│       ├── const.py      # Constants
│       ├── api.py        # Evon API client
│       ├── coordinator.py# Data update coordinator
│       ├── __init__.py   # Integration setup
│       ├── config_flow.py# UI configuration
│       ├── light.py      # Light platform
│       ├── cover.py      # Cover platform
│       ├── climate.py    # Climate platform
│       └── translations/
│           └── en.json   # English translations
├── package.json
├── tsconfig.json
└── README.md
```

## License

MIT
