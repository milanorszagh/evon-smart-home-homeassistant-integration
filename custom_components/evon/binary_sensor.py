"""Binary sensor platform for Evon Smart Home integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .base_entity import EvonEntity
from .const import DOMAIN
from .coordinator import EvonDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Evon binary sensors from a config entry."""
    coordinator: EvonDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    entities: list[BinarySensorEntity] = []

    # Create valve sensors
    if coordinator.data and "valves" in coordinator.data:
        for valve in coordinator.data["valves"]:
            entities.append(
                EvonValveSensor(
                    coordinator,
                    valve["id"],
                    valve["name"],
                    valve.get("room_name", ""),
                    entry,
                )
            )

    async_add_entities(entities)


class EvonValveSensor(EvonEntity, BinarySensorEntity):
    """Representation of an Evon valve sensor."""

    _attr_device_class = BinarySensorDeviceClass.OPENING

    def __init__(
        self,
        coordinator: EvonDataUpdateCoordinator,
        instance_id: str,
        name: str,
        room_name: str,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, instance_id, name, room_name, entry)
        self._attr_name = None  # Use device name
        self._attr_unique_id = f"evon_valve_{instance_id}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for this sensor."""
        return self._build_device_info("Climate Valve")

    @property
    def is_on(self) -> bool | None:
        """Return true if the valve is open."""
        data = self.coordinator.get_entity_data("valves", self._instance_id)
        if data:
            return data.get("is_open", False)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        data = self.coordinator.get_entity_data("valves", self._instance_id)
        attrs = {"evon_id": self._instance_id}
        if data:
            attrs["valve_type"] = data.get("valve_type")
        return attrs
