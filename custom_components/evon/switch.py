"""Switch platform for Evon Smart Home integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import EvonApi
from .base_entity import EvonEntity
from .const import DOMAIN
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
    if coordinator.data and "switches" in coordinator.data:
        for switch in coordinator.data["switches"]:
            entities.append(EvonSwitch(
                coordinator,
                switch["id"],
                switch["name"],
                switch.get("room_name", ""),
                entry,
                api,
            ))

    async_add_entities(entities)


class EvonSwitch(EvonEntity, SwitchEntity):
    """Representation of an Evon controllable switch (relay)."""

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

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for this switch."""
        return self._build_device_info("Switch")

    @property
    def is_on(self) -> bool:
        """Return true if the switch is on."""
        data = self.coordinator.get_entity_data("switches", self._instance_id)
        if data:
            return data.get("is_on", False)
        return False

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        return {"evon_id": self._instance_id}

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch."""
        await self._api.turn_on_switch(self._instance_id)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch."""
        await self._api.turn_off_switch(self._instance_id)
        await self.coordinator.async_request_refresh()
