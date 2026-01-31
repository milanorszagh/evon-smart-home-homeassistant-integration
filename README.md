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
| **Lights** | On/off, brightness control, color temperature (RGBW lights) |
| **Light Groups** | Control multiple lights as a single entity |
| **Blinds/Covers** | Open/close/stop, position, tilt angle |
| **Blind Groups** | Control multiple blinds as a single entity |
| **Climate** | Temperature, presets (comfort, eco, away), heating/cooling status, humidity |
| **Season Mode** | Global heating/cooling switch for the whole house |
| **Home State** | Switch between home modes (At Home, Night, Work, Holiday) |
| **Smart Meter** | Power consumption, energy usage, voltage per phase |
| **Air Quality** | CO2 levels, humidity (if available) |
| **Valves** | Climate valve open/closed state |
| **Temperature Sensors** | Room temperature readings |
| **Switches** | Controllable relay outputs |
| **Bathroom Radiators** | Electric heater control with timer |
| **Scenes** | Trigger Evon-defined scenes from Home Assistant |
| **Security Doors** | Door open/closed state, call in progress indicator |
| **Intercoms** | Door open/closed state, doorbell events, connection status |

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

5. Choose your connection type and enter credentials (see [Connection Methods](#connection-methods) below)

### Manual Installation

1. Copy `custom_components/evon` to your Home Assistant's `custom_components` directory
2. Restart Home Assistant
3. Add the integration via Settings → Devices & Services

---

## Connection Methods

The integration supports two connection methods:

| Method | When to Use |
|--------|-------------|
| **Local Network** (Recommended) | When Home Assistant is on the same network as your Evon system. Faster and more reliable. |
| **Remote Access** | When connecting from outside your home network (e.g., cloud-hosted Home Assistant). |

### Local Network Setup

1. Select **Local network** as connection type
2. Enter your Evon system's local IP address or hostname (e.g., `http://192.168.1.100`)
3. Enter your username and password

### Remote Access Setup

1. Select **Remote access** as connection type
2. Enter your **Engine ID** (found in your Evon system settings or documentation)
3. Enter your username and password (same credentials as local login)

**Note:** Local network connection is recommended for faster response times and better reliability. Only use remote access when you cannot connect locally.

---

## Configuration

### Options

After installation, configure via **Settings** → **Devices & Services** → **Evon Smart Home** → **Configure**:

| Option | Description |
|--------|-------------|
| **Use HTTP API only** | Disable WebSocket and use HTTP polling only. WebSocket is recommended and enabled by default. Only enable this if you experience connection issues. |
| **Poll interval** | How often to fetch device states (5-300 seconds). Used as fallback when WebSocket is enabled, or as primary method when HTTP only mode is enabled. |
| **Sync areas from Evon** | Automatically assign devices to HA areas based on Evon room assignments |
| **Non-dimmable lights** | Select lights that should be on/off only (useful for LED strips with PWM controllers) |

To change connection credentials or switch between local and remote access, use **Reconfigure** from the integration menu.

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

### Real-Time Updates & Control (WebSocket)

WebSocket is **enabled by default** for instant state synchronization and device control. To disable, check **"Use HTTP API only"** in options.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        THE WEBSOCKET ADVANTAGE                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   HTTP Polling (old)              WebSocket (default)                   │
│   ──────────────────              ──────────────────────                │
│                                                                         │
│   HA ──────► Evon                 HA ◄═══════════════► Evon             │
│      poll     │                         persistent                      │
│      every    │                         bidirectional                   │
│      30s      ▼                         connection                      │
│            response                                                     │
│                                   • State changes push instantly        │
│   • State can be 30s stale        • Commands execute in <50ms           │
│   • Control takes 200-500ms       • Single connection, no handshakes    │
│   • Constant network traffic      • Event-driven, minimal traffic       │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

| Feature | HTTP Only | WebSocket (Default) |
|---------|-----------|---------------------|
| **State updates** | Up to 30 seconds | Instant (<100ms) |
| **Control response** | ~200-500ms | Instant (<50ms) |
| **Poll interval** | 30 seconds | 300 seconds (fallback) |
| **Network traffic** | Continuous polling | Event-driven |

**How it works:**
- **Bidirectional communication**: Same WebSocket connection handles both state updates AND device control
- **State updates**: When a light is turned on via wall switch, HA updates immediately (no polling delay)
- **Device control**: Commands execute in <50ms - tap a light and it responds instantly
- **Automatic fallback**: If WebSocket is unavailable, commands fall back to HTTP API seamlessly
- HTTP polling continues at reduced frequency (5 minutes) as a safety net
- For remote connections, WebSocket connects via `wss://my.evon-smarthome.com/`

**Note:** WebSocket is recommended for the best experience. Only disable it if you experience connection issues.

---

## Security

### Credential Handling

- Credentials are stored securely in Home Assistant's configuration storage
- Passwords are encoded using SHA-512 hash of username+password, then Base64 encoded before transmission
- No credentials are logged or exposed in diagnostics

### Remote Access Security

When using remote access via `my.evon-smarthome.com`:

- **SSL/TLS**: All connections use HTTPS with certificate verification
- **Authentication**: Requires your Evon credentials and Engine ID
- **Relay Server**: Traffic passes through Evon's relay server, which proxies requests to your local system

**Recommendations:**
- Use **local network** connection when possible (faster and doesn't rely on external servers)
- Keep your Evon credentials secure and don't share them
- The Engine ID is not secret but identifies your specific system

### Network Security

For local connections:
- Ensure your Evon system is on a trusted network
- Consider using a VLAN to isolate IoT devices
- The integration uses HTTP by default for local connections (most Evon systems don't have HTTPS enabled locally)

---

## Supported Platforms

### Lights

- Turn on/off
- Brightness control (0-100%)
- Color temperature control for RGBW lights (warm to cool white) *
- Light Groups: Control multiple lights as a single entity
- Non-dimmable lights can be configured to show as simple on/off switches

\* *RGBW color temperature support is untested - please report issues if you have RGBW Evon modules*

### Covers (Blinds)

- Open, close, stop
- Position control (0-100%)
- Tilt angle control (0-100%)
- Blind Groups: Control multiple blinds as a single entity

### Climate

- Target temperature control with min/max limits
- Activity display: Shows when system is actively Heating, Cooling, or Idle
- Current humidity display (if sensor available in the room)
- Presets:
  - **Comfort** - Normal comfortable temperature
  - **Eco** - Energy saving mode
  - **Away** - Protection mode (freeze protection in winter, heat protection in summer)

The Evon system automatically decides when to heat or cool based on the target temperature and the global Season Mode setting.

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

These states trigger automations in the Evon system and can be used in Home Assistant automations as well.

### Sensors

- Temperature sensors from climate devices
- Smart meter:
  - Power (W), Energy Total (kWh), Energy 24h Rolling
  - Voltage per phase (V) - L1, L2, L3
  - Current per phase (A) - L1, L2, L3
  - Frequency (Hz)
  - Feed-in Energy Total (kWh) - for solar/grid export tracking
- Air quality: CO2 (ppm), Humidity (%)

**Note:** For the Energy Dashboard, use `sensor.*_energy_total` (not the 24h rolling sensor). The "Energy (24h Rolling)" sensor from Evon is a rolling 24-hour window that can decrease during the day, which is not suitable for HA's energy tracking.

### Binary Sensors

- Climate valve state (open/closed)
- Security door state (open/closed)
- Security door call in progress
- Intercom door state (open/closed)
- Intercom connection status

### Events

The integration fires Home Assistant events that can be used in automations:

- **`evon_doorbell`**: Fired when a doorbell is pressed on an intercom *
  - Event data: `device_id` (intercom instance ID), `name` (intercom name)
  - Use in automations to trigger notifications, announcements, or other actions

\* *Doorbell events are untested - please report issues if you have 2N intercoms*

### Switches

- Controllable relay outputs (on/off)
- Bathroom radiators with timer (turns off automatically after configured duration)

---

## MCP Server

An MCP (Model Context Protocol) server is included for AI assistant integration (e.g., Claude). This allows AI assistants to control your Evon devices directly.

See [DEVELOPMENT.md](DEVELOPMENT.md) for setup instructions and available tools.

---

## WebSocket Client

A TypeScript WebSocket client (`src/ws-client.ts`) is included for real-time communication with Evon systems. This provides:

- **Real-time subscriptions** - Get instant notifications when device states change
- **Faster control** - Lower latency than HTTP API for device control
- **Batch queries** - Request multiple device properties in a single call

### Usage

```typescript
import { getWsClient, wsGetLights, wsControlLight } from './dist/ws-client.js';

// Get singleton client
const client = getWsClient();
await client.connect();

// Get all lights
const lights = await wsGetLights();

// Control a light
await wsControlLight('SC1_M01.Light1', { on: true, brightness: 75 });

// Subscribe to real-time changes
client.registerValuesChanged([
  { Instanceid: 'SC1_M01.Light1', Properties: ['IsOn', 'Brightness'] }
], (instanceId, props) => {
  console.log(`${instanceId} changed:`, props);
});
```

See [docs/WEBSOCKET_API.md](docs/WEBSOCKET_API.md) for complete API documentation.

---

## Version History

| Version | Changes |
|---------|---------|
| **1.14.0** | **WebSocket device control** - instant response when controlling lights, blinds, and climate via HA (no more waiting for poll cycles). Security doors and intercoms with doorbell events, light/blind groups, RGBW color temperature*, climate humidity display |
| **1.13.0** | WebSocket support for real-time updates (enabled by default), instant state sync, reduced polling when connected |
| **1.12.0** | Remote access via my.evon-smarthome.com, switch between local/remote in reconfigure, security improvements (SSL, input validation, token handling) |
| **1.11.0** | Scene support, smart meter current sensors (L1/L2/L3), frequency sensor, feed-in energy sensor |
| **1.10.2** | Data caching to prevent entity unavailability during transient API failures |
| **1.10.1** | Optimistic time display for bathroom radiators, fixed Energy sensor for HA Energy Dashboard |
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
