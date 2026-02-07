"""Cover platform for Evon Smart Home integration.

POSITION AND TILT CONVENTIONS
=============================

Position:
- Home Assistant: 0 = closed, 100 = open
- Evon: 0 = open, 100 = closed
- Conversion: ha_position = 100 - evon_position

Tilt (Angle):
- Home Assistant: 0 = closed (blocking light), 100 = open (horizontal)
- Evon: 0 = open (horizontal), 100 = closed (blocking light)
- Conversion: ha_tilt = 100 - evon_angle

EVON BLIND TILT BEHAVIOR - IMPORTANT NOTES
==========================================

Evon blinds have a hardware quirk where the tilt/slat orientation depends on
the last movement direction of the blind:

- After moving DOWN: angle 0 = slats OPEN (horizontal), angle 100 = slats CLOSED
- After moving UP: angle 0 = slats CLOSED, angle 100 = slats OPEN (inverted!)

This means the same angle value can produce opposite physical results depending
on whether the blind last moved up or down. This behavior is inherent to how
the blind motor controls the slats and cannot be changed.

The Evon API only provides a `SetAngle` method with values 0-100. There are no
dedicated "open tilt" or "close tilt" commands that would handle direction
automatically.

This integration converts between Evon and HA conventions (inverting the value),
but the hardware quirk means physical behavior may not always match the UI when
the blind's last movement direction was UP.

ALTERNATIVES CONSIDERED
-----------------------
A "normalization" approach was tested where the blind would automatically move
down slightly before setting tilt to ensure consistent orientation. This was
rejected because:
1. Large blinds (e.g., 3m) take significant time to move
2. The delay would negatively impact user experience
3. It would cause unexpected position changes
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from homeassistant.components.cover import (
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import EvonApi, EvonApiError
from .base_entity import EvonEntity
from .const import (
    COVER_STOP_DELAY,
    DOMAIN,
    ENTITY_TYPE_BLINDS,
    OPTIMISTIC_STATE_TIMEOUT,
    OPTIMISTIC_STATE_TOLERANCE,
)
from .coordinator import EvonDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Evon covers from a config entry."""
    coordinator: EvonDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    api: EvonApi = hass.data[DOMAIN][entry.entry_id]["api"]

    entities = []
    if coordinator.data and ENTITY_TYPE_BLINDS in coordinator.data:
        for blind in coordinator.data[ENTITY_TYPE_BLINDS]:
            entities.append(
                EvonCover(
                    coordinator,
                    blind["id"],
                    blind["name"],
                    blind.get("room_name", ""),
                    entry,
                    api,
                )
            )

    if entities:
        async_add_entities(entities)


class EvonCover(EvonEntity, CoverEntity):
    """Representation of an Evon blind/cover."""

    _attr_icon = "mdi:blinds"
    _attr_device_class = CoverDeviceClass.BLIND
    _attr_supported_features = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.STOP
        | CoverEntityFeature.SET_POSITION
        | CoverEntityFeature.OPEN_TILT
        | CoverEntityFeature.CLOSE_TILT
        | CoverEntityFeature.SET_TILT_POSITION
    )

    def __init__(
        self,
        coordinator: EvonDataUpdateCoordinator,
        instance_id: str,
        name: str,
        room_name: str,
        entry: ConfigEntry,
        api: EvonApi,
    ) -> None:
        """Initialize the cover."""
        super().__init__(coordinator, instance_id, name, room_name, entry, api)
        self._attr_name = None  # Use device name
        self._attr_unique_id = f"evon_cover_{instance_id}"
        # Optimistic state to prevent UI flicker during updates (HA scale: 0=closed, 100=open)
        self._optimistic_position: int | None = None
        self._optimistic_tilt: int | None = None
        self._optimistic_is_moving: bool | None = None
        self._optimistic_direction: str | None = None  # "opening" or "closing"
        # Timestamp when optimistic state was set (for timeout-based clearance)
        self._optimistic_state_set_at: float | None = None

        # Check if this is a blind group (requires different API calls)
        data = coordinator.get_entity_data(ENTITY_TYPE_BLINDS, instance_id)
        self._is_group = data.get("is_group", False) if data else False

        # Initialize API caches for WebSocket control
        if data:
            api.update_blind_position(instance_id, data.get("position", 0))
            api.update_blind_angle(instance_id, data.get("angle", 0))

    def _clear_optimistic_state_if_expired(self) -> None:
        """Clear optimistic state if timeout has expired."""
        if (
            self._optimistic_state_set_at is not None
            and time.monotonic() - self._optimistic_state_set_at > OPTIMISTIC_STATE_TIMEOUT
        ):
            self._optimistic_position = None
            self._optimistic_tilt = None
            self._optimistic_is_moving = None
            self._optimistic_direction = None
            self._optimistic_state_set_at = None

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for this cover."""
        return self._build_device_info("Blind")

    @property
    def current_cover_position(self) -> int | None:
        """Return current position of cover (0=closed, 100=open in HA)."""
        # Clear expired optimistic state to prevent stale UI on network recovery
        self._clear_optimistic_state_if_expired()

        # Return optimistic value if set (prevents UI flicker during updates)
        if self._optimistic_position is not None:
            return self._optimistic_position

        data = self.coordinator.get_entity_data(ENTITY_TYPE_BLINDS, self._instance_id)
        if data:
            # Evon: 0=open, 100=closed
            # Home Assistant: 0=closed, 100=open
            return 100 - data.get("position", 0)
        return None

    @property
    def current_cover_tilt_position(self) -> int | None:
        """Return current tilt position of cover (0=closed, 100=open in HA)."""
        # Clear expired optimistic state to prevent stale UI on network recovery
        self._clear_optimistic_state_if_expired()

        # Return optimistic value if set (prevents UI flicker during updates)
        if self._optimistic_tilt is not None:
            return self._optimistic_tilt

        data = self.coordinator.get_entity_data(ENTITY_TYPE_BLINDS, self._instance_id)
        if data:
            # Evon: 0=open (horizontal), 100=closed (blocking)
            # Home Assistant: 0=closed, 100=open
            return 100 - data.get("angle", 0)
        return None

    @property
    def is_closed(self) -> bool | None:
        """Return if the cover is closed."""
        position = self.current_cover_position
        if position is not None:
            return position == 0
        return None

    @property
    def is_opening(self) -> bool:
        """Return if the cover is opening."""
        # Clear expired optimistic state to prevent stale UI on network recovery
        self._clear_optimistic_state_if_expired()

        # Use optimistic direction if set
        if self._optimistic_is_moving is not None and self._optimistic_direction is not None:
            return self._optimistic_is_moving and self._optimistic_direction == "opening"
        # Fallback: Evon API doesn't provide direction, so we can't know from coordinator data
        # Return False when not using optimistic state (HA will show as idle)
        return False

    @property
    def is_closing(self) -> bool:
        """Return if the cover is closing."""
        # Clear expired optimistic state to prevent stale UI on network recovery
        self._clear_optimistic_state_if_expired()

        # Use optimistic direction if set
        if self._optimistic_is_moving is not None and self._optimistic_direction is not None:
            return self._optimistic_is_moving and self._optimistic_direction == "closing"
        # Fallback: Evon API doesn't provide direction, so we can't know from coordinator data
        # Return False when not using optimistic state (HA will show as idle)
        return False

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        attrs = super().extra_state_attributes
        data = self.coordinator.get_entity_data(ENTITY_TYPE_BLINDS, self._instance_id)
        if data:
            # Evon native values (for debugging)
            attrs["evon_position"] = data.get("position", 0)  # 0=open, 100=closed
            attrs["evon_angle"] = data.get("angle", 0)  # 0=open, 100=closed
        return attrs

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        data = self.coordinator.get_entity_data(ENTITY_TYPE_BLINDS, self._instance_id)
        coordinator_is_moving = data.get("is_moving", False) if data else False
        # Check both coordinator data AND optimistic state (in case coordinator hasn't refreshed yet)
        is_moving = coordinator_is_moving or self._optimistic_is_moving is True

        if is_moving:
            # Blind is moving - this command will stop it (toggle behavior)
            # Clear optimistic values since we don't know final position
            self._optimistic_position = None
            self._optimistic_tilt = None
            # Optimistically set is_moving to False (same as stop)
            self._optimistic_is_moving = False
            self._optimistic_direction = None
            self.async_write_ha_state()

            try:
                if self._is_group:
                    await self._api.open_all_blinds()
                else:
                    await self._api.open_blind(self._instance_id)
            except EvonApiError:
                self._optimistic_is_moving = None
                self._optimistic_state_set_at = None
                self.async_write_ha_state()
                raise

            # Small delay then update state again to ensure UI reflects stopped state
            await asyncio.sleep(COVER_STOP_DELAY)
            # Check entity is still available before updating state
            if self.hass is not None:
                self.async_write_ha_state()
        else:
            # Blind is stopped - this will start opening
            self._optimistic_position = 100
            self._optimistic_is_moving = True  # Mark as moving so next click knows to stop
            self._optimistic_direction = "opening"
            self._optimistic_state_set_at = time.monotonic()
            self.async_write_ha_state()
            try:
                if self._is_group:
                    await self._api.open_all_blinds()
                else:
                    await self._api.open_blind(self._instance_id)
            except EvonApiError:
                self._optimistic_position = None
                self._optimistic_is_moving = None
                self._optimistic_direction = None
                self._optimistic_state_set_at = None
                self.async_write_ha_state()
                raise
            await self.coordinator.async_request_refresh()

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        data = self.coordinator.get_entity_data(ENTITY_TYPE_BLINDS, self._instance_id)
        coordinator_is_moving = data.get("is_moving", False) if data else False
        # Check both coordinator data AND optimistic state (in case coordinator hasn't refreshed yet)
        is_moving = coordinator_is_moving or self._optimistic_is_moving is True

        if is_moving:
            # Blind is moving - this command will stop it (toggle behavior)
            # Clear optimistic values since we don't know final position
            self._optimistic_position = None
            self._optimistic_tilt = None
            # Optimistically set is_moving to False (same as stop)
            self._optimistic_is_moving = False
            self._optimistic_direction = None
            self.async_write_ha_state()

            try:
                if self._is_group:
                    await self._api.close_all_blinds()
                else:
                    await self._api.close_blind(self._instance_id)
            except EvonApiError:
                self._optimistic_is_moving = None
                self._optimistic_state_set_at = None
                self.async_write_ha_state()
                raise

            # Small delay then update state again to ensure UI reflects stopped state
            await asyncio.sleep(COVER_STOP_DELAY)
            # Check entity is still available before updating state
            if self.hass is not None:
                self.async_write_ha_state()
        else:
            # Blind is stopped - this will start closing
            self._optimistic_position = 0
            self._optimistic_is_moving = True  # Mark as moving so next click knows to stop
            self._optimistic_direction = "closing"
            self._optimistic_state_set_at = time.monotonic()
            self.async_write_ha_state()
            try:
                if self._is_group:
                    await self._api.close_all_blinds()
                else:
                    await self._api.close_blind(self._instance_id)
            except EvonApiError:
                self._optimistic_position = None
                self._optimistic_is_moving = None
                self._optimistic_direction = None
                self._optimistic_state_set_at = None
                self.async_write_ha_state()
                raise
            await self.coordinator.async_request_refresh()

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        # Clear optimistic values since we don't know where it will stop
        self._optimistic_position = None
        self._optimistic_tilt = None
        # Optimistically set is_moving to False immediately
        # This fixes the issue where group stop actions leave arrows inactive
        self._optimistic_is_moving = False
        self._optimistic_direction = None
        self.async_write_ha_state()

        try:
            if self._is_group:
                await self._api.stop_all_blinds()
            else:
                await self._api.stop_blind(self._instance_id)
        except EvonApiError:
            self._optimistic_is_moving = None
            self._optimistic_state_set_at = None
            self.async_write_ha_state()
            raise

        # Small delay then update state again to ensure UI reflects stopped state
        # This helps when multiple blinds are stopped via group action
        await asyncio.sleep(COVER_STOP_DELAY)
        # Check entity is still available before updating state
        if self.hass is not None:
            self.async_write_ha_state()

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Set the cover position."""
        if ATTR_POSITION in kwargs:
            # Clamp to valid range 0-100
            ha_position = max(0, min(100, int(kwargs[ATTR_POSITION])))
            # Set optimistic value immediately
            self._optimistic_position = ha_position
            self._optimistic_state_set_at = time.monotonic()
            self.async_write_ha_state()

            # Convert from HA (0=closed, 100=open) to Evon (0=open, 100=closed)
            evon_position = 100 - ha_position
            try:
                await self._api.set_blind_position(self._instance_id, evon_position)
            except EvonApiError:
                self._optimistic_position = None
                self._optimistic_state_set_at = None
                self.async_write_ha_state()
                raise
            await self.coordinator.async_request_refresh()

    async def async_open_cover_tilt(self, **kwargs: Any) -> None:
        """Open the cover tilt (slats horizontal, letting light through).

        Note: Due to Evon hardware behavior, tilt orientation depends on the
        blind's last movement direction. See module docstring for details.
        """
        # HA tilt 100 = open (horizontal), Evon angle 0 = open
        self._optimistic_tilt = 100
        self._optimistic_state_set_at = time.monotonic()
        self.async_write_ha_state()

        try:
            await self._api.set_blind_tilt(self._instance_id, 0)
        except EvonApiError:
            self._optimistic_tilt = None
            self._optimistic_state_set_at = None
            self.async_write_ha_state()
            raise
        await self.coordinator.async_request_refresh()

    async def async_close_cover_tilt(self, **kwargs: Any) -> None:
        """Close the cover tilt (slats angled to block light).

        Note: Due to Evon hardware behavior, tilt orientation depends on the
        blind's last movement direction. See module docstring for details.
        """
        # HA tilt 0 = closed (blocking), Evon angle 100 = closed
        self._optimistic_tilt = 0
        self._optimistic_state_set_at = time.monotonic()
        self.async_write_ha_state()

        try:
            await self._api.set_blind_tilt(self._instance_id, 100)
        except EvonApiError:
            self._optimistic_tilt = None
            self._optimistic_state_set_at = None
            self.async_write_ha_state()
            raise
        await self.coordinator.async_request_refresh()

    async def async_set_cover_tilt_position(self, **kwargs: Any) -> None:
        """Set the cover tilt position.

        Home Assistant convention:
        - Tilt 0 = slats CLOSED (blocking light)
        - Tilt 100 = slats OPEN (horizontal, letting light through)

        Note: Due to Evon hardware behavior, tilt orientation depends on the
        blind's last movement direction. See module docstring for details.
        """
        if ATTR_TILT_POSITION in kwargs:
            # Clamp to valid range 0-100
            ha_tilt = max(0, min(100, int(kwargs[ATTR_TILT_POSITION])))
            self._optimistic_tilt = ha_tilt
            self._optimistic_state_set_at = time.monotonic()
            self.async_write_ha_state()

            # Convert from HA (0=closed, 100=open) to Evon (0=open, 100=closed)
            evon_angle = 100 - ha_tilt
            try:
                await self._api.set_blind_tilt(self._instance_id, evon_angle)
            except EvonApiError:
                self._optimistic_tilt = None
                self._optimistic_state_set_at = None
                self.async_write_ha_state()
                raise
            await self.coordinator.async_request_refresh()

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        # Only clear optimistic state when coordinator data matches expected value
        data = self.coordinator.get_entity_data(ENTITY_TYPE_BLINDS, self._instance_id)
        if data:
            # Update API caches for WebSocket control
            # Position is Evon native (0=open, 100=closed)
            evon_position = data.get("position", 0)
            evon_angle = data.get("angle", 0)
            self._api.update_blind_position(self._instance_id, evon_position)
            self._api.update_blind_angle(self._instance_id, evon_angle)

            all_cleared = True

            if self._optimistic_position is not None:
                # Convert Evon position to HA position for comparison
                actual_position = 100 - data.get("position", 0)
                # Allow small tolerance for rounding
                if abs(actual_position - self._optimistic_position) <= OPTIMISTIC_STATE_TOLERANCE:
                    self._optimistic_position = None
                else:
                    all_cleared = False

            if self._optimistic_tilt is not None:
                # Convert Evon angle to HA tilt for comparison
                actual_tilt = 100 - data.get("angle", 0)
                if abs(actual_tilt - self._optimistic_tilt) <= OPTIMISTIC_STATE_TOLERANCE:
                    self._optimistic_tilt = None
                else:
                    all_cleared = False

            if self._optimistic_is_moving is not None:
                actual_is_moving = data.get("is_moving", False)
                if actual_is_moving == self._optimistic_is_moving:
                    self._optimistic_is_moving = None
                    self._optimistic_direction = None
                else:
                    all_cleared = False

            # Clear timestamp if all optimistic state has been confirmed
            if all_cleared:
                self._optimistic_state_set_at = None
                self._optimistic_direction = None

        super()._handle_coordinator_update()
