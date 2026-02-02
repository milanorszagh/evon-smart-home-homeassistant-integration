"""Binary sensor platform for Evon Smart Home integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .base_entity import EvonEntity
from .const import DOMAIN
from .coordinator import EvonDataUpdateCoordinator


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

    # Create security door sensors
    if coordinator.data and "security_doors" in coordinator.data:
        for door in coordinator.data["security_doors"]:
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
    if coordinator.data and "intercoms" in coordinator.data:
        for intercom in coordinator.data["intercoms"]:
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

    if entities:
        async_add_entities(entities)


class EvonValveSensor(EvonEntity, BinarySensorEntity):
    """Representation of an Evon valve sensor."""

    _attr_icon = "mdi:valve"
    _attr_device_class = BinarySensorDeviceClass.OPENING
    _attr_entity_category = EntityCategory.DIAGNOSTIC

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
        attrs = super().extra_state_attributes
        data = self.coordinator.get_entity_data("valves", self._instance_id)
        if data:
            attrs["valve_type"] = data.get("valve_type")
        return attrs


class EvonSecurityDoorSensor(EvonEntity, BinarySensorEntity):
    """Representation of an Evon security door sensor."""

    _attr_icon = "mdi:door"
    _attr_device_class = BinarySensorDeviceClass.DOOR

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

    @property
    def is_on(self) -> bool | None:
        """Return true if the door is open."""
        data = self.coordinator.get_entity_data("security_doors", self._instance_id)
        if data:
            return data.get("is_open", False)
        return None


class EvonSecurityDoorCallSensor(EvonEntity, BinarySensorEntity):
    """Representation of an Evon security door call in progress sensor."""

    _attr_icon = "mdi:phone-ring"
    _attr_device_class = BinarySensorDeviceClass.OCCUPANCY

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
        self._attr_name = "Call In Progress"
        self._attr_unique_id = f"evon_security_door_{instance_id}_call"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for this sensor."""
        return self._build_device_info("Security Door")

    @property
    def is_on(self) -> bool | None:
        """Return true if a call is in progress."""
        data = self.coordinator.get_entity_data("security_doors", self._instance_id)
        if data:
            return data.get("call_in_progress", False)
        return None


class EvonIntercomDoorSensor(EvonEntity, BinarySensorEntity):
    """Representation of an Evon intercom door sensor."""

    _attr_icon = "mdi:doorbell-video"
    _attr_device_class = BinarySensorDeviceClass.DOOR

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
    def is_on(self) -> bool | None:
        """Return true if the door is open."""
        data = self.coordinator.get_entity_data("intercoms", self._instance_id)
        if data:
            return data.get("is_door_open", False)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        attrs = super().extra_state_attributes
        data = self.coordinator.get_entity_data("intercoms", self._instance_id)
        if data:
            attrs["doorbell_triggered"] = data.get("doorbell_triggered", False)
            attrs["door_open_triggered"] = data.get("door_open_triggered", False)
        return attrs


class EvonIntercomConnectionSensor(EvonEntity, BinarySensorEntity):
    """Representation of an Evon intercom connection status sensor."""

    _attr_icon = "mdi:lan-connect"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

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
        self._attr_name = "Connection"
        self._attr_unique_id = f"evon_intercom_{instance_id}_connection"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for this sensor."""
        return self._build_device_info("Intercom")

    @property
    def is_on(self) -> bool | None:
        """Return true if the intercom is connected (not lost)."""
        data = self.coordinator.get_entity_data("intercoms", self._instance_id)
        if data:
            # is_on = connected (inverse of connection_lost)
            return not data.get("connection_lost", False)
        return None
