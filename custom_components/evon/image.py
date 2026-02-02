"""Image platform for Evon Smart Home integration - doorbell snapshots."""

from __future__ import annotations

from datetime import datetime
import logging
from typing import Any

from homeassistant.components.image import ImageEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import EvonDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

# Maximum number of snapshot entities to create (always create all for consistency)
MAX_SNAPSHOTS = 10


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Evon doorbell snapshot images from a config entry."""
    coordinator: EvonDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    entities: list[ImageEntity] = []

    # Find security doors - create MAX_SNAPSHOTS entities for each door
    # This ensures consistent entity count across reloads
    if coordinator.data and "security_doors" in coordinator.data:
        for door in coordinator.data["security_doors"]:
            door_name = door.get("name", "Doorbell")

            # Always create MAX_SNAPSHOTS entities per door for consistency
            for idx in range(MAX_SNAPSHOTS):
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


class EvonDoorbellSnapshot(CoordinatorEntity[EvonDataUpdateCoordinator], ImageEntity):
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
        # Initialize CoordinatorEntity first
        CoordinatorEntity.__init__(self, coordinator)
        # Initialize ImageEntity with hass
        ImageEntity.__init__(self, coordinator.hass)
        self._door_id = door_id
        self._door_name = door_name
        self._index = index
        self._entry = entry
        self._attr_unique_id = f"evon_snapshot_{door_id}_{index}"
        self._cached_image: bytes | None = None
        self._cached_path: str | None = None

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        # Entity is available if coordinator is available AND this snapshot index exists
        if not self.coordinator.last_update_success:
            return False
        snapshot = self._get_snapshot()
        return snapshot is not None

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

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        # Check if the snapshot path changed - if so, invalidate cache
        snapshot = self._get_snapshot()
        if snapshot:
            new_path = snapshot.get("path", "")
            if new_path != self._cached_path:
                # Path changed, invalidate cache so next image request fetches new image
                self._cached_image = None
                self._cached_path = None
        self.async_write_ha_state()

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

        # Fetch the image from Evon using shared API method
        image = await self.coordinator.api.fetch_image(path)
        if image:
            self._cached_image = image
            self._cached_path = path
            return self._cached_image

        return self._cached_image
