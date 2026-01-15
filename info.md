# Evon Smart Home Integration

Control your [Evon Smart Home](https://www.evon-smarthome.com/) system directly from Home Assistant.

## Features

- **Lights**: On/off and brightness control (0-100%)
- **Switches**: On/off with click event detection (single, double, long press)
- **Blinds**: Open/close/stop, position and tilt angle control
- **Climate**: Temperature control with preset modes (comfort, energy saving, freeze protection)
- **Sensors**: Temperature readings from climate devices

## Configuration

After installation, add the integration via **Settings** → **Devices & Services** → **Add Integration** and search for "Evon Smart Home".

You'll need:
- Your Evon system's IP address/URL
- Your Evon username and password

## Options

- **Poll interval**: Configure how often device states are updated (5-300 seconds)
- **Reconfigure**: Change connection credentials without removing the integration

## Automations

Use switch click events in automations:

```yaml
automation:
  - trigger:
      - platform: event
        event_type: evon_event
        event_data:
          event_type: double_click
    action:
      - service: scene.turn_on
        target:
          entity_id: scene.movie_mode
```

## Support

Report issues at the [GitHub repository](https://github.com/milanorszagh/evon-smart-home-homeassistant-integration/issues).
