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
from .const import DOMAIN, ENTITY_TYPE_LIGHTS, ENTITY_TYPE_SCENES, LIGHT_IDENTIFY_ANIMATION_DELAY
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

    entities = []

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

    if entities:
        async_add_entities(entities)


class EvonSceneButton(EvonEntity, ButtonEntity):
    """Representation of an Evon scene as a button."""

    _attr_icon = "mdi:play-circle"

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
    _attr_device_class = ButtonDeviceClass.IDENTIFY
    _attr_entity_category = EntityCategory.CONFIG

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
        self._attr_name = "Identify"
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
            data = self.coordinator.get_entity_data(ENTITY_TYPE_LIGHTS, self._instance_id)
            was_on = data.get("is_on", False) if data else False
            original_brightness = data.get("brightness", 100) if data else 100

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
