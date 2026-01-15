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

# Climate modes
CLIMATE_MODE_COMFORT = "comfort"
CLIMATE_MODE_ENERGY_SAVING = "energy_saving"
CLIMATE_MODE_FREEZE_PROTECTION = "freeze_protection"

# Evon class names
EVON_CLASS_LIGHT_DIM = "SmartCOM.Light.LightDim"
EVON_CLASS_LIGHT = "SmartCOM.Light.Light"
EVON_CLASS_BLIND = "SmartCOM.Blind.Blind"
EVON_CLASS_CLIMATE = "SmartCOM.Clima.ClimateControl"
EVON_CLASS_CLIMATE_UNIVERSAL = "ClimateControlUniversal"
EVON_CLASS_SWITCH = "SmartCOM.Switch"
EVON_CLASS_BUTTON = "SmartCOM.Button.Button"
EVON_CLASS_ROOM = "System.Location.Room"
EVON_CLASS_SMART_METER = "Energy.SmartMeter"
EVON_CLASS_AIR_QUALITY = "System.Location.AirQuality"
EVON_CLASS_VALVE = "SmartCOM.Clima.Valve"

# Event types
EVENT_SINGLE_CLICK = "single_click"
EVENT_DOUBLE_CLICK = "double_click"
EVENT_LONG_PRESS = "long_press"
