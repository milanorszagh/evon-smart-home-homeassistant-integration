"""Tests for optimistic state timeout (C-L6)."""

from __future__ import annotations

import sys
import time
from unittest.mock import MagicMock, patch

import pytest

from custom_components.evon.const import (
    OPTIMISTIC_SETTLING_PERIOD,
    OPTIMISTIC_SETTLING_PERIOD_SHORT,
    OPTIMISTIC_STATE_TIMEOUT,
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

        for mod_name in list(sys.modules.keys()):
            if mod_name in (
                "custom_components.evon.base_entity",
                "custom_components.evon.const",
            ):
                del sys.modules[mod_name]

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

    def test_settling_period_is_2_5_seconds(self):
        """Test OPTIMISTIC_SETTLING_PERIOD is 2.5 seconds."""
        assert OPTIMISTIC_SETTLING_PERIOD == 2.5

    def test_short_settling_period_is_1_second(self):
        """Test OPTIMISTIC_SETTLING_PERIOD_SHORT is 1.0 second."""
        assert OPTIMISTIC_SETTLING_PERIOD_SHORT == 1.0

    def test_settling_less_than_timeout(self):
        """Test that settling period is less than timeout."""
        assert OPTIMISTIC_SETTLING_PERIOD < OPTIMISTIC_STATE_TIMEOUT
        assert OPTIMISTIC_SETTLING_PERIOD_SHORT < OPTIMISTIC_STATE_TIMEOUT
