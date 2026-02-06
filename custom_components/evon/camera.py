"""Camera platform for Evon Smart Home integration."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .base_entity import EvonEntity
from .const import CAMERA_IMAGE_CAPTURE_DELAY, DOMAIN, ENTITY_TYPE_CAMERAS, ENTITY_TYPE_SECURITY_DOORS
from .coordinator import EvonDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Evon cameras from a config entry."""
    coordinator: EvonDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    entities: list[Camera] = []

    if coordinator.data and ENTITY_TYPE_CAMERAS in coordinator.data:
        for camera in coordinator.data[ENTITY_TYPE_CAMERAS]:
            entities.append(
                EvonCamera(
                    coordinator,
                    camera["id"],
                    camera["name"],
                    camera.get("room_name", ""),
                    entry,
                )
            )

    if entities:
        async_add_entities(entities)


class EvonCamera(EvonEntity, Camera):
    """Representation of an Evon camera (2N Intercom)."""

    _attr_supported_features = CameraEntityFeature.ON_OFF

    def __init__(
        self,
        coordinator: EvonDataUpdateCoordinator,
        instance_id: str,
        name: str,
        room_name: str,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the camera."""
        EvonEntity.__init__(self, coordinator, instance_id, name, room_name, entry)
        Camera.__init__(self)
        self._attr_name = None  # Use device name
        self._attr_unique_id = f"evon_camera_{instance_id}"
        self._is_streaming = False
        self._last_image: bytes | None = None
        self._image_lock = asyncio.Lock()

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for this camera."""
        return self._build_device_info("Intercom Camera")

    @property
    def is_streaming(self) -> bool:
        """Return true if the camera is streaming."""
        return self._is_streaming

    @property
    def is_on(self) -> bool:
        """Return true if the camera is on."""
        data = self.coordinator.get_entity_data(ENTITY_TYPE_CAMERAS, self._instance_id)
        if data:
            return not data.get("error", False)
        return False

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        attrs = super().extra_state_attributes
        data = self.coordinator.get_entity_data(ENTITY_TYPE_CAMERAS, self._instance_id)
        if data:
            attrs["ip_address"] = data.get("ip_address")
            attrs["error"] = data.get("error", False)

        # Find linked door and get saved pictures
        saved_pictures = self._get_saved_pictures()
        if saved_pictures:
            attrs["saved_pictures"] = saved_pictures
        return attrs

    def _get_saved_pictures(self) -> list[dict[str, Any]]:
        """Get saved pictures from the linked door entity."""
        if not self.coordinator.data or ENTITY_TYPE_SECURITY_DOORS not in self.coordinator.data:
            return []

        # Find the door that links to this camera
        for door in self.coordinator.data[ENTITY_TYPE_SECURITY_DOORS]:
            cam_instance = door.get("cam_instance_name", "")
            # CamInstanceName might be just "Cam" or full "Intercom2N1000.Cam"
            if cam_instance and (cam_instance == self._instance_id or self._instance_id.endswith(f".{cam_instance}")):
                return door.get("saved_pictures", [])
        return []

    async def async_camera_image(self, width: int | None = None, height: int | None = None) -> bytes | None:
        """Return a still image from the camera.

        This triggers a fresh image request via WebSocket and fetches it.
        """
        async with self._image_lock:
            try:
                # Get camera data
                data = self.coordinator.get_entity_data(ENTITY_TYPE_CAMERAS, self._instance_id)
                if not data:
                    return self._last_image

                # Request a new image via WebSocket
                ws_client = self.coordinator._ws_client
                if ws_client and ws_client.is_connected:
                    await self._request_image_via_ws(ws_client)
                    # Wait for image to be captured
                    await asyncio.sleep(CAMERA_IMAGE_CAPTURE_DELAY)
                    # Refresh data to get new image path
                    data = self.coordinator.get_entity_data(ENTITY_TYPE_CAMERAS, self._instance_id)

                # Fetch the image via HTTP
                image_path = data.get("image_path", "")
                if not image_path:
                    return self._last_image

                image = await self._fetch_image(image_path)
                if image:
                    self._last_image = image
                return self._last_image

            except Exception as err:
                _LOGGER.warning("Error getting camera image: %s", err)
                return self._last_image

    async def _request_image_via_ws(self, ws_client: Any) -> None:
        """Request a new image via WebSocket."""
        try:
            await ws_client.set_value(
                self._instance_id,
                "ImageRequest",
                True,
            )
        except Exception as err:
            _LOGGER.debug("Failed to request image via WS: %s", err)

    async def _fetch_image(self, image_path: str) -> bytes | None:
        """Fetch image from Evon server."""
        return await self.coordinator.api.fetch_image(image_path)

    async def async_turn_on(self) -> None:
        """Turn on the camera (start streaming)."""
        self._is_streaming = True
        self.async_write_ha_state()

    async def async_turn_off(self) -> None:
        """Turn off the camera (stop streaming)."""
        self._is_streaming = False
        self.async_write_ha_state()

    async def async_get_saved_picture(self, index: int = 0) -> bytes | None:
        """Get a saved picture by index (0 = most recent).

        Args:
            index: The index of the saved picture (0-based, most recent first).

        Returns:
            The image bytes or None if not available.
        """
        saved_pictures = self._get_saved_pictures()
        if not saved_pictures or index >= len(saved_pictures):
            return None

        picture = saved_pictures[index]
        path = picture.get("path", "")
        if not path:
            return None

        return await self._fetch_image(path)
