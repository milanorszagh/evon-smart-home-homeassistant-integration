# Evon Smart Home Integration

<img src="custom_components/evon/icon.png" alt="Evon Smart Home" width="128" align="right">

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/release/milanorszagh/evon-smart-home-homeassistant-integration.svg)](https://github.com/milanorszagh/evon-smart-home-homeassistant-integration/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![IoT Class](https://img.shields.io/badge/IoT_Class-local_push-blue.svg)](https://developers.home-assistant.io/docs/creating_integration_manifest#iot-class)
[![HA Version](https://img.shields.io/badge/Home_Assistant-2024.1+-blue.svg)](https://www.home-assistant.io/)
[![Python](https://img.shields.io/badge/Python-3.12%20|%203.13-blue.svg)](https://www.python.org/)

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
| **Cameras** | Live feed from 2N intercom cameras, snapshot-based video recording |
| **Doorbell Snapshots** | Historical snapshots from doorbell events (image entities) |

## Known Limitations

### Physical Buttons (Taster)

Physical wall buttons (Taster) **do not fire WebSocket events**. They operate at the hardware level and directly signal their associated actuators (lights, blinds) without going through the software layer. This means:

- Button presses cannot be detected or monitored by Home Assistant
- The buttons work normally within the Evon system for controlling devices
- State changes from button presses ARE visible (e.g., light turns on), but the button press itself is not

This is by design in the Evon system - physical buttons work even if the software layer has issues.

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
| **Sync areas from Evon** | Automatically assign devices to HA areas based on Evon room assignments |
| **Non-dimmable lights** | Select lights that should be on/off only (useful for LED strips with PWM controllers) |

**HTTP API vs WebSocket** (collapsible section):

| Option | Description |
|--------|-------------|
| **Use HTTP API only** | Disable WebSocket and use HTTP polling only. WebSocket is recommended and enabled by default. Only enable this if you experience connection issues. |
| **Poll interval** | How often to fetch device states (5-300 seconds). Used as fallback when WebSocket is enabled, or as primary method when HTTP only mode is enabled. |

**Camera Recording** (collapsible section, shown when cameras are present):

| Option | Description |
|--------|-------------|
| **Max recording duration** | Maximum recording duration in seconds (30-3600, default: 300). Prevents forgotten recordings from filling disk. |
| **Recording output format** | Choose "MP4 only" or "MP4 + JPEG frames" to also save individual frames. |

**Debug Logging** (collapsible section):

| Option | Description |
|--------|-------------|
| **API** | Enable debug logging for HTTP API requests and responses. |
| **WebSocket** | Enable debug logging for WebSocket messages. |
| **Coordinator** | Enable debug logging for the data coordinator. |

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
| **Poll interval** | 30 seconds | 60 seconds (safety net) |
| **Network traffic** | Continuous polling | Event-driven |

**How it works:**
- **Bidirectional communication**: Same WebSocket connection handles both state updates AND device control
- **State updates**: When a light is turned on via wall switch, HA updates immediately (no polling delay)
- **Device control**: Commands execute in <50ms - tap a light and it responds instantly
- **Automatic fallback**: If WebSocket is unavailable, commands fall back to HTTP API seamlessly
- HTTP polling continues at reduced frequency (1 minute) as a safety net
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
  - **Energy Today** (kWh) - today's consumption, calculated from HA statistics
  - **Energy This Month** (kWh) - this month's total, combining Evon data with today's stats
  - Voltage per phase (V) - L1, L2, L3
  - Current per phase (A) - L1, L2, L3
  - Frequency (Hz)
  - Feed-in Energy Total (kWh) - for solar/grid export tracking
- Air quality: CO2 (ppm), Humidity (%)

**Note:** For the Energy Dashboard, use `sensor.*_energy_total` (not the 24h rolling sensor). The "Energy (24h Rolling)" sensor from Evon is a rolling 24-hour window that can decrease during the day, which is not suitable for HA's energy tracking.

#### Daily Energy Statistics

The integration provides two calculated sensors for easy energy tracking:

| Sensor | Description |
|--------|-------------|
| **Energy Today** | Today's consumption, calculated from HA statistics on the Energy Total sensor |
| **Energy This Month** | This month's total, combining Evon's daily data (previous days) with today's consumption |

These sensors update automatically with each coordinator refresh.

The integration also imports **daily energy consumption data** from Evon's `EnergyDataMonth` into Home Assistant's external statistics. This provides accurate daily consumption values for the **previous 31 days** (not including today).

**Statistic ID:** `evon:energy_smartmeter{ID}` (e.g., `evon:energy_smartmeter3006939`)

Display in a dashboard using the `statistics-graph` card:

```yaml
type: statistics-graph
entities:
  - entity: evon:energy_smartmeter3006939
    name: Daily Energy
stat_types:
  - change
period: day
days_to_show: 31
```

For detailed documentation, see [Energy Statistics](docs/ENERGY_STATISTICS.md).

### Binary Sensors

- Climate valve state (open/closed)
- Security door state (open/closed)
- Security door call in progress
- Intercom door state (open/closed)
- Intercom connection status
- **WebSocket connection status** (diagnostic) - shows if real-time updates are active

### Device Triggers

The integration provides device triggers for automations:

- **Doorbell pressed** - Triggered when a doorbell is pressed on an intercom *

To use: Go to **Automations** → **Create Automation** → **Device** → Select your intercom → **Doorbell pressed**

### Events

The integration fires Home Assistant events that can be used in automations:

- **`evon_doorbell`**: Fired when a doorbell is pressed on an intercom *
  - Event data: `device_id` (intercom instance ID), `name` (intercom name)
  - Use in automations to trigger notifications, announcements, or other actions

\* *Doorbell events are untested - please report issues if you have 2N intercoms*

### Cameras

Cameras from 2N intercoms are supported with live feed capability:

- **Live feed**: Near-real-time image updates via WebSocket
- **Snapshot on demand**: Triggers image capture from the intercom camera
- **Error monitoring**: Shows connection status
- **Saved pictures**: Historical doorbell snapshots available as image entities

The camera entity provides a still image that updates when you view it. The integration triggers an image request via WebSocket and fetches the resulting JPEG from the Evon server.

**Camera Recording:**

Since Evon cameras are snapshot-based (no RTSP stream), the integration provides a custom recording feature that rapidly polls snapshots and stitches them into an MP4 video:

- **Start/Stop via services**: `evon.start_recording` and `evon.stop_recording`
- **Recording switch**: Toggle entity for easy dashboard control
- **Timestamp overlay**: Each frame includes a burned-in timestamp
- **Configurable output**: MP4 only, or MP4 + individual JPEG frames
- **Auto-stop**: Configurable max duration (default: 5 minutes) prevents forgotten recordings
- **Output location**: Saved to `/media/evon_recordings/` in your HA instance
- **Custom Lovelace card**: `evon-camera-recording-card` provides an inline recording UI with record button, live stopwatch, recent recordings list with inline video playback, and a link to the media browser
- **Media browser access**: Recordings are accessible via HA's media browser under **My media → evon_recordings**

**Note:** Frame rate is limited by hardware response time (~0.5-2 FPS). The result is more of a timelapse than smooth video, but is useful for security and monitoring purposes.

**Recording Card Usage:**

Add the recording card to any dashboard (works great inside Bubble Card popups):
```yaml
type: custom:evon-camera-recording-card
entity: camera.your_camera_entity
recording_switch: switch.your_camera_recording  # optional, auto-derived from entity if omitted
```

The card auto-registers as a Lovelace resource on integration setup — no manual YAML imports needed.

**2N Intercom Camera Specifications:**
- Frame rate: Up to 10 fps for streaming
- Resolutions: 160×120 to 1280×960 (model dependent)
- Historical buffer: 30 seconds of footage retained on device

### Doorbell Snapshots

When someone rings the doorbell, Evon automatically captures and stores a snapshot. These are exposed as image entities:

- **Up to 10 snapshots** stored by Evon (their limit)
- **Entities**: `image.eingangstur_snapshots_snapshot_1` through `..._snapshot_10`
- **Attributes**: Each image includes `datetime` timestamp
- **Dashboard ready**: Add to any Lovelace card for a visual doorbell history

Example dashboard card:
```yaml
type: vertical-stack
cards:
  - type: picture-entity
    entity: camera.2n_camera
    name: Live Feed
  - type: grid
    columns: 5
    square: true
    cards:
      - type: picture-entity
        entity: image.eingangstur_snapshots_snapshot_1
        show_state: false
        show_name: false
      # ... repeat for snapshot_2 through snapshot_10
```

### Switches

- Controllable relay outputs (on/off)
- Bathroom radiators with timer (turns off automatically after configured duration)

---

## Services

The integration provides the following services that can be called from automations, scripts, or the Developer Tools:

| Service | Description |
|---------|-------------|
| `evon.refresh` | Force refresh all device states from the Evon system |
| `evon.reconnect_websocket` | Reconnect the WebSocket connection (use if real-time updates stop working) |
| `evon.set_home_state` | Set home state: `at_home`, `night`, `work`, `holiday` |
| `evon.set_season_mode` | Set season mode: `heating` or `cooling` |
| `evon.all_lights_off` | Turn off all Evon lights at once |
| `evon.all_blinds_close` | Close all Evon blinds at once |
| `evon.all_blinds_open` | Open all Evon blinds at once |
| `evon.all_climate_comfort` | Set all climate devices to Comfort preset |
| `evon.all_climate_eco` | Set all climate devices to Eco (energy saving) preset |
| `evon.all_climate_away` | Set all climate devices to Away (freeze/heat protection) preset |
| `evon.start_recording` | Start recording snapshots from a camera (target entity_id + optional duration) |
| `evon.stop_recording` | Stop an active camera recording and save the video |

### Example Automations

**Refresh on Home Assistant start:**
```yaml
automation:
  - alias: "Refresh Evon on startup"
    trigger:
      - platform: homeassistant
        event: start
    action:
      - delay: "00:00:30"
      - service: evon.refresh
```

**Doorbell notification (for 2N intercoms):**
```yaml
automation:
  - alias: "Doorbell notification"
    trigger:
      - platform: event
        event_type: evon_doorbell
    action:
      - service: notify.mobile_app
        data:
          title: "Doorbell"
          message: "Someone is at {{ trigger.event.data.name }}"
```

**Close all blinds at sunset:**
```yaml
automation:
  - alias: "Close blinds at sunset"
    trigger:
      - platform: sun
        event: sunset
    action:
      - service: cover.close_cover
        target:
          entity_id: cover.living_room_blinds
```

**Set away mode when leaving:**
```yaml
automation:
  - alias: "Away mode when leaving"
    trigger:
      - platform: state
        entity_id: person.me
        from: "home"
    action:
      - service: evon.set_home_state
        data:
          state: work
```

**All lights off at midnight:**
```yaml
automation:
  - alias: "All lights off at midnight"
    trigger:
      - platform: time
        at: "00:00:00"
    action:
      - service: evon.all_lights_off
```

**Eco mode when leaving home:**
```yaml
automation:
  - alias: "Eco climate when away"
    trigger:
      - platform: state
        entity_id: person.me
        from: "home"
    action:
      - service: evon.all_climate_eco
```

**Switch to cooling in summer:**
```yaml
automation:
  - alias: "Summer cooling mode"
    trigger:
      - platform: numeric_state
        entity_id: sensor.outdoor_temperature
        above: 25
        for:
          hours: 2
    action:
      - service: evon.set_season_mode
        data:
          mode: cooling
```

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

## Troubleshooting

### Connection Issues

| Problem | Solution |
|---------|----------|
| **"Failed to connect"** during setup | Verify the Evon system is powered on and reachable. Try pinging the IP address. |
| **Devices show "Unavailable"** | Check network connectivity. Use `evon.reconnect_websocket` service to re-establish connection. |
| **Slow state updates** | Ensure WebSocket is enabled (uncheck "Use HTTP API only" in options). |
| **Remote access not working** | Verify Engine ID is correct. Check that remote access is enabled in your Evon system. |

### WebSocket Troubleshooting

```
Check WebSocket status in Home Assistant logs:
Settings → System → Logs → Filter by "evon"

Common WebSocket messages:
✓ "WebSocket connected" - Working normally
✗ "WebSocket connection failed" - Network/firewall issue
✗ "WebSocket authentication failed" - Check credentials
```

If WebSocket keeps disconnecting:
1. Check your router/firewall allows WebSocket connections
2. Try the `evon.reconnect_websocket` service
3. As a last resort, enable "Use HTTP API only" in options

### Entity Issues

| Problem | Solution |
|---------|----------|
| **Missing devices** | Go to Settings → Devices & Services → Evon → Reload |
| **Stale entities** | The integration automatically cleans up removed devices on restart |
| **Wrong room assignment** | Enable "Sync areas from Evon" in options, then reload |

### Debug Logging

The easiest way to enable debug logging is via the integration options:

**Settings** → **Devices & Services** → **Evon Smart Home** → **Configure** → Enable the relevant debug toggle(s):

| Option | What it logs |
|--------|-------------|
| **Debug logging: API** | HTTP requests, responses, authentication |
| **Debug logging: WebSocket** | WebSocket messages, connection events |
| **Debug logging: Coordinator** | Data processing, entity updates |

Alternatively, enable full debug logging via `configuration.yaml`:

```yaml
logger:
  default: info
  logs:
    custom_components.evon: debug
```

---

## Version History

| Version | Changes |
|---------|---------|
| **1.17.0** | **Camera recording** - Snapshot-based video recording for 2N intercom cameras. Custom `evon-camera-recording-card` Lovelace card with record button, live stopwatch, and inline video playback. Services: `evon.start_recording` / `evon.stop_recording`. Recording switch entity for dashboard control. Configurable max duration and output format. Recordings accessible via HA media browser. **Also:** Code quality audit fixes (filesystem caching, timezone-aware datetimes, migration robustness, deprecated API cleanup). |
| **1.16.0** | **Energy Today & Energy This Month sensors** - Built-in calculated sensors for daily and monthly energy consumption. Energy Today queries HA statistics, Energy This Month combines Evon's daily data with today's consumption. No more manual utility_meter configuration needed. **Also:** Climate WebSocket fixes, group climate services, debug logging options, and WebSocket stability improvements. |
| **1.15.0** | **Camera & doorbell snapshots** - Live feed from 2N intercom cameras via WebSocket, doorbell snapshot history as image entities (up to 10), security door sensors with call-in-progress indicator. Performance improvements with parallel data processing. Security hardening (credentials removed from diagnostics, tokens removed from logs). Code quality: session management hardening, WebSocket reconnect jitter, improved input validation. |
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
