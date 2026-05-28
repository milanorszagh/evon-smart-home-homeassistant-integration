"""Base entity for Evon Smart Home integration."""

from __future__ import annotations

import logging
import time
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import EvonApi
from .const import DOMAIN, OPTIMISTIC_STATE_TIMEOUT, POST_COMMAND_QUIESCE_PERIOD
from .coordinator import EvonDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


class EntityData:
    """Descriptor that reads a field from coordinator entity data.

    Eliminates boilerplate ``@property`` methods that fetch a single key
    from the coordinator. Requires the owning class to define
    ``_entity_type`` and inherit from ``EvonEntity``.

    Usage::

        class EvonValveSensor(EvonEntity, BinarySensorEntity):
            _entity_type = ENTITY_TYPE_VALVES
            is_on = EntityData("is_open", default=False)
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
        # Post-command recheck state — see _schedule_post_command_recheck.
        self._data_snapshot_at_command: dict[str, Any] | None = None
        self._recheck_cancel: CALLBACK_TYPE | None = None

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.coordinator.last_update_success and self.coordinator.data is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes with evon_id and debug info."""
        attrs: dict[str, Any] = {
            "evon_id": self._instance_id,
            "integration": DOMAIN,
        }
        if self._room_name:
            attrs["room"] = self._room_name
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
        """Clear optimistic state if the 30s backstop timeout has expired."""
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

    def _schedule_post_command_recheck(self) -> None:
        """Schedule an HTTP recheck for POST_COMMAND_QUIESCE_PERIOD seconds from now.

        Captures the current entity data dict identity so that subsequent
        coordinator updates touching this entity can cancel the recheck
        (see _cancel_post_command_recheck_if_data_changed).

        If a recheck is already pending, the prior one is cancelled first
        (newer command takes precedence).
        """
        if self._recheck_cancel is not None:
            self._recheck_cancel()
        self._data_snapshot_at_command = self._get_data()
        self._recheck_cancel = async_call_later(
            self.hass,
            POST_COMMAND_QUIESCE_PERIOD,
            self._do_post_command_recheck,
        )

    def _cancel_post_command_recheck_if_data_changed(self) -> None:
        """Cancel the pending recheck if this entity's data dict has been replaced.

        Coordinator WS updates atomically replace the entity's dict in
        _data_index/entities_list (coordinator/__init__.py). HTTP polls
        rebuild self.data wholesale. In both cases the dict identity
        changes, which is our signal that a fresh update arrived for this
        entity and a manual recheck is no longer needed.
        """
        if self._recheck_cancel is None:
            return
        if self._get_data() is not self._data_snapshot_at_command:
            self._recheck_cancel()
            self._recheck_cancel = None
            self._data_snapshot_at_command = None

    def _cleanup_post_command_recheck(self) -> None:
        """Cancel any pending recheck (call from async_will_remove_from_hass)."""
        if self._recheck_cancel is not None:
            self._recheck_cancel()
            self._recheck_cancel = None
        self._data_snapshot_at_command = None

    async def _do_post_command_recheck(self, _now: Any) -> None:
        """Fire the HTTP recheck — only reached if no WS event arrived in time."""
        self._recheck_cancel = None
        self._data_snapshot_at_command = None
        _LOGGER.info(
            "Post-command recheck firing for %s — no WS update arrived within %.1fs",
            self._instance_id,
            POST_COMMAND_QUIESCE_PERIOD,
        )
        await self.coordinator.async_request_refresh()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()
