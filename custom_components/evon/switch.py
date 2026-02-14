"""Switch platform for Evon Smart Home integration."""

from __future__ import annotations

import logging
import time
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_call_later

from .api import EvonApi, EvonApiError
from .base_entity import EvonEntity
from .const import (
    CONF_MAX_RECORDING_DURATION,
    DEFAULT_MAX_RECORDING_DURATION,
    DOMAIN,
    ENTITY_TYPE_BATHROOM_RADIATORS,
    ENTITY_TYPE_CAMERAS,
    ENTITY_TYPE_SWITCHES,
    OPTIMISTIC_SETTLING_PERIOD_SHORT,
)
from .coordinator import EvonDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


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

    # Camera recording switches (one per camera)
    if coordinator.data and ENTITY_TYPE_CAMERAS in coordinator.data:
        for camera_data in coordinator.data[ENTITY_TYPE_CAMERAS]:
            entities.append(
                EvonCameraRecordingSwitch(
                    coordinator,
                    camera_data["id"],
                    camera_data["name"],
                    camera_data.get("room_name", ""),
                    entry,
                )
            )

    if entities:
        async_add_entities(entities)


class EvonSwitch(EvonEntity, SwitchEntity):
    """Representation of an Evon controllable switch (relay)."""

    _attr_icon = "mdi:electric-switch"
    _entity_type = ENTITY_TYPE_SWITCHES

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

    def _reset_optimistic_state(self) -> None:
        """Reset switch-specific optimistic state fields."""
        self._optimistic_is_on = None

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

        data = self._get_data()
        if data:
            return data.get("is_on", False)
        return False

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch."""
        self._optimistic_is_on = True
        self._set_optimistic_timestamp()
        self.async_write_ha_state()

        try:
            await self._api.turn_on_switch(self._instance_id)
        except EvonApiError:
            self._optimistic_is_on = None
            self._optimistic_state_set_at = None
            self.async_write_ha_state()
            raise
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch."""
        self._optimistic_is_on = False
        self._set_optimistic_timestamp()
        self.async_write_ha_state()

        try:
            await self._api.turn_off_switch(self._instance_id)
        except EvonApiError:
            self._optimistic_is_on = None
            self._optimistic_state_set_at = None
            self.async_write_ha_state()
            raise
        await self.coordinator.async_request_refresh()

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        # Only clear optimistic state when coordinator data matches expected value
        if self._optimistic_is_on is not None:
            data = self._get_data()
            if data:
                actual_is_on = data.get("is_on", False)
                if actual_is_on == self._optimistic_is_on:
                    self._optimistic_is_on = None
                    self._optimistic_state_set_at = None
        super()._handle_coordinator_update()


class EvonBathroomRadiatorSwitch(EvonEntity, SwitchEntity):
    """Representation of an Evon bathroom radiator (electric heater)."""

    _attr_icon = "mdi:radiator"
    _entity_type = ENTITY_TYPE_BATHROOM_RADIATORS

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
        # Cancel handle for delayed post-toggle verification refresh
        self._cancel_post_toggle_verify: CALLBACK_TYPE | None = None

    def _reset_optimistic_state(self) -> None:
        """Reset radiator-specific optimistic state fields."""
        self._optimistic_is_on = None
        self._optimistic_time_remaining_mins = None

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

        data = self._get_data()
        if data:
            return data.get("is_on", False)
        return False

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        attrs = super().extra_state_attributes
        data = self._get_data()
        if data:
            duration_mins = data.get("duration_mins", 30)
            attrs["duration_mins"] = duration_mins

            # Use optimistic time if set (for immediate UI feedback when turning on)
            if self._optimistic_time_remaining_mins is not None:
                time_remaining = max(0.0, self._optimistic_time_remaining_mins)
                mins = int(time_remaining)
                secs = min(59, int((time_remaining - mins) * 60))
                attrs["time_remaining"] = f"{mins}:{secs:02d}"
                attrs["time_remaining_mins"] = round(time_remaining, 1)
            else:
                time_remaining = data.get("time_remaining", -1)
                if time_remaining > 0:
                    # Convert to minutes:seconds format
                    mins = int(time_remaining)
                    secs = min(59, int((time_remaining - mins) * 60))
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
        data = self._get_data()
        self._optimistic_is_on = True
        # Set optimistic time to full duration for immediate progress bar display
        if data:
            self._optimistic_time_remaining_mins = float(data.get("duration_mins", 30))
        self._set_optimistic_timestamp()
        self.async_write_ha_state()

        try:
            await self._api.turn_on_bathroom_radiator(self._instance_id)
        except EvonApiError:
            self._optimistic_is_on = None
            self._optimistic_time_remaining_mins = None
            self._optimistic_state_set_at = None
            self.async_write_ha_state()
            raise
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the radiator.

        Uses Switch (toggle) because SwitchOff doesn't work on Evon bathroom
        radiators (acknowledged by the controller but has no effect). Only
        toggles if the radiator is currently on to prevent accidentally
        turning it ON.

        Race window: if the radiator turns off between our state check and
        the toggle command, the toggle will turn it back on. The double-tap
        guard and optimistic state mitigate this for rapid user interactions.
        """
        # Guard against double-tap: if we already sent a turn-off, don't toggle again
        if self._optimistic_is_on is False:
            _LOGGER.debug(
                "Radiator %s: skipping turn_off, optimistic off already pending",
                self._instance_id,
            )
            return

        data = self._get_data()
        current_is_on = data.get("is_on", False) if data else False

        if not current_is_on:
            _LOGGER.debug(
                "Radiator %s: skipping turn_off, already off (is_on=%s)",
                self._instance_id,
                current_is_on,
            )
            return

        _LOGGER.debug(
            "Radiator %s: turning off via toggle (is_on=%s, using Switch because SwitchOff is broken)",
            self._instance_id,
            current_is_on,
        )

        self._optimistic_is_on = False
        # Clear optimistic time when turning off
        self._optimistic_time_remaining_mins = None
        self._set_optimistic_timestamp()
        self.async_write_ha_state()

        try:
            await self._api.turn_off_bathroom_radiator(self._instance_id)
        except EvonApiError:
            self._optimistic_is_on = None
            self._optimistic_time_remaining_mins = None
            self._optimistic_state_set_at = None
            self.async_write_ha_state()
            raise
        await self.coordinator.async_request_refresh()

        # Schedule a delayed verification refresh to confirm the toggle
        # actually converged to the expected state (mitigates race condition
        # where the radiator turned off between our state check and the toggle).
        if self._cancel_post_toggle_verify:
            self._cancel_post_toggle_verify()
        self._cancel_post_toggle_verify = async_call_later(
            self.hass, 3, self._async_post_toggle_verify
        )

    async def _async_post_toggle_verify(self, _now: Any) -> None:
        """Verify state converged after toggle by requesting a coordinator refresh."""
        self._cancel_post_toggle_verify = None
        _LOGGER.debug(
            "Radiator %s: post-toggle verification refresh", self._instance_id
        )
        await self.coordinator.async_request_refresh()

    async def async_will_remove_from_hass(self) -> None:
        """Cancel pending verification when entity is removed."""
        if self._cancel_post_toggle_verify:
            self._cancel_post_toggle_verify()
            self._cancel_post_toggle_verify = None
        await super().async_will_remove_from_hass()

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

            data = self._get_data()
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


class EvonCameraRecordingSwitch(EvonEntity, SwitchEntity):
    """Switch entity to toggle camera recording on/off."""

    _attr_has_entity_name = True
    _attr_translation_key = "camera_recording"
    _entity_type = ENTITY_TYPE_CAMERAS

    def __init__(
        self,
        coordinator: EvonDataUpdateCoordinator,
        instance_id: str,
        name: str,
        room_name: str,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the recording switch."""
        super().__init__(coordinator, instance_id, name, room_name, entry)
        self._attr_unique_id = f"evon_camera_recording_{instance_id}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info linking to the same device as the camera."""
        return self._build_device_info("Intercom Camera")

    @property
    def icon(self) -> str:
        """Return icon based on recording state."""
        return "mdi:record-circle" if self.is_on else "mdi:record-circle-outline"

    @property
    def is_on(self) -> bool:
        """Return true if recording is active."""
        camera = self._get_camera_entity()
        if camera:
            return camera.recorder.is_recording
        return False

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        attrs = super().extra_state_attributes
        camera = self._get_camera_entity()
        if camera:
            attrs.update(camera.recorder.get_extra_attributes())
        return attrs

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Start recording."""
        camera = self._get_camera_entity()
        if not camera:
            raise HomeAssistantError(f"Camera entity not found for recording switch {self.entity_id}")
        max_dur = self._entry.options.get(CONF_MAX_RECORDING_DURATION, DEFAULT_MAX_RECORDING_DURATION)
        await camera.async_start_recording(duration=max_dur)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Stop recording."""
        camera = self._get_camera_entity()
        if not camera:
            raise HomeAssistantError(f"Camera entity not found for recording switch {self.entity_id}")
        await camera.async_stop_recording()
        self.async_write_ha_state()

    def _get_camera_entity(self):
        """Find the linked EvonCamera entity from the shared camera registry."""
        entry_data = self.hass.data.get(DOMAIN, {}).get(self._entry.entry_id, {})
        return entry_data.get("cameras", {}).get(self._instance_id)
