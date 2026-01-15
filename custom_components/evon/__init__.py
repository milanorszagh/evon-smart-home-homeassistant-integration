"""The Evon Smart Home integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
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

    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register update listener for options changes
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


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
