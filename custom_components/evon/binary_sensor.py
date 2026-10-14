"""Binary sensor platform for Evon Smart Home integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .base_entity import EntityData, EvonEntity
from .const import (
    DOMAIN,
    ENTITY_TYPE_INTERCOMS,
    ENTITY_TYPE_SECURITY_DOORS,
    ENTITY_TYPE_VALVES,
    ENTITY_TYPE_WEATHER,
)
from .coordinator import EvonDataUpdateCoordinator


@dataclass(frozen=True, kw_only=True)
class EvonBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes an Evon binary sensor entity.

    ``key`` doubles as the coordinator data field to read and the unique_id suffix.
    """


# Weather-station binary sensors. ``key`` is the coordinator data field.
WEATHER_BINARY_SENSORS: tuple[EvonBinarySensorEntityDescription, ...] = (
    EvonBinarySensorEntityDescription(
        key="rain",
        translation_key="weather_rain",
        device_class=BinarySensorDeviceClass.MOISTURE,
    ),
    EvonBinarySensorEntityDescription(
        key="twilight",
        translation_key="weather_twilight",
        icon="mdi:weather-night",
    ),
    EvonBinarySensorEntityDescription(
        key="wind_alarm",
        translation_key="weather_wind_alarm",
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    EvonBinarySensorEntityDescription(
        key="wind_alarm_1",
        translation_key="weather_wind_alarm_1",
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    EvonBinarySensorEntityDescription(
        key="wind_alarm_2",
        translation_key="weather_wind_alarm_2",
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
    EvonBinarySensorEntityDescription(
        key="connected",
        translation_key="weather_connected",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    EvonBinarySensorEntityDescription(
        key="temperature_valid",
        translation_key="weather_temperature_valid",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    EvonBinarySensorEntityDescription(
        key="polling_activated",
        translation_key="weather_polling_activated",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Evon binary sensors from a config entry."""
    coordinator: EvonDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    entities: list[BinarySensorEntity] = []

    # Create valve sensors
    if coordinator.data and ENTITY_TYPE_VALVES in coordinator.data:
        for valve in coordinator.data[ENTITY_TYPE_VALVES]:
            entities.append(
                EvonValveSensor(
                    coordinator,
                    valve["id"],
                    valve["name"],
                    valve.get("room_name", ""),
                    entry,
                )
            )

    # Create security door sensors
    if coordinator.data and ENTITY_TYPE_SECURITY_DOORS in coordinator.data:
        for door in coordinator.data[ENTITY_TYPE_SECURITY_DOORS]:
            # Door open/closed sensor
            entities.append(
                EvonSecurityDoorSensor(
                    coordinator,
                    door["id"],
                    door["name"],
                    door.get("room_name", ""),
                    entry,
                )
            )
            # Call in progress sensor
            entities.append(
                EvonSecurityDoorCallSensor(
                    coordinator,
                    door["id"],
                    door["name"],
                    door.get("room_name", ""),
                    entry,
                )
            )

    # Create intercom sensors
    if coordinator.data and ENTITY_TYPE_INTERCOMS in coordinator.data:
        for intercom in coordinator.data[ENTITY_TYPE_INTERCOMS]:
            # Door open sensor
            entities.append(
                EvonIntercomDoorSensor(
                    coordinator,
                    intercom["id"],
                    intercom["name"],
                    intercom.get("room_name", ""),
                    entry,
                )
            )
            # Connection status sensor
            entities.append(
                EvonIntercomConnectionSensor(
                    coordinator,
                    intercom["id"],
                    intercom["name"],
                    intercom.get("room_name", ""),
                    entry,
                )
            )

    # WebSocket connection status sensor (one per integration)
    entities.append(
        EvonWebSocketStatusSensor(
            coordinator,
            entry,
        )
    )

    # Create weather-station binary sensors using entity descriptions
    if coordinator.data and ENTITY_TYPE_WEATHER in coordinator.data:
        for station in coordinator.data[ENTITY_TYPE_WEATHER]:
            for description in WEATHER_BINARY_SENSORS:
                entities.append(
                    EvonWeatherBinarySensor(
                        coordinator,
                        station["id"],
                        station["name"],
                        station.get("room_name", ""),
                        entry,
                        description,
                    )
                )

    if entities:
        async_add_entities(entities)


class EvonWeatherBinarySensor(EvonEntity, BinarySensorEntity):
    """Representation of an Evon weather-station binary sensor (one field)."""

    _entity_type = ENTITY_TYPE_WEATHER
    entity_description: EvonBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: EvonDataUpdateCoordinator,
        instance_id: str,
        name: str,
        room_name: str,
        entry: ConfigEntry,
        description: EvonBinarySensorEntityDescription,
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
    def is_on(self) -> bool | None:
        """Return the binary state, or None when the field is missing."""
        data = self._get_data()
        if not data:
            return None
        value = data.get(self.entity_description.key)
        if value is None:
            return None
        return bool(value)


class EvonValveSensor(EvonEntity, BinarySensorEntity):
    """Representation of an Evon valve sensor."""

    _attr_icon = "mdi:valve"
    _attr_device_class = BinarySensorDeviceClass.OPENING
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _entity_type = ENTITY_TYPE_VALVES

    is_on = EntityData("is_open", default=False)

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
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        attrs = super().extra_state_attributes
        data = self._get_data()
        if data:
            attrs["valve_type"] = data.get("valve_type")
        return attrs


class EvonSecurityDoorSensor(EvonEntity, BinarySensorEntity):
    """Representation of an Evon security door sensor."""

    _attr_icon = "mdi:door"
    _attr_device_class = BinarySensorDeviceClass.DOOR
    _entity_type = ENTITY_TYPE_SECURITY_DOORS

    is_on = EntityData("is_open", default=False)

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
        self._attr_unique_id = f"evon_security_door_{instance_id}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for this sensor."""
        return self._build_device_info("Security Door")


class EvonSecurityDoorCallSensor(EvonEntity, BinarySensorEntity):
    """Representation of an Evon security door call in progress sensor."""

    _attr_icon = "mdi:phone-ring"
    # No device_class: HA has no class for "call in progress" — OCCUPANCY would show
    # "Occupied"/"Clear" which is semantically wrong. The translation_key provides the label.
    _attr_translation_key = "call_in_progress"
    _entity_type = ENTITY_TYPE_SECURITY_DOORS

    is_on = EntityData("call_in_progress", default=False)

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
        self._attr_unique_id = f"evon_security_door_{instance_id}_call"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for this sensor."""
        return self._build_device_info("Security Door")


class EvonIntercomDoorSensor(EvonEntity, BinarySensorEntity):
    """Representation of an Evon intercom door sensor."""

    _attr_icon = "mdi:doorbell-video"
    _attr_device_class = BinarySensorDeviceClass.DOOR
    _entity_type = ENTITY_TYPE_INTERCOMS

    is_on = EntityData("is_door_open", default=False)

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
        self._attr_unique_id = f"evon_intercom_{instance_id}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for this sensor."""
        return self._build_device_info("Intercom")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        attrs = super().extra_state_attributes
        data = self._get_data()
        if data:
            attrs["doorbell_triggered"] = data.get("doorbell_triggered", False)
            attrs["door_open_triggered"] = data.get("door_open_triggered", False)
        return attrs


class EvonIntercomConnectionSensor(EvonEntity, BinarySensorEntity):
    """Representation of an Evon intercom connection status sensor."""

    _attr_icon = "mdi:lan-connect"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "connection"
    _entity_type = ENTITY_TYPE_INTERCOMS

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
        self._attr_unique_id = f"evon_intercom_{instance_id}_connection"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for this sensor."""
        return self._build_device_info("Intercom")

    @property
    def is_on(self) -> bool | None:
        """Return true if the intercom is connected (not lost)."""
        data = self._get_data()
        if data:
            # is_on = connected (inverse of connection_lost)
            # Use `is not True` to safely handle None/missing values as "connected"
            return data.get("connection_lost") is not True
        return None


class EvonWebSocketStatusSensor(BinarySensorEntity):
    """Sensor showing WebSocket connection status."""

    # Push-only: state is driven by the coordinator listener below, not polling.
    # Not a CoordinatorEntity, so should_poll must be set explicitly (defaults True).
    _attr_should_poll = False
    _attr_icon = "mdi:websocket"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_has_entity_name = True
    _attr_translation_key = "websocket"

    def __init__(
        self,
        coordinator: EvonDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        self.coordinator = coordinator
        self._entry = entry
        self._attr_unique_id = f"evon_websocket_{entry.entry_id}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info linking to the hub device."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
        )

    @property
    def is_on(self) -> bool:
        """Return true if WebSocket is connected."""
        return self.coordinator.ws_connected

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.coordinator.last_update_success

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        return {
            "use_websocket": self.coordinator.use_websocket,
        }

    async def async_added_to_hass(self) -> None:
        """Register callbacks when added to hass."""
        self.async_on_remove(self.coordinator.async_add_listener(self._handle_coordinator_update))

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()
