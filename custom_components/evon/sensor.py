"""Sensor platform for Evon Smart Home integration."""
from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any, Callable

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONCENTRATION_PARTS_PER_MILLION,
    PERCENTAGE,
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import EvonDataUpdateCoordinator


@dataclass(frozen=True, kw_only=True)
class EvonSensorEntityDescription(SensorEntityDescription):
    """Describes an Evon sensor entity."""

    value_fn: Callable[[dict[str, Any]], Any] | None = None
    extra_attrs_fn: Callable[[dict[str, Any]], dict[str, Any]] | None = None


SMART_METER_SENSORS: tuple[EvonSensorEntityDescription, ...] = (
    EvonSensorEntityDescription(
        key="power",
        name="Power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        value_fn=lambda data: data.get("power"),
    ),
    EvonSensorEntityDescription(
        key="energy",
        name="Energy Total",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value_fn=lambda data: data.get("energy"),
    ),
    EvonSensorEntityDescription(
        key="energy_24h",
        name="Energy Today",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value_fn=lambda data: data.get("energy_24h"),
    ),
    EvonSensorEntityDescription(
        key="voltage_l1",
        name="Voltage L1",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.get("voltage_l1"),
    ),
    EvonSensorEntityDescription(
        key="voltage_l2",
        name="Voltage L2",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.get("voltage_l2"),
    ),
    EvonSensorEntityDescription(
        key="voltage_l3",
        name="Voltage L3",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.get("voltage_l3"),
    ),
)

AIR_QUALITY_SENSORS: tuple[EvonSensorEntityDescription, ...] = (
    EvonSensorEntityDescription(
        key="co2",
        name="CO2",
        device_class=SensorDeviceClass.CO2,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        value_fn=lambda data: data.get("co2"),
    ),
    EvonSensorEntityDescription(
        key="humidity",
        name="Humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda data: data.get("humidity"),
    ),
)

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
                    climate.get("room_name", ""),
                    entry,
                )
            )

    # Create smart meter sensors using entity descriptions
    if coordinator.data and "smart_meters" in coordinator.data:
        for meter in coordinator.data["smart_meters"]:
            for description in SMART_METER_SENSORS:
                entities.append(
                    EvonSmartMeterSensor(
                        coordinator,
                        meter["id"],
                        meter["name"],
                        meter.get("room_name", ""),
                        entry,
                        description,
                    )
                )

    # Create air quality sensors using entity descriptions
    if coordinator.data and "air_quality" in coordinator.data:
        for aq in coordinator.data["air_quality"]:
            for description in AIR_QUALITY_SENSORS:
                # Only create sensor if data is available
                if aq.get(description.key) is not None:
                    entities.append(
                        EvonAirQualitySensor(
                            coordinator,
                            aq["id"],
                            aq["name"],
                            aq.get("room_name", ""),
                            entry,
                            description,
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
        room_name: str,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._instance_id = instance_id
        self._attr_name = "Temperature"
        self._attr_unique_id = f"evon_temp_{instance_id}"
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
            model="Climate Control",
            via_device=(DOMAIN, self._entry.entry_id),
        )
        if self._room_name:
            info["suggested_area"] = self._room_name
        return info

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


class EvonSmartMeterSensor(CoordinatorEntity[EvonDataUpdateCoordinator], SensorEntity):
    """Representation of an Evon smart meter sensor."""

    _attr_has_entity_name = True
    entity_description: EvonSensorEntityDescription

    def __init__(
        self,
        coordinator: EvonDataUpdateCoordinator,
        instance_id: str,
        name: str,
        room_name: str,
        entry: ConfigEntry,
        description: EvonSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._instance_id = instance_id
        self._attr_unique_id = f"evon_meter_{description.key}_{instance_id}"
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
            model="Smart Meter",
            via_device=(DOMAIN, self._entry.entry_id),
        )
        if self._room_name:
            info["suggested_area"] = self._room_name
        return info

    @property
    def native_value(self) -> float | None:
        """Return the sensor value."""
        data = self.coordinator.get_smart_meter_data(self._instance_id)
        if data and self.entity_description.value_fn:
            return self.entity_description.value_fn(data)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        attrs = {"evon_id": self._instance_id}
        # Add feed_in and frequency for power sensor
        if self.entity_description.key == "power":
            data = self.coordinator.get_smart_meter_data(self._instance_id)
            if data:
                attrs["feed_in"] = data.get("feed_in")
                attrs["frequency"] = data.get("frequency")
        return attrs

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()


class EvonAirQualitySensor(CoordinatorEntity[EvonDataUpdateCoordinator], SensorEntity):
    """Representation of an Evon air quality sensor."""

    _attr_has_entity_name = True
    entity_description: EvonSensorEntityDescription

    def __init__(
        self,
        coordinator: EvonDataUpdateCoordinator,
        instance_id: str,
        name: str,
        room_name: str,
        entry: ConfigEntry,
        description: EvonSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._instance_id = instance_id
        self._attr_unique_id = f"evon_{description.key}_{instance_id}"
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
            model="Air Quality Sensor",
            via_device=(DOMAIN, self._entry.entry_id),
        )
        if self._room_name:
            info["suggested_area"] = self._room_name
        return info

    @property
    def native_value(self) -> float | int | None:
        """Return the sensor value."""
        data = self.coordinator.get_air_quality_data(self._instance_id)
        if data and self.entity_description.value_fn:
            return self.entity_description.value_fn(data)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        data = self.coordinator.get_air_quality_data(self._instance_id)
        attrs = {"evon_id": self._instance_id}
        if data:
            if self.entity_description.key == "co2":
                attrs["health_index"] = data.get("health_index")
                attrs["co2_index"] = data.get("co2_index")
            elif self.entity_description.key == "humidity":
                attrs["humidity_index"] = data.get("humidity_index")
        return attrs

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()
