"""The Evon Smart Home integration."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
import logging
from pathlib import Path
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr, entity_registry as er, issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import INSTANCE_ID_PATTERN, EvonApi
from .const import (
    CONF_CONNECTION_TYPE,
    CONF_DEBUG_API,
    CONF_DEBUG_COORDINATOR,
    CONF_DEBUG_WEBSOCKET,
    CONF_ENGINE_ID,
    CONF_HOST,
    CONF_HTTP_ONLY,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_SYNC_AREAS,
    CONF_USERNAME,
    CONNECTION_TYPE_LOCAL,
    CONNECTION_TYPE_REMOTE,
    DEFAULT_DEBUG_API,
    DEFAULT_DEBUG_COORDINATOR,
    DEFAULT_DEBUG_WEBSOCKET,
    DEFAULT_HTTP_ONLY,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SYNC_AREAS,
    DOMAIN,
    ENTITY_TYPE_AIR_QUALITY,
    ENTITY_TYPE_BATHROOM_RADIATORS,
    ENTITY_TYPE_BLINDS,
    ENTITY_TYPE_CAMERAS,
    ENTITY_TYPE_CLIMATES,
    ENTITY_TYPE_INTERCOMS,
    ENTITY_TYPE_LIGHTS,
    ENTITY_TYPE_SCENES,
    ENTITY_TYPE_SECURITY_DOORS,
    ENTITY_TYPE_SMART_METERS,
    ENTITY_TYPE_SWITCHES,
    ENTITY_TYPE_VALVES,
    EVON_REMOTE_HOST,
    HOME_STATE_MAP,
    REPAIR_CONFIG_MIGRATION,
    REPAIR_STALE_ENTITIES_CLEANED,
    SERVICE_ALL_BLINDS_CLOSE,
    SERVICE_ALL_BLINDS_OPEN,
    SERVICE_ALL_CLIMATE_AWAY,
    SERVICE_ALL_CLIMATE_COMFORT,
    SERVICE_ALL_CLIMATE_ECO,
    SERVICE_ALL_LIGHTS_OFF,
    SERVICE_RECONNECT_WEBSOCKET,
    SERVICE_REFRESH,
    SERVICE_SET_HOME_STATE,
    SERVICE_SET_SEASON_MODE,
    SERVICE_START_RECORDING,
    SERVICE_STOP_RECORDING,
)
from .coordinator import EvonDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


def _apply_debug_logging(entry: ConfigEntry) -> None:
    """Apply debug logging settings from config entry options.

    This sets the log level for specific evon loggers based on user preferences.
    Changes take effect immediately without requiring a restart.
    """
    debug_api = entry.options.get(CONF_DEBUG_API, DEFAULT_DEBUG_API)
    debug_ws = entry.options.get(CONF_DEBUG_WEBSOCKET, DEFAULT_DEBUG_WEBSOCKET)
    debug_coord = entry.options.get(CONF_DEBUG_COORDINATOR, DEFAULT_DEBUG_COORDINATOR)

    # API logger (custom_components.evon.api)
    api_logger = logging.getLogger("custom_components.evon.api")
    api_logger.setLevel(logging.DEBUG if debug_api else logging.INFO)

    # WebSocket logger (custom_components.evon.ws_client)
    ws_logger = logging.getLogger("custom_components.evon.ws_client")
    ws_logger.setLevel(logging.DEBUG if debug_ws else logging.INFO)

    # Coordinator logger (custom_components.evon.coordinator)
    coord_logger = logging.getLogger("custom_components.evon.coordinator")
    coord_logger.setLevel(logging.DEBUG if debug_coord else logging.INFO)

    _LOGGER.info(
        "Debug logging: API=%s, WebSocket=%s, Coordinator=%s",
        "DEBUG" if debug_api else "INFO",
        "DEBUG" if debug_ws else "INFO",
        "DEBUG" if debug_coord else "INFO",
    )


def _get_service_lock(hass: HomeAssistant) -> asyncio.Lock:
    """Get or create the service lock for this hass instance.

    The lock is stored in hass.data to ensure it's properly bound to the
    event loop and isolated per HA instance.
    """
    lock_key = f"{DOMAIN}_service_lock"
    return hass.data.setdefault(lock_key, asyncio.Lock())


async def _async_setup_websocket(
    hass: HomeAssistant,
    coordinator: EvonDataUpdateCoordinator,
    config_entry: ConfigEntry,
) -> None:
    """Set up WebSocket connection for a coordinator based on config entry."""
    connection_type = config_entry.data.get(CONF_CONNECTION_TYPE, CONNECTION_TYPE_LOCAL)
    if connection_type == CONNECTION_TYPE_LOCAL:
        await coordinator.async_setup_websocket(
            session=async_get_clientsession(hass),
            host=config_entry.data[CONF_HOST],
            username=config_entry.data[CONF_USERNAME],
            password=config_entry.data[CONF_PASSWORD],
        )
    else:
        await coordinator.async_setup_websocket(
            session=async_get_clientsession(hass),
            host=None,
            username=config_entry.data[CONF_USERNAME],
            password=config_entry.data[CONF_PASSWORD],
            is_remote=True,
            engine_id=config_entry.data[CONF_ENGINE_ID],
        )


PLATFORMS: list[Platform] = [
    Platform.BUTTON,
    Platform.CAMERA,
    Platform.IMAGE,
    Platform.LIGHT,
    Platform.COVER,
    Platform.CLIMATE,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.BINARY_SENSOR,
    Platform.SELECT,
]


def _find_camera_entity(hass: HomeAssistant, entity_id: str) -> Any:
    """Find an EvonCamera entity by entity_id from the shared camera registry."""
    for entry_data in hass.data.get(DOMAIN, {}).values():
        if not isinstance(entry_data, dict):
            continue
        for camera in entry_data.get("cameras", {}).values():
            if camera.entity_id == entity_id:
                return camera
    return None


def _ensure_recordings_dir(recordings_dir: str) -> None:
    """Create recordings directory (runs in executor)."""
    Path(recordings_dir).mkdir(parents=True, exist_ok=True)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Evon Smart Home from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    # Determine connection type (default to local for backwards compatibility)
    connection_type = entry.data.get(CONF_CONNECTION_TYPE, CONNECTION_TYPE_LOCAL)

    # Create API client based on connection type
    session = async_get_clientsession(hass)
    if connection_type == CONNECTION_TYPE_REMOTE:
        api = EvonApi(
            engine_id=entry.data[CONF_ENGINE_ID],
            username=entry.data[CONF_USERNAME],
            password=entry.data[CONF_PASSWORD],
            session=session,
        )
        configuration_url = f"{EVON_REMOTE_HOST}/{entry.data[CONF_ENGINE_ID]}"
    else:
        api = EvonApi(
            host=entry.data[CONF_HOST],
            username=entry.data[CONF_USERNAME],
            password=entry.data[CONF_PASSWORD],
            session=session,
        )
        configuration_url = entry.data[CONF_HOST]

    # Test connection
    if not await api.test_connection():
        raise ConfigEntryNotReady("Failed to connect to Evon Smart Home")

    # Get options
    scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    sync_areas = entry.options.get(CONF_SYNC_AREAS, DEFAULT_SYNC_AREAS)
    http_only = entry.options.get(CONF_HTTP_ONLY, DEFAULT_HTTP_ONLY)
    use_websocket = not http_only

    # Create coordinator
    coordinator = EvonDataUpdateCoordinator(hass, api, scan_interval, sync_areas, use_websocket)

    # Fetch initial data
    await coordinator.async_config_entry_first_refresh()

    # Store coordinator and connection info for WebSocket
    hass.data[DOMAIN][entry.entry_id] = {
        "api": api,
        "coordinator": coordinator,
        "cameras": {},  # instance_id -> EvonCamera, populated by camera platform
    }

    # Apply debug logging settings
    _apply_debug_logging(entry)

    # Set up WebSocket for real-time updates (both local and remote connections)
    if use_websocket:
        # Remote connection via my.evon-smarthome.com handled in helper
        await _async_setup_websocket(hass, coordinator, entry)

    # Create hub device that child devices reference via via_device
    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        name="Evon Smart Home",
        manufacturer="Evon",
        model="Smart Home Controller",
        configuration_url=configuration_url,
    )

    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register services (only once per domain)
    if not hass.services.has_service(DOMAIN, SERVICE_REFRESH):

        async def handle_refresh(call: ServiceCall) -> None:
            """Handle the refresh service call."""
            _LOGGER.info("Refresh service called - forcing data update")
            async with _get_service_lock(hass):
                entries = list(hass.data.get(DOMAIN, {}).values())
                for entry_data in entries:
                    if not isinstance(entry_data, dict) or entry_data.get("unloading"):
                        continue
                    if "coordinator" in entry_data:
                        await entry_data["coordinator"].async_refresh()

        async def handle_reconnect_websocket(call: ServiceCall) -> None:
            """Handle the reconnect websocket service call."""
            _LOGGER.info("Reconnect WebSocket service called")
            async with _get_service_lock(hass):
                entries = list(hass.data.get(DOMAIN, {}).items())
                for entry_id, entry_data in entries:
                    if not isinstance(entry_data, dict) or "coordinator" not in entry_data or entry_data.get("unloading"):
                        continue
                    coordinator = entry_data["coordinator"]
                    config_entry = hass.config_entries.async_get_entry(entry_id)
                    if not config_entry:
                        _LOGGER.debug("Config entry %s not found, skipping WebSocket reconnect", entry_id)
                        continue
                    if not coordinator.use_websocket:
                        _LOGGER.debug("WebSocket disabled for %s, skipping reconnect", entry_id)
                        continue
                    try:
                        await coordinator.async_shutdown_websocket()
                        await _async_setup_websocket(hass, coordinator, config_entry)
                    except Exception as err:
                        _LOGGER.error("Failed to reconnect WebSocket for %s: %s", entry_id, err)

        async def handle_set_home_state(call: ServiceCall) -> None:
            """Handle the set home state service call."""
            state = call.data.get("state")
            if not state or state not in HOME_STATE_MAP:
                _LOGGER.error("Invalid home state: %s", state)
                return
            evon_state = HOME_STATE_MAP[state]
            _LOGGER.info("Set home state service called: %s -> %s", state, evon_state)
            async with _get_service_lock(hass):
                entries = list(hass.data.get(DOMAIN, {}).values())
                for entry_data in entries:
                    if not isinstance(entry_data, dict) or entry_data.get("unloading"):
                        continue
                    if "api" in entry_data:
                        try:
                            await entry_data["api"].activate_home_state(evon_state)
                        except Exception as err:
                            _LOGGER.warning("Failed to set home state: %s", err)
                    if "coordinator" in entry_data:
                        await entry_data["coordinator"].async_refresh()

        async def handle_set_season_mode(call: ServiceCall) -> None:
            """Handle the set season mode service call."""
            mode = call.data.get("mode")
            if mode not in ("heating", "cooling"):
                _LOGGER.error("Invalid season mode: %s", mode)
                return
            is_cooling = mode == "cooling"
            _LOGGER.info("Set season mode service called: %s", mode)
            async with _get_service_lock(hass):
                entries = list(hass.data.get(DOMAIN, {}).values())
                for entry_data in entries:
                    if not isinstance(entry_data, dict) or entry_data.get("unloading"):
                        continue
                    if "api" in entry_data:
                        try:
                            await entry_data["api"].set_season_mode(is_cooling)
                        except Exception as err:
                            _LOGGER.warning("Failed to set season mode: %s", err)
                    if "coordinator" in entry_data:
                        await entry_data["coordinator"].async_refresh()

        async def _bulk_api_call(
            service_name: str,
            api_method: str,
        ) -> None:
            """Execute a bulk API method across all entries."""
            _LOGGER.info("%s service called", service_name)
            async with _get_service_lock(hass):
                entries = list(hass.data.get(DOMAIN, {}).items())
                for _entry_id, entry_data in entries:
                    if not isinstance(entry_data, dict) or "coordinator" not in entry_data or "api" not in entry_data or entry_data.get("unloading"):
                        continue
                    coordinator = entry_data["coordinator"]
                    api = entry_data["api"]
                    try:
                        await getattr(api, api_method)()
                    except Exception as err:
                        _LOGGER.warning("Failed %s: %s", service_name, err)
                    await coordinator.async_refresh()

        async def _bulk_entity_call(
            service_name: str,
            entity_type: str,
            api_method: str,
            filter_fn: Callable[[dict[str, Any]], bool] | None = None,
        ) -> None:
            """Execute a per-entity API method across all entries."""
            _LOGGER.info("%s service called", service_name)
            async with _get_service_lock(hass):
                entries = list(hass.data.get(DOMAIN, {}).items())
                for _entry_id, entry_data in entries:
                    if not isinstance(entry_data, dict) or "coordinator" not in entry_data or "api" not in entry_data or entry_data.get("unloading"):
                        continue
                    coordinator = entry_data["coordinator"]
                    api = entry_data["api"]
                    if coordinator.data and entity_type in coordinator.data:
                        for entity in list(coordinator.data[entity_type]):
                            entity_id = entity.get("id")
                            if not entity_id:
                                continue
                            if not INSTANCE_ID_PATTERN.match(entity_id):
                                _LOGGER.warning("Invalid instance ID in bulk call: %r", entity_id)
                                continue
                            if filter_fn and not filter_fn(entity):
                                continue
                            try:
                                await getattr(api, api_method)(entity_id)
                            except Exception as err:
                                _LOGGER.warning("Failed %s for %s: %s", service_name, entity_id, err)
                    await coordinator.async_refresh()

        async def handle_all_lights_off(call: ServiceCall) -> None:
            await _bulk_entity_call(
                "All lights off",
                ENTITY_TYPE_LIGHTS,
                "turn_off_light",
                filter_fn=lambda light: light.get("is_on"),
            )

        async def handle_all_blinds_close(call: ServiceCall) -> None:
            await _bulk_entity_call("All blinds close", ENTITY_TYPE_BLINDS, "close_blind")

        async def handle_all_blinds_open(call: ServiceCall) -> None:
            await _bulk_entity_call("All blinds open", ENTITY_TYPE_BLINDS, "open_blind")

        async def handle_all_climate_comfort(call: ServiceCall) -> None:
            await _bulk_api_call("All climate comfort", "all_climate_comfort")

        async def handle_all_climate_eco(call: ServiceCall) -> None:
            await _bulk_api_call("All climate eco", "all_climate_eco")

        async def handle_all_climate_away(call: ServiceCall) -> None:
            await _bulk_api_call("All climate away", "all_climate_away")

        async def handle_start_recording(call: ServiceCall) -> None:
            """Handle the start recording service call."""
            entity_id = call.data.get("entity_id")
            duration = call.data.get("duration")
            if duration is not None:
                try:
                    duration = int(duration)
                    if duration <= 0:
                        raise ValueError("duration must be positive")
                except (TypeError, ValueError):
                    _LOGGER.error("Invalid recording duration: %r", duration)
                    return
            if not entity_id:
                _LOGGER.error("entity_id is required for start_recording")
                return
            entity = hass.states.get(entity_id)
            if not entity:
                _LOGGER.error("Entity %s not found", entity_id)
                return
            # Find the camera entity object
            camera_entity = _find_camera_entity(hass, entity_id)
            if camera_entity:
                await camera_entity.async_start_recording(duration=duration)
            else:
                _LOGGER.error("Camera entity %s not found", entity_id)

        async def handle_stop_recording(call: ServiceCall) -> None:
            """Handle the stop recording service call."""
            entity_id = call.data.get("entity_id")
            if not entity_id:
                _LOGGER.error("entity_id is required for stop_recording")
                return
            camera_entity = _find_camera_entity(hass, entity_id)
            if camera_entity:
                await camera_entity.async_stop_recording()
            else:
                _LOGGER.error("Camera entity %s not found", entity_id)

        hass.services.async_register(DOMAIN, SERVICE_REFRESH, handle_refresh)
        hass.services.async_register(DOMAIN, SERVICE_RECONNECT_WEBSOCKET, handle_reconnect_websocket)
        hass.services.async_register(DOMAIN, SERVICE_SET_HOME_STATE, handle_set_home_state)
        hass.services.async_register(DOMAIN, SERVICE_SET_SEASON_MODE, handle_set_season_mode)
        hass.services.async_register(DOMAIN, SERVICE_ALL_LIGHTS_OFF, handle_all_lights_off)
        hass.services.async_register(DOMAIN, SERVICE_ALL_BLINDS_CLOSE, handle_all_blinds_close)
        hass.services.async_register(DOMAIN, SERVICE_ALL_BLINDS_OPEN, handle_all_blinds_open)
        hass.services.async_register(DOMAIN, SERVICE_ALL_CLIMATE_COMFORT, handle_all_climate_comfort)
        hass.services.async_register(DOMAIN, SERVICE_ALL_CLIMATE_ECO, handle_all_climate_eco)
        hass.services.async_register(DOMAIN, SERVICE_ALL_CLIMATE_AWAY, handle_all_climate_away)
        hass.services.async_register(DOMAIN, SERVICE_START_RECORDING, handle_start_recording)
        hass.services.async_register(DOMAIN, SERVICE_STOP_RECORDING, handle_stop_recording)

    # Register frontend card and recordings static paths (once per HA instance)
    frontend_key = f"{DOMAIN}_frontend_registered"
    if frontend_key not in hass.data:
        from homeassistant.components.http import StaticPathConfig

        recordings_dir = hass.config.path("media/evon_recordings")
        await hass.async_add_executor_job(_ensure_recordings_dir, recordings_dir)

        await hass.http.async_register_static_paths(
            [
                StaticPathConfig(
                    "/evon/evon-camera-recording-card.js",
                    hass.config.path("custom_components/evon/www/evon-camera-recording-card.js"),
                    cache_headers=False,
                ),
                StaticPathConfig(
                    "/evon/recordings",
                    recordings_dir,
                    cache_headers=False,
                ),
            ]
        )
        hass.data[frontend_key] = True

    # Clean up stale entities only on initial setup with successful data
    if coordinator.last_update_success and coordinator.data is not None:
        await _async_cleanup_stale_entities(hass, entry, coordinator)

    # Register update listener for options changes
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


def _extract_instance_id_from_unique_id(unique_id: str, entry_id: str) -> str | None:
    """Extract the Evon instance ID from an entity's unique_id.

    Our entities use formats like:
    - evon_light_{instance_id}
    - evon_cover_{instance_id}
    - evon_climate_{instance_id}
    - evon_switch_{instance_id}
    - evon_radiator_{instance_id}
    - evon_valve_{instance_id}
    - evon_security_door_{instance_id}[_call]
    - evon_intercom_{instance_id}[_connection]
    - evon_scene_{instance_id}
    - evon_identify_{instance_id}
    - evon_camera_{instance_id}
    - evon_snapshot_{door_id}_{index}
    - evon_temp_{instance_id}
    - evon_meter_{key}_{instance_id}
    - evon_{key}_{instance_id} (air quality)
    - evon_home_state_{entry_id} (special)
    - evon_season_mode_{entry_id} (special)
    - evon_websocket_{entry_id} (special)

    Returns the instance_id or None if it can't be extracted.
    """
    if not unique_id or not unique_id.startswith("evon_"):
        return None

    # Special entities that use entry_id instead of instance_id - skip these
    special_prefixes = (f"evon_home_state_{entry_id}", f"evon_season_mode_{entry_id}", f"evon_websocket_{entry_id}")
    if unique_id in special_prefixes or unique_id.startswith(special_prefixes):
        return None

    # Known type prefixes - order matters (longer prefixes first to avoid partial matches)
    type_prefixes = [
        "evon_security_door_",
        "evon_camera_recording_",
        "evon_intercom_",
        "evon_snapshot_",
        "evon_radiator_",
        "evon_identify_",
        "evon_climate_",
        "evon_camera_",
        "evon_switch_",
        "evon_cover_",
        "evon_light_",
        "evon_scene_",
        "evon_valve_",
        "evon_meter_",
        "evon_temp_",
    ]

    for prefix in type_prefixes:
        if unique_id.startswith(prefix):
            remainder = unique_id[len(prefix) :]
            # Handle suffixes like _call, _connection, _power, _energy, etc.
            # Instance IDs can contain dots (e.g., SC1_M01.Light1)
            # Strip known suffixes
            for suffix in (
                "_call",
                "_connection",
                "_power",
                "_energy",
                "_co2",
                "_humidity",
                "_temperature",
                "_pm25",
                "_pm10",
                "_voc",
            ):
                if remainder.endswith(suffix):
                    remainder = remainder[: -len(suffix)]
                    break
            # For meter sensors, the format is evon_meter_{key}_{instance_id}
            # Known meter sensor keys from SMART_METER_SENSORS (ordered longest first)
            if prefix == "evon_meter_":
                meter_keys = [
                    "feed_in_month_",
                    "feed_in_today_",
                    "feed_in_energy_",
                    "energy_month_",
                    "energy_today_",
                    "energy_24h_",
                    "voltage_l1_",
                    "voltage_l2_",
                    "voltage_l3_",
                    "current_l1_",
                    "current_l2_",
                    "current_l3_",
                    "frequency_",
                    "energy_",
                    "power_",
                ]
                for key in meter_keys:
                    if remainder.startswith(key):
                        return remainder[len(key) :]
                # Fallback: try to find a part with a dot (old format)
                parts = remainder.split("_")
                for i, part in enumerate(parts):
                    if "." in part:
                        return "_".join(parts[i:])
                # Can't reliably extract - return None to skip this entity
                _LOGGER.debug("Cannot extract instance_id from meter unique_id: %s", unique_id)
                return None
            # For snapshot, format is evon_snapshot_{door_id}_{index}
            if prefix == "evon_snapshot_":
                # Remove the trailing index (last underscore-separated number)
                parts = remainder.rsplit("_", 1)
                if len(parts) == 2 and parts[1].isdigit():
                    return parts[0]
                return remainder
            return remainder

    # Fallback for air quality sensors: evon_{key}_{instance_id}
    # These don't have a specific type prefix
    parts = unique_id.split("_")
    if len(parts) >= 3:
        # Try to find the instance_id (contains a dot)
        for i, part in enumerate(parts[1:], 1):
            if "." in part:
                return "_".join(parts[i:])

    return None


async def _async_cleanup_stale_entities(
    hass: HomeAssistant,
    entry: ConfigEntry,
    coordinator: EvonDataUpdateCoordinator,
) -> None:
    """Remove entities that no longer exist in Evon."""
    if not coordinator.data:
        return

    # Collect all current device IDs from coordinator data
    current_device_ids: set[str] = set()
    for entity_type in [
        ENTITY_TYPE_LIGHTS,
        ENTITY_TYPE_BLINDS,
        ENTITY_TYPE_CLIMATES,
        ENTITY_TYPE_SWITCHES,
        ENTITY_TYPE_SMART_METERS,
        ENTITY_TYPE_AIR_QUALITY,
        ENTITY_TYPE_VALVES,
        ENTITY_TYPE_BATHROOM_RADIATORS,
        ENTITY_TYPE_SCENES,
        ENTITY_TYPE_SECURITY_DOORS,
        ENTITY_TYPE_INTERCOMS,
        ENTITY_TYPE_CAMERAS,
    ]:
        if entity_type in coordinator.data:
            for device in coordinator.data[entity_type]:
                current_device_ids.add(device["id"])

    # Get entity registry
    entity_registry = er.async_get(hass)

    # Find entities belonging to this config entry
    entities_to_remove: list[str] = []
    for entity_entry in er.async_entries_for_config_entry(entity_registry, entry.entry_id):
        unique_id = entity_entry.unique_id
        if not unique_id:
            continue

        # Extract the instance_id from the unique_id
        instance_id = _extract_instance_id_from_unique_id(unique_id, entry.entry_id)
        if instance_id is None:
            # Special entity or unrecognized format - skip
            continue

        # Check if this device still exists
        if instance_id not in current_device_ids:
            entities_to_remove.append(entity_entry.entity_id)
            _LOGGER.debug("Marking stale entity for removal: %s (instance_id: %s)", entity_entry.entity_id, instance_id)

    # Remove stale entities
    for entity_id in entities_to_remove:
        _LOGGER.info("Removing stale entity: %s", entity_id)
        entity_registry.async_remove(entity_id)

    if entities_to_remove:
        _LOGGER.info("Cleaned up %d stale entities from Evon integration", len(entities_to_remove))
        # Create informational repair to notify user
        ir.async_create_issue(
            hass,
            DOMAIN,
            f"{REPAIR_STALE_ENTITIES_CLEANED}_{entry.entry_id}",
            is_fixable=True,
            is_persistent=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="stale_entities_cleaned",
            translation_placeholders={
                "count": str(len(entities_to_remove)),
                "entities": ", ".join(entities_to_remove[:5]) + ("..." if len(entities_to_remove) > 5 else ""),
            },
        )


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update.

    Debug logging is applied instantly. All other changes (scan interval,
    sync areas, WebSocket mode, non-dimmable lights) are applied via
    a full reload to ensure consistent state.
    """
    # Apply debug logging immediately (takes effect without reload)
    _apply_debug_logging(entry)

    # Reload integration to apply all other option changes
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # Shut down WebSocket client and API first
    if entry.entry_id in hass.data.get(DOMAIN, {}):
        entry_data = hass.data[DOMAIN][entry.entry_id]

        # Mark entry as unloading so services won't access partially-unloaded data
        entry_data["unloading"] = True

        coordinator: EvonDataUpdateCoordinator = entry_data.get("coordinator")
        if coordinator:
            await coordinator.async_shutdown_websocket()
        api: EvonApi = entry_data.get("api")
        if api:
            await api.close()

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

        # Unregister services when the last config entry is unloaded
        if not hass.data[DOMAIN]:
            for service_name in (
                SERVICE_REFRESH,
                SERVICE_RECONNECT_WEBSOCKET,
                SERVICE_SET_HOME_STATE,
                SERVICE_SET_SEASON_MODE,
                SERVICE_ALL_LIGHTS_OFF,
                SERVICE_ALL_BLINDS_CLOSE,
                SERVICE_ALL_BLINDS_OPEN,
                SERVICE_ALL_CLIMATE_COMFORT,
                SERVICE_ALL_CLIMATE_ECO,
                SERVICE_ALL_CLIMATE_AWAY,
                SERVICE_START_RECORDING,
                SERVICE_STOP_RECORDING,
            ):
                hass.services.async_remove(DOMAIN, service_name)
            _LOGGER.debug("Unregistered all Evon services (last entry removed)")

    return unload_ok


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle removal of a config entry.

    This is called when the user removes the integration completely.
    Clean up any remaining devices and entities.
    """
    # Clean up devices associated with this config entry
    device_registry = dr.async_get(hass)
    devices_to_remove = [device.id for device in dr.async_entries_for_config_entry(device_registry, entry.entry_id)]
    for device_id in devices_to_remove:
        device_registry.async_remove_device(device_id)
        _LOGGER.debug("Removed device %s for config entry %s", device_id, entry.entry_id)

    # Clean up any repair issues for this entry
    ir.async_delete_issue(hass, DOMAIN, f"{REPAIR_STALE_ENTITIES_CLEANED}_{entry.entry_id}")

    _LOGGER.info("Cleaned up %d devices for removed config entry", len(devices_to_remove))


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old config entry to new version."""
    _LOGGER.debug("Migrating Evon config entry from version %s", config_entry.version)

    while config_entry.version < 3:
        if config_entry.version == 1:
            # Migration from v1 to v2
            # v2 adds non_dimmable_lights option (defaults to empty list, no action needed)
            _LOGGER.info("Migrating Evon config entry from version 1 to 2")
            hass.config_entries.async_update_entry(config_entry, version=2, minor_version=0)
            _LOGGER.info("Migration to version 2 successful")
        elif config_entry.version == 2:
            # Migration from v2 to v3
            # v3 adds connection_type (defaults to local for existing configs)
            _LOGGER.info("Migrating Evon config entry from version 2 to 3")
            new_data = dict(config_entry.data)
            new_data[CONF_CONNECTION_TYPE] = CONNECTION_TYPE_LOCAL
            hass.config_entries.async_update_entry(config_entry, data=new_data, version=3, minor_version=0)
            _LOGGER.info("Migration to version 3 successful")
        else:
            break

    if config_entry.version > 3:
        # Future version - can't migrate forward
        _LOGGER.error(
            "Cannot migrate Evon config entry from version %s (current integration supports up to version 3)",
            config_entry.version,
        )
        ir.async_create_issue(
            hass,
            DOMAIN,
            REPAIR_CONFIG_MIGRATION,
            is_fixable=False,
            is_persistent=True,
            severity=ir.IssueSeverity.ERROR,
            translation_key="config_migration_failed",
            translation_placeholders={
                "current_version": str(config_entry.version),
                "supported_version": "3",
            },
        )
        return False

    return True
