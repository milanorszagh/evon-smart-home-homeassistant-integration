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
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import EvonDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Evon lights from a config entry."""
    coordinator: EvonDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    api = hass.data[DOMAIN][entry.entry_id]["api"]

    entities = []
    if coordinator.data and "lights" in coordinator.data:
        for light in coordinator.data["lights"]:
            entities.append(EvonLight(coordinator, api, light["id"], light["name"], entry))

    async_add_entities(entities)


class EvonLight(CoordinatorEntity[EvonDataUpdateCoordinator], LightEntity):
    """Representation of an Evon light."""

    _attr_has_entity_name = True
    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}

    def __init__(
        self,
        coordinator: EvonDataUpdateCoordinator,
        api,
        instance_id: str,
        name: str,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the light."""
        super().__init__(coordinator)
        self._api = api
        self._instance_id = instance_id
        self._attr_name = None  # Use device name
        self._attr_unique_id = f"evon_light_{instance_id}"
        self._device_name = name
        self._entry = entry

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for this light."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._instance_id)},
            name=self._device_name,
            manufacturer="Evon",
            model="Dimmable Light",
            via_device=(DOMAIN, self._entry.entry_id),
        )

    @property
    def is_on(self) -> bool:
        """Return true if the light is on."""
        data = self.coordinator.get_light_data(self._instance_id)
        if data:
            return data.get("is_on", False)
        return False

    @property
    def brightness(self) -> int | None:
        """Return the brightness of the light (0-255)."""
        data = self.coordinator.get_light_data(self._instance_id)
        if data:
            # Evon uses 0-100, Home Assistant uses 0-255
            evon_brightness = data.get("brightness", 0)
            return int(evon_brightness * 255 / 100)
        return None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the light."""
        if ATTR_BRIGHTNESS in kwargs:
            # Convert from Home Assistant 0-255 to Evon 0-100
            brightness = int(kwargs[ATTR_BRIGHTNESS] * 100 / 255)
            await self._api.set_light_brightness(self._instance_id, brightness)
        else:
            await self._api.turn_on_light(self._instance_id)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the light."""
        await self._api.turn_off_light(self._instance_id)
        await self.coordinator.async_request_refresh()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()
