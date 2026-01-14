"""Constants for the Evon Smart Home integration."""

DOMAIN = "evon"

# Configuration keys
CONF_HOST = "host"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"

# Default values
DEFAULT_HOST = "http://192.168.1.4"
DEFAULT_SCAN_INTERVAL = 30

# Climate modes
CLIMATE_MODE_COMFORT = "comfort"
CLIMATE_MODE_ENERGY_SAVING = "energy_saving"
CLIMATE_MODE_FREEZE_PROTECTION = "freeze_protection"

# Evon class names
EVON_CLASS_LIGHT_DIM = "SmartCOM.Light.LightDim"
EVON_CLASS_BLIND = "SmartCOM.Blind.Blind"
EVON_CLASS_CLIMATE = "SmartCOM.Clima.ClimateControl"
EVON_CLASS_CLIMATE_UNIVERSAL = "ClimateControlUniversal"
