# Evon Smart Home Integration

![Evon Smart Home](https://brands.home-assistant.io/evon/icon.png)

[![GitHub Release](https://img.shields.io/github/release/milanorszagh/evon-smart-home-homeassistant-integration.svg)](https://github.com/milanorszagh/evon-smart-home-homeassistant-integration/releases)
[![CI](https://github.com/milanorszagh/evon-smart-home-homeassistant-integration/actions/workflows/ci.yml/badge.svg)](https://github.com/milanorszagh/evon-smart-home-homeassistant-integration/actions/workflows/ci.yml)
[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![HA Version](https://img.shields.io/badge/Home_Assistant-2026.8+-blue.svg)](https://www.home-assistant.io/)

Home Assistant custom integration for [evon Smart Home](https://building.schrack.at/evon-smarthome-partner/) systems.

> **evon is now Schrack Smart Building.** evon Smart Home has been taken over by [Schrack Technik](https://building.schrack.at/) and the product and app are being renamed *Schrack Smart Building*. Nothing changes for this integration: it works with systems carrying either name, the integration keeps the `evon` domain and entity IDs, and the remote-access relay (`my.evon-smarthome.com`) is unchanged.

## Supported Devices

| Device Type | Features |
|-------------|----------|
| **Lights** | On/off, brightness control, color temperature (RGBW lights), identify (flash the light) |
| **Light Groups** | Control multiple lights as a single entity |
| **Blinds/Covers** | Open/close/stop, position, tilt angle |
| **Blind Groups** | Control multiple blinds as a single entity |
| **Climate** | Temperature, presets (comfort, eco, away), heating/cooling status, humidity |
| **Season Mode** | Global heating/cooling switch for the whole house |
| **Home State** | Switch between home modes (At Home, Night, Work, Holiday) |
| **Smart Meter** | Power consumption, energy usage, voltage per phase |
| **Air Quality** | CO2 levels, humidity (if available) |
| **Weather Station** | Temperature, wind, brightness, sun intensity, rain and wind alarms (read via the Home Connect gateway) |
| **Valves** | Climate valve open/closed state |
| **Temperature Sensors** | Room temperature readings |
| **Relay Outputs** | On/off light entities for relay modules (L1144, L1244) |
| **Bathroom Radiators** | Electric heater control with timer |
| **Scenes** | Trigger scenes defined in your evon system from Home Assistant |
| **Security Doors** | Door open/closed state, call in progress indicator |
| **Intercoms** | Door open/closed state, doorbell events, connection status, door opener button (disabled by default) |
| **Cameras** | Camera image from 2N intercoms (still image, refreshed when viewed), snapshot-based video recording |
| **Doorbell Snapshots** | Historical snapshots from doorbell events (image entities) |
| **Wall Buttons (Taster)** | Single, double and long press events (the push buttons on the wall, not the relay outputs above) |

---

## Installation

### Requirements

- Home Assistant 2026.8.0 or newer
- The **Energy Today** / **Energy This Month** sensors and the energy statistics import need the `recorder` integration; the media browser for camera recordings needs the `media_source` integration. Both are part of `default_config`.

### Via HACS (Recommended)

1. Make sure [HACS](https://hacs.xyz/) is installed
2. Add this repository to HACS by clicking the button below:

   [![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=milanorszagh&repository=evon-smart-home-homeassistant-integration&category=integration)

   Or manually: open **HACS** → **⋮** (top right) → **Custom repositories**, paste `https://github.com/milanorszagh/evon-smart-home-homeassistant-integration`, choose the type **Integration** and click **Add**

3. Search for **Evon Smart Home** in HACS, click **Download** and restart Home Assistant
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
| **Local Network** (Recommended) | When Home Assistant is on the same network as your evon system. Faster and more reliable. |
| **Remote Access** | When connecting from outside your home network (e.g., cloud-hosted Home Assistant). |

### Local Network Setup

1. Select **Local network** as connection type
2. Enter your evon system's local IP address or hostname (e.g., `http://192.168.1.100`)
3. Enter your username and password

### Remote Access Setup

1. Select **Remote access** as connection type
2. Enter your **Engine ID** (4–12 letters/digits, found in your evon system settings or documentation)
3. Enter your username and password (same credentials as local login)

**Note:** Local network connection is recommended for faster response times and better reliability. Only use remote access when you cannot connect locally.

---

## Configuration

### Options

After installation, configure via **Settings** → **Devices & Services** → **Evon Smart Home** → **Configure**:

| Option | Description |
|--------|-------------|
| **Sync areas from Evon** | Automatically assign devices to HA areas based on evon room assignments |
| **Non-dimmable lights** | Select lights that should be on/off only (useful for LED strips with PWM controllers). Only shown when at least one dimmable light exists. |

**HTTP API vs WebSocket** (collapsible section):

| Option | Description |
|--------|-------------|
| **Use HTTP API only** | Disable WebSocket and use HTTP polling only. WebSocket is recommended and enabled by default. Only enable this if you experience connection issues. |
| **Poll interval** | How often to fetch device states (5-300 seconds). Used as fallback when WebSocket is enabled, or as primary method when HTTP only mode is enabled. |

**Camera Recording** (collapsible section, shown when cameras are present):

| Option | Description |
|--------|-------------|
| **Max recording duration (seconds)** | Maximum recording duration in seconds (30-3600, default: 300). Prevents forgotten recordings from filling disk. |
| **Recording output format** | Choose "MP4 only" or "MP4 + JPEG frames" to also save individual frames. |

**Physical Buttons** (collapsible section, shown when wall buttons are detected):

| Option | Description |
|--------|-------------|
| **Double-click delay (seconds)** | Time to wait after a button release before firing a single press event (0.2–1.4 seconds, default: 0.8). A longer delay improves double-press detection but makes single presses feel slower. |

**Door Opener** (collapsible section, shown when a 2N intercom is present):

| Option | Description |
|--------|-------------|
| **Door open pulse (seconds)** | How long the *Open door* buttons release the door (1–30 seconds, default: 2). |

**Weather Station** (collapsible section, shown when the controller has a Home Connect gateway):

| Option | Description |
|--------|-------------|
| **Home Connect proxy ID** / **Weather station ID** | Manual override for when automatic discovery does not find your weather station. Set both or neither; clear both to return to automatic discovery. |

Settings of a section that is currently hidden (for example while the controller is offline) are kept when you save the form.

**Debug Logging** (collapsible section): per-component debug toggles for the API, WebSocket and coordinator — see [Debug Logging](#debug-logging) under Troubleshooting.

To change connection credentials or switch between local and remote access, use **Reconfigure** from the integration menu.

### Repairs

The integration creates repair issues in **Settings** → **System** → **Repairs** for:

| Issue | Description |
|-------|-------------|
| **Connection failed** | Alerts after 3 consecutive API failures. Auto-clears when connection restores. |
| **WebSocket disconnected** | Warning when the real-time WebSocket connection is lost. Auto-clears on reconnect. |
| **Stale entities cleaned** | Notice when orphaned entities are removed (dismissible). |
| **Relay migrated to light** | Notice when relay switch entities are migrated to light entities (dismissible). |
| **Config migration failed** | Error if configuration was created with a newer incompatible version. |

If your credentials stop working, Home Assistant's own re-authentication prompt appears on the integration card (**Settings** → **Devices & Services**) and guides you through entering new credentials.

### Translations

Supported languages:
- English (default)
- German (Deutsch)
- French (Français)
- Italian (Italiano)
- Spanish (Español)
- Portuguese (Português)
- Polish (Polski)
- Czech (Čeština)
- Slovak (Slovenčina)
- Slovenian (Slovenščina)

### Real-Time Updates & Control (WebSocket)

WebSocket is **enabled by default** for instant state synchronization and device control. To disable, check **"Use HTTP API only"** in options.

| Feature | HTTP Only | WebSocket (Default) |
|---------|-----------|---------------------|
| **State updates** | Up to 30 seconds | Instant |
| **Control response** | Noticeable delay | Instant |
| **Poll interval** | 30 seconds (default) | 2 minutes (safety net) |
| **Network traffic** | Continuous polling | Event-driven |

**How it works:**
- **Bidirectional communication**: Same WebSocket connection handles both state updates AND device control
- **State updates**: When a light is turned on via a physical wall button (Taster), HA updates immediately (no polling delay)
- **Device control**: Commands are sent over the open connection — tap a light and it responds instantly
- **Automatic fallback**: If WebSocket is unavailable, commands fall back to HTTP API seamlessly
- HTTP polling continues at reduced frequency (2 minutes) as a safety net
- The *WebSocket status* diagnostic sensor shows how often that poll runs, how long it takes and whether it ever corrected a value the WebSocket missed
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
- **Authentication**: Requires your evon credentials and Engine ID
- **Relay Server**: Traffic passes through the evon relay server, which proxies requests to your local system

**Recommendations:**
- Use **local network** connection when possible (faster and doesn't rely on external servers)
- Keep your evon credentials secure and don't share them
- The Engine ID is not secret but identifies your specific system

### Network Security

For local connections:
- Ensure your evon system is on a trusted network
- Consider using a VLAN to isolate IoT devices
- The integration uses HTTP by default for local connections (most evon systems don't have HTTPS enabled locally)

---

## Supported Platforms

### Lights

- Turn on/off
- Brightness control (0-100%)
- Color temperature control for RGBW lights (warm to cool white)
- Light Groups: Control multiple lights as a single entity
- Relay outputs (L1144/L1244 modules) appear as on/off lights automatically
- Dimmable lights can be configured as non-dimmable (useful for LED strips with PWM controllers)
- **Identify** button: every light has an Identify button (in the device's configuration section) that briefly flashes the light, so you can tell which physical light an entity belongs to

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

The evon system automatically decides when to heat or cool based on the target temperature and the global Season Mode setting.

### Season Mode

Global setting that controls whether the house is in heating (winter) or cooling (summer) mode. Changing this affects all climate devices simultaneously.

Options:
- **Heating (Winter)** - House in heating mode
- **Cooling (Summer)** - House in cooling mode

### Home State

Switch between home-wide modes defined in your evon system:

- **At Home** - Normal home operation
- **Night** - Night mode
- **Work** - Away at work
- **Holiday** - Vacation mode

These states trigger automations in the evon system and can be used in Home Assistant automations as well.

The select entity's option values are `at_home`, `night`, `work` and `holiday` (the same names the `evon.set_home_state` action uses). The raw evon state ID is still available in the entity's `evon_id` attribute.

> **Upgrading from 1.22 or earlier:** the options used to be the raw evon IDs (`HomeStateAtHome`, `HomeStateNight`, ...). Those values are still accepted by the `select.select_option` action for now (with a warning in the log; planned removal in 1.25), but state conditions and dashboards that compare against the old values need to be updated.

### Sensors

- Temperature sensors from climate devices
- Smart meter:
  - Power (W), Energy Total (kWh), Energy (24h Rolling)
  - Energy Today and Energy This Month (kWh) - calculated sensors, see [Energy Statistics](#energy-statistics) below
  - Voltage per phase (V) - L1, L2, L3
  - Current per phase (A) - L1, L2, L3
  - Frequency (Hz)
  - Feed-in Energy Total (kWh) - for solar/grid export tracking
- Air quality: CO2 (ppm), Humidity (%)
- Weather station (read via the Home Connect gateway, polled): temperature (°C), wind speed (km/h), brightness (lx), sun intensity north/east/south/west (kLx), today's and all-time min/max temperature and max wind, last rain (timestamp) and days since rain

**Note:** For the Energy Dashboard, use `sensor.*_energy_total` (not the 24h rolling sensor). The "Energy (24h Rolling)" sensor from evon is a rolling 24-hour window that can decrease during the day, which is not suitable for HA's energy tracking.

#### Energy Statistics

The integration provides two calculated sensors for easy energy tracking:

| Sensor | Description |
|--------|-------------|
| **Energy Today** | Today's consumption, calculated from Home Assistant's statistics on the Energy Total sensor |
| **Energy This Month** | This month's total, combining the daily values reported by your evon system (previous days) with today's consumption |

These sensors update automatically with each refresh. They need the `recorder` integration (part of `default_config`).

The integration also imports the **daily energy consumption** reported by your evon smart meter into Home Assistant's long-term statistics. This provides accurate daily values for the **previous 31 days** (not including today), plus monthly totals and feed-in energy where your meter reports them.

**Statistic IDs:** `evon:energy_<meter>`, `evon:feed_in_<meter>` and `evon:energy_monthly_<meter>`, where `<meter>` is the meter's ID in lowercase (e.g., `evon:energy_smartmeter3006939`)

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
- Weather station: rain, twilight, three wind alarms, plus diagnostic connected / temperature-valid / polling-active
- Security door state (open/closed)
- Security door call in progress
- Intercom door state (open/closed)
- Intercom connection status
- Door opener: an **Open door** button on each 2N intercom, and on each security door that is linked to an intercom, pulses the door release (2 seconds by default, adjustable under the integration's options → *Door opener*). The buttons are created **disabled** — enable them under the entity's settings before dashboards or automations can open the door
- **WebSocket connection status** (diagnostic) - shows if real-time updates are active

### Diagnostic Sensors

- **WebSocket Status** - Connection state (connected/disconnected/disabled) with detailed attributes (reconnect count, messages received, uptime, pending requests, last error)
- **WebSocket Latency** - Average response time in milliseconds for WebSocket commands (supports HA long-term statistics)

### Device Triggers

The integration provides device triggers for automations:

- **Doorbell pressed** - on intercom devices, when the doorbell is pressed
- **Button single press**, **Button double press** and **Button long press** - on every wall button (Taster) device

To use: Go to **Settings** → **Automations & Scenes** → **Create Automation** → **Device** → select your intercom or wall button → pick the trigger

### Events

The integration fires Home Assistant events that can be used in automations:

- **`evon_doorbell`**: Fired when a doorbell is pressed on an intercom
  - Event data: `device_id` (intercom ID), `name` (intercom name)
  - Use in automations to trigger notifications, announcements, or other actions
- **`evon_button_press`**: Fired for every detected wall button press
  - Event data: `device_id` (button ID), `name` (button name), `press_type` (`single_press`, `double_press` or `long_press`)
- **`evon_recording_finished`**: Fired when a camera recording has been saved
  - Event data: `entity_id` (camera entity), `path` (path of the saved MP4 file), `frames` (number of captured frames; included when the recording was stopped automatically at the maximum duration)

### Event Entities

- **Doorbell** - Event entity for 2N intercoms that fires a `ring` event when the doorbell is pressed. This provides a native HA event entity in addition to the `evon_doorbell` custom event.
- **Physical Buttons** - Event entities for wall buttons (Taster) with press type detection: `single_press`, `double_press`, and `long_press`. **Requires WebSocket connection** — button events are not available in HTTP-only mode. See [Physical Button Automations](#physical-button-automations) for examples.

### Cameras

Cameras from 2N intercoms are supported:

- **Camera image**: A still image that is refreshed each time you view it — the integration asks the intercom for a fresh snapshot and fetches the resulting JPEG
- **Error monitoring**: Shows connection status
- **Frame time**: The `image_last_updated` attribute holds the time the currently shown picture was captured, so you can see how fresh the live view is (see [Live-Feed Age Overlay](#live-feed-age-overlay))
- **Saved pictures**: Historical doorbell snapshots available as image entities (see [Doorbell Snapshots](#doorbell-snapshots))

**Camera Recording:**

Since the cameras are snapshot-based (no video stream), the integration provides a recording feature that rapidly polls snapshots and stitches them into an MP4 video:

- **Start/stop via actions**: `evon.start_recording` and `evon.stop_recording` (see [Actions](#actions))
- **Recording switch**: Toggle entity for easy dashboard control
- **Timestamp overlay**: Each frame includes a burned-in timestamp
- **Configurable output**: MP4 only, or MP4 + individual JPEG frames
- **Auto-stop**: Configurable max duration (default: 5 minutes) prevents forgotten recordings. The `evon_recording_finished` event fires when a recording has been saved.
- **Storage location**: Recordings are saved in Home Assistant's local media folder — `/media/evon_recordings` on Home Assistant OS and Docker, `<config>/media/evon_recordings` on venv installs. Recordings made with versions before 1.23.0 are moved there automatically.
- **Media browser**: Recordings appear in Home Assistant's media browser under **My media → evon_recordings** (requires the `media_source` integration, part of `default_config`)
- **Custom Lovelace card**: `evon-camera-recording-card` provides an inline recording UI with record button, live stopwatch, a list of recent recordings with inline video playback, a link to the media browser, and an optional **Open door** button for the intercom's door opener

**Note:** The frame rate is limited by how quickly the intercom delivers snapshots (roughly 0.5–2 frames per second). The result is more of a timelapse than smooth video, but is useful for security and monitoring purposes.

**Recording Card Usage:**

The integration serves the card at `/evon/evon-camera-recording-card.js`, but you have to register it as a dashboard resource once:

1. Go to **Settings** → **Dashboards** → **⋮** (top right) → **Resources** → **Add resource** (the Resources entry is only visible with **Advanced mode** enabled in your user profile)
2. Enter the URL `/evon/evon-camera-recording-card.js` and choose the type **JavaScript module**
3. Reload the browser page

If you manage dashboards in YAML, add the resource to `configuration.yaml` instead:
```yaml
lovelace:
  resources:
    - url: /evon/evon-camera-recording-card.js
      type: module
```

Then add the card to any dashboard (works great inside Bubble Card popups):
```yaml
type: custom:evon-camera-recording-card
entity: camera.your_camera_entity
recording_switch: switch.your_camera_recording  # optional, auto-derived from entity if omitted
door_button: button.your_intercom_open_door     # optional, adds an "Open door" button next to "Record"
sip_extension: "8001"                           # optional, adds a "Talk" button for SIP two-way audio (see docs/INTERCOM_AUDIO.md)
show_title: false                               # optional, hides the "Recording" heading (default: true)
```

`door_button` takes one of the integration's *Open door* button entities (created disabled — enable it in the entity settings first). Pressing it pulses the door release and shows *Opening…* for a few seconds.

`sip_extension` adds a **Talk** button for two-way audio with the door station. It needs an optional, self-hosted SIP stack (an Asterisk add-on, the SIP Core card, and HTTPS for microphone access, e.g. via Tailscale) that is **not** part of this integration. The full setup, requirements and config templates are in [docs/INTERCOM_AUDIO.md](docs/INTERCOM_AUDIO.md).

#### Live-Feed Age Overlay

The same resource also provides a small `evon-live-clock` badge for a `picture-elements` card. It shows when the picture you are looking at was captured and how old it is, for example `19:53:07 · 2s ago`. If the feed freezes, the age keeps climbing and the badge turns amber after 5 seconds and red after 15 seconds:

```yaml
type: picture-elements
camera_image: camera.your_camera_entity
camera_view: live
elements:
  - type: custom:evon-live-clock
    entity: camera.your_camera_entity
    style:
      top: 6%
      right: 2%
      transform: none
```

### Doorbell Snapshots

When someone rings the doorbell, evon automatically captures and stores a snapshot. These are exposed as image entities:

- **Up to 10 snapshots** stored by evon (their limit)
- **Entities**: One image entity per snapshot, grouped in a "<Door name> Snapshots" device — e.g., `image.front_door_snapshots_snapshot_1` through `..._snapshot_10`
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
        entity: image.front_door_snapshots_snapshot_1
        show_state: false
        show_name: false
      # ... repeat for snapshot_2 through snapshot_10
```

### Bathroom Radiators

- Electric heater control with timer (turns off automatically after configured duration)

---

## Actions

The integration provides the following actions that can be called from automations, scripts, or the Developer Tools:

| Action | Description |
|--------|-------------|
| `evon.refresh` | Force refresh all device states from the evon system |
| `evon.reconnect_websocket` | Reconnect the WebSocket connection (use if real-time updates stop working) |
| `evon.set_home_state` | Set home state: `at_home`, `night`, `work`, `holiday` |
| `evon.set_season_mode` | Set season mode: `heating` or `cooling` |
| `evon.all_lights_off` | Turn off all evon lights at once |
| `evon.all_blinds_close` | Close all evon blinds at once |
| `evon.all_blinds_open` | Open all evon blinds at once |
| `evon.all_climate_comfort` | Set all climate devices to Comfort preset |
| `evon.all_climate_eco` | Set all climate devices to Eco (energy saving) preset |
| `evon.all_climate_away` | Set all climate devices to Away (freeze/heat protection) preset |
| `evon.start_recording` | Start recording snapshots from a camera. Fields: `entity_id` (camera entity, required), `duration` (optional, 30–3600 seconds; uses the configured maximum if omitted) |
| `evon.stop_recording` | Stop an active camera recording and save the video. Field: `entity_id` (camera entity, required) |

For the recording actions, `entity_id` is a data field (under `data:`), not a `target:`.

### Example Automations

**Refresh on Home Assistant start:**
```yaml
automation:
  - alias: "Refresh Evon on startup"
    triggers:
      - trigger: homeassistant
        event: start
    actions:
      - delay: "00:00:30"
      - action: evon.refresh
```

**Doorbell notification (for 2N intercoms):**
```yaml
automation:
  - alias: "Doorbell notification"
    triggers:
      - trigger: event
        event_type: evon_doorbell
    actions:
      - action: notify.mobile_app
        data:
          title: "Doorbell"
          message: "Someone is at {{ trigger.event.data.name }}"
```

**Close all blinds at sunset:**
```yaml
automation:
  - alias: "Close blinds at sunset"
    triggers:
      - trigger: sun
        event: sunset
    actions:
      - action: cover.close_cover
        target:
          entity_id: cover.living_room_blinds
```

**Set away mode when leaving:**
```yaml
automation:
  - alias: "Away mode when leaving"
    triggers:
      - trigger: state
        entity_id: person.me
        from: "home"
    actions:
      - action: evon.set_home_state
        data:
          state: work
```

**All lights off at midnight:**
```yaml
automation:
  - alias: "All lights off at midnight"
    triggers:
      - trigger: time
        at: "00:00:00"
    actions:
      - action: evon.all_lights_off
```

**Eco mode when leaving home:**
```yaml
automation:
  - alias: "Eco climate when away"
    triggers:
      - trigger: state
        entity_id: person.me
        from: "home"
    actions:
      - action: evon.all_climate_eco
```

### Physical Button Automations

Physical wall buttons (Taster) fire event entities with three press types: `single_press`, `double_press`, and `long_press`. Use them to trigger any Home Assistant automation. Button events require the default WebSocket connection (not available in HTTP-only mode).

**Toggle a relay on button press:**
```yaml
automation:
  - alias: "Toggle desk lamp relay on button press"
    triggers:
      - trigger: state
        entity_id: event.hallway_button
        attribute: event_type
        to: "single_press"
    actions:
      - action: light.toggle
        target:
          entity_id: light.desk_lamp  # relay output entity (on/off light)
```

**Double-press to trigger a scene:**
```yaml
automation:
  - alias: "Movie mode on double press"
    triggers:
      - trigger: state
        entity_id: event.living_room_button
        attribute: event_type
        to: "double_press"
    actions:
      - action: scene.turn_on
        target:
          entity_id: scene.movie_mode
```

**Long press to turn off all lights:**
```yaml
automation:
  - alias: "All lights off on long press"
    triggers:
      - trigger: state
        entity_id: event.bedroom_button
        attribute: event_type
        to: "long_press"
    actions:
      - action: evon.all_lights_off
```

**Using the bus event (for advanced automations):**
```yaml
automation:
  - alias: "Button press notification"
    triggers:
      - trigger: event
        event_type: evon_button_press
        event_data:
          press_type: double_press
    actions:
      - action: notify.mobile_app
        data:
          title: "Button Pressed"
          message: "{{ trigger.event.data.name }} was double-pressed"
```

**Switch to cooling in summer:**
```yaml
automation:
  - alias: "Summer cooling mode"
    triggers:
      - trigger: numeric_state
        entity_id: sensor.outdoor_temperature
        above: 25
        for:
          hours: 2
    actions:
      - action: evon.set_season_mode
        data:
          mode: cooling
```

---

## MCP Server

An MCP (Model Context Protocol) server is included for AI assistant integration (e.g., Claude). This allows AI assistants to control your evon devices directly.

See [DEVELOPMENT.md](DEVELOPMENT.md) for setup instructions and available tools.

---

## Troubleshooting

### Connection Issues

| Problem | Solution |
|---------|----------|
| **"Failed to connect"** during setup | Verify the evon system is powered on and reachable. Try pinging the IP address. |
| **Devices show "Unavailable"** | Check that the evon system is reachable from Home Assistant, then reload the integration (see below). |
| **Slow state updates** | Ensure WebSocket is enabled (uncheck "Use HTTP API only" in options). |
| **Remote access not working** | Verify Engine ID is correct. Check that remote access is enabled in your evon system. |

**Devices show "Unavailable":** this means the integration could not fetch device states from the evon system. Check that the system is reachable from Home Assistant (try pinging its IP address), then reload the integration via **Settings** → **Devices & Services** → **Evon** → **⋮** → **Reload**. A lost WebSocket connection alone does not make devices unavailable — the integration falls back to polling.

### WebSocket Troubleshooting

Check the WebSocket status in the Home Assistant logs (**Settings** → **System** → **Logs**, search for "evon") or on the **WebSocket Status** diagnostic sensor. Messages you may see in the log:

| Message | Meaning |
|---------|---------|
| `WebSocket connected to Evon Smart Home` | Working normally |
| `WebSocket connection failed: ...` | Network / firewall issue — the error details follow the colon |
| `WebSocket login failed: Invalid credentials` | Check your username and password |

If WebSocket keeps disconnecting:
1. Check your router/firewall allows WebSocket connections
2. Try the `evon.reconnect_websocket` action
3. As a last resort, enable "Use HTTP API only" in options

### Entity Issues

| Problem | Solution |
|---------|----------|
| **Missing devices** | Go to Settings → Devices & Services → Evon → Reload |
| **Stale entities** | The integration automatically cleans up removed devices on restart |
| **Wrong room assignment** | Enable "Sync areas from Evon" in options, then reload |

### Debug Logging

The easiest way to enable debug logging is via the integration options:

**Settings** → **Devices & Services** → **Evon Smart Home** → **Configure** → **Debug Logging** → Enable the relevant toggle(s):

| Option | What it logs |
|--------|-------------|
| **API** | HTTP requests, responses, authentication |
| **WebSocket** | WebSocket messages, connection events |
| **Coordinator** | Data processing, entity updates |

Alternatively, enable full debug logging via `configuration.yaml`:

```yaml
logger:
  default: info
  logs:
    custom_components.evon: debug
```

---

## Version History

Every version is described in detail in [CHANGELOG.md](CHANGELOG.md). Highlights:

| Version | Date | Highlights |
|---------|------|------------|
| **1.23.0** | 2026-10-12 | HA 2026.10 compatibility, recordings in the media folder, hassfest in CI, MCP heartbeat, translated action dropdowns. **Breaking:** minimum HA 2026.8.0; Home State select options are now `at_home` / `night` / `work` / `holiday` |
| **1.22.1** | 2026-08-24 | Quiet systems no longer disconnect every 3 minutes |
| **1.22.0** | 2026-08-07 | Post-command bounce-back fixed, camera recordings served through an authenticated endpoint, many review fixes. **Breaking:** minimum HA 2026.5.0 (Python 3.14), Node 24 for the MCP server |
| **1.21.0** | 2026-03-24 | HA 2026.3 compatibility, HACS hardening, security fixes |
| **1.20.0** | 2026-02-22 | Relay outputs are light entities (**breaking**, with automatic migration), 14 review fixes |
| **1.19.2** | 2026-02-21 | Double-click detection for the fourth button pattern |
| **1.19.1** | 2026-02-21 | Relay switch 401 errors fixed |
| **1.19.0** | 2026-02-17 | Physical wall buttons as event entities with single / double / long press detection |
| **1.18.0** | 2026-02-15 | Auth retry storm fix, WebSocket diagnostic sensors, doorbell event entity, 8 new languages |
| **1.17.1** | 2026-02-11 | Code quality audit: 8 bug fixes, hardening, 260+ new tests |
| **1.17.0** | 2026-02-08 | Camera recording with a custom Lovelace card |
| **1.16.0** | 2026-02-07 | Energy Today and Energy This Month sensors |
| **1.15.0** | 2026-02-02 | Camera live feed, doorbell snapshots, security door sensors |
| **1.14.0 – 1.14.3** | 2026-02-01 – 06 | WebSocket device control, security doors and intercoms, light and blind groups, climate WebSocket control fixes |
| **1.13.0** | 2026-01-31 | WebSocket real-time state updates |
| **1.12.0** | 2026-01-30 | Remote access via the relay server, security improvements |
| **1.11.0** | 2026-01-29 | Scenes, smart meter current / frequency / feed-in sensors |
| **1.10.0 – 1.10.2** | 2026-01-24 – 29 | Non-dimmable lights option, Repairs, hub device, Energy Dashboard fix, data caching |
| **1.9.0** | 2026-01-17 | Season Mode select, climate activity display |
| **1.8.0 – 1.8.2** | 2026-01-16 | Optimistic updates for all entities |
| **1.7.0 – 1.7.4** | 2026-01-15 – 16 | Bathroom radiators, climate preset fixes |
| **1.6.0** | 2026-01-15 | Automatic stale entity cleanup |
| **1.5.0 – 1.5.2** | 2026-01-15 | Home State selector |
| **1.3.0 – 1.4.1** | 2026-01-15 | Smart meter, air quality and valve sensors, diagnostics, blind control fix |
| **1.0.0 – 1.2.0** | 2026-01-15 | Initial release, sensors and switches, options and reconfigure flows, area sync, German translations |

---

## Contributing

Contributions are welcome! See [DEVELOPMENT.md](DEVELOPMENT.md) for architecture details, API reference, and development guidelines.

## License

MIT License - see [LICENSE](LICENSE) file.

## Disclaimer

This project is not affiliated with or endorsed by evon Smart Home, Schrack Technik or Schrack Smart Building. Use at your own risk.
