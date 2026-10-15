"""Sensor platform for Evon Smart Home integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    LIGHT_LUX,
    PERCENTAGE,
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfRatio,
    UnitOfSpeed,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .base_entity import EntityData, EvonEntity
from .const import (
    DOMAIN,
    ENTITY_TYPE_AIR_QUALITY,
    ENTITY_TYPE_CLIMATES,
    ENTITY_TYPE_SMART_METERS,
    ENTITY_TYPE_WEATHER,
)
from .coordinator import EvonDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class EvonSensorEntityDescription(SensorEntityDescription):
    """Describes an Evon sensor entity."""

    value_fn: Callable[[dict[str, Any]], Any] | None = None


SMART_METER_SENSORS: tuple[EvonSensorEntityDescription, ...] = (
    EvonSensorEntityDescription(
        key="power",
        name="Power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=0,
        value_fn=lambda data: data.get("power"),
    ),
    EvonSensorEntityDescription(
        key="energy",
        name="Energy Total",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=1,
        value_fn=lambda data: data.get("energy"),
    ),
    # NOTE: Energy24h from Evon is a ROLLING 24-hour window, not daily reset.
    # It can decrease during the day as old data rolls off.
    # Use Energy Total (total_increasing) for HA Energy Dashboard instead.
    # No device_class - ENERGY requires total/total_increasing state_class.
    EvonSensorEntityDescription(
        key="energy_24h",
        name="Energy (24h Rolling)",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=1,
        value_fn=lambda data: data.get("energy_24h"),
    ),
    EvonSensorEntityDescription(
        key="voltage_l1",
        name="Voltage L1",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.get("voltage_l1"),
    ),
    EvonSensorEntityDescription(
        key="voltage_l2",
        name="Voltage L2",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.get("voltage_l2"),
    ),
    EvonSensorEntityDescription(
        key="voltage_l3",
        name="Voltage L3",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.get("voltage_l3"),
    ),
    EvonSensorEntityDescription(
        key="current_l1",
        name="Current L1",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.get("current_l1"),
    ),
    EvonSensorEntityDescription(
        key="current_l2",
        name="Current L2",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.get("current_l2"),
    ),
    EvonSensorEntityDescription(
        key="current_l3",
        name="Current L3",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.get("current_l3"),
    ),
    EvonSensorEntityDescription(
        key="frequency",
        name="Frequency",
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.get("frequency"),
    ),
    EvonSensorEntityDescription(
        key="feed_in_energy",
        name="Feed-in Energy Total",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=1,
        value_fn=lambda data: data.get("feed_in_energy"),
    ),
)

# Energy Today and Energy This Month are created as separate sensor classes
# because they need async access to HA statistics

AIR_QUALITY_SENSORS: tuple[EvonSensorEntityDescription, ...] = (
    EvonSensorEntityDescription(
        key="co2",
        name="CO2",
        device_class=SensorDeviceClass.CO2,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfRatio.PARTS_PER_MILLION,
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

# "kLx" (kilolux) is not a standard HA unit, so the sun-intensity sensors carry no
# device_class; the raw value and an icon are enough for display.
_KILOLUX = "kLx"

WEATHER_SENSORS: tuple[EvonSensorEntityDescription, ...] = (
    EvonSensorEntityDescription(
        key="temperature",
        translation_key="weather_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
        value_fn=lambda data: data.get("temperature"),
    ),
    EvonSensorEntityDescription(
        key="wind_speed",
        translation_key="weather_wind_speed",
        device_class=SensorDeviceClass.WIND_SPEED,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        suggested_display_precision=1,
        value_fn=lambda data: data.get("wind_speed"),
    ),
    EvonSensorEntityDescription(
        key="brightness",
        translation_key="weather_brightness",
        device_class=SensorDeviceClass.ILLUMINANCE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=LIGHT_LUX,
        suggested_display_precision=0,
        value_fn=lambda data: data.get("brightness"),
    ),
    EvonSensorEntityDescription(
        key="sun_north",
        translation_key="weather_sun_north",
        icon="mdi:weather-sunny",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=_KILOLUX,
        suggested_display_precision=1,
        value_fn=lambda data: data.get("sun_north"),
    ),
    EvonSensorEntityDescription(
        key="sun_east",
        translation_key="weather_sun_east",
        icon="mdi:weather-sunny",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=_KILOLUX,
        suggested_display_precision=1,
        value_fn=lambda data: data.get("sun_east"),
    ),
    EvonSensorEntityDescription(
        key="sun_south",
        translation_key="weather_sun_south",
        icon="mdi:weather-sunny",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=_KILOLUX,
        suggested_display_precision=1,
        value_fn=lambda data: data.get("sun_south"),
    ),
    EvonSensorEntityDescription(
        key="sun_west",
        translation_key="weather_sun_west",
        icon="mdi:weather-sunny",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=_KILOLUX,
        suggested_display_precision=1,
        value_fn=lambda data: data.get("sun_west"),
    ),
    EvonSensorEntityDescription(
        key="temp_min_today",
        translation_key="weather_temp_min_today",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
        value_fn=lambda data: data.get("temp_min_today"),
    ),
    EvonSensorEntityDescription(
        key="temp_max_today",
        translation_key="weather_temp_max_today",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
        value_fn=lambda data: data.get("temp_max_today"),
    ),
    EvonSensorEntityDescription(
        key="wind_max_today",
        translation_key="weather_wind_max_today",
        device_class=SensorDeviceClass.WIND_SPEED,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        suggested_display_precision=1,
        value_fn=lambda data: data.get("wind_max_today"),
    ),
    # Lifetime extremes: no state_class (not a live measurement to graph/aggregate).
    EvonSensorEntityDescription(
        key="temp_min",
        translation_key="weather_temp_min",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.get("temp_min"),
    ),
    EvonSensorEntityDescription(
        key="temp_max",
        translation_key="weather_temp_max",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.get("temp_max"),
    ),
    EvonSensorEntityDescription(
        key="wind_max",
        translation_key="weather_wind_max",
        device_class=SensorDeviceClass.WIND_SPEED,
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.get("wind_max"),
    ),
    EvonSensorEntityDescription(
        key="last_rain",
        translation_key="weather_last_rain",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: data.get("last_rain"),
    ),
    EvonSensorEntityDescription(
        key="last_rain_in_days",
        translation_key="weather_last_rain_in_days",
        icon="mdi:weather-rainy",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.DAYS,
        suggested_display_precision=1,
        value_fn=lambda data: data.get("last_rain_in_days"),
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
    if coordinator.data and ENTITY_TYPE_CLIMATES in coordinator.data:
        for climate in coordinator.data[ENTITY_TYPE_CLIMATES]:
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
    if coordinator.data and ENTITY_TYPE_SMART_METERS in coordinator.data:
        for meter in coordinator.data[ENTITY_TYPE_SMART_METERS]:
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

            # Create Energy Today and Energy This Month sensors
            # Values are calculated in the coordinator from HA statistics + Evon data
            _LOGGER.debug(
                "Creating Energy Today/This Month sensors for meter %s (id=%s), "
                "energy_today_calculated=%s, energy_this_month_calculated=%s",
                meter["name"],
                meter["id"],
                meter.get("energy_today_calculated"),
                meter.get("energy_this_month_calculated"),
            )
            entities.append(
                EvonEnergyTodaySensor(
                    coordinator,
                    meter["id"],
                    meter["name"],
                    meter.get("room_name", ""),
                    entry,
                )
            )
            entities.append(
                EvonEnergyThisMonthSensor(
                    coordinator,
                    meter["id"],
                    meter["name"],
                    meter.get("room_name", ""),
                    entry,
                )
            )

    # Create air quality sensors using entity descriptions
    if coordinator.data and ENTITY_TYPE_AIR_QUALITY in coordinator.data:
        for aq in coordinator.data[ENTITY_TYPE_AIR_QUALITY]:
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

    # Create weather-station sensors using entity descriptions. All fields are
    # created regardless of their current value: a None (e.g. last_rain before the
    # first rain) must not permanently suppress the entity.
    if coordinator.data and ENTITY_TYPE_WEATHER in coordinator.data:
        for station in coordinator.data[ENTITY_TYPE_WEATHER]:
            for description in WEATHER_SENSORS:
                entities.append(
                    EvonWeatherSensor(
                        coordinator,
                        station["id"],
                        station["name"],
                        station.get("room_name", ""),
                        entry,
                        description,
                    )
                )

    # WebSocket diagnostic sensors
    entities.append(EvonWebSocketStatusSensor(coordinator, entry))
    if coordinator.ws_client is not None:
        entities.append(EvonWebSocketLatencySensor(coordinator, entry))

    if entities:
        async_add_entities(entities)


class EvonTemperatureSensor(EvonEntity, SensorEntity):
    """Representation of an Evon temperature sensor."""

    _attr_icon = "mdi:thermometer"
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_suggested_display_precision = 1
    _attr_translation_key = "temperature"
    _entity_type = ENTITY_TYPE_CLIMATES

    native_value = EntityData("current_temperature")

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
        self._attr_unique_id = f"evon_temp_{instance_id}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for this sensor."""
        return self._build_device_info("Climate Control")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        attrs = super().extra_state_attributes
        data = self._get_data()
        if data:
            attrs["target_temperature"] = data.get("target_temperature")
        return attrs


class EvonSmartMeterSensor(EvonEntity, SensorEntity):
    """Representation of an Evon smart meter sensor."""

    _attr_icon = "mdi:meter-electric"
    _entity_type = ENTITY_TYPE_SMART_METERS
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
        data = self._get_data()
        if data and self.entity_description.value_fn:
            return self.entity_description.value_fn(data)
        return None


class EvonAirQualitySensor(EvonEntity, SensorEntity):
    """Representation of an Evon air quality sensor."""

    _attr_icon = "mdi:air-filter"
    _entity_type = ENTITY_TYPE_AIR_QUALITY
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
        data = self._get_data()
        if data and self.entity_description.value_fn:
            return self.entity_description.value_fn(data)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        attrs = super().extra_state_attributes
        data = self._get_data()
        if data:
            if self.entity_description.key == "co2":
                attrs["health_index"] = data.get("health_index")
                attrs["co2_index"] = data.get("co2_index")
            elif self.entity_description.key == "humidity":
                attrs["humidity_index"] = data.get("humidity_index")
        return attrs


class EvonWeatherSensor(EvonEntity, SensorEntity):
    """Representation of an Evon weather-station sensor (one field)."""

    _entity_type = ENTITY_TYPE_WEATHER
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
        self._attr_unique_id = f"evon_weather_{instance_id}_{description.key}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for this sensor."""
        return self._build_device_info("Weather Station")

    @property
    def native_value(self) -> Any:
        """Return the sensor value."""
        data = self._get_data()
        if data and self.entity_description.value_fn:
            return self.entity_description.value_fn(data)
        return None


class EvonEnergyTodaySensor(EvonEntity, SensorEntity):
    """Sensor that shows today's energy consumption."""

    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_icon = "mdi:calendar-today"
    _attr_translation_key = "energy_today"
    _entity_type = ENTITY_TYPE_SMART_METERS

    native_value = EntityData("energy_today_calculated")

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
        self._attr_unique_id = f"evon_energy_today_{instance_id}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for this sensor."""
        return self._build_device_info("Smart Meter")


class EvonEnergyThisMonthSensor(EvonEntity, SensorEntity):
    """Sensor that shows this month's energy consumption."""

    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_icon = "mdi:calendar-month"
    _attr_translation_key = "energy_this_month"
    _entity_type = ENTITY_TYPE_SMART_METERS

    native_value = EntityData("energy_this_month_calculated")

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
        self._attr_unique_id = f"evon_energy_this_month_{instance_id}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for this sensor."""
        return self._build_device_info("Smart Meter")


class EvonWebSocketStatusSensor(CoordinatorEntity[EvonDataUpdateCoordinator], SensorEntity):
    """Diagnostic sensor for WebSocket connection status."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:websocket"
    _attr_translation_key = "websocket_status"
    # Enum so the three states are translated (entity.sensor.websocket_status.state)
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = ["connected", "disconnected", "disabled"]

    def __init__(
        self,
        coordinator: EvonDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"evon_websocket_status_{entry.entry_id}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info — attached to integration system device."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name="Evon Smart Home",
            manufacturer="Evon",
        )

    @property
    def native_value(self) -> str:
        """Return connection state."""
        ws_client = self.coordinator.ws_client
        if ws_client is None:
            return "disabled"
        return "connected" if ws_client.is_connected else "disconnected"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return safety-net poll statistics and connection quality metrics."""
        coordinator = self.coordinator
        corrected_at = coordinator.last_poll_correction_at
        attrs: dict[str, Any] = {
            "poll_count": coordinator.poll_count,
            "last_poll_duration_seconds": coordinator.last_poll_duration,
            "last_poll_instances_fetched": coordinator.last_poll_instances_fetched,
            "poll_corrections": coordinator.poll_correction_count,
            "last_poll_correction": coordinator.last_poll_correction,
            "last_poll_correction_at": corrected_at.isoformat() if corrected_at is not None else None,
        }
        ws_client = coordinator.ws_client
        if ws_client is None:
            return attrs
        attrs.update(
            {
                "connection_uptime_seconds": round(ws_client.connection_uptime, 1),
                "reconnect_count": ws_client.reconnect_count,
                "messages_received": ws_client.messages_received,
                "requests_sent": ws_client.requests_sent,
                "pending_requests": ws_client.pending_request_count,
                "avg_response_time_ms": round(ws_client.avg_response_time_ms, 1)
                if ws_client.avg_response_time_ms is not None
                else None,
                "last_error": ws_client.last_error,
            }
        )
        return attrs


class EvonWebSocketLatencySensor(CoordinatorEntity[EvonDataUpdateCoordinator], SensorEntity):
    """Diagnostic sensor for WebSocket response latency (long-term statistics)."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "ms"
    _attr_suggested_display_precision = 1
    _attr_icon = "mdi:timer-outline"
    _attr_translation_key = "websocket_latency"

    def __init__(
        self,
        coordinator: EvonDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"evon_websocket_latency_{entry.entry_id}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info — attached to integration system device."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name="Evon Smart Home",
            manufacturer="Evon",
        )

    @property
    def native_value(self) -> float | None:
        """Return average response time in ms."""
        ws_client = self.coordinator.ws_client
        if ws_client is None:
            return None
        return ws_client.avg_response_time_ms
