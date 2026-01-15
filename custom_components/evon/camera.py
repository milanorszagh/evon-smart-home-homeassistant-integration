"""Camera platform for Evon Smart Home integration."""

from __future__ import annotations

import logging

from homeassistant.components.camera import Camera
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import EvonApi
from .const import DOMAIN
from .coordinator import EvonDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Evon cameras from a config entry."""
    coordinator: EvonDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    api: EvonApi = hass.data[DOMAIN][entry.entry_id]["api"]

    entities: list[Camera] = []

    if coordinator.data and "cameras" in coordinator.data:
        for camera in coordinator.data["cameras"]:
            entities.append(
                EvonCamera(
                    coordinator,
                    api,
                    camera["id"],
                    camera["name"],
                    camera.get("room_name", ""),
                    entry,
                )
            )

    async_add_entities(entities)


class EvonCamera(Camera):
    """Representation of an Evon intercom camera."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: EvonDataUpdateCoordinator,
        api: EvonApi,
        instance_id: str,
        name: str,
        room_name: str,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the camera."""
        super().__init__()
        self.coordinator = coordinator
        self._api = api
        self._instance_id = instance_id
        self._device_name = name
        self._room_name = room_name
        self._entry = entry
        self._attr_name = "Camera"
        self._attr_unique_id = f"evon_camera_{instance_id}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for this camera."""
        info = DeviceInfo(
            identifiers={(DOMAIN, self._instance_id)},
            name=self._device_name,
            manufacturer="Evon",
            model="Intercom Camera",
            via_device=(DOMAIN, self._entry.entry_id),
        )
        if self._room_name:
            info["suggested_area"] = self._room_name
        return info

    @property
    def available(self) -> bool:
        """Return True if camera is available."""
        return self.coordinator.get_camera_data(self._instance_id) is not None

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        """Return extra state attributes."""
        data = self.coordinator.get_camera_data(self._instance_id)
        attrs = {"evon_id": self._instance_id}
        if data:
            if data.get("ip_address"):
                attrs["ip_address"] = data["ip_address"]
            if data.get("jpeg_url"):
                attrs["direct_url"] = data["jpeg_url"]
        return attrs

    async def async_camera_image(self, width: int | None = None, height: int | None = None) -> bytes | None:
        """Return a still image from the camera."""
        return await self._api.get_camera_image(self._instance_id)
