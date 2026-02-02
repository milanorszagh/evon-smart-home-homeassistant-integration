"""Image platform for Evon Smart Home integration - doorbell snapshots."""

from __future__ import annotations

from datetime import datetime
import logging
from typing import Any

import aiohttp
from homeassistant.components.image import ImageEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import EvonDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

# Maximum number of snapshot entities to create
MAX_SNAPSHOTS = 10


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Evon doorbell snapshot images from a config entry."""
    coordinator: EvonDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    entities: list[ImageEntity] = []

    # Find security doors with saved pictures
    if coordinator.data and "security_doors" in coordinator.data:
        for door in coordinator.data["security_doors"]:
            saved_pictures = door.get("saved_pictures", [])

            if not saved_pictures:
                continue

            door_name = door.get("name", "Doorbell")

            # Create image entities for saved pictures (up to MAX_SNAPSHOTS)
            for idx in range(min(len(saved_pictures), MAX_SNAPSHOTS)):
                entities.append(
                    EvonDoorbellSnapshot(
                        coordinator,
                        door["id"],
                        door_name,
                        idx,
                        entry,
                    )
                )

    if entities:
        async_add_entities(entities)


class EvonDoorbellSnapshot(ImageEntity):
    """Representation of a doorbell snapshot image."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: EvonDataUpdateCoordinator,
        door_id: str,
        door_name: str,
        index: int,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the snapshot image."""
        super().__init__(coordinator.hass)
        self.coordinator = coordinator
        self._door_id = door_id
        self._door_name = door_name
        self._index = index
        self._entry = entry
        self._attr_unique_id = f"evon_snapshot_{door_id}_{index}"
        self._cached_image: bytes | None = None
        self._cached_path: str | None = None

    @property
    def name(self) -> str:
        """Return the name of the image entity."""
        return f"Snapshot {self._index + 1}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info - create a dedicated snapshots device."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._entry.entry_id}_snapshots_{self._door_id}")},
            name=f"{self._door_name} Snapshots",
            manufacturer="Evon",
            model="Doorbell Snapshots",
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        attrs: dict[str, Any] = {
            "index": self._index,
            "door_id": self._door_id,
        }
        snapshot = self._get_snapshot()
        if snapshot:
            ts = snapshot.get("timestamp")
            if ts:
                attrs["timestamp"] = ts
                attrs["datetime"] = datetime.fromtimestamp(ts / 1000).isoformat()
            attrs["path"] = snapshot.get("path", "")
        return attrs

    @property
    def image_last_updated(self) -> datetime | None:
        """Return when the image was last updated."""
        snapshot = self._get_snapshot()
        if snapshot:
            ts = snapshot.get("timestamp")
            if ts:
                return datetime.fromtimestamp(ts / 1000)
        return None

    def _get_snapshot(self) -> dict[str, Any] | None:
        """Get the snapshot data for this index."""
        if not self.coordinator.data or "security_doors" not in self.coordinator.data:
            return None

        for door in self.coordinator.data["security_doors"]:
            if door.get("id") == self._door_id:
                saved_pictures = door.get("saved_pictures", [])
                if self._index < len(saved_pictures):
                    return saved_pictures[self._index]
        return None

    async def async_image(self) -> bytes | None:
        """Return the image bytes."""
        snapshot = self._get_snapshot()
        if not snapshot:
            return None

        path = snapshot.get("path", "")
        if not path:
            return None

        # Use cached image if path hasn't changed
        if path == self._cached_path and self._cached_image:
            return self._cached_image

        # Fetch the image from Evon
        try:
            session = async_get_clientsession(self.hass)
            api = self.coordinator.api

            url = f"{api._host}{path}"
            token = await api._ensure_token()
            cookies = {"token": token}

            async with session.get(url, cookies=cookies, timeout=10) as resp:
                if resp.status == 200:
                    self._cached_image = await resp.read()
                    self._cached_path = path
                    return self._cached_image
                _LOGGER.debug("Failed to fetch snapshot: HTTP %d", resp.status)
        except aiohttp.ClientError as err:
            _LOGGER.debug("Failed to fetch snapshot: %s", err)
        except Exception as err:
            _LOGGER.warning("Unexpected error fetching snapshot: %s", err)

        return self._cached_image
