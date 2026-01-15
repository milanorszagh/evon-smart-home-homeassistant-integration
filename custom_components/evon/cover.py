"""Cover platform for Evon Smart Home integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.cover import (
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import EvonDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Evon covers from a config entry."""
    coordinator: EvonDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    api = hass.data[DOMAIN][entry.entry_id]["api"]

    entities = []
    if coordinator.data and "blinds" in coordinator.data:
        for blind in coordinator.data["blinds"]:
            entities.append(EvonCover(
                coordinator,
                api,
                blind["id"],
                blind["name"],
                blind.get("room_name", ""),
                entry,
            ))

    async_add_entities(entities)


class EvonCover(CoordinatorEntity[EvonDataUpdateCoordinator], CoverEntity):
    """Representation of an Evon blind/cover."""

    _attr_has_entity_name = True
    _attr_device_class = CoverDeviceClass.BLIND
    _attr_supported_features = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.STOP
        | CoverEntityFeature.SET_POSITION
        | CoverEntityFeature.OPEN_TILT
        | CoverEntityFeature.CLOSE_TILT
        | CoverEntityFeature.SET_TILT_POSITION
    )

    def __init__(
        self,
        coordinator: EvonDataUpdateCoordinator,
        api,
        instance_id: str,
        name: str,
        room_name: str,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the cover."""
        super().__init__(coordinator)
        self._api = api
        self._instance_id = instance_id
        self._attr_name = None  # Use device name
        self._attr_unique_id = f"evon_cover_{instance_id}"
        self._device_name = name
        self._room_name = room_name
        self._entry = entry

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.coordinator.last_update_success and self.coordinator.data is not None

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for this cover."""
        info = DeviceInfo(
            identifiers={(DOMAIN, self._instance_id)},
            name=self._device_name,
            manufacturer="Evon",
            model="Blind",
            via_device=(DOMAIN, self._entry.entry_id),
        )
        if self._room_name:
            info["suggested_area"] = self._room_name
        return info

    @property
    def current_cover_position(self) -> int | None:
        """Return current position of cover (0=closed, 100=open in HA)."""
        data = self.coordinator.get_blind_data(self._instance_id)
        if data:
            # Evon: 0=open, 100=closed
            # Home Assistant: 0=closed, 100=open
            return 100 - data.get("position", 0)
        return None

    @property
    def current_cover_tilt_position(self) -> int | None:
        """Return current tilt position of cover."""
        data = self.coordinator.get_blind_data(self._instance_id)
        if data:
            return data.get("angle", 0)
        return None

    @property
    def is_closed(self) -> bool | None:
        """Return if the cover is closed."""
        position = self.current_cover_position
        if position is not None:
            return position == 0
        return None

    @property
    def is_opening(self) -> bool:
        """Return if the cover is opening."""
        data = self.coordinator.get_blind_data(self._instance_id)
        if data:
            return data.get("is_moving", False)
        return False

    @property
    def is_closing(self) -> bool:
        """Return if the cover is closing."""
        data = self.coordinator.get_blind_data(self._instance_id)
        if data:
            return data.get("is_moving", False)
        return False

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        data = self.coordinator.get_blind_data(self._instance_id)
        attrs = {}
        if data:
            # Evon native position (0=open, 100=closed)
            attrs["evon_position"] = data.get("position", 0)
            attrs["tilt_angle"] = data.get("angle", 0)
            attrs["evon_id"] = self._instance_id
        return attrs

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        await self._api.open_blind(self._instance_id)
        await self.coordinator.async_request_refresh()

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        await self._api.close_blind(self._instance_id)
        await self.coordinator.async_request_refresh()

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        await self._api.stop_blind(self._instance_id)
        await self.coordinator.async_request_refresh()

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Set the cover position."""
        if ATTR_POSITION in kwargs:
            # Convert from HA (0=closed, 100=open) to Evon (0=open, 100=closed)
            position = 100 - kwargs[ATTR_POSITION]
            await self._api.set_blind_position(self._instance_id, position)
            await self.coordinator.async_request_refresh()

    async def async_open_cover_tilt(self, **kwargs: Any) -> None:
        """Open the cover tilt."""
        await self._api.set_blind_tilt(self._instance_id, 100)
        await self.coordinator.async_request_refresh()

    async def async_close_cover_tilt(self, **kwargs: Any) -> None:
        """Close the cover tilt."""
        await self._api.set_blind_tilt(self._instance_id, 0)
        await self.coordinator.async_request_refresh()

    async def async_set_cover_tilt_position(self, **kwargs: Any) -> None:
        """Set the cover tilt position."""
        if ATTR_TILT_POSITION in kwargs:
            await self._api.set_blind_tilt(self._instance_id, kwargs[ATTR_TILT_POSITION])
            await self.coordinator.async_request_refresh()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()
