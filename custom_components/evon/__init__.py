"""The Evon Smart Home integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er, issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import EvonApi
from .const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_SYNC_AREAS,
    CONF_USERNAME,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SYNC_AREAS,
    DOMAIN,
    REPAIR_CONFIG_MIGRATION,
    REPAIR_STALE_ENTITIES_CLEANED,
)
from .coordinator import EvonDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
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

    # Create API client
    session = async_get_clientsession(hass)
    api = EvonApi(
        host=entry.data[CONF_HOST],
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
        session=session,
    )

    # Test connection
    if not await api.test_connection():
        _LOGGER.error("Failed to connect to Evon Smart Home")
        return False

    # Get options
    scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    sync_areas = entry.options.get(CONF_SYNC_AREAS, DEFAULT_SYNC_AREAS)

    # Create coordinator
    coordinator = EvonDataUpdateCoordinator(hass, api, scan_interval, sync_areas)

    # Fetch initial data
    await coordinator.async_config_entry_first_refresh()

    # Store coordinator
    hass.data[DOMAIN][entry.entry_id] = {
        "api": api,
        "coordinator": coordinator,
    }

    # Create hub device that child devices reference via via_device
    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        name="Evon Smart Home",
        manufacturer="Evon",
        model="Smart Home Controller",
        configuration_url=entry.data[CONF_HOST],
    )

    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

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
    ]:
        if entity_type in coordinator.data:
            for device in coordinator.data[entity_type]:
                current_device_ids.add(device["id"])

    # Home states use a different entity (select), add those IDs too
    if "home_states" in coordinator.data and coordinator.data["home_states"]:
        # The home state select entity uses a fixed ID pattern
        current_device_ids.add("home_state_selector")

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

    # Reload integration to apply area changes to devices
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
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

    if config_entry.version > 2:
        # Future version - can't migrate forward
        _LOGGER.error(
            "Cannot migrate Evon config entry from version %s (current integration supports up to version 2)",
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
                "supported_version": "2",
            },
        )
        return False

    return True
