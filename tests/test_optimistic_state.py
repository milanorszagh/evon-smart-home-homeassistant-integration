"""Tests for optimistic state timeout (C-L6)."""

from __future__ import annotations

import sys
import time
from unittest.mock import MagicMock, patch

import pytest

from custom_components.evon.const import (
    OPTIMISTIC_STATE_TIMEOUT,
    POST_COMMAND_QUIESCE_PERIOD,
)


class TestOptimisticStateTimeout:
    """Test optimistic state expiry at the timeout boundary."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self):
        """Set up mocks for Home Assistant modules."""
        modules_to_mock = {
            "homeassistant": MagicMock(),
            "homeassistant.config_entries": MagicMock(),
            "homeassistant.core": MagicMock(),
            "homeassistant.helpers": MagicMock(),
            "homeassistant.helpers.device_registry": MagicMock(),
            "homeassistant.helpers.update_coordinator": MagicMock(),
        }

        class MockCoordinatorEntity:
            def __init__(self, coordinator):
                self.coordinator = coordinator

            def __class_getitem__(cls, item):
                return cls

        modules_to_mock["homeassistant.helpers.update_coordinator"].CoordinatorEntity = MockCoordinatorEntity
        modules_to_mock["homeassistant.helpers.device_registry"].DeviceInfo = dict
        modules_to_mock["homeassistant.core"].callback = lambda f: f

        with patch.dict(sys.modules, modules_to_mock):
            yield

    def _make_entity(self):
        """Create a minimal EvonEntity for testing."""
        from custom_components.evon.base_entity import EvonEntity

        coordinator = MagicMock()
        coordinator.last_update_success = True
        coordinator.data = {"lights": []}
        entry = MagicMock()
        entry.entry_id = "test_entry"

        entity = EvonEntity(coordinator, "light_1", "Test Light", "", entry)
        return entity

    def test_optimistic_state_not_expired_before_timeout(self):
        """Test that optimistic state persists before timeout."""
        entity = self._make_entity()
        entity._optimistic_state_set_at = time.monotonic()

        # Should NOT clear (just set, well within timeout)
        entity._clear_optimistic_state_if_expired()
        assert entity._optimistic_state_set_at is not None

    def test_optimistic_state_expired_after_timeout(self):
        """Test that optimistic state is cleared after timeout."""
        entity = self._make_entity()
        # Set timestamp to OPTIMISTIC_STATE_TIMEOUT + 1 seconds ago
        entity._optimistic_state_set_at = time.monotonic() - OPTIMISTIC_STATE_TIMEOUT - 1

        entity._clear_optimistic_state_if_expired()
        assert entity._optimistic_state_set_at is None

    def test_optimistic_state_not_expired_at_exact_boundary(self):
        """Test that optimistic state is NOT cleared at exactly the timeout.

        The condition is > (strictly greater than), so at exactly the timeout
        the state should still persist.
        """
        entity = self._make_entity()
        # Use a fixed reference time to avoid clock drift between set and check
        fixed_now = 1000.0
        entity._optimistic_state_set_at = fixed_now - OPTIMISTIC_STATE_TIMEOUT

        with patch("time.monotonic", return_value=fixed_now):
            entity._clear_optimistic_state_if_expired()
        # At exactly the boundary, > means NOT expired
        assert entity._optimistic_state_set_at is not None

    def test_optimistic_state_expired_just_past_boundary(self):
        """Test that optimistic state IS cleared just past the timeout."""
        entity = self._make_entity()
        entity._optimistic_state_set_at = time.monotonic() - OPTIMISTIC_STATE_TIMEOUT - 0.001

        entity._clear_optimistic_state_if_expired()
        assert entity._optimistic_state_set_at is None

    def test_no_crash_when_no_optimistic_state(self):
        """Test that clearing with no optimistic state is a no-op."""
        entity = self._make_entity()
        assert entity._optimistic_state_set_at is None

        entity._clear_optimistic_state_if_expired()
        assert entity._optimistic_state_set_at is None

    def test_reset_optimistic_state_called_on_expiry(self):
        """Test that _reset_optimistic_state is called when expired."""
        entity = self._make_entity()
        entity._optimistic_state_set_at = time.monotonic() - OPTIMISTIC_STATE_TIMEOUT - 1

        reset_called = False
        original_reset = entity._reset_optimistic_state

        def mock_reset():
            nonlocal reset_called
            reset_called = True
            original_reset()

        entity._reset_optimistic_state = mock_reset
        entity._clear_optimistic_state_if_expired()

        assert reset_called
        assert entity._optimistic_state_set_at is None

    def test_set_optimistic_timestamp(self):
        """Test that _set_optimistic_timestamp records current time."""
        entity = self._make_entity()
        assert entity._optimistic_state_set_at is None

        before = time.monotonic()
        entity._set_optimistic_timestamp()
        after = time.monotonic()

        assert entity._optimistic_state_set_at is not None
        assert before <= entity._optimistic_state_set_at <= after


class TestOptimisticStateConstants:
    """Test optimistic state timing constants are reasonable."""

    def test_timeout_is_30_seconds(self):
        """Test OPTIMISTIC_STATE_TIMEOUT is 30 seconds."""
        assert OPTIMISTIC_STATE_TIMEOUT == 30.0

    def test_quiesce_period_is_5_seconds(self):
        """Test POST_COMMAND_QUIESCE_PERIOD is 5 seconds."""
        assert POST_COMMAND_QUIESCE_PERIOD == 5.0

    def test_quiesce_less_than_timeout(self):
        """Test that quiesce period is less than timeout backstop."""
        assert POST_COMMAND_QUIESCE_PERIOD < OPTIMISTIC_STATE_TIMEOUT


class TestPostCommandRecheck:
    """Test scheduled HTTP recheck after device commands.

    These tests patch `custom_components.evon.base_entity.async_call_later`
    directly rather than mocking sys.modules — that lets the tests cooperate
    with the rest of the suite without forcing entity modules to reload
    (which would break downstream tests holding references to the old
    `EvonEntity` class).
    """

    def _make_entity_with_data(self, data_dict):
        """Build a minimal EvonEntity whose _get_data returns data_dict."""
        from custom_components.evon.base_entity import EvonEntity

        coordinator = MagicMock()
        coordinator.last_update_success = True
        coordinator.async_request_refresh = MagicMock()
        entry = MagicMock()
        entry.entry_id = "test_entry"

        entity = EvonEntity(coordinator, "light_1", "Test Light", "", entry)
        entity._entity_type = "lights"
        entity.hass = MagicMock()
        entity._get_data = lambda: data_dict
        # Default: no WS update recorded for this entity yet.
        coordinator.get_ws_update_timestamp = MagicMock(return_value=None)
        return entity

    def test_schedule_recheck_captures_snapshot(self):
        """Scheduling stores the current WS-liveness snapshot for later comparison."""
        entity = self._make_entity_with_data({"id": "light_1", "is_on": False})
        entity.coordinator.get_ws_update_timestamp = MagicMock(return_value=42.0)

        with patch("custom_components.evon.base_entity.async_call_later", return_value=MagicMock()):
            entity._schedule_post_command_recheck()

        assert entity._data_snapshot_at_command == 42.0
        assert entity._recheck_cancel is not None

    def test_schedule_recheck_calls_async_call_later_with_quiesce_period(self):
        """Scheduling uses POST_COMMAND_QUIESCE_PERIOD as the delay."""
        from custom_components.evon.const import POST_COMMAND_QUIESCE_PERIOD

        entity = self._make_entity_with_data({"is_on": True})

        with patch("custom_components.evon.base_entity.async_call_later") as mock_call_later:
            mock_call_later.return_value = MagicMock()
            entity._schedule_post_command_recheck()

        mock_call_later.assert_called_once()
        args = mock_call_later.call_args[0]
        assert args[0] is entity.hass
        assert args[1] == POST_COMMAND_QUIESCE_PERIOD

    def test_cancel_recheck_does_nothing_when_no_ws_update(self):
        """With no WS update recorded for the entity, the recheck is preserved."""
        entity = self._make_entity_with_data({"is_on": False})
        entity.coordinator.get_ws_update_timestamp = MagicMock(return_value=None)
        cancel_handle = MagicMock()

        with patch("custom_components.evon.base_entity.async_call_later", return_value=cancel_handle):
            entity._schedule_post_command_recheck()

        entity._cancel_post_command_recheck_if_data_changed()

        cancel_handle.assert_not_called()
        assert entity._recheck_cancel is not None

    def test_stale_poll_rebuild_does_not_cancel_recheck(self):
        """RV-D1: a completed HTTP poll (no WS update for this entity) must NOT cancel
        the recheck. A stale in-flight poll rebuilds the entity dict (new identity)
        but does not advance the per-entity WS timestamp, so the safety net stays
        armed and fires the fallback refresh."""
        entity = self._make_entity_with_data({"is_on": False})
        entity.coordinator.get_ws_update_timestamp = MagicMock(return_value=None)
        cancel_handle = MagicMock()

        with patch("custom_components.evon.base_entity.async_call_later", return_value=cancel_handle):
            entity._schedule_post_command_recheck()

        # Poll rebuild: a brand-new dict (different identity) with no WS update.
        entity._get_data = lambda: {"is_on": False}
        entity._cancel_post_command_recheck_if_data_changed()

        cancel_handle.assert_not_called()
        assert entity._recheck_cancel is not None

    def test_cancel_recheck_if_data_changed_safe_when_no_pending(self):
        """Calling with no pending recheck is a safe no-op."""
        entity = self._make_entity_with_data({"is_on": False})
        entity._cancel_post_command_recheck_if_data_changed()

    def test_cleanup_cancels_pending_recheck(self):
        """Cleanup helper cancels any pending recheck (for entity removal)."""
        entity = self._make_entity_with_data({"is_on": False})
        cancel_handle = MagicMock()

        with patch("custom_components.evon.base_entity.async_call_later", return_value=cancel_handle):
            entity._schedule_post_command_recheck()

        entity._cleanup_post_command_recheck()

        cancel_handle.assert_called_once()
        assert entity._recheck_cancel is None
        assert entity._data_snapshot_at_command is None

    def test_cleanup_safe_when_no_pending(self):
        """Cleanup is a safe no-op when nothing is scheduled."""
        entity = self._make_entity_with_data({"is_on": False})
        entity._cleanup_post_command_recheck()

    def test_do_recheck_calls_coordinator_refresh(self):
        """The timer callback triggers coordinator.async_request_refresh."""
        import asyncio

        entity = self._make_entity_with_data({"is_on": False})

        async def refresh():
            pass

        entity.coordinator.async_request_refresh = MagicMock(return_value=refresh())

        asyncio.run(entity._do_post_command_recheck(None))

        entity.coordinator.async_request_refresh.assert_called_once()
        assert entity._recheck_cancel is None
        assert entity._data_snapshot_at_command is None

    def test_scheduling_twice_cancels_first(self):
        """Issuing a second command before the first recheck fires cancels the first."""
        entity = self._make_entity_with_data({"is_on": False})
        first_handle = MagicMock()
        second_handle = MagicMock()

        with patch(
            "custom_components.evon.base_entity.async_call_later",
            side_effect=[first_handle, second_handle],
        ):
            entity._schedule_post_command_recheck()
            entity._schedule_post_command_recheck()

        first_handle.assert_called_once()
        assert entity._recheck_cancel is second_handle

    def test_recheck_fires_after_quiesce_period_when_no_ws_arrives(self):
        """Full timer flow: schedule → POST_COMMAND_QUIESCE_PERIOD elapses → recheck fires."""
        import asyncio

        from custom_components.evon.const import POST_COMMAND_QUIESCE_PERIOD

        entity = self._make_entity_with_data({"is_on": False})

        async def refresh():
            pass

        entity.coordinator.async_request_refresh = MagicMock(return_value=refresh())

        # Capture the callback that async_call_later would schedule.
        captured = {}

        def fake_async_call_later(hass, delay, callback):
            captured["delay"] = delay
            captured["callback"] = callback
            return MagicMock()

        with patch(
            "custom_components.evon.base_entity.async_call_later",
            side_effect=fake_async_call_later,
        ):
            entity._schedule_post_command_recheck()

        assert captured["delay"] == POST_COMMAND_QUIESCE_PERIOD
        # Simulate the timer firing — no WS event arrived in the meantime.
        asyncio.run(captured["callback"](None))

        entity.coordinator.async_request_refresh.assert_called_once()
        assert entity._recheck_cancel is None
        assert entity._data_snapshot_at_command is None

    def test_ws_event_during_quiesce_cancels_recheck(self):
        """If a genuine WS update arrives during quiesce, the pending recheck is
        cancelled (a real WS update proves WS is alive, so a manual HTTP recheck is
        unnecessary). The coordinator records a fresh WS timestamp on each
        ValuesChanged event (coordinator/__init__.py)."""
        entity = self._make_entity_with_data({"is_on": False, "brightness": 0})
        entity.coordinator.get_ws_update_timestamp = MagicMock(return_value=10.0)
        cancel_handle = MagicMock()

        with patch(
            "custom_components.evon.base_entity.async_call_later",
            return_value=cancel_handle,
        ):
            entity._schedule_post_command_recheck()

        # WS ValuesChanged for this entity advances the recorded WS timestamp.
        entity.coordinator.get_ws_update_timestamp = MagicMock(return_value=11.0)
        entity._cancel_post_command_recheck_if_data_changed()

        cancel_handle.assert_called_once()
        assert entity._recheck_cancel is None

    def test_select_override_uses_value_comparison(self):
        """Select entities override _recheck_snapshot/_recheck_data_changed to compare
        coordinator method return values by ==, not dict identity. Verify the override
        path triggers cancel when the value changes."""
        from custom_components.evon.base_entity import EvonEntity

        coordinator = MagicMock()
        coordinator.last_update_success = True
        coordinator.async_request_refresh = MagicMock()
        coordinator.get_active_home_state = MagicMock(return_value="HomeStateAtHome")
        entry = MagicMock()
        entry.entry_id = "test_entry"

        # Build a minimal entity that overrides snapshot/comparator the same way
        # EvonHomeStateSelect does in production.
        entity = EvonEntity(coordinator, "home_state_x", "Home State", "", entry)
        entity.hass = MagicMock()
        entity._recheck_snapshot = lambda: entity.coordinator.get_active_home_state()
        entity._recheck_data_changed = lambda current, snapshot: current != snapshot

        with patch(
            "custom_components.evon.base_entity.async_call_later",
            return_value=MagicMock(),
        ):
            entity._schedule_post_command_recheck()

        # Snapshot captured the original value.
        assert entity._data_snapshot_at_command == "HomeStateAtHome"

        # Coordinator now reports a different value (WS event).
        coordinator.get_active_home_state.return_value = "HomeStateWork"
        entity._cancel_post_command_recheck_if_data_changed()

        # The override's value comparison detected the change and cancelled.
        assert entity._recheck_cancel is None
        assert entity._data_snapshot_at_command is None


class TestPreCommandSnapshot:
    """The recheck snapshot must be captured BEFORE the command await.

    A WS confirmation can land while `await self._api...` is in flight (WS-mode
    control races the CallMethod response). If the snapshot were captured after
    the await, it would already include that confirmation and — with no further
    WS event coming for single-event devices like relays — the recheck would
    fire a redundant full poll 5s after every command. Passing the pre-await
    snapshot into `_schedule_post_command_recheck` lets it detect the mid-flight
    confirmation and skip arming the safety net entirely.
    """

    def _make_entity(self):
        from custom_components.evon.base_entity import EvonEntity

        coordinator = MagicMock()
        coordinator.last_update_success = True
        coordinator.async_request_refresh = MagicMock()
        coordinator.get_ws_update_timestamp = MagicMock(return_value=None)
        entry = MagicMock()
        entry.entry_id = "test_entry"

        entity = EvonEntity(coordinator, "switch_1", "Test Switch", "", entry)
        entity._entity_type = "switches"
        entity.hass = MagicMock()
        return entity

    def test_ws_event_during_command_skips_scheduling(self):
        """A WS event arriving between snapshot capture and scheduling proves WS
        liveness — no recheck is armed, so no redundant poll fires later."""
        entity = self._make_entity()

        # Before the command: no WS update ever recorded.
        snapshot_before = entity._recheck_snapshot()
        assert snapshot_before is None

        # During the command await, a WS confirmation arrives.
        entity.coordinator.get_ws_update_timestamp = MagicMock(return_value=123.45)

        with patch("custom_components.evon.base_entity.async_call_later") as mock_call_later:
            entity._schedule_post_command_recheck(snapshot_before)

        mock_call_later.assert_not_called()
        assert entity._recheck_cancel is None
        assert entity._data_snapshot_at_command is None

    def test_no_ws_event_during_command_still_schedules(self):
        """With no WS event during the await, the safety net arms as before."""
        entity = self._make_entity()

        snapshot_before = entity._recheck_snapshot()

        with patch(
            "custom_components.evon.base_entity.async_call_later",
            return_value=MagicMock(),
        ) as mock_call_later:
            entity._schedule_post_command_recheck(snapshot_before)

        mock_call_later.assert_called_once()
        assert entity._recheck_cancel is not None

    def test_pre_await_snapshot_stored_so_later_ws_event_cancels(self):
        """The stored snapshot is the pre-command one: a WS event arriving after
        scheduling still cancels through the normal coordinator-update path."""
        entity = self._make_entity()
        entity.coordinator.get_ws_update_timestamp = MagicMock(return_value=100.0)

        snapshot_before = entity._recheck_snapshot()  # 100.0

        cancel_handle = MagicMock()
        with patch(
            "custom_components.evon.base_entity.async_call_later",
            return_value=cancel_handle,
        ):
            entity._schedule_post_command_recheck(snapshot_before)

        assert entity._data_snapshot_at_command == 100.0

        # WS confirmation arrives after scheduling.
        entity.coordinator.get_ws_update_timestamp = MagicMock(return_value=101.0)
        entity._cancel_post_command_recheck_if_data_changed()

        cancel_handle.assert_called_once()
        assert entity._recheck_cancel is None

    def test_no_arg_call_keeps_current_behavior(self):
        """Calling without a snapshot captures at schedule time (back-compat)."""
        entity = self._make_entity()
        entity.coordinator.get_ws_update_timestamp = MagicMock(return_value=55.0)

        with patch(
            "custom_components.evon.base_entity.async_call_later",
            return_value=MagicMock(),
        ):
            entity._schedule_post_command_recheck()

        assert entity._data_snapshot_at_command == 55.0
        assert entity._recheck_cancel is not None


class TestRecheckFireLogLevel:
    """The recheck-fired log line must not spam INFO in HTTP-only mode.

    With WebSocket disabled the recheck fires after EVERY command by design —
    it IS the state-confirmation mechanism there, not an anomaly worth INFO.
    """

    def _make_entity(self, use_websocket):
        from custom_components.evon.base_entity import EvonEntity

        coordinator = MagicMock()
        coordinator.last_update_success = True
        coordinator.use_websocket = use_websocket
        entry = MagicMock()
        entry.entry_id = "test_entry"

        entity = EvonEntity(coordinator, "light_1", "Test Light", "", entry)
        entity._entity_type = "lights"
        entity.hass = MagicMock()
        return entity

    def test_http_only_mode_logs_debug(self, caplog):
        import asyncio
        import logging

        entity = self._make_entity(use_websocket=False)

        async def refresh():
            pass

        entity.coordinator.async_request_refresh = MagicMock(return_value=refresh())

        with caplog.at_level(logging.DEBUG, logger="custom_components.evon.base_entity"):
            asyncio.run(entity._do_post_command_recheck(None))

        recheck_records = [r for r in caplog.records if "Post-command recheck firing" in r.message]
        assert len(recheck_records) == 1
        assert recheck_records[0].levelno == logging.DEBUG

    def test_websocket_mode_logs_info(self, caplog):
        import asyncio
        import logging

        entity = self._make_entity(use_websocket=True)

        async def refresh():
            pass

        entity.coordinator.async_request_refresh = MagicMock(return_value=refresh())

        with caplog.at_level(logging.DEBUG, logger="custom_components.evon.base_entity"):
            asyncio.run(entity._do_post_command_recheck(None))

        recheck_records = [r for r in caplog.records if "Post-command recheck firing" in r.message]
        assert len(recheck_records) == 1
        assert recheck_records[0].levelno == logging.INFO
