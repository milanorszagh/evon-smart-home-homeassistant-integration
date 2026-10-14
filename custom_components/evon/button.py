"""Button platform for Evon Smart Home integration."""

from __future__ import annotations

import asyncio
import logging

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import EvonApi, EvonApiError
from .base_entity import EvonEntity
from .const import (
    CONF_DOOR_OPEN_SECONDS,
    DEFAULT_DOOR_OPEN_SECONDS,
    DOMAIN,
    ENTITY_TYPE_INTERCOMS,
    ENTITY_TYPE_LIGHTS,
    ENTITY_TYPE_SCENES,
    ENTITY_TYPE_SECURITY_DOORS,
    LIGHT_IDENTIFY_ANIMATION_DELAY,
)
from .coordinator import EvonDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Evon buttons from a config entry."""
    coordinator: EvonDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    api: EvonApi = hass.data[DOMAIN][entry.entry_id]["api"]

    entities: list[ButtonEntity] = []

    # Scene buttons
    if coordinator.data and ENTITY_TYPE_SCENES in coordinator.data:
        for scene in coordinator.data[ENTITY_TYPE_SCENES]:
            entities.append(
                EvonSceneButton(
                    coordinator,
                    scene["id"],
                    scene["name"],
                    entry,
                    api,
                )
            )

    # Identify buttons for lights
    if coordinator.data and ENTITY_TYPE_LIGHTS in coordinator.data:
        for light in coordinator.data[ENTITY_TYPE_LIGHTS]:
            entities.append(
                EvonIdentifyButton(
                    coordinator,
                    light["id"],
                    light["name"],
                    light.get("room_name", ""),
                    entry,
                    api,
                )
            )

    # Door-opener buttons for 2N intercoms. Created disabled: opening the front door
    # from Home Assistant must be a deliberate choice made in the entity settings.
    if coordinator.data and ENTITY_TYPE_INTERCOMS in coordinator.data:
        for intercom in coordinator.data[ENTITY_TYPE_INTERCOMS]:
            entities.append(
                EvonIntercomDoorButton(
                    coordinator,
                    intercom["id"],
                    intercom["name"],
                    intercom.get("room_name", ""),
                    entry,
                    api,
                )
            )

    # Open-door buttons on security doors that are linked to an intercom (the door
    # object has no opener of its own; the button pulses the linked intercom).
    if coordinator.data and ENTITY_TYPE_SECURITY_DOORS in coordinator.data:
        for door in coordinator.data[ENTITY_TYPE_SECURITY_DOORS]:
            intercom_id = door.get("intercom_instance_name")
            if not intercom_id:
                continue
            entities.append(
                EvonSecurityDoorOpenButton(
                    coordinator,
                    door["id"],
                    door["name"],
                    door.get("room_name", ""),
                    entry,
                    api,
                    intercom_id,
                )
            )

    if entities:
        async_add_entities(entities)


class EvonSceneButton(EvonEntity, ButtonEntity):
    """Representation of an Evon scene as a button."""

    _attr_icon = "mdi:play-circle"
    _entity_type = ENTITY_TYPE_SCENES

    def __init__(
        self,
        coordinator: EvonDataUpdateCoordinator,
        instance_id: str,
        name: str,
        entry: ConfigEntry,
        api: EvonApi,
    ) -> None:
        """Initialize the scene button."""
        # Scenes don't have room assignments
        super().__init__(coordinator, instance_id, name, "", entry, api)
        self._attr_name = None  # Use device name
        self._attr_unique_id = f"evon_scene_{instance_id}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for this scene."""
        return self._build_device_info("Scene")

    async def async_press(self) -> None:
        """Execute the scene."""
        _LOGGER.debug("Executing scene %s (%s)", self._device_name, self._instance_id)
        try:
            await self._api.execute_scene(self._instance_id)
        except EvonApiError as err:
            raise HomeAssistantError(f"Failed to execute scene {self._device_name}: {err}") from err
        # Refresh coordinator to update any affected entities
        await self.coordinator.async_request_refresh()


class EvonIdentifyButton(EvonEntity, ButtonEntity):
    """Button to identify a light by flashing it."""

    _attr_icon = "mdi:lightbulb-alert"
    _entity_type = ENTITY_TYPE_LIGHTS
    _attr_device_class = ButtonDeviceClass.IDENTIFY
    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "identify"

    def __init__(
        self,
        coordinator: EvonDataUpdateCoordinator,
        instance_id: str,
        name: str,
        room_name: str,
        entry: ConfigEntry,
        api: EvonApi,
    ) -> None:
        """Initialize the identify button."""
        super().__init__(coordinator, instance_id, name, room_name, entry, api)
        self._attr_unique_id = f"evon_identify_{instance_id}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for this light."""
        return self._build_device_info("Light")

    async def async_press(self) -> None:
        """Flash the light to identify it (off -> on -> restore)."""
        _LOGGER.debug("Identifying light %s (%s)", self._device_name, self._instance_id)
        try:
            # Get current state for restoration
            data = self._get_data()
            was_on = data.get("is_on", False) if data else False
            original_brightness = max(0, min(100, data.get("brightness", 100))) if data else 100

            # Always do off -> on -> restore (works regardless of state detection)
            await self._api.turn_off_light(self._instance_id)
            await asyncio.sleep(LIGHT_IDENTIFY_ANIMATION_DELAY)  # Wait for fade-out

            await self._api.turn_on_light(self._instance_id)
            await asyncio.sleep(LIGHT_IDENTIFY_ANIMATION_DELAY)  # Wait for fade-in

            # Restore original state
            if not was_on:
                await self._api.turn_off_light(self._instance_id)
            elif original_brightness != 100:
                await self._api.set_light_brightness(self._instance_id, original_brightness)

        except EvonApiError as err:
            raise HomeAssistantError(f"Failed to identify light {self._device_name}: {err}") from err


class EvonIntercomDoorButton(EvonEntity, ButtonEntity):
    """Button that opens the door of a 2N intercom (a ``SwitchOnFor`` pulse)."""

    _attr_icon = "mdi:door-open"
    _entity_type = ENTITY_TYPE_INTERCOMS
    _attr_translation_key = "open_door"
    # Opening the front door from HA must be enabled deliberately in the entity settings
    _attr_entity_registry_enabled_default = False

    def __init__(
        self,
        coordinator: EvonDataUpdateCoordinator,
        instance_id: str,
        name: str,
        room_name: str,
        entry: ConfigEntry,
        api: EvonApi,
    ) -> None:
        """Initialize the door-opener button."""
        super().__init__(coordinator, instance_id, name, room_name, entry, api)
        self._attr_unique_id = f"evon_open_door_{instance_id}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for this intercom."""
        return self._build_device_info("Intercom")

    @property
    def _intercom_id(self) -> str:
        """The intercom whose SwitchOnFor pulses the door release."""
        return self._instance_id

    def _pulse_seconds(self) -> int:
        """Pulse length from the integration options (door_open_seconds)."""
        return int(self._entry.options.get(CONF_DOOR_OPEN_SECONDS, DEFAULT_DOOR_OPEN_SECONDS))

    async def async_press(self) -> None:
        """Open the door (SwitchOnFor pulse on the intercom)."""
        seconds = self._pulse_seconds()
        _LOGGER.info("Opening door %s for %ss via intercom %s", self._device_name, seconds, self._intercom_id)
        try:
            await self._api.open_intercom_door(self._intercom_id, seconds)
        except EvonApiError as err:
            raise HomeAssistantError(f"Failed to open door {self._device_name}: {err}") from err


class EvonSecurityDoorOpenButton(EvonIntercomDoorButton):
    """Open-door button on a Security.Door, pulsing the intercom linked to it.

    ``Security.Door`` objects have no opener of their own; ``IntercomInstanceName``
    names the intercom whose ``SwitchOnFor`` releases the door.
    """

    _entity_type = ENTITY_TYPE_SECURITY_DOORS

    def __init__(
        self,
        coordinator: EvonDataUpdateCoordinator,
        instance_id: str,
        name: str,
        room_name: str,
        entry: ConfigEntry,
        api: EvonApi,
        intercom_id: str,
    ) -> None:
        """Initialize the door-opener button for a security door."""
        super().__init__(coordinator, instance_id, name, room_name, entry, api)
        self._linked_intercom_id = intercom_id

    @property
    def _intercom_id(self) -> str:
        return self._linked_intercom_id

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for this security door."""
        return self._build_device_info("Security Door")
