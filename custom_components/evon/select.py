"""Select platform for Evon Smart Home integration."""

from __future__ import annotations

import logging
import re
from typing import Any

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import EvonApi, EvonApiError
from .base_entity import EvonEntity
from .const import DOMAIN, HOME_STATE_MAP, SEASON_MODE_COOLING, SEASON_MODE_HEATING
from .coordinator import EvonDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

# Season mode options
SEASON_MODE_OPTIONS = [SEASON_MODE_HEATING, SEASON_MODE_COOLING]

# Preferred order for home states (select option keys)
HOME_STATE_ORDER = ["at_home", "night", "work", "holiday"]

# Evon instance ID -> select option key (the service-level names from HOME_STATE_MAP).
# HA translation keys must match [a-z0-9-_]+, so the select cannot expose the raw
# Evon IDs ("HomeStateAtHome") as options.
_HOME_STATE_ID_TO_OPTION = {evon_id: option for option, evon_id in HOME_STATE_MAP.items()}
_HOME_STATE_ID_PREFIX = "HomeState"


def home_state_option_for_id(state_id: str) -> str:
    """Map an Evon home-state instance ID to the select option key.

    Known IDs use the names from HOME_STATE_MAP; anything else is derived from
    the ID ("HomeStateMyParty" -> "my_party") so custom states still get a
    valid option value.
    """
    if state_id in _HOME_STATE_ID_TO_OPTION:
        return _HOME_STATE_ID_TO_OPTION[state_id]
    name = state_id.removeprefix(_HOME_STATE_ID_PREFIX) or state_id
    snake = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", name).lower()
    return re.sub(r"[^a-z0-9_-]+", "_", snake).strip("_-") or state_id.lower()


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


class EvonHomeStateSelect(EvonEntity, SelectEntity):
    """Representation of Evon Home State selector."""

    _attr_icon = "mdi:home-account"
    _attr_translation_key = "home_state"

    def __init__(
        self,
        coordinator: EvonDataUpdateCoordinator,
        entry: ConfigEntry,
        api: EvonApi,
    ) -> None:
        """Initialize the home state select."""
        super().__init__(
            coordinator,
            instance_id=f"home_state_{entry.entry_id}",
            name="Evon Home State",
            room_name="",
            entry=entry,
            api=api,
        )
        self._attr_unique_id = f"evon_home_state_{entry.entry_id}"
        # Option key -> Evon instance ID and the reverse; HA translations handle display names
        self._option_to_id: dict[str, str] = {}
        self._id_to_option: dict[str, str] = {}
        self._update_options()
        # Optimistic state to prevent UI flicker during updates
        self._optimistic_option: str | None = None

    def _reset_optimistic_state(self) -> None:
        """Clear optimistic option."""
        self._optimistic_option = None

    def _recheck_snapshot(self) -> str | None:
        """Snapshot the active home state for cancel-on-change detection.

        Overrides the default `_get_data()` snapshot because this entity reads
        state from `coordinator.get_active_home_state()`, not from the
        per-entity data dict.
        """
        return self.coordinator.get_active_home_state()

    def _recheck_data_changed(self, current: str | None, snapshot: str | None) -> bool:
        """Compare snapshots by value — `get_active_home_state` returns a string."""
        return current != snapshot

    def _update_options(self) -> None:
        """Update options from coordinator data."""
        home_states = self.coordinator.get_home_states()
        option_to_id: dict[str, str] = {}
        for state in home_states:
            state_id = state.get("id")
            if state_id:
                option_to_id[home_state_option_for_id(state_id)] = state_id
        self._option_to_id = option_to_id
        self._id_to_option = {evon_id: option for option, evon_id in option_to_id.items()}
        # Sort by preferred order, unknown states go to the end
        self._attr_options = sorted(
            option_to_id, key=lambda x: HOME_STATE_ORDER.index(x) if x in HOME_STATE_ORDER else len(HOME_STATE_ORDER)
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
        """Return the current selected option key (e.g. "at_home")."""
        # Clear expired optimistic state to prevent stale UI on network recovery
        self._clear_optimistic_state_if_expired()

        # Return optimistic value if set (prevents UI flicker during updates)
        if self._optimistic_option is not None:
            return self._optimistic_option

        active_id = self.coordinator.get_active_home_state()
        if not active_id:
            return None
        return self._id_to_option.get(active_id)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        attrs = super().extra_state_attributes
        active_id = self.coordinator.get_active_home_state()
        attrs["evon_id"] = active_id
        return attrs

    async def async_select_option(self, option: str) -> None:
        """Change the selected option (option key such as "night")."""
        # Capture WS-liveness BEFORE the command await: a confirmation can
        # land mid-flight, and the snapshot comparison in
        # _schedule_post_command_recheck must not mistake it for silence.
        recheck_snapshot = self._recheck_snapshot()
        if option not in self._option_to_id and option in self._id_to_option:
            # Before v1.23.0 the options were the raw Evon IDs ("HomeStateNight").
            # Keep accepting them so existing automations don't break outright.
            legacy_option, option = option, self._id_to_option[option]
            _LOGGER.warning(
                "Option %r for %s is deprecated; use %r instead and update your automations/dashboards",
                legacy_option,
                self.entity_id,
                option,
            )
        if option in self._option_to_id:
            # Set optimistic value immediately to prevent UI flicker
            self._optimistic_option = option
            self._set_optimistic_timestamp()
            self.async_write_ha_state()

            try:
                await self._api.activate_home_state(self._option_to_id[option])
            except EvonApiError:
                self._optimistic_option = None
                self._optimistic_state_set_at = None
                self.async_write_ha_state()
                raise
            self._schedule_post_command_recheck(recheck_snapshot)
        else:
            _LOGGER.warning("Ignoring invalid option %r for %s", option, self.entity_id)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._cancel_post_command_recheck_if_data_changed()
        self._update_options()

        # Only clear optimistic state when coordinator data matches expected value
        if self._optimistic_option is not None:
            active_id = self.coordinator.get_active_home_state()
            if self._id_to_option.get(active_id) == self._optimistic_option:
                self._optimistic_option = None
                self._optimistic_state_set_at = None

        super()._handle_coordinator_update()

    async def async_will_remove_from_hass(self) -> None:
        """Cancel any pending recheck when entity is removed."""
        self._cleanup_post_command_recheck()
        await super().async_will_remove_from_hass()


class EvonSeasonModeSelect(EvonEntity, SelectEntity):
    """Representation of Evon Season Mode selector (global heating/cooling).

    This controls whether the entire house is in heating (winter) or cooling (summer) mode.
    This is separate from per-room presets (comfort/eco/away).
    """

    _attr_translation_key = "season_mode"
    _attr_icon = "mdi:sun-snowflake-variant"

    def __init__(
        self,
        coordinator: EvonDataUpdateCoordinator,
        entry: ConfigEntry,
        api: EvonApi,
    ) -> None:
        """Initialize the season mode select."""
        super().__init__(
            coordinator,
            instance_id=f"season_mode_{entry.entry_id}",
            name="Evon Season Mode",
            room_name="",
            entry=entry,
            api=api,
        )
        self._attr_unique_id = f"evon_season_mode_{entry.entry_id}"
        self._attr_options = SEASON_MODE_OPTIONS
        # Optimistic state to prevent UI flicker during updates
        self._optimistic_option: str | None = None

    def _reset_optimistic_state(self) -> None:
        """Clear optimistic option."""
        self._optimistic_option = None

    def _recheck_snapshot(self) -> str:
        """Snapshot the season mode for cancel-on-change detection."""
        is_cooling = self.coordinator.get_season_mode()
        return SEASON_MODE_COOLING if is_cooling else SEASON_MODE_HEATING

    def _recheck_data_changed(self, current: str, snapshot: str) -> bool:
        """Compare snapshots by value — season mode is a string."""
        return current != snapshot

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
        # Clear expired optimistic state to prevent stale UI on network recovery
        self._clear_optimistic_state_if_expired()

        # Return optimistic value if set (prevents UI flicker during updates)
        if self._optimistic_option is not None:
            return self._optimistic_option

        is_cooling = self.coordinator.get_season_mode()
        return SEASON_MODE_COOLING if is_cooling else SEASON_MODE_HEATING

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        attrs = super().extra_state_attributes
        is_cooling = self.coordinator.get_season_mode()
        attrs["is_cooling"] = is_cooling
        attrs["description"] = "Summer mode (cooling)" if is_cooling else "Winter mode (heating)"
        return attrs

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        # Capture WS-liveness BEFORE the command await: a confirmation can
        # land mid-flight, and the snapshot comparison in
        # _schedule_post_command_recheck must not mistake it for silence.
        recheck_snapshot = self._recheck_snapshot()
        if option in SEASON_MODE_OPTIONS:
            # Set optimistic value immediately to prevent UI flicker
            self._optimistic_option = option
            self._set_optimistic_timestamp()
            self.async_write_ha_state()

            is_cooling = option == SEASON_MODE_COOLING
            try:
                await self._api.set_season_mode(is_cooling)
            except EvonApiError:
                self._optimistic_option = None
                self._optimistic_state_set_at = None
                self.async_write_ha_state()
                raise
            self._schedule_post_command_recheck(recheck_snapshot)
        else:
            _LOGGER.warning("Ignoring invalid option %r for %s", option, self.entity_id)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._cancel_post_command_recheck_if_data_changed()
        # Only clear optimistic state when coordinator data matches expected value
        if self._optimistic_option is not None:
            is_cooling = self.coordinator.get_season_mode()
            actual_option = SEASON_MODE_COOLING if is_cooling else SEASON_MODE_HEATING
            if actual_option == self._optimistic_option:
                self._optimistic_option = None
                self._optimistic_state_set_at = None

        super()._handle_coordinator_update()

    async def async_will_remove_from_hass(self) -> None:
        """Cancel any pending recheck when entity is removed."""
        self._cleanup_post_command_recheck()
        await super().async_will_remove_from_hass()
