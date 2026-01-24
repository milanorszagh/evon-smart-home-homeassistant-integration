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
from .const import DOMAIN, SEASON_MODE_COOLING, SEASON_MODE_HEATING
from .coordinator import EvonDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

# Season mode options
SEASON_MODE_OPTIONS = [SEASON_MODE_HEATING, SEASON_MODE_COOLING]

# Preferred order for home states (Evon IDs)
HOME_STATE_ORDER = [
    "HomeStateAtHome",
    "HomeStateNight",
    "HomeStateWork",
    "HomeStateHoliday",
]


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

    # Add season mode select (global heating/cooling switch)
    entities.append(EvonSeasonModeSelect(coordinator, entry, api))

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
        # Use Evon IDs as options - HA translation system handles display names
        self._update_options()
        # Optimistic state to prevent UI flicker during updates
        self._optimistic_option: str | None = None

    def _update_options(self) -> None:
        """Update options from coordinator data."""
        home_states = self.coordinator.get_home_states()
        # Use Evon IDs directly as options - translations handle display
        options = [state["id"] for state in home_states]
        # Sort by preferred order, unknown states go to the end
        self._attr_options = sorted(
            options,
            key=lambda x: HOME_STATE_ORDER.index(x) if x in HOME_STATE_ORDER else len(HOME_STATE_ORDER)
        )

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
        """Return the current selected option (Evon ID)."""
        # Return optimistic value if set (prevents UI flicker during updates)
        if self._optimistic_option is not None:
            return self._optimistic_option

        active_id = self.coordinator.get_active_home_state()
        if active_id and active_id in self._attr_options:
            return active_id
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        active_id = self.coordinator.get_active_home_state()
        return {"evon_id": active_id}

    async def async_select_option(self, option: str) -> None:
        """Change the selected option (option is the Evon ID)."""
        if option in self._attr_options:
            # Set optimistic value immediately to prevent UI flicker
            self._optimistic_option = option
            self.async_write_ha_state()

            await self._api.activate_home_state(option)
            await self.coordinator.async_request_refresh()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_options()

        # Only clear optimistic state when coordinator data matches expected value
        if self._optimistic_option is not None:
            active_id = self.coordinator.get_active_home_state()
            if active_id == self._optimistic_option:
                self._optimistic_option = None

        self.async_write_ha_state()


class EvonSeasonModeSelect(CoordinatorEntity[EvonDataUpdateCoordinator], SelectEntity):
    """Representation of Evon Season Mode selector (global heating/cooling).

    This controls whether the entire house is in heating (winter) or cooling (summer) mode.
    This is separate from per-room presets (comfort/eco/away).
    """

    _attr_has_entity_name = True
    _attr_translation_key = "season_mode"
    _attr_icon = "mdi:sun-snowflake-variant"

    def __init__(
        self,
        coordinator: EvonDataUpdateCoordinator,
        entry: ConfigEntry,
        api: EvonApi,
    ) -> None:
        """Initialize the season mode select."""
        super().__init__(coordinator)
        self._api = api
        self._entry = entry
        self._attr_unique_id = f"evon_season_mode_{entry.entry_id}"
        self._attr_name = "Season Mode"
        self._attr_options = SEASON_MODE_OPTIONS
        # Optimistic state to prevent UI flicker during updates
        self._optimistic_option: str | None = None

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for season mode."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._entry.entry_id}_season_mode")},
            name="Evon Season Mode",
            manufacturer="Evon",
            model="Season Mode",
            via_device=(DOMAIN, self._entry.entry_id),
        )

    @property
    def current_option(self) -> str | None:
        """Return the current selected option."""
        # Return optimistic value if set (prevents UI flicker during updates)
        if self._optimistic_option is not None:
            return self._optimistic_option

        is_cooling = self.coordinator.get_season_mode()
        return SEASON_MODE_COOLING if is_cooling else SEASON_MODE_HEATING

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        is_cooling = self.coordinator.get_season_mode()
        return {
            "is_cooling": is_cooling,
            "description": "Summer mode (cooling)" if is_cooling else "Winter mode (heating)",
        }

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        if option in SEASON_MODE_OPTIONS:
            # Set optimistic value immediately to prevent UI flicker
            self._optimistic_option = option
            self.async_write_ha_state()

            is_cooling = option == SEASON_MODE_COOLING
            await self._api.set_season_mode(is_cooling)
            await self.coordinator.async_request_refresh()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        # Only clear optimistic state when coordinator data matches expected value
        if self._optimistic_option is not None:
            is_cooling = self.coordinator.get_season_mode()
            actual_option = SEASON_MODE_COOLING if is_cooling else SEASON_MODE_HEATING
            if actual_option == self._optimistic_option:
                self._optimistic_option = None

        self.async_write_ha_state()
