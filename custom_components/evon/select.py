"""Select platform for Evon Smart Home integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import EvonApi
from .const import DOMAIN
from .coordinator import EvonDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Evon select entities from a config entry."""
    coordinator: EvonDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    api: EvonApi = hass.data[DOMAIN][entry.entry_id]["api"]

    entities = []

    # Add home state select if there are home states
    home_states = coordinator.get_home_states()
    if home_states:
        entities.append(EvonHomeStateSelect(coordinator, entry, api))

    async_add_entities(entities)


class EvonHomeStateSelect(CoordinatorEntity[EvonDataUpdateCoordinator], SelectEntity):
    """Representation of Evon Home State selector."""

    _attr_has_entity_name = True
    _attr_translation_key = "home_state"

    def __init__(
        self,
        coordinator: EvonDataUpdateCoordinator,
        entry: ConfigEntry,
        api: EvonApi,
    ) -> None:
        """Initialize the home state select."""
        super().__init__(coordinator)
        self._api = api
        self._entry = entry
        self._attr_unique_id = f"evon_home_state_{entry.entry_id}"
        self._attr_name = "Home State"
        # Build options mapping (id -> name)
        self._options_map: dict[str, str] = {}
        self._reverse_map: dict[str, str] = {}
        self._update_options()

    def _update_options(self) -> None:
        """Update options from coordinator data."""
        home_states = self.coordinator.get_home_states()
        self._options_map = {state["id"]: state["name"] for state in home_states}
        self._reverse_map = {state["name"]: state["id"] for state in home_states}
        self._attr_options = list(self._options_map.values())

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for home state."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._entry.entry_id}_home_state")},
            name="Evon Home State",
            manufacturer="Evon",
            model="Home State",
            via_device=(DOMAIN, self._entry.entry_id),
        )

    @property
    def current_option(self) -> str | None:
        """Return the current selected option."""
        active_id = self.coordinator.get_active_home_state()
        if active_id and active_id in self._options_map:
            return self._options_map[active_id]
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        active_id = self.coordinator.get_active_home_state()
        return {"evon_id": active_id}

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        if option in self._reverse_map:
            instance_id = self._reverse_map[option]
            await self._api.activate_home_state(instance_id)
            await self.coordinator.async_request_refresh()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_options()
        self.async_write_ha_state()
