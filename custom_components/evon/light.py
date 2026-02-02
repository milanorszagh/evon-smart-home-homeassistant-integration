"""Light platform for Evon Smart Home integration."""

from __future__ import annotations

import logging
import time
from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ColorMode,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import EvonApi
from .base_entity import EvonEntity
from .const import (
    CONF_NON_DIMMABLE_LIGHTS,
    DOMAIN,
    OPTIMISTIC_SETTLING_PERIOD,
    OPTIMISTIC_STATE_TIMEOUT,
    OPTIMISTIC_STATE_TOLERANCE,
)
from .coordinator import EvonDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Evon lights from a config entry."""
    coordinator: EvonDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    api: EvonApi = hass.data[DOMAIN][entry.entry_id]["api"]

    entities = []
    if coordinator.data and "lights" in coordinator.data:
        for light in coordinator.data["lights"]:
            entities.append(
                EvonLight(
                    coordinator,
                    light["id"],
                    light["name"],
                    light.get("room_name", ""),
                    entry,
                    api,
                )
            )

    if entities:
        async_add_entities(entities)


class EvonLight(EvonEntity, LightEntity):
    """Representation of an Evon light."""

    _attr_icon = "mdi:lightbulb"

    def __init__(
        self,
        coordinator: EvonDataUpdateCoordinator,
        instance_id: str,
        name: str,
        room_name: str,
        entry: ConfigEntry,
        api: EvonApi,
    ) -> None:
        """Initialize the light."""
        super().__init__(coordinator, instance_id, name, room_name, entry, api)
        self._attr_name = None  # Use device name
        self._attr_unique_id = f"evon_light_{instance_id}"

        # Check if this light should be non-dimmable (from options)
        non_dimmable_lights = entry.options.get(CONF_NON_DIMMABLE_LIGHTS, [])
        self._is_dimmable = instance_id not in non_dimmable_lights

        # Check if this light supports color temperature from coordinator data
        data = coordinator.get_entity_data("lights", instance_id)
        self._supports_color_temp = data.get("supports_color_temp", False) if data else False

        if self._supports_color_temp:
            self._attr_color_mode = ColorMode.COLOR_TEMP
            self._attr_supported_color_modes = {ColorMode.COLOR_TEMP}
        elif self._is_dimmable:
            self._attr_color_mode = ColorMode.BRIGHTNESS
            self._attr_supported_color_modes = {ColorMode.BRIGHTNESS}
        else:
            self._attr_color_mode = ColorMode.ONOFF
            self._attr_supported_color_modes = {ColorMode.ONOFF}

        # Optimistic state to prevent UI flicker during updates
        self._optimistic_is_on: bool | None = None
        self._optimistic_brightness: int | None = None  # HA scale 0-255
        self._optimistic_color_temp: int | None = None  # Mireds
        # Store last known brightness for optimistic turn_on (HA scale 0-255)
        self._last_brightness: int | None = None
        # Timestamp when optimistic state was set (for timeout-based clearance)
        self._optimistic_state_set_at: float | None = None

    def _clear_optimistic_state_if_expired(self) -> None:
        """Clear optimistic state if timeout has expired."""
        if (
            self._optimistic_state_set_at is not None
            and time.monotonic() - self._optimistic_state_set_at > OPTIMISTIC_STATE_TIMEOUT
        ):
            self._optimistic_is_on = None
            self._optimistic_brightness = None
            self._optimistic_color_temp = None
            self._optimistic_state_set_at = None

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for this light."""
        if self._supports_color_temp:
            model = "RGBW Light"
        elif self._is_dimmable:
            model = "Dimmable Light"
        else:
            model = "Light"
        return self._build_device_info(model)

    @property
    def is_on(self) -> bool:
        """Return true if the light is on."""
        # Clear expired optimistic state to prevent stale UI on network recovery
        self._clear_optimistic_state_if_expired()

        # Return optimistic value if set (prevents UI flicker during updates)
        if self._optimistic_is_on is not None:
            return self._optimistic_is_on

        data = self.coordinator.get_entity_data("lights", self._instance_id)
        if data:
            return data.get("is_on", False)
        return False

    @property
    def brightness(self) -> int | None:
        """Return the brightness of the light (0-255)."""
        # Non-dimmable lights don't report brightness
        if not self._is_dimmable and not self._supports_color_temp:
            return None

        # Clear expired optimistic state to prevent stale UI on network recovery
        self._clear_optimistic_state_if_expired()

        # Return optimistic value if set (prevents UI flicker during updates)
        if self._optimistic_brightness is not None:
            return self._optimistic_brightness

        data = self.coordinator.get_entity_data("lights", self._instance_id)
        if data:
            # Evon uses 0-100, Home Assistant uses 0-255
            evon_brightness = data.get("brightness", 0)
            return int(evon_brightness * 255 / 100)
        return None

    @property
    def color_temp(self) -> int | None:
        """Return the color temperature in mireds."""
        if not self._supports_color_temp:
            return None

        # Clear expired optimistic state to prevent stale UI on network recovery
        self._clear_optimistic_state_if_expired()

        # Return optimistic value if set (prevents UI flicker during updates)
        if self._optimistic_color_temp is not None:
            return self._optimistic_color_temp

        data = self.coordinator.get_entity_data("lights", self._instance_id)
        if data and data.get("color_temp") is not None:
            # Convert from Kelvin to mireds
            kelvin = data["color_temp"]
            if kelvin > 0:
                return int(1000000 / kelvin)
        return None

    @property
    def min_mireds(self) -> int | None:
        """Return the minimum color temperature in mireds (from max Kelvin)."""
        if not self._supports_color_temp:
            return None

        data = self.coordinator.get_entity_data("lights", self._instance_id)
        if data and data.get("max_color_temp") is not None:
            # Min mireds = 1000000 / max_kelvin
            max_kelvin = data["max_color_temp"]
            if max_kelvin > 0:
                return int(1000000 / max_kelvin)
        return None

    @property
    def max_mireds(self) -> int | None:
        """Return the maximum color temperature in mireds (from min Kelvin)."""
        if not self._supports_color_temp:
            return None

        data = self.coordinator.get_entity_data("lights", self._instance_id)
        if data and data.get("min_color_temp") is not None:
            # Max mireds = 1000000 / min_kelvin
            min_kelvin = data["min_color_temp"]
            if min_kelvin > 0:
                return int(1000000 / min_kelvin)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        attrs = super().extra_state_attributes
        data = self.coordinator.get_entity_data("lights", self._instance_id)
        if data:
            attrs["brightness_pct"] = data.get("brightness", 0)
        return attrs

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the light."""
        # Check actual state from coordinator (before setting optimistic state)
        data = self.coordinator.get_entity_data("lights", self._instance_id)
        actual_is_on = data.get("is_on", False) if data else False

        # Set optimistic values immediately to prevent UI flicker
        self._optimistic_is_on = True
        if ATTR_BRIGHTNESS in kwargs and (self._is_dimmable or self._supports_color_temp):
            # User explicitly set brightness - use that value
            self._optimistic_brightness = kwargs[ATTR_BRIGHTNESS]
        elif self._last_brightness is not None and (self._is_dimmable or self._supports_color_temp):
            # Use last known brightness for smooth animation during turn-on
            # Note: _last_brightness is NOT updated during turn-off to avoid corruption
            # from Evon's turn-off animation (87% → 0%)
            self._optimistic_brightness = self._last_brightness
        if ATTR_COLOR_TEMP_KELVIN in kwargs and self._supports_color_temp:
            # Store as mireds for internal use (HA still uses mireds for color_temp property)
            kelvin = kwargs[ATTR_COLOR_TEMP_KELVIN]
            self._optimistic_color_temp = int(1000000 / kelvin) if kelvin > 0 else 250
        self._optimistic_state_set_at = time.monotonic()
        self.async_write_ha_state()

        # For non-dimmable lights that are already on, skip the API call.
        # This handles combined lights (Evon relay + Govee) where:
        # - Evon controls power (on/off only)
        # - Another device (e.g., Govee) handles dimming
        # When user adjusts brightness on a light group, HA calls turn_on() on all
        # members. We skip the redundant call to Evon since the light is already on.
        if not self._is_dimmable and not self._supports_color_temp and actual_is_on:
            _LOGGER.debug("Skipping API call for non-dimmable light %s (already on)", self._instance_id)
            return

        # Handle color temperature change
        if ATTR_COLOR_TEMP_KELVIN in kwargs and self._supports_color_temp:
            kelvin = kwargs[ATTR_COLOR_TEMP_KELVIN]
            await self._api.set_light_color_temp(self._instance_id, kelvin)

        # Handle brightness change
        if ATTR_BRIGHTNESS in kwargs and (self._is_dimmable or self._supports_color_temp):
            # Convert from Home Assistant 0-255 to Evon 0-100 and clamp to valid range
            brightness = max(0, min(100, int(kwargs[ATTR_BRIGHTNESS] * 100 / 255)))
            await self._api.set_light_brightness(self._instance_id, brightness)
        elif ATTR_COLOR_TEMP_KELVIN not in kwargs:
            # Only turn on if no brightness or color temp change
            await self._api.turn_on_light(self._instance_id)
        # Only request refresh if WebSocket is not connected
        # When WS is connected, we trust optimistic state + WS ValuesChanged events
        if not self.coordinator.ws_connected:
            await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the light."""
        # Set optimistic value immediately to prevent UI flicker
        self._optimistic_is_on = False
        self._optimistic_state_set_at = time.monotonic()
        self.async_write_ha_state()

        await self._api.turn_off_light(self._instance_id)
        # Only request refresh if WebSocket is not connected
        # When WS is connected, we trust optimistic state + WS ValuesChanged events
        if not self.coordinator.ws_connected:
            await self.coordinator.async_request_refresh()

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        # During settling period, completely ignore coordinator updates
        # This prevents UI flicker from intermediate WebSocket states during
        # Evon's light animation (0% → target brightness) or relay switching
        # Note: Don't call super() here - it triggers async_write_ha_state() which
        # can cause frontend animation glitches even with unchanged optimistic values
        if (
            self._optimistic_state_set_at is not None
            and time.monotonic() - self._optimistic_state_set_at < OPTIMISTIC_SETTLING_PERIOD
        ):
            return

        # Only clear optimistic state when coordinator data matches expected value
        data = self.coordinator.get_entity_data("lights", self._instance_id)
        if data:
            all_cleared = True

            # Save last known brightness when light is on (for optimistic turn_on)
            # BUT: Only save when NO optimistic state is active - this prevents
            # corruption from both turn-on and turn-off animations
            if (
                data.get("is_on", False)
                and (self._is_dimmable or self._supports_color_temp)
                and self._optimistic_state_set_at is None  # No active optimistic state
            ):
                evon_brightness = data.get("brightness", 0)
                if evon_brightness > 0:
                    self._last_brightness = int(evon_brightness * 255 / 100)

            if self._optimistic_is_on is not None:
                actual_is_on = data.get("is_on", False)
                if actual_is_on == self._optimistic_is_on:
                    self._optimistic_is_on = None
                else:
                    all_cleared = False

            if self._optimistic_brightness is not None:
                evon_brightness = data.get("brightness", 0)
                actual_brightness = int(evon_brightness * 255 / 100)
                # Allow small tolerance for rounding differences
                if abs(actual_brightness - self._optimistic_brightness) <= OPTIMISTIC_STATE_TOLERANCE:
                    self._optimistic_brightness = None
                else:
                    all_cleared = False

            if self._optimistic_color_temp is not None:
                kelvin = data.get("color_temp")
                if kelvin and kelvin > 0:
                    actual_mireds = int(1000000 / kelvin)
                    # Allow small tolerance for rounding differences (mireds)
                    if abs(actual_mireds - self._optimistic_color_temp) <= OPTIMISTIC_STATE_TOLERANCE:
                        self._optimistic_color_temp = None
                    else:
                        all_cleared = False

            # Clear timestamp if all optimistic state has been confirmed
            if all_cleared:
                self._optimistic_state_set_at = None

        super()._handle_coordinator_update()
