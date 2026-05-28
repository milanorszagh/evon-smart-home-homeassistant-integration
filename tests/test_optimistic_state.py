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
        return entity

    def test_schedule_recheck_captures_data_snapshot(self):
        """Scheduling stores the current data dict reference for later comparison."""
        data = {"id": "light_1", "is_on": False}
        entity = self._make_entity_with_data(data)

        with patch("custom_components.evon.base_entity.async_call_later", return_value=MagicMock()):
            entity._schedule_post_command_recheck()

        assert entity._data_snapshot_at_command is data
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

    def test_cancel_recheck_if_data_changed_cancels_when_dict_replaced(self):
        """When entity's data dict ref changes, the pending recheck is cancelled."""
        initial_data = {"is_on": False}
        entity = self._make_entity_with_data(initial_data)
        cancel_handle = MagicMock()

        with patch("custom_components.evon.base_entity.async_call_later", return_value=cancel_handle):
            entity._schedule_post_command_recheck()

        entity._get_data = lambda: {"is_on": True}
        entity._cancel_post_command_recheck_if_data_changed()

        cancel_handle.assert_called_once()
        assert entity._recheck_cancel is None
        assert entity._data_snapshot_at_command is None

    def test_cancel_recheck_if_data_changed_does_nothing_when_dict_same(self):
        """When entity's data dict ref is unchanged, recheck is preserved."""
        data = {"is_on": False}
        entity = self._make_entity_with_data(data)
        cancel_handle = MagicMock()

        with patch("custom_components.evon.base_entity.async_call_later", return_value=cancel_handle):
            entity._schedule_post_command_recheck()

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
