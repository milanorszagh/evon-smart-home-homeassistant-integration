"""Sensor platform for Evon Smart Home integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
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
    """Set up Evon sensors from a config entry."""
    coordinator: EvonDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    entities: list[SensorEntity] = []

    # Create temperature sensors for each climate device
    if coordinator.data and "climates" in coordinator.data:
        for climate in coordinator.data["climates"]:
            entities.append(
                EvonTemperatureSensor(
                    coordinator,
                    climate["id"],
                    climate["name"],
                    entry,
                )
            )

    async_add_entities(entities)


class EvonTemperatureSensor(CoordinatorEntity[EvonDataUpdateCoordinator], SensorEntity):
    """Representation of an Evon temperature sensor."""

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    def __init__(
        self,
        coordinator: EvonDataUpdateCoordinator,
        instance_id: str,
        name: str,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._instance_id = instance_id
        self._attr_name = "Temperature"
        self._attr_unique_id = f"evon_temp_{instance_id}"
        self._device_name = name
        self._entry = entry

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for this sensor."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._instance_id)},
            name=self._device_name,
            manufacturer="Evon",
            model="Climate Control",
            via_device=(DOMAIN, self._entry.entry_id),
        )

    @property
    def native_value(self) -> float | None:
        """Return the current temperature."""
        data = self.coordinator.get_climate_data(self._instance_id)
        if data:
            return data.get("current_temperature")
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        data = self.coordinator.get_climate_data(self._instance_id)
        attrs = {"evon_id": self._instance_id}
        if data:
            attrs["target_temperature"] = data.get("target_temperature")
        return attrs

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()
