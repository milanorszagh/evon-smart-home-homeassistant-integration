"""Constants for the Evon Smart Home integration."""

DOMAIN = "evon"

# Configuration keys
CONF_HOST = "host"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_SYNC_AREAS = "sync_areas"

# Default values
DEFAULT_SCAN_INTERVAL = 30
DEFAULT_SYNC_AREAS = False

# Season mode (global heating/cooling)
SEASON_MODE_HEATING = "heating"
SEASON_MODE_COOLING = "cooling"

# Climate preset modes (using HA built-in presets for icons)
CLIMATE_MODE_COMFORT = "comfort"
CLIMATE_MODE_ENERGY_SAVING = "eco"  # Was "energy_saving" - eco has leaf icon
CLIMATE_MODE_FREEZE_PROTECTION = "away"  # Was "freeze_protection" - away has door icon

# Evon ModeSaved values differ based on Season Mode!
# HEATING mode (winter): 2=away, 3=eco, 4=comfort
# COOLING mode (summer): 5=away, 6=eco, 7=comfort
EVON_PRESET_HEATING = {
    2: CLIMATE_MODE_FREEZE_PROTECTION,  # away
    3: CLIMATE_MODE_ENERGY_SAVING,  # eco
    4: CLIMATE_MODE_COMFORT,  # comfort
}
EVON_PRESET_COOLING = {
    5: CLIMATE_MODE_FREEZE_PROTECTION,  # away (heat protection in cooling)
    6: CLIMATE_MODE_ENERGY_SAVING,  # eco
    7: CLIMATE_MODE_COMFORT,  # comfort
}

# Evon class names
EVON_CLASS_LIGHT_DIM = "SmartCOM.Light.LightDim"
EVON_CLASS_LIGHT = "SmartCOM.Light.Light"
EVON_CLASS_BLIND = "SmartCOM.Blind.Blind"
EVON_CLASS_CLIMATE = "SmartCOM.Clima.ClimateControl"
EVON_CLASS_CLIMATE_UNIVERSAL = "ClimateControlUniversal"
EVON_CLASS_SWITCH = "SmartCOM.Switch"
EVON_CLASS_ROOM = "System.Location.Room"
EVON_CLASS_SMART_METER = "Energy.SmartMeter"
EVON_CLASS_AIR_QUALITY = "System.Location.AirQuality"
EVON_CLASS_VALVE = "SmartCOM.Clima.Valve"
EVON_CLASS_HOME_STATE = "System.HomeState"
EVON_CLASS_BATHROOM_RADIATOR = "Heating.BathroomRadiator"

# Options keys
CONF_NON_DIMMABLE_LIGHTS = "non_dimmable_lights"
