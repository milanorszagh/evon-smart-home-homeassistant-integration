"""Constants for the Evon Smart Home integration."""

DOMAIN = "evon"

# Configuration keys
CONF_HOST = "host"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_SYNC_AREAS = "sync_areas"
CONF_CONNECTION_TYPE = "connection_type"
CONF_ENGINE_ID = "engine_id"

# Connection types
CONNECTION_TYPE_LOCAL = "local"
CONNECTION_TYPE_REMOTE = "remote"

# Remote access endpoint
EVON_REMOTE_HOST = "https://my.evon-smarthome.com"

# Default values
DEFAULT_SCAN_INTERVAL = 30
DEFAULT_SYNC_AREAS = False
DEFAULT_REQUEST_TIMEOUT = 30  # seconds (for API requests)
DEFAULT_LOGIN_TIMEOUT = 15  # seconds (login should be faster)
DEFAULT_CONNECTION_POOL_SIZE = 10  # HTTP connection pool limit

# Poll interval range (seconds)
MIN_POLL_INTERVAL = 5
MAX_POLL_INTERVAL = 300

# Climate temperature defaults (Celsius)
DEFAULT_MIN_TEMP = 15.0
DEFAULT_MAX_TEMP = 25.0
DEFAULT_BATHROOM_RADIATOR_DURATION = 30  # minutes

# Validation constants
MIN_PASSWORD_LENGTH = 1  # Evon allows short passwords
ENGINE_ID_MIN_LENGTH = 4
ENGINE_ID_MAX_LENGTH = 12

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
EVON_CLASS_CLIMATE_UNIVERSAL = "Heating.ClimateControlUniversal"
EVON_CLASS_SWITCH = "SmartCOM.Switch"
EVON_CLASS_SMART_METER = "Energy.SmartMeter"
EVON_CLASS_AIR_QUALITY = "System.Location.AirQuality"
EVON_CLASS_VALVE = "SmartCOM.Clima.Valve"
EVON_CLASS_HOME_STATE = "System.HomeState"
EVON_CLASS_BATHROOM_RADIATOR = "Heating.BathroomRadiator"
EVON_CLASS_SCENE = "System.SceneApp"
EVON_CLASS_LIGHT_GROUP = "SmartCOM.Light.LightGroup"
EVON_CLASS_BLIND_GROUP = "SmartCOM.Blind.BlindGroup"
EVON_CLASS_SECURITY_DOOR = "SmartCOM.Security.SecurityDoor"
EVON_CLASS_INTERCOM_2N = "SmartCOM.Intercom.Intercom2N"

# Options keys
CONF_NON_DIMMABLE_LIGHTS = "non_dimmable_lights"

# Repair issue IDs
REPAIR_CONNECTION_FAILED = "connection_failed"
REPAIR_STALE_ENTITIES_CLEANED = "stale_entities_cleaned"
REPAIR_CONFIG_MIGRATION = "config_migration_needed"

# Connection failure threshold before creating repair
CONNECTION_FAILURE_THRESHOLD = 3

# Optimistic state tolerance (allows small rounding differences)
OPTIMISTIC_STATE_TOLERANCE = 2

# Delay after cover stop to ensure UI reflects stopped state (seconds)
COVER_STOP_DELAY = 0.3

# Timeout for optimistic state clearance (seconds)
# If coordinator hasn't confirmed state within this time, clear optimistic state
# to prevent stale UI when recovering from network issues
OPTIMISTIC_STATE_TIMEOUT = 30.0

# Settling period after control actions (seconds)
# During this time, ignore coordinator updates and trust optimistic state
# This prevents UI flicker from intermediate WebSocket states during Evon's
# light animation (0% → target brightness) or relay switching delays
# Note: Evon fade-out takes ~2.2-2.3 seconds, so 2.5s provides buffer
OPTIMISTIC_SETTLING_PERIOD = 2.5

# Shorter settling period for bathroom radiators (no animation, just response delay)
OPTIMISTIC_SETTLING_PERIOD_SHORT = 1.0

# WebSocket configuration
CONF_HTTP_ONLY = "http_only"
DEFAULT_HTTP_ONLY = False  # WebSocket is enabled by default (recommended)
DEFAULT_WS_RECONNECT_DELAY = 5  # Initial reconnect delay in seconds
WS_RECONNECT_MAX_DELAY = 300  # Maximum reconnect delay in seconds
WS_PROTOCOL = "echo-protocol"  # WebSocket sub-protocol
WS_POLL_INTERVAL = 60  # Safety net poll interval when WebSocket connected (seconds)
