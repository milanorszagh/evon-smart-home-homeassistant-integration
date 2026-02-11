"""Unit tests for select platform (no HA framework required)."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock

import pytest

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
def setup_select_mocks():
    """Mock HA modules and set up stub classes for select tests."""
    saved_evon = {}
    for key in list(sys.modules):
        if key.startswith("custom_components.evon"):
            saved_evon[key] = sys.modules.pop(key)

    saved = {}
    for mod in _HA_MODULES:
        if mod in sys.modules:
            saved[mod] = sys.modules[mod]
        sys.modules[mod] = MagicMock()

    class MockCoordinatorEntity:
        def __init__(self, coordinator):
            self.coordinator = coordinator

        def __class_getitem__(cls, item):
            return cls

        def async_write_ha_state(self):
            pass

    class MockSelectEntity:
        pass

    sys.modules["homeassistant.helpers.update_coordinator"].CoordinatorEntity = MockCoordinatorEntity
    sys.modules["homeassistant.helpers.device_registry"].DeviceInfo = dict
    sys.modules["homeassistant.core"].callback = lambda f: f
    sys.modules["homeassistant.components.select"].SelectEntity = MockSelectEntity

    yield

    for mod in _HA_MODULES:
        if mod in saved:
            sys.modules[mod] = saved[mod]
        else:
            sys.modules.pop(mod, None)

    for key in list(sys.modules):
        if key.startswith("custom_components.evon"):
            del sys.modules[key]
    sys.modules.update(saved_evon)
    cc = sys.modules.get("custom_components")
    evon_pkg = saved_evon.get("custom_components.evon")
    if cc and evon_pkg:
        cc.evon = evon_pkg


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_home_state_select(home_states=None, active_state=None):
    from custom_components.evon.select import EvonHomeStateSelect

    coordinator = MagicMock()
    coordinator.get_home_states.return_value = home_states or []
    coordinator.get_active_home_state.return_value = active_state
    entry = MagicMock()
    entry.entry_id = "test_entry"
    api = MagicMock()
    return EvonHomeStateSelect(coordinator, entry, api)


def _make_season_mode_select(is_cooling=False):
    from custom_components.evon.select import EvonSeasonModeSelect

    coordinator = MagicMock()
    coordinator.get_season_mode.return_value = is_cooling
    entry = MagicMock()
    entry.entry_id = "test_entry"
    api = MagicMock()
    return EvonSeasonModeSelect(coordinator, entry, api)


# ---------------------------------------------------------------------------
# EvonHomeStateSelect — options
# ---------------------------------------------------------------------------


class TestHomeStateSelectOptions:
    def test_sorted_by_home_state_order(self):
        states = [
            {"id": "HomeStateHoliday"},
            {"id": "HomeStateAtHome"},
            {"id": "HomeStateNight"},
            {"id": "HomeStateWork"},
        ]
        select = _make_home_state_select(home_states=states)
        assert select._attr_options == [
            "HomeStateAtHome",
            "HomeStateNight",
            "HomeStateWork",
            "HomeStateHoliday",
        ]

    def test_unknown_states_at_end(self):
        states = [
            {"id": "HomeStateCustom"},
            {"id": "HomeStateAtHome"},
        ]
        select = _make_home_state_select(home_states=states)
        assert select._attr_options == ["HomeStateAtHome", "HomeStateCustom"]

    def test_empty_ids_excluded(self):
        states = [{"id": ""}, {"id": "HomeStateAtHome"}, {"id": None}]
        select = _make_home_state_select(home_states=states)
        assert select._attr_options == ["HomeStateAtHome"]

    def test_empty_states(self):
        select = _make_home_state_select(home_states=[])
        assert select._attr_options == []


# ---------------------------------------------------------------------------
# EvonHomeStateSelect — current_option
# ---------------------------------------------------------------------------


class TestHomeStateSelectCurrentOption:
    def test_returns_active_state(self):
        states = [{"id": "HomeStateAtHome"}, {"id": "HomeStateNight"}]
        select = _make_home_state_select(home_states=states, active_state="HomeStateAtHome")
        assert select.current_option == "HomeStateAtHome"

    def test_returns_none_when_not_in_options(self):
        states = [{"id": "HomeStateAtHome"}]
        select = _make_home_state_select(home_states=states, active_state="HomeStateUnknown")
        assert select.current_option is None

    def test_optimistic_override(self):
        states = [{"id": "HomeStateAtHome"}, {"id": "HomeStateNight"}]
        select = _make_home_state_select(home_states=states, active_state="HomeStateAtHome")
        select._optimistic_option = "HomeStateNight"
        assert select.current_option == "HomeStateNight"


# ---------------------------------------------------------------------------
# EvonHomeStateSelect — _handle_coordinator_update
# ---------------------------------------------------------------------------


class TestHomeStateSelectHandleUpdate:
    def test_clears_optimistic_when_matches(self):
        states = [{"id": "HomeStateAtHome"}, {"id": "HomeStateNight"}]
        select = _make_home_state_select(home_states=states, active_state="HomeStateAtHome")
        select._optimistic_option = "HomeStateAtHome"
        select._optimistic_state_set_at = 1.0
        select._handle_coordinator_update()
        assert select._optimistic_option is None
        assert select._optimistic_state_set_at is None

    def test_keeps_optimistic_when_differs(self):
        states = [{"id": "HomeStateAtHome"}, {"id": "HomeStateNight"}]
        select = _make_home_state_select(home_states=states, active_state="HomeStateAtHome")
        select._optimistic_option = "HomeStateNight"
        select._optimistic_state_set_at = 1.0
        select._handle_coordinator_update()
        assert select._optimistic_option == "HomeStateNight"

    def test_refreshes_options(self):
        states = [{"id": "HomeStateAtHome"}]
        select = _make_home_state_select(home_states=states)
        # Simulate coordinator returning updated states
        select.coordinator.get_home_states.return_value = [
            {"id": "HomeStateAtHome"},
            {"id": "HomeStateNight"},
        ]
        select._handle_coordinator_update()
        assert "HomeStateNight" in select._attr_options


# ---------------------------------------------------------------------------
# EvonSeasonModeSelect — options
# ---------------------------------------------------------------------------


class TestSeasonModeSelectOptions:
    def test_options_are_heating_cooling(self):
        select = _make_season_mode_select()
        assert select._attr_options == ["heating", "cooling"]


# ---------------------------------------------------------------------------
# EvonSeasonModeSelect — current_option
# ---------------------------------------------------------------------------


class TestSeasonModeSelectCurrentOption:
    def test_returns_heating(self):
        select = _make_season_mode_select(is_cooling=False)
        assert select.current_option == "heating"

    def test_returns_cooling(self):
        select = _make_season_mode_select(is_cooling=True)
        assert select.current_option == "cooling"

    def test_optimistic_override(self):
        select = _make_season_mode_select(is_cooling=False)
        select._optimistic_option = "cooling"
        assert select.current_option == "cooling"


# ---------------------------------------------------------------------------
# EvonSeasonModeSelect — extra_state_attributes
# ---------------------------------------------------------------------------


class TestSeasonModeSelectExtraAttrs:
    def test_heating_attrs(self):
        select = _make_season_mode_select(is_cooling=False)
        attrs = select.extra_state_attributes
        assert attrs["is_cooling"] is False
        assert "Winter" in attrs["description"]

    def test_cooling_attrs(self):
        select = _make_season_mode_select(is_cooling=True)
        attrs = select.extra_state_attributes
        assert attrs["is_cooling"] is True
        assert "Summer" in attrs["description"]


# ---------------------------------------------------------------------------
# EvonSeasonModeSelect — _handle_coordinator_update
# ---------------------------------------------------------------------------


class TestSeasonModeSelectHandleUpdate:
    def test_clears_optimistic_when_matches(self):
        select = _make_season_mode_select(is_cooling=False)
        select._optimistic_option = "heating"
        select._optimistic_state_set_at = 1.0
        select._handle_coordinator_update()
        assert select._optimistic_option is None
        assert select._optimistic_state_set_at is None

    def test_keeps_optimistic_when_differs(self):
        select = _make_season_mode_select(is_cooling=False)
        select._optimistic_option = "cooling"
        select._optimistic_state_set_at = 1.0
        select._handle_coordinator_update()
        assert select._optimistic_option == "cooling"
