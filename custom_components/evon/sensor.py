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
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .base_entity import EvonEntity
from .const import DOMAIN
from .coordinator import EvonDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


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


class EvonTemperatureSensor(EvonEntity, SensorEntity):
    """Representation of an Evon temperature sensor."""

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
        super().__init__(coordinator, instance_id, name, room_name, entry)
        self._attr_name = "Temperature"
        self._attr_unique_id = f"evon_temp_{instance_id}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for this sensor."""
        return self._build_device_info("Climate Control")

    @property
    def native_value(self) -> float | None:
        """Return the current temperature."""
        data = self.coordinator.get_entity_data("climates", self._instance_id)
        if data:
            return data.get("current_temperature")
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        data = self.coordinator.get_entity_data("climates", self._instance_id)
        attrs = {"evon_id": self._instance_id}
        if data:
            attrs["target_temperature"] = data.get("target_temperature")
        return attrs


class EvonSmartMeterSensor(EvonEntity, SensorEntity):
    """Representation of an Evon smart meter sensor."""

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
        super().__init__(coordinator, instance_id, name, room_name, entry)
        self.entity_description = description
        self._attr_unique_id = f"evon_meter_{description.key}_{instance_id}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for this sensor."""
        return self._build_device_info("Smart Meter")

    @property
    def native_value(self) -> float | None:
        """Return the sensor value."""
        data = self.coordinator.get_entity_data("smart_meters", self._instance_id)
        if data and self.entity_description.value_fn:
            return self.entity_description.value_fn(data)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        attrs = {"evon_id": self._instance_id}
        # Add feed_in and frequency for power sensor
        if self.entity_description.key == "power":
            data = self.coordinator.get_entity_data("smart_meters", self._instance_id)
            if data:
                attrs["feed_in"] = data.get("feed_in")
                attrs["frequency"] = data.get("frequency")
        return attrs


class EvonAirQualitySensor(EvonEntity, SensorEntity):
    """Representation of an Evon air quality sensor."""

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
        super().__init__(coordinator, instance_id, name, room_name, entry)
        self.entity_description = description
        self._attr_unique_id = f"evon_{description.key}_{instance_id}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for this sensor."""
        return self._build_device_info("Air Quality Sensor")

    @property
    def native_value(self) -> float | int | None:
        """Return the sensor value."""
        data = self.coordinator.get_entity_data("air_quality", self._instance_id)
        if data and self.entity_description.value_fn:
            return self.entity_description.value_fn(data)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        data = self.coordinator.get_entity_data("air_quality", self._instance_id)
        attrs = {"evon_id": self._instance_id}
        if data:
            if self.entity_description.key == "co2":
                attrs["health_index"] = data.get("health_index")
                attrs["co2_index"] = data.get("co2_index")
            elif self.entity_description.key == "humidity":
                attrs["humidity_index"] = data.get("humidity_index")
        return attrs
