"""Binary sensor platform for Evon Smart Home integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
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


class EvonValveSensor(CoordinatorEntity[EvonDataUpdateCoordinator], BinarySensorEntity):
    """Representation of an Evon valve sensor."""

    _attr_has_entity_name = True
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
        super().__init__(coordinator)
        self._instance_id = instance_id
        self._attr_name = None  # Use device name
        self._attr_unique_id = f"evon_valve_{instance_id}"
        self._device_name = name
        self._room_name = room_name
        self._entry = entry

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.coordinator.last_update_success and self.coordinator.data is not None

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for this sensor."""
        info = DeviceInfo(
            identifiers={(DOMAIN, self._instance_id)},
            name=self._device_name,
            manufacturer="Evon",
            model="Climate Valve",
            via_device=(DOMAIN, self._entry.entry_id),
        )
        if self._room_name:
            info["suggested_area"] = self._room_name
        return info

    @property
    def is_on(self) -> bool | None:
        """Return true if the valve is open."""
        data = self.coordinator.get_valve_data(self._instance_id)
        if data:
            return data.get("is_open", False)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        data = self.coordinator.get_valve_data(self._instance_id)
        attrs = {"evon_id": self._instance_id}
        if data:
            attrs["valve_type"] = data.get("valve_type")
        return attrs

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()
