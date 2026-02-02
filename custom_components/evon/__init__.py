"""The Evon Smart Home integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import device_registry as dr, entity_registry as er, issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import EvonApi
from .const import (
    CONF_CONNECTION_TYPE,
    CONF_ENGINE_ID,
    CONF_HOST,
    CONF_HTTP_ONLY,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_SYNC_AREAS,
    CONF_USERNAME,
    CONNECTION_TYPE_LOCAL,
    CONNECTION_TYPE_REMOTE,
    DEFAULT_HTTP_ONLY,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SYNC_AREAS,
    DOMAIN,
    EVON_REMOTE_HOST,
    REPAIR_CONFIG_MIGRATION,
    REPAIR_STALE_ENTITIES_CLEANED,
)
from .coordinator import EvonDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

SERVICE_REFRESH = "refresh"
SERVICE_RECONNECT_WEBSOCKET = "reconnect_websocket"
SERVICE_SET_HOME_STATE = "set_home_state"
SERVICE_SET_SEASON_MODE = "set_season_mode"
SERVICE_ALL_LIGHTS_OFF = "all_lights_off"
SERVICE_ALL_BLINDS_CLOSE = "all_blinds_close"
SERVICE_ALL_BLINDS_OPEN = "all_blinds_open"

# Home state mapping from service values to Evon instance IDs
HOME_STATE_MAP = {
    "at_home": "HomeStateAtHome",
    "night": "HomeStateNight",
    "work": "HomeStateWork",
    "holiday": "HomeStateHoliday",
}

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
        _LOGGER.error("Failed to connect to Evon Smart Home")
        return False

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
        "session": session,
        "host": entry.data.get(CONF_HOST) if connection_type == CONNECTION_TYPE_LOCAL else None,
        "username": entry.data[CONF_USERNAME],
        "password": entry.data[CONF_PASSWORD],
    }

    # Set up WebSocket for real-time updates (both local and remote connections)
    if use_websocket:
        if connection_type == CONNECTION_TYPE_LOCAL:
            await coordinator.async_setup_websocket(
                session=session,
                host=entry.data[CONF_HOST],
                username=entry.data[CONF_USERNAME],
                password=entry.data[CONF_PASSWORD],
            )
        else:
            # Remote connection via my.evon-smarthome.com
            await coordinator.async_setup_websocket(
                session=session,
                host=None,
                username=entry.data[CONF_USERNAME],
                password=entry.data[CONF_PASSWORD],
                is_remote=True,
                engine_id=entry.data[CONF_ENGINE_ID],
            )

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
            for entry_data in hass.data[DOMAIN].values():
                if "coordinator" in entry_data:
                    await entry_data["coordinator"].async_refresh()

        async def handle_reconnect_websocket(call: ServiceCall) -> None:
            """Handle the reconnect websocket service call."""
            _LOGGER.info("Reconnect WebSocket service called")
            for entry_id, entry_data in hass.data[DOMAIN].items():
                if "coordinator" in entry_data:
                    coordinator = entry_data["coordinator"]
                    # Get the config entry to access connection details
                    config_entry = hass.config_entries.async_get_entry(entry_id)
                    if config_entry and coordinator.use_websocket:
                        await coordinator.async_shutdown_websocket()
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

        async def handle_set_home_state(call: ServiceCall) -> None:
            """Handle the set home state service call."""
            state = call.data.get("state")
            if not state or state not in HOME_STATE_MAP:
                _LOGGER.error("Invalid home state: %s", state)
                return
            evon_state = HOME_STATE_MAP[state]
            _LOGGER.info("Set home state service called: %s -> %s", state, evon_state)
            for entry_data in hass.data[DOMAIN].values():
                if "api" in entry_data:
                    await entry_data["api"].activate_home_state(evon_state)
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
            for entry_data in hass.data[DOMAIN].values():
                if "api" in entry_data:
                    await entry_data["api"].set_season_mode(is_cooling)
                if "coordinator" in entry_data:
                    await entry_data["coordinator"].async_refresh()

        async def handle_all_lights_off(call: ServiceCall) -> None:
            """Handle the all lights off service call."""
            _LOGGER.info("All lights off service called")
            for entry_data in hass.data[DOMAIN].values():
                if "coordinator" in entry_data and "api" in entry_data:
                    coordinator = entry_data["coordinator"]
                    api = entry_data["api"]
                    if coordinator.data and "lights" in coordinator.data:
                        for light in coordinator.data["lights"]:
                            if light.get("is_on"):
                                await api.turn_off_light(light["id"])
                    await coordinator.async_refresh()

        async def handle_all_blinds_close(call: ServiceCall) -> None:
            """Handle the all blinds close service call."""
            _LOGGER.info("All blinds close service called")
            for entry_data in hass.data[DOMAIN].values():
                if "coordinator" in entry_data and "api" in entry_data:
                    coordinator = entry_data["coordinator"]
                    api = entry_data["api"]
                    if coordinator.data and "blinds" in coordinator.data:
                        for blind in coordinator.data["blinds"]:
                            await api.close_blind(blind["id"])
                    await coordinator.async_refresh()

        async def handle_all_blinds_open(call: ServiceCall) -> None:
            """Handle the all blinds open service call."""
            _LOGGER.info("All blinds open service called")
            for entry_data in hass.data[DOMAIN].values():
                if "coordinator" in entry_data and "api" in entry_data:
                    coordinator = entry_data["coordinator"]
                    api = entry_data["api"]
                    if coordinator.data and "blinds" in coordinator.data:
                        for blind in coordinator.data["blinds"]:
                            await api.open_blind(blind["id"])
                    await coordinator.async_refresh()

        hass.services.async_register(DOMAIN, SERVICE_REFRESH, handle_refresh)
        hass.services.async_register(DOMAIN, SERVICE_RECONNECT_WEBSOCKET, handle_reconnect_websocket)
        hass.services.async_register(DOMAIN, SERVICE_SET_HOME_STATE, handle_set_home_state)
        hass.services.async_register(DOMAIN, SERVICE_SET_SEASON_MODE, handle_set_season_mode)
        hass.services.async_register(DOMAIN, SERVICE_ALL_LIGHTS_OFF, handle_all_lights_off)
        hass.services.async_register(DOMAIN, SERVICE_ALL_BLINDS_CLOSE, handle_all_blinds_close)
        hass.services.async_register(DOMAIN, SERVICE_ALL_BLINDS_OPEN, handle_all_blinds_open)

    # Clean up stale entities
    await _async_cleanup_stale_entities(hass, entry, coordinator)

    # Register update listener for options changes
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


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
        "lights",
        "blinds",
        "climates",
        "switches",
        "smart_meters",
        "air_quality",
        "valves",
        "bathroom_radiators",
        "scenes",
        "security_doors",
        "intercoms",
        "cameras",
    ]:
        if entity_type in coordinator.data:
            for device in coordinator.data[entity_type]:
                current_device_ids.add(device["id"])

    # Home states use a different entity (select), add those IDs too
    if "home_states" in coordinator.data and coordinator.data["home_states"]:
        # The home state select entity uses a fixed ID pattern
        current_device_ids.add("home_state_selector")

    # Season mode uses a fixed ID pattern
    if "season_mode" in coordinator.data:
        current_device_ids.add("season_mode")

    # Get entity registry
    entity_registry = er.async_get(hass)

    # Find entities belonging to this config entry
    entities_to_remove: list[str] = []
    for entity_entry in er.async_entries_for_config_entry(entity_registry, entry.entry_id):
        # Extract device ID from the entity's unique_id
        # Our entities use unique_id format: "{entry_id}_{instance_id}" or "{entry_id}_{instance_id}_{suffix}"
        unique_id = entity_entry.unique_id
        if not unique_id:
            continue

        # Remove entry_id prefix to get the device identifier
        prefix = f"{entry.entry_id}_"
        if not unique_id.startswith(prefix):
            continue

        device_part = unique_id[len(prefix) :]

        # Check if this device still exists
        # Handle suffixes like "_power", "_energy", "_co2", etc.
        device_exists = False
        for current_id in current_device_ids:
            if device_part == current_id or device_part.startswith(f"{current_id}_"):
                device_exists = True
                break

        if not device_exists:
            entities_to_remove.append(entity_entry.entity_id)
            _LOGGER.debug("Marking stale entity for removal: %s (unique_id: %s)", entity_entry.entity_id, unique_id)

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
    """Handle options update."""
    coordinator: EvonDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    # Update scan interval
    scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    coordinator.set_update_interval(scan_interval)
    _LOGGER.debug("Updated scan interval to %s seconds", scan_interval)

    # Update sync areas setting
    sync_areas = entry.options.get(CONF_SYNC_AREAS, DEFAULT_SYNC_AREAS)
    coordinator.set_sync_areas(sync_areas)
    _LOGGER.debug("Updated sync areas to %s", sync_areas)

    # Update WebSocket setting
    http_only = entry.options.get(CONF_HTTP_ONLY, DEFAULT_HTTP_ONLY)
    coordinator.set_use_websocket(not http_only)
    _LOGGER.debug("Updated http_only to %s (use_websocket=%s)", http_only, not http_only)

    # Reload integration to apply changes
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # Shut down WebSocket client first
    if entry.entry_id in hass.data.get(DOMAIN, {}):
        coordinator: EvonDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id].get("coordinator")
        if coordinator:
            await coordinator.async_shutdown_websocket()

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old config entry to new version."""
    _LOGGER.debug("Migrating Evon config entry from version %s", config_entry.version)

    if config_entry.version == 1:
        # Migration from v1 to v2
        # v2 adds non_dimmable_lights option (defaults to empty list, no action needed)
        _LOGGER.info("Migrating Evon config entry from version 1 to 2")
        hass.config_entries.async_update_entry(config_entry, version=2, minor_version=0)
        _LOGGER.info("Migration to version 2 successful")

    if config_entry.version == 2:
        # Migration from v2 to v3
        # v3 adds connection_type (defaults to local for existing configs)
        _LOGGER.info("Migrating Evon config entry from version 2 to 3")
        new_data = dict(config_entry.data)
        new_data[CONF_CONNECTION_TYPE] = CONNECTION_TYPE_LOCAL
        hass.config_entries.async_update_entry(config_entry, data=new_data, version=3, minor_version=0)
        _LOGGER.info("Migration to version 3 successful")

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
