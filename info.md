# Evon Smart Home Integration

Control your [Evon Smart Home](https://www.evon-smarthome.com/) system directly from Home Assistant.

## Features

- **Lights**: On/off, brightness, and color temperature control (RGBW)
- **Light Groups**: Control multiple lights as one entity
- **Blinds**: Position and tilt angle control
- **Blind Groups**: Control multiple blinds as one entity
- **Climate**: Temperature control with presets and humidity display
- **Season Mode**: Global heating/cooling switch
- **Home State**: Switch between home modes (At Home, Night, Work, Holiday)
- **Sensors**: Temperature, energy, air quality
- **Switches**: Controllable relay outputs
- **Bathroom Radiators**: Electric heater control with timer
- **Scenes**: Trigger Evon-defined scenes from Home Assistant
- **Security Doors**: Door state and call in progress sensors
- **Intercoms**: Door state, connection status, and doorbell events
- **Cameras**: Live feed from 2N intercom cameras with recording controls and media browser integration
- **Doorbell Snapshots**: Historical snapshots as image entities

## Configuration

After installation, add the integration via **Settings** → **Devices & Services** → **Add Integration** and search for "Evon Smart Home".

### Connection Methods

- **Local Network** (Recommended): Direct connection using your Evon system's IP address
- **Remote Access**: Connect via my.evon-smarthome.com when outside your home network

You'll need:
- Your Evon system's IP address (local) or Engine ID (remote)
- Your Evon username and password

## Instant Response via WebSocket

WebSocket is **enabled by default** for:
- **Instant state updates**: Device changes are reflected immediately (<100ms)
- **Instant control**: Commands sent via WebSocket respond in <50ms

No more waiting for poll cycles - when you tap a light in HA, it responds instantly.

Works for both local and remote connections.

## Options

- **Use HTTP API only**: Disable WebSocket (not recommended unless you have connection issues)
- **Poll interval**: Configure how often device states are updated (5-300 seconds)
- **Area sync**: Automatically assign devices to Home Assistant areas
- **Non-dimmable lights**: Mark lights as on/off only

## Support

Report issues at the [GitHub repository](https://github.com/milanorszagh/evon-smart-home-homeassistant-integration/issues).
