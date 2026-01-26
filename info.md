# Evon Smart Home Integration

Control your [Evon Smart Home](https://www.evon-smarthome.com/) system directly from Home Assistant.

## Features

- **Lights**: On/off and brightness control
- **Blinds**: Position and tilt angle control
- **Climate**: Temperature control with presets (comfort, eco, away)
- **Season Mode**: Global heating/cooling switch
- **Home State**: Switch between home modes (At Home, Night, Work, Holiday)
- **Sensors**: Temperature, energy, air quality
- **Switches**: Controllable relay outputs
- **Bathroom Radiators**: Electric heater control with timer

## Configuration

After installation, add the integration via **Settings** → **Devices & Services** → **Add Integration** and search for "Evon Smart Home".

You'll need:
- Your Evon system's IP address/URL
- Your Evon username and password

## Options

- **Poll interval**: Configure how often device states are updated (5-300 seconds)
- **Area sync**: Automatically assign devices to Home Assistant areas
- **Non-dimmable lights**: Mark lights as on/off only

## Support

Report issues at the [GitHub repository](https://github.com/milanorszagh/evon-smart-home-homeassistant-integration/issues).
