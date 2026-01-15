"""Base entity for Evon Smart Home integration."""
from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import EvonApi
from .const import DOMAIN
from .coordinator import EvonDataUpdateCoordinator


class EvonEntity(CoordinatorEntity[EvonDataUpdateCoordinator]):
    """Base class for Evon entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: EvonDataUpdateCoordinator,
        instance_id: str,
        name: str,
        room_name: str,
        entry: ConfigEntry,
        api: EvonApi | None = None,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._api = api
        self._instance_id = instance_id
        self._device_name = name
        self._room_name = room_name
        self._entry = entry

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.coordinator.last_update_success and self.coordinator.data is not None

    def _build_device_info(self, model: str) -> DeviceInfo:
        """Build device info dictionary."""
        info = DeviceInfo(
            identifiers={(DOMAIN, self._instance_id)},
            name=self._device_name,
            manufacturer="Evon",
            model=model,
            via_device=(DOMAIN, self._entry.entry_id),
        )
        if self._room_name:
            info["suggested_area"] = self._room_name
        return info

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()
