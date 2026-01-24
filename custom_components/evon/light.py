"""Light platform for Evon Smart Home integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ColorMode,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import EvonApi
from .base_entity import EvonEntity
from .const import CONF_NON_DIMMABLE_LIGHTS, DOMAIN
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

    async_add_entities(entities)


class EvonLight(EvonEntity, LightEntity):
    """Representation of an Evon light."""

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

        if self._is_dimmable:
            self._attr_color_mode = ColorMode.BRIGHTNESS
            self._attr_supported_color_modes = {ColorMode.BRIGHTNESS}
        else:
            self._attr_color_mode = ColorMode.ONOFF
            self._attr_supported_color_modes = {ColorMode.ONOFF}

        # Optimistic state to prevent UI flicker during updates
        self._optimistic_is_on: bool | None = None
        self._optimistic_brightness: int | None = None  # HA scale 0-255

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for this light."""
        model = "Dimmable Light" if self._is_dimmable else "Light"
        return self._build_device_info(model)

    @property
    def is_on(self) -> bool:
        """Return true if the light is on."""
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
        if not self._is_dimmable:
            return None

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
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        data = self.coordinator.get_entity_data("lights", self._instance_id)
        attrs = {}
        if data:
            attrs["brightness_pct"] = data.get("brightness", 0)
            attrs["evon_id"] = self._instance_id
        return attrs

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the light."""
        # Set optimistic values immediately to prevent UI flicker
        self._optimistic_is_on = True
        if ATTR_BRIGHTNESS in kwargs:
            self._optimistic_brightness = kwargs[ATTR_BRIGHTNESS]
        self.async_write_ha_state()

        if ATTR_BRIGHTNESS in kwargs:
            # Convert from Home Assistant 0-255 to Evon 0-100
            brightness = int(kwargs[ATTR_BRIGHTNESS] * 100 / 255)
            await self._api.set_light_brightness(self._instance_id, brightness)
        else:
            await self._api.turn_on_light(self._instance_id)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the light."""
        # Set optimistic value immediately to prevent UI flicker
        self._optimistic_is_on = False
        self.async_write_ha_state()

        await self._api.turn_off_light(self._instance_id)
        await self.coordinator.async_request_refresh()

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        # Only clear optimistic state when coordinator data matches expected value
        data = self.coordinator.get_entity_data("lights", self._instance_id)
        if data:
            if self._optimistic_is_on is not None:
                actual_is_on = data.get("is_on", False)
                if actual_is_on == self._optimistic_is_on:
                    self._optimistic_is_on = None

            if self._optimistic_brightness is not None:
                evon_brightness = data.get("brightness", 0)
                actual_brightness = int(evon_brightness * 255 / 100)
                # Allow small tolerance for rounding differences
                if abs(actual_brightness - self._optimistic_brightness) <= 3:
                    self._optimistic_brightness = None

        super()._handle_coordinator_update()
