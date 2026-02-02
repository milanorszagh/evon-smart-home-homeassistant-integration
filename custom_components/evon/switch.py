"""Switch platform for Evon Smart Home integration."""

from __future__ import annotations

import time
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import EvonApi
from .base_entity import EvonEntity
from .const import (
    DOMAIN,
    ENTITY_TYPE_BATHROOM_RADIATORS,
    ENTITY_TYPE_SWITCHES,
    OPTIMISTIC_SETTLING_PERIOD_SHORT,
    OPTIMISTIC_STATE_TIMEOUT,
)
from .coordinator import EvonDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Evon switches from a config entry."""
    coordinator: EvonDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    api: EvonApi = hass.data[DOMAIN][entry.entry_id]["api"]

    entities = []

    # Regular switches (relays)
    if coordinator.data and ENTITY_TYPE_SWITCHES in coordinator.data:
        for switch in coordinator.data[ENTITY_TYPE_SWITCHES]:
            entities.append(
                EvonSwitch(
                    coordinator,
                    switch["id"],
                    switch["name"],
                    switch.get("room_name", ""),
                    entry,
                    api,
                )
            )

    # Bathroom radiators (electric heaters)
    if coordinator.data and ENTITY_TYPE_BATHROOM_RADIATORS in coordinator.data:
        for radiator in coordinator.data[ENTITY_TYPE_BATHROOM_RADIATORS]:
            entities.append(
                EvonBathroomRadiatorSwitch(
                    coordinator,
                    radiator["id"],
                    radiator["name"],
                    radiator.get("room_name", ""),
                    entry,
                    api,
                )
            )

    if entities:
        async_add_entities(entities)


class EvonSwitch(EvonEntity, SwitchEntity):
    """Representation of an Evon controllable switch (relay)."""

    _attr_icon = "mdi:electric-switch"

    def __init__(
        self,
        coordinator: EvonDataUpdateCoordinator,
        instance_id: str,
        name: str,
        room_name: str,
        entry: ConfigEntry,
        api: EvonApi,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, instance_id, name, room_name, entry, api)
        self._attr_name = None  # Use device name
        self._attr_unique_id = f"evon_switch_{instance_id}"
        # Optimistic state to prevent UI flicker during updates
        self._optimistic_is_on: bool | None = None
        # Timestamp when optimistic state was set (for timeout-based clearance)
        self._optimistic_state_set_at: float | None = None

    def _clear_optimistic_state_if_expired(self) -> None:
        """Clear optimistic state if timeout has expired."""
        if (
            self._optimistic_state_set_at is not None
            and time.monotonic() - self._optimistic_state_set_at > OPTIMISTIC_STATE_TIMEOUT
        ):
            self._optimistic_is_on = None
            self._optimistic_state_set_at = None

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for this switch."""
        return self._build_device_info("Switch")

    @property
    def is_on(self) -> bool:
        """Return true if the switch is on."""
        # Clear expired optimistic state to prevent stale UI on network recovery
        self._clear_optimistic_state_if_expired()

        # Return optimistic value if set (prevents UI flicker during updates)
        if self._optimistic_is_on is not None:
            return self._optimistic_is_on

        data = self.coordinator.get_entity_data(ENTITY_TYPE_SWITCHES, self._instance_id)
        if data:
            return data.get("is_on", False)
        return False

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch."""
        self._optimistic_is_on = True
        self._optimistic_state_set_at = time.monotonic()
        self.async_write_ha_state()

        await self._api.turn_on_switch(self._instance_id)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch."""
        self._optimistic_is_on = False
        self._optimistic_state_set_at = time.monotonic()
        self.async_write_ha_state()

        await self._api.turn_off_switch(self._instance_id)
        await self.coordinator.async_request_refresh()

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        # Only clear optimistic state when coordinator data matches expected value
        if self._optimistic_is_on is not None:
            data = self.coordinator.get_entity_data(ENTITY_TYPE_SWITCHES, self._instance_id)
            if data:
                actual_is_on = data.get("is_on", False)
                if actual_is_on == self._optimistic_is_on:
                    self._optimistic_is_on = None
                    self._optimistic_state_set_at = None
        super()._handle_coordinator_update()


class EvonBathroomRadiatorSwitch(EvonEntity, SwitchEntity):
    """Representation of an Evon bathroom radiator (electric heater)."""

    _attr_icon = "mdi:radiator"

    def __init__(
        self,
        coordinator: EvonDataUpdateCoordinator,
        instance_id: str,
        name: str,
        room_name: str,
        entry: ConfigEntry,
        api: EvonApi,
    ) -> None:
        """Initialize the bathroom radiator switch."""
        super().__init__(coordinator, instance_id, name, room_name, entry, api)
        self._attr_name = None  # Use device name
        self._attr_unique_id = f"evon_radiator_{instance_id}"
        # Optimistic state to prevent UI flicker during updates
        self._optimistic_is_on: bool | None = None
        # Optimistic time remaining for immediate UI feedback when turning on
        self._optimistic_time_remaining_mins: float | None = None
        # Timestamp when optimistic state was set (for timeout-based clearance)
        self._optimistic_state_set_at: float | None = None

    def _clear_optimistic_state_if_expired(self) -> None:
        """Clear optimistic state if timeout has expired."""
        if (
            self._optimistic_state_set_at is not None
            and time.monotonic() - self._optimistic_state_set_at > OPTIMISTIC_STATE_TIMEOUT
        ):
            self._optimistic_is_on = None
            self._optimistic_time_remaining_mins = None
            self._optimistic_state_set_at = None

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for this radiator."""
        return self._build_device_info("Bathroom Radiator")

    @property
    def is_on(self) -> bool:
        """Return true if the radiator is on."""
        # Clear expired optimistic state to prevent stale UI on network recovery
        self._clear_optimistic_state_if_expired()

        # Return optimistic value if set (prevents UI flicker during updates)
        if self._optimistic_is_on is not None:
            return self._optimistic_is_on

        data = self.coordinator.get_entity_data(ENTITY_TYPE_BATHROOM_RADIATORS, self._instance_id)
        if data:
            return data.get("is_on", False)
        return False

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        attrs = super().extra_state_attributes
        data = self.coordinator.get_entity_data(ENTITY_TYPE_BATHROOM_RADIATORS, self._instance_id)
        if data:
            duration_mins = data.get("duration_mins", 30)
            attrs["duration_mins"] = duration_mins

            # Use optimistic time if set (for immediate UI feedback when turning on)
            if self._optimistic_time_remaining_mins is not None:
                time_remaining = self._optimistic_time_remaining_mins
                mins = int(time_remaining)
                secs = int((time_remaining - mins) * 60)
                attrs["time_remaining"] = f"{mins}:{secs:02d}"
                attrs["time_remaining_mins"] = round(time_remaining, 1)
            else:
                time_remaining = data.get("time_remaining", -1)
                if time_remaining > 0:
                    # Convert to minutes:seconds format
                    mins = int(time_remaining)
                    secs = int((time_remaining - mins) * 60)
                    attrs["time_remaining"] = f"{mins}:{secs:02d}"
                    attrs["time_remaining_mins"] = round(time_remaining, 1)
                else:
                    attrs["time_remaining"] = None
                    attrs["time_remaining_mins"] = None

            attrs["permanently_on"] = data.get("permanently_on", False)
            attrs["permanently_off"] = data.get("permanently_off", False)
        return attrs

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the radiator (for configured duration).

        Uses SwitchOneTime for explicit turn on (no state check needed).
        """
        data = self.coordinator.get_entity_data(ENTITY_TYPE_BATHROOM_RADIATORS, self._instance_id)
        self._optimistic_is_on = True
        # Set optimistic time to full duration for immediate progress bar display
        if data:
            self._optimistic_time_remaining_mins = float(data.get("duration_mins", 30))
        self._optimistic_state_set_at = time.monotonic()
        self.async_write_ha_state()

        await self._api.turn_on_bathroom_radiator(self._instance_id)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the radiator.

        Uses Switch (toggle) only if currently on to prevent toggling ON.
        """
        data = self.coordinator.get_entity_data(ENTITY_TYPE_BATHROOM_RADIATORS, self._instance_id)
        if data and data.get("is_on", False):
            self._optimistic_is_on = False
            # Clear optimistic time when turning off
            self._optimistic_time_remaining_mins = None
            self._optimistic_state_set_at = time.monotonic()
            self.async_write_ha_state()

            await self._api.turn_off_bathroom_radiator(self._instance_id)
            await self.coordinator.async_request_refresh()

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        # Only clear optimistic state when coordinator data matches expected value
        # AND settling period has passed (prevents UI flicker from intermediate states)
        if self._optimistic_is_on is not None:
            # During settling period, keep optimistic state to avoid intermediate state flicker
            # Note: Don't call super() - it triggers async_write_ha_state() which can cause
            # frontend animation glitches even with unchanged optimistic values
            if (
                self._optimistic_state_set_at is not None
                and time.monotonic() - self._optimistic_state_set_at < OPTIMISTIC_SETTLING_PERIOD_SHORT
            ):
                return

            data = self.coordinator.get_entity_data(ENTITY_TYPE_BATHROOM_RADIATORS, self._instance_id)
            if data:
                actual_is_on = data.get("is_on", False)
                actual_time_remaining = data.get("time_remaining", -1)
                # Only clear optimistic state when:
                # - is_on matches AND
                # - time_remaining is valid (> 0) when turning on
                if actual_is_on == self._optimistic_is_on:
                    if self._optimistic_is_on and actual_time_remaining <= 0:
                        # Turning on but time_remaining not yet reported - keep optimistic
                        return
                    self._optimistic_is_on = None
                    # Clear optimistic time once real data is available
                    self._optimistic_time_remaining_mins = None
                    self._optimistic_state_set_at = None
        super()._handle_coordinator_update()
