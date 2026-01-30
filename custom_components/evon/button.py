"""Button platform for Evon Smart Home integration."""

from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import EvonApi, EvonApiError
from .base_entity import EvonEntity
from .const import DOMAIN
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
    if coordinator.data and "scenes" in coordinator.data:
        for scene in coordinator.data["scenes"]:
            entities.append(
                EvonSceneButton(
                    coordinator,
                    scene["id"],
                    scene["name"],
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
