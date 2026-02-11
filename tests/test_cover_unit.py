"""Unit tests for cover platform (no HA framework required)."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock

import pytest

# All HA modules that may be imported transitively by the evon package
_HA_MODULES = [
    "homeassistant",
    "homeassistant.components",
    "homeassistant.components.binary_sensor",
    "homeassistant.components.cover",
    "homeassistant.components.diagnostics",
    "homeassistant.components.recorder",
    "homeassistant.components.recorder.statistics",
    "homeassistant.components.select",
    "homeassistant.components.sensor",
    "homeassistant.config_entries",
    "homeassistant.const",
    "homeassistant.core",
    "homeassistant.exceptions",
    "homeassistant.helpers",
    "homeassistant.helpers.aiohttp_client",
    "homeassistant.helpers.device_registry",
    "homeassistant.helpers.entity_platform",
    "homeassistant.helpers.issue_registry",
    "homeassistant.helpers.update_coordinator",
    "homeassistant.util",
    "homeassistant.util.dt",
]


@pytest.fixture(autouse=True)
def setup_cover_mocks():
    """Mock HA modules and set up stub classes for cover tests."""
    # Save and remove cached evon modules for a clean import
    saved_evon = {}
    for key in list(sys.modules):
        if key.startswith("custom_components.evon"):
            saved_evon[key] = sys.modules.pop(key)

    saved = {}
    for mod in _HA_MODULES:
        if mod in sys.modules:
            saved[mod] = sys.modules[mod]
        sys.modules[mod] = MagicMock()

    # Stub base classes
    class MockCoordinatorEntity:
        def __init__(self, coordinator):
            self.coordinator = coordinator

        def __class_getitem__(cls, item):
            return cls

        def async_write_ha_state(self):
            pass

    class MockCoverEntity:
        pass

    sys.modules["homeassistant.helpers.update_coordinator"].CoordinatorEntity = (
        MockCoordinatorEntity
    )
    sys.modules["homeassistant.helpers.device_registry"].DeviceInfo = dict
    sys.modules["homeassistant.core"].callback = lambda f: f
    sys.modules["homeassistant.components.cover"].CoverEntity = MockCoverEntity
    sys.modules["homeassistant.components.cover"].CoverEntityFeature = MagicMock()

    yield

    for mod in _HA_MODULES:
        if mod in saved:
            sys.modules[mod] = saved[mod]
        else:
            sys.modules.pop(mod, None)

    # Restore evon modules to pre-test state
    for key in list(sys.modules):
        if key.startswith("custom_components.evon"):
            del sys.modules[key]
    sys.modules.update(saved_evon)
    # Fix parent package reference so patch() resolves correctly
    cc = sys.modules.get("custom_components")
    evon_pkg = saved_evon.get("custom_components.evon")
    if cc and evon_pkg:
        cc.evon = evon_pkg


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_cover(entity_data=None, instance_id="blind_1", room_name=""):
    """Create an EvonCover with controlled coordinator data."""
    from custom_components.evon.cover import EvonCover

    coordinator = MagicMock()
    coordinator.get_entity_data.return_value = entity_data
    entry = MagicMock()
    entry.entry_id = "test_entry"
    api = MagicMock()
    return EvonCover(coordinator, instance_id, "Test Blind", room_name, entry, api)


# ---------------------------------------------------------------------------
# Position conversion (Evon 0=open -> HA 100=open)
# ---------------------------------------------------------------------------


class TestCoverPositionConversion:
    """Tests for Evon->HA position inversion."""

    def test_evon_0_returns_ha_100(self):
        cover = _make_cover({"position": 0, "angle": 0})
        assert cover.current_cover_position == 100

    def test_evon_100_returns_ha_0(self):
        cover = _make_cover({"position": 100, "angle": 0})
        assert cover.current_cover_position == 0

    def test_evon_50_returns_ha_50(self):
        cover = _make_cover({"position": 50, "angle": 0})
        assert cover.current_cover_position == 50

    def test_evon_75_returns_ha_25(self):
        cover = _make_cover({"position": 75, "angle": 0})
        assert cover.current_cover_position == 25

    def test_position_none_when_no_data(self):
        cover = _make_cover(None)
        assert cover.current_cover_position is None

    def test_position_default_when_key_missing(self):
        cover = _make_cover({"angle": 0})
        # Default position is 0, so HA position = 100 - 0 = 100
        assert cover.current_cover_position == 100


# ---------------------------------------------------------------------------
# Tilt / angle conversion
# ---------------------------------------------------------------------------


class TestCoverTiltConversion:
    """Tests for Evon angle->HA tilt inversion."""

    def test_evon_angle_0_returns_ha_100(self):
        cover = _make_cover({"position": 0, "angle": 0})
        assert cover.current_cover_tilt_position == 100

    def test_evon_angle_100_returns_ha_0(self):
        cover = _make_cover({"position": 0, "angle": 100})
        assert cover.current_cover_tilt_position == 0

    def test_evon_angle_45_returns_ha_55(self):
        cover = _make_cover({"position": 0, "angle": 45})
        assert cover.current_cover_tilt_position == 55

    def test_tilt_none_when_no_data(self):
        cover = _make_cover(None)
        assert cover.current_cover_tilt_position is None

    def test_tilt_default_when_key_missing(self):
        cover = _make_cover({"position": 0})
        # Default angle is 0, so HA tilt = 100 - 0 = 100
        assert cover.current_cover_tilt_position == 100


# ---------------------------------------------------------------------------
# is_closed
# ---------------------------------------------------------------------------


class TestCoverIsClosed:
    """Tests for is_closed property."""

    def test_closed_when_position_0(self):
        cover = _make_cover({"position": 100, "angle": 0})  # HA pos = 0
        assert cover.is_closed is True

    def test_not_closed_when_position_nonzero(self):
        cover = _make_cover({"position": 50, "angle": 0})  # HA pos = 50
        assert cover.is_closed is False

    def test_none_when_no_data(self):
        cover = _make_cover(None)
        assert cover.is_closed is None


# ---------------------------------------------------------------------------
# Optimistic state
# ---------------------------------------------------------------------------


class TestCoverOptimisticState:
    """Tests for optimistic state overrides."""

    def test_optimistic_position_overrides_coordinator(self):
        cover = _make_cover({"position": 50, "angle": 0})  # HA pos = 50
        cover._optimistic_position = 75
        assert cover.current_cover_position == 75

    def test_optimistic_tilt_overrides_coordinator(self):
        cover = _make_cover({"position": 0, "angle": 50})  # HA tilt = 50
        cover._optimistic_tilt = 80
        assert cover.current_cover_tilt_position == 80

    def test_reset_clears_all_fields(self):
        cover = _make_cover({"position": 0, "angle": 0})
        cover._optimistic_position = 50
        cover._optimistic_tilt = 30
        cover._optimistic_is_moving = True
        cover._optimistic_direction = "opening"

        cover._reset_optimistic_state()

        assert cover._optimistic_position is None
        assert cover._optimistic_tilt is None
        assert cover._optimistic_is_moving is None
        assert cover._optimistic_direction is None


# ---------------------------------------------------------------------------
# is_opening / is_closing
# ---------------------------------------------------------------------------


class TestCoverIsOpeningClosing:
    """Tests for opening/closing detection."""

    def test_opening_true(self):
        cover = _make_cover({"position": 0, "angle": 0})
        cover._optimistic_is_moving = True
        cover._optimistic_direction = "opening"
        assert cover.is_opening is True

    def test_opening_false_when_closing(self):
        cover = _make_cover({"position": 0, "angle": 0})
        cover._optimistic_is_moving = True
        cover._optimistic_direction = "closing"
        assert cover.is_opening is False

    def test_opening_false_no_optimistic(self):
        cover = _make_cover({"position": 0, "angle": 0})
        assert cover.is_opening is False

    def test_closing_true(self):
        cover = _make_cover({"position": 0, "angle": 0})
        cover._optimistic_is_moving = True
        cover._optimistic_direction = "closing"
        assert cover.is_closing is True

    def test_closing_false_when_not_moving(self):
        cover = _make_cover({"position": 0, "angle": 0})
        cover._optimistic_is_moving = False
        cover._optimistic_direction = "closing"
        assert cover.is_closing is False

    def test_closing_false_no_optimistic(self):
        cover = _make_cover({"position": 0, "angle": 0})
        assert cover.is_closing is False


# ---------------------------------------------------------------------------
# Extra state attributes
# ---------------------------------------------------------------------------


class TestCoverExtraAttributes:
    """Tests for extra_state_attributes."""

    def test_includes_evon_position_and_angle(self):
        cover = _make_cover({"position": 30, "angle": 60})
        attrs = cover.extra_state_attributes
        assert attrs["evon_position"] == 30
        assert attrs["evon_angle"] == 60

    def test_no_data_still_has_base_attrs(self):
        cover = _make_cover(None)
        attrs = cover.extra_state_attributes
        assert attrs["evon_id"] == "blind_1"
        assert attrs["integration"] == "evon"
        assert "evon_position" not in attrs


# ---------------------------------------------------------------------------
# _handle_coordinator_update
# ---------------------------------------------------------------------------


class TestCoverHandleCoordinatorUpdate:
    """Tests for coordinator update handling."""

    def _make_and_update(self, init_data, optimistic, update_data):
        """Create cover, set optimistic state, update coordinator, call handler."""
        from custom_components.evon.cover import EvonCover

        coordinator = MagicMock()
        coordinator.get_entity_data.return_value = init_data
        entry = MagicMock()
        entry.entry_id = "test_entry"
        api = MagicMock()
        cover = EvonCover(coordinator, "blind_1", "Test Blind", "", entry, api)

        for attr, val in optimistic.items():
            setattr(cover, attr, val)

        coordinator.get_entity_data.return_value = update_data
        cover._handle_coordinator_update()
        return cover

    def test_clears_position_within_tolerance(self):
        # Optimistic HA 50.  Evon 51 -> HA 49.  |49-50|=1 <= 2 -> cleared
        cover = self._make_and_update(
            {"position": 0, "angle": 0},
            {"_optimistic_position": 50, "_optimistic_state_set_at": 1.0},
            {"position": 51, "angle": 0},
        )
        assert cover._optimistic_position is None

    def test_keeps_position_outside_tolerance(self):
        # Optimistic HA 50.  Evon 45 -> HA 55.  |55-50|=5 > 2 -> kept
        cover = self._make_and_update(
            {"position": 0, "angle": 0},
            {"_optimistic_position": 50, "_optimistic_state_set_at": 1.0},
            {"position": 45, "angle": 0},
        )
        assert cover._optimistic_position == 50

    def test_clears_tilt_within_tolerance(self):
        # Optimistic tilt HA 60.  Evon 41 -> HA 59.  |59-60|=1 <= 2 -> cleared
        cover = self._make_and_update(
            {"position": 0, "angle": 0},
            {"_optimistic_tilt": 60, "_optimistic_state_set_at": 1.0},
            {"position": 0, "angle": 41},
        )
        assert cover._optimistic_tilt is None

    def test_clears_is_moving_when_matches(self):
        cover = self._make_and_update(
            {"position": 0, "angle": 0},
            {
                "_optimistic_is_moving": False,
                "_optimistic_direction": "opening",
                "_optimistic_state_set_at": 1.0,
            },
            {"position": 0, "angle": 0, "is_moving": False},
        )
        assert cover._optimistic_is_moving is None
        assert cover._optimistic_direction is None

    def test_clears_timestamp_when_all_cleared(self):
        # Position within tolerance -> all cleared -> timestamp cleared
        cover = self._make_and_update(
            {"position": 0, "angle": 0},
            {"_optimistic_position": 50, "_optimistic_state_set_at": 1.0},
            {"position": 50, "angle": 0},  # HA 50, |50-50|=0 -> cleared
        )
        assert cover._optimistic_state_set_at is None

    def test_keeps_timestamp_when_not_all_cleared(self):
        # Position cleared but tilt outside tolerance -> timestamp kept
        cover = self._make_and_update(
            {"position": 0, "angle": 0},
            {
                "_optimistic_position": 50,
                "_optimistic_tilt": 80,
                "_optimistic_state_set_at": 1.0,
            },
            {"position": 50, "angle": 10},  # Pos: HA 50 (ok). Tilt: HA 90, |90-80|=10
        )
        assert cover._optimistic_position is None
        assert cover._optimistic_tilt == 80
        assert cover._optimistic_state_set_at == 1.0


# ---------------------------------------------------------------------------
# Group flag
# ---------------------------------------------------------------------------


class TestCoverGroupFlag:
    """Tests for is_group detection."""

    def test_is_group_true(self):
        cover = _make_cover({"position": 0, "angle": 0, "is_group": True})
        assert cover._is_group is True

    def test_is_group_false(self):
        cover = _make_cover({"position": 0, "angle": 0, "is_group": False})
        assert cover._is_group is False

    def test_is_group_no_data(self):
        cover = _make_cover(None)
        assert cover._is_group is False
