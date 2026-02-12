"""Base entity for Evon Smart Home integration."""

from __future__ import annotations

import time
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import EvonApi
from .const import DOMAIN, OPTIMISTIC_STATE_TIMEOUT
from .coordinator import EvonDataUpdateCoordinator


class entity_data:
    """Descriptor that reads a field from coordinator entity data.

    Eliminates boilerplate ``@property`` methods that fetch a single key
    from the coordinator. Requires the owning class to define
    ``_entity_type`` and inherit from ``EvonEntity``.

    Usage::

        class EvonValveSensor(EvonEntity, BinarySensorEntity):
            _entity_type = ENTITY_TYPE_VALVES
            is_on = entity_data("is_open", default=False)
    """

    __slots__ = ("key", "default", "transform")

    def __init__(
        self,
        key: str,
        *,
        default: Any = None,
        transform: Any = None,
    ) -> None:
        self.key = key
        self.default = default
        self.transform = transform

    def __get__(self, obj: Any, objtype: Any = None) -> Any:
        if obj is None:
            return self
        data = obj._get_data()
        if data is None:
            return None
        value = data.get(self.key, self.default)
        if self.transform is not None and value is not None:
            return self.transform(value)
        return value


class EvonEntity(CoordinatorEntity[EvonDataUpdateCoordinator]):
    """Base class for Evon entities."""

    _attr_has_entity_name = True
    _entity_type: str | None = None

    def _get_data(self) -> dict[str, Any] | None:
        """Get this entity's data from the coordinator."""
        if self._entity_type is None:
            return None
        return self.coordinator.get_entity_data(self._entity_type, self._instance_id)

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
        self._optimistic_state_set_at: float | None = None

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.coordinator.last_update_success and self.coordinator.data is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes with evon_id and debug info."""
        attrs = {
            "evon_id": self._instance_id,
            "integration": DOMAIN,
        }
        # Add room name if available
        if self._room_name:
            attrs["room"] = self._room_name
        # Add WebSocket connection status
        if hasattr(self.coordinator, "ws_connected"):
            attrs["websocket_connected"] = self.coordinator.ws_connected
        return attrs

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

    def _clear_optimistic_state_if_expired(self) -> None:
        """Clear optimistic state if timeout has expired.

        Subclasses that use optimistic state should initialize
        ``_optimistic_state_set_at`` to ``None`` and call
        ``_set_optimistic_timestamp()`` when setting optimistic values.
        Override ``_reset_optimistic_state()`` to clear entity-specific fields.
        """
        if (
            self._optimistic_state_set_at is not None
            and time.monotonic() - self._optimistic_state_set_at > OPTIMISTIC_STATE_TIMEOUT
        ):
            self._reset_optimistic_state()
            self._optimistic_state_set_at = None

    def _reset_optimistic_state(self) -> None:
        """Reset entity-specific optimistic state fields. Override in subclasses."""

    def _set_optimistic_timestamp(self) -> None:
        """Record when optimistic state was set."""
        self._optimistic_state_set_at = time.monotonic()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()
