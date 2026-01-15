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
from homeassistant.const import (
    CONCENTRATION_PARTS_PER_MILLION,
    PERCENTAGE,
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

    # Create smart meter sensors
    if coordinator.data and "smart_meters" in coordinator.data:
        for meter in coordinator.data["smart_meters"]:
            # Power sensor
            entities.append(
                EvonSmartMeterPowerSensor(
                    coordinator,
                    meter["id"],
                    meter["name"],
                    meter.get("room_name", ""),
                    entry,
                )
            )
            # Energy sensor
            entities.append(
                EvonSmartMeterEnergySensor(
                    coordinator,
                    meter["id"],
                    meter["name"],
                    meter.get("room_name", ""),
                    entry,
                )
            )
            # Energy 24h sensor
            entities.append(
                EvonSmartMeterEnergy24hSensor(
                    coordinator,
                    meter["id"],
                    meter["name"],
                    meter.get("room_name", ""),
                    entry,
                )
            )
            # Voltage sensors (per phase)
            for phase in [1, 2, 3]:
                entities.append(
                    EvonSmartMeterVoltageSensor(
                        coordinator,
                        meter["id"],
                        meter["name"],
                        meter.get("room_name", ""),
                        entry,
                        phase,
                    )
                )

    # Create air quality sensors
    if coordinator.data and "air_quality" in coordinator.data:
        for aq in coordinator.data["air_quality"]:
            # CO2 sensor (if available)
            if aq.get("co2") is not None:
                entities.append(
                    EvonCO2Sensor(
                        coordinator,
                        aq["id"],
                        aq["name"],
                        aq.get("room_name", ""),
                        entry,
                    )
                )
            # Humidity sensor (if available)
            if aq.get("humidity") is not None:
                entities.append(
                    EvonHumiditySensor(
                        coordinator,
                        aq["id"],
                        aq["name"],
                        aq.get("room_name", ""),
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


class EvonSmartMeterPowerSensor(CoordinatorEntity[EvonDataUpdateCoordinator], SensorEntity):
    """Representation of an Evon smart meter power sensor."""

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfPower.WATT

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
        self._attr_name = "Power"
        self._attr_unique_id = f"evon_meter_power_{instance_id}"
        self._device_name = name
        self._room_name = room_name
        self._entry = entry

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
        """Return the current power."""
        data = self.coordinator.get_smart_meter_data(self._instance_id)
        if data:
            return data.get("power")
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        data = self.coordinator.get_smart_meter_data(self._instance_id)
        attrs = {"evon_id": self._instance_id}
        if data:
            attrs["feed_in"] = data.get("feed_in")
            attrs["frequency"] = data.get("frequency")
        return attrs

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()


class EvonSmartMeterEnergySensor(CoordinatorEntity[EvonDataUpdateCoordinator], SensorEntity):
    """Representation of an Evon smart meter energy sensor."""

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR

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
        self._attr_name = "Energy Total"
        self._attr_unique_id = f"evon_meter_energy_{instance_id}"
        self._device_name = name
        self._room_name = room_name
        self._entry = entry

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
        """Return the total energy."""
        data = self.coordinator.get_smart_meter_data(self._instance_id)
        if data:
            return data.get("energy")
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        return {"evon_id": self._instance_id}

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()


class EvonSmartMeterEnergy24hSensor(CoordinatorEntity[EvonDataUpdateCoordinator], SensorEntity):
    """Representation of an Evon smart meter 24h energy sensor."""

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR

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
        self._attr_name = "Energy Today"
        self._attr_unique_id = f"evon_meter_energy_24h_{instance_id}"
        self._device_name = name
        self._room_name = room_name
        self._entry = entry

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
        """Return the 24h energy."""
        data = self.coordinator.get_smart_meter_data(self._instance_id)
        if data:
            return data.get("energy_24h")
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        return {"evon_id": self._instance_id}

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()


class EvonSmartMeterVoltageSensor(CoordinatorEntity[EvonDataUpdateCoordinator], SensorEntity):
    """Representation of an Evon smart meter voltage sensor."""

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.VOLTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfElectricPotential.VOLT

    def __init__(
        self,
        coordinator: EvonDataUpdateCoordinator,
        instance_id: str,
        name: str,
        room_name: str,
        entry: ConfigEntry,
        phase: int,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._instance_id = instance_id
        self._phase = phase
        self._attr_name = f"Voltage L{phase}"
        self._attr_unique_id = f"evon_meter_voltage_l{phase}_{instance_id}"
        self._device_name = name
        self._room_name = room_name
        self._entry = entry

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
        """Return the voltage."""
        data = self.coordinator.get_smart_meter_data(self._instance_id)
        if data:
            return data.get(f"voltage_l{self._phase}")
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        return {"evon_id": self._instance_id, "phase": self._phase}

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()


class EvonCO2Sensor(CoordinatorEntity[EvonDataUpdateCoordinator], SensorEntity):
    """Representation of an Evon CO2 sensor."""

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.CO2
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = CONCENTRATION_PARTS_PER_MILLION

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
        self._attr_name = "CO2"
        self._attr_unique_id = f"evon_co2_{instance_id}"
        self._device_name = name
        self._room_name = room_name
        self._entry = entry

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
    def native_value(self) -> int | None:
        """Return the CO2 level."""
        data = self.coordinator.get_air_quality_data(self._instance_id)
        if data:
            return data.get("co2")
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        data = self.coordinator.get_air_quality_data(self._instance_id)
        attrs = {"evon_id": self._instance_id}
        if data:
            attrs["health_index"] = data.get("health_index")
            attrs["co2_index"] = data.get("co2_index")
        return attrs

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()


class EvonHumiditySensor(CoordinatorEntity[EvonDataUpdateCoordinator], SensorEntity):
    """Representation of an Evon humidity sensor."""

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.HUMIDITY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE

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
        self._attr_name = "Humidity"
        self._attr_unique_id = f"evon_humidity_{instance_id}"
        self._device_name = name
        self._room_name = room_name
        self._entry = entry

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
    def native_value(self) -> float | None:
        """Return the humidity."""
        data = self.coordinator.get_air_quality_data(self._instance_id)
        if data:
            return data.get("humidity")
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        data = self.coordinator.get_air_quality_data(self._instance_id)
        attrs = {"evon_id": self._instance_id}
        if data:
            attrs["humidity_index"] = data.get("humidity_index")
        return attrs

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()
