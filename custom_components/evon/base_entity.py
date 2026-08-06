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

# Sentinel distinguishing "no snapshot passed" from a legitimate None snapshot
# (None means "no WS update ever recorded for this entity").
_SNAPSHOT_UNSET: Any = object()


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
        # Holds whatever _recheck_snapshot() returns (default: a WS-update
        # timestamp; select overrides return a state string).
        self._data_snapshot_at_command: Any = None
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

    def _recheck_snapshot(self) -> Any:
        """Return a value representing WS liveness for this entity at command time.

        Default: the coordinator's per-entity WS-update timestamp. A genuine WS
        update advances it; an HTTP poll rebuild does NOT. Comparing timestamps
        (see `_recheck_data_changed`) means only real WS liveness cancels the
        recheck — a stale in-flight poll completing during the quiesce window
        cannot defeat the safety net (RV-D1).

        Subclasses whose state/liveness lives outside the WS-timestamp map (e.g.
        selects reading `coordinator.get_active_home_state()`) override this AND
        `_recheck_data_changed`.
        """
        if self._entity_type is None:
            return None
        return self.coordinator.get_ws_update_timestamp(self._entity_type, self._instance_id)

    def _recheck_data_changed(self, current: Any, snapshot: Any) -> bool:
        """Return True if a genuine WS update for this entity arrived since the command.

        Default compares WS-update timestamps: True only when a newer timestamp
        exists. ``None == None`` (the entity never received a WS update) is False,
        so the recheck stays armed and fires the fallback HTTP poll. Subclasses
        overriding `_recheck_snapshot` to return scalar values compare by `!=`.
        """
        return current is not None and current != snapshot

    def _schedule_post_command_recheck(self, snapshot_before_command: Any = _SNAPSHOT_UNSET) -> None:
        """Schedule an HTTP recheck for POST_COMMAND_QUIESCE_PERIOD seconds from now.

        Command methods should capture ``self._recheck_snapshot()`` BEFORE
        awaiting the API call and pass it here. A WS confirmation often lands
        while the command await is still in flight (WS-control mode races the
        CallMethod response); comparing against the pre-await snapshot detects
        that and skips arming the safety net — WS is proven alive, so the push
        path is trusted. Without this, single-event devices (relays) would
        fire a redundant full poll 5s after every toggle, since their one
        confirmation always precedes scheduling and nothing arrives later to
        cancel the recheck.

        Called without an argument, the snapshot is captured at schedule time.

        If a recheck is already pending, the prior one is cancelled first
        (newer command takes precedence).
        """
        if self._recheck_cancel is not None:
            self._recheck_cancel()
            self._recheck_cancel = None
        if snapshot_before_command is not _SNAPSHOT_UNSET and self._recheck_data_changed(
            self._recheck_snapshot(), snapshot_before_command
        ):
            # A WS event for this entity arrived while the command was in
            # flight — same liveness criterion as the cancel-on-update path.
            self._data_snapshot_at_command = None
            return
        self._data_snapshot_at_command = (
            self._recheck_snapshot() if snapshot_before_command is _SNAPSHOT_UNSET else snapshot_before_command
        )
        self._recheck_cancel = async_call_later(
            self.hass,
            POST_COMMAND_QUIESCE_PERIOD,
            self._do_post_command_recheck,
        )

    def _cancel_post_command_recheck_if_data_changed(self) -> None:
        """Cancel the pending recheck if a genuine WS update arrived for this entity.

        The default `_recheck_data_changed` compares the coordinator's per-entity
        WS-update timestamp: only a real WebSocket update (proving WS is alive)
        cancels the recheck. An HTTP poll rebuild does NOT — otherwise a stale
        in-flight poll completing during the quiesce window would defeat the
        safety net exactly when it's needed (RV-D1). Selects override the
        snapshot/compare to use their coordinator state value instead.
        """
        if self._recheck_cancel is None:
            return
        if self._recheck_data_changed(self._recheck_snapshot(), self._data_snapshot_at_command):
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
        # In HTTP-only mode the recheck IS the confirmation mechanism and fires
        # after every command by design — that's DEBUG. With WS enabled, firing
        # means the push path went quiet, which is worth an INFO.
        level = logging.INFO if getattr(self.coordinator, "use_websocket", False) else logging.DEBUG
        _LOGGER.log(
            level,
            "Post-command recheck firing for %s — no WS update arrived within %.1fs",
            self._instance_id,
            POST_COMMAND_QUIESCE_PERIOD,
        )
        await self.coordinator.async_request_refresh()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()
