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
CLIMATE_MODE_ECO = "eco"  # HA built-in preset with leaf icon (Evon: "energy saving / night mode")
CLIMATE_MODE_AWAY = "away"  # HA built-in preset with door icon (Evon: "freeze/heat protection")

# Evon ModeSaved values differ based on Season Mode!
# HEATING mode (winter): 2=away, 3=eco, 4=comfort
# COOLING mode (summer): 5=away, 6=eco, 7=comfort
EVON_PRESET_HEATING = {
    2: CLIMATE_MODE_AWAY,  # away / freeze protection
    3: CLIMATE_MODE_ECO,  # eco / energy saving
    4: CLIMATE_MODE_COMFORT,  # comfort
}
EVON_PRESET_COOLING = {
    5: CLIMATE_MODE_AWAY,  # away / heat protection in cooling
    6: CLIMATE_MODE_ECO,  # eco / energy saving
    7: CLIMATE_MODE_COMFORT,  # comfort
}

# Evon class names
EVON_CLASS_LIGHT_DIM = "SmartCOM.Light.LightDim"
EVON_CLASS_LIGHT = "SmartCOM.Light.Light"  # Relay outputs — exposed as HA switches (not lights)
EVON_CLASS_BLIND = "SmartCOM.Blind.Blind"
EVON_CLASS_CLIMATE = "SmartCOM.Clima.ClimateControl"
EVON_CLASS_CLIMATE_UNIVERSAL = "Heating.ClimateControlUniversal"
EVON_CLASS_PHYSICAL_BUTTON = "SmartCOM.Switch"  # Physical wall buttons (Tasters) — exposed as HA event entities
EVON_CLASS_SMART_METER = "Energy.SmartMeter"
EVON_CLASS_AIR_QUALITY = "System.Location.AirQuality"
EVON_CLASS_VALVE = "SmartCOM.Clima.Valve"
EVON_CLASS_HOME_STATE = "System.HomeState"
EVON_CLASS_BATHROOM_RADIATOR = "Heating.BathroomRadiator"
EVON_CLASS_SCENE = "System.SceneApp"
EVON_CLASS_LIGHT_RGBW = "SmartCOM.Light.DynamicRGBWLight"
EVON_CLASS_LIGHT_GROUP = "SmartCOM.Light.LightGroup"
EVON_CLASS_BLIND_GROUP = "SmartCOM.Blind.BlindGroup"
EVON_CLASS_SECURITY_DOOR = "Security.Door"
EVON_CLASS_INTERCOM_2N = "Security.Intercom.2N.Intercom2N"
EVON_CLASS_INTERCOM_2N_CAM = "Security.Intercom.2N.Intercom2NCam"

# Entity type keys (used in coordinator.data dictionary)
ENTITY_TYPE_LIGHTS = "lights"
ENTITY_TYPE_BLINDS = "blinds"
ENTITY_TYPE_CLIMATES = "climates"
ENTITY_TYPE_SWITCHES = "switches"
ENTITY_TYPE_SMART_METERS = "smart_meters"
ENTITY_TYPE_AIR_QUALITY = "air_quality"
ENTITY_TYPE_BATHROOM_RADIATORS = "bathroom_radiators"
ENTITY_TYPE_SCENES = "scenes"
ENTITY_TYPE_INTERCOMS = "intercoms"
ENTITY_TYPE_SECURITY_DOORS = "security_doors"
ENTITY_TYPE_HOME_STATES = "home_states"
ENTITY_TYPE_VALVES = "valves"
ENTITY_TYPE_CAMERAS = "cameras"
ENTITY_TYPE_BUTTON_EVENTS = "button_events"

# Button press detection timing (seconds)
# Double-click window must be >0.6s (Evon double-press span is ~400-600ms)
BUTTON_DOUBLE_CLICK_WINDOW = 1.0  # Max time after last release to wait for more presses
BUTTON_LONG_PRESS_THRESHOLD = 1.5  # Min hold duration for long press

# Options keys
CONF_NON_DIMMABLE_LIGHTS = "non_dimmable_lights"

# Debug logging options
CONF_DEBUG_API = "debug_api"
CONF_DEBUG_WEBSOCKET = "debug_websocket"
CONF_DEBUG_COORDINATOR = "debug_coordinator"
DEFAULT_DEBUG_API = False
DEFAULT_DEBUG_WEBSOCKET = False
DEFAULT_DEBUG_COORDINATOR = False

# Repair issue IDs
REPAIR_CONNECTION_FAILED = "connection_failed"
REPAIR_STALE_ENTITIES_CLEANED = "stale_entities_cleaned"
REPAIR_CONFIG_MIGRATION = "config_migration_needed"

# Connection failure threshold before creating repair
CONNECTION_FAILURE_THRESHOLD = 3

# Energy statistics consecutive failure threshold before escalating log level
ENERGY_STATS_FAILURE_LOG_THRESHOLD = 3

# Optimistic state tolerance (allows small rounding differences)
OPTIMISTIC_STATE_TOLERANCE = 2

# Delay after cover stop to ensure UI reflects stopped state (seconds)
COVER_STOP_DELAY = 0.3

# Timeout for optimistic state clearance (seconds)
# If coordinator hasn't confirmed state within this time, clear optimistic state
# to prevent stale UI when recovering from network issues
OPTIMISTIC_STATE_TIMEOUT = 30.0

# Login rate limiting
LOGIN_MAX_BACKOFF = 300  # Maximum backoff delay in seconds (5 minutes)
LOGIN_BACKOFF_BASE = 2  # Exponential backoff base (2^failures seconds)

# Camera/Image fetch settings
CAMERA_IMAGE_UPDATE_TIMEOUT = 5.0  # seconds to wait for WS image_path update after ImageRequest
IMAGE_FETCH_TIMEOUT = 10  # seconds timeout for fetching images from Evon server

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
WS_RECONNECT_JITTER = 0.25  # Jitter factor for reconnect delays (0.0 to 1.0)
WS_RECONNECT_MAX_DELAY = 300  # Maximum reconnect delay in seconds
WS_PROTOCOL = "echo-protocol"  # WebSocket sub-protocol
WS_POLL_INTERVAL = 60  # Safety net poll interval when WebSocket connected (seconds)
WS_HEARTBEAT_INTERVAL = 30  # WebSocket heartbeat/ping interval (seconds)
WS_DEFAULT_REQUEST_TIMEOUT = 10.0  # Default timeout for WebSocket RPC requests (seconds)
WS_SUBSCRIBE_REQUEST_TIMEOUT = 30.0  # Timeout for subscription requests (many devices) (seconds)
WS_RECEIVE_TIMEOUT = (
    WS_HEARTBEAT_INTERVAL * 6
)  # 180s — detect silent connection death (relaxed to avoid false disconnects on low-traffic systems)
WS_LOG_MESSAGE_TRUNCATE = 500  # Max characters to log from WebSocket messages
WS_MAX_PENDING_REQUESTS = 100  # Maximum pending WebSocket requests before rejecting new ones

# Light identification animation timing (seconds)
# Evon lights fade in/out over ~2.5s, so 3s provides buffer for visual effect
LIGHT_IDENTIFY_ANIMATION_DELAY = 3.0

# Service names
SERVICE_REFRESH = "refresh"
SERVICE_RECONNECT_WEBSOCKET = "reconnect_websocket"
SERVICE_SET_HOME_STATE = "set_home_state"
SERVICE_SET_SEASON_MODE = "set_season_mode"
SERVICE_ALL_LIGHTS_OFF = "all_lights_off"
SERVICE_ALL_BLINDS_CLOSE = "all_blinds_close"
SERVICE_ALL_BLINDS_OPEN = "all_blinds_open"
SERVICE_ALL_CLIMATE_COMFORT = "all_climate_comfort"
SERVICE_ALL_CLIMATE_ECO = "all_climate_eco"
SERVICE_ALL_CLIMATE_AWAY = "all_climate_away"
SERVICE_START_RECORDING = "start_recording"
SERVICE_STOP_RECORDING = "stop_recording"

# Home state mapping from service values to Evon instance IDs
HOME_STATE_MAP = {
    "at_home": "HomeStateAtHome",
    "night": "HomeStateNight",
    "work": "HomeStateWork",
    "holiday": "HomeStateHoliday",
}

# Camera recording settings
CONF_MAX_RECORDING_DURATION = "max_recording_duration"
CONF_RECORDING_OUTPUT_FORMAT = "recording_output_format"
DEFAULT_MAX_RECORDING_DURATION = 300  # seconds (5 minutes)
MIN_RECORDING_DURATION = 30  # seconds
MAX_RECORDING_DURATION = 3600  # seconds (1 hour)
MAX_RECORDING_FRAMES = 7200  # Cap frame buffer (1hr at 2fps)
RECORDING_MEDIA_DIR = "evon_recordings"
RECORDING_OUTPUT_MP4 = "mp4"
RECORDING_OUTPUT_MP4_AND_FRAMES = "mp4_and_frames"
