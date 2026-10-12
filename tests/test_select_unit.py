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
        """Mirror the part of HA's SelectEntity the shim builds on."""

        async def async_handle_select_option(self, option):
            if option not in self._attr_options:
                raise ValueError(f"Option {option} is not valid")
            await self.async_select_option(option)

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
        assert select._attr_options == ["at_home", "night", "work", "holiday"]

    def test_unknown_states_at_end(self):
        states = [
            {"id": "HomeStateCustom"},
            {"id": "HomeStateAtHome"},
        ]
        select = _make_home_state_select(home_states=states)
        assert select._attr_options == ["at_home", "custom"]

    def test_empty_ids_excluded(self):
        states = [{"id": ""}, {"id": "HomeStateAtHome"}, {"id": None}]
        select = _make_home_state_select(home_states=states)
        assert select._attr_options == ["at_home"]

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
        assert select.current_option == "at_home"

    def test_returns_none_without_active_state(self):
        select = _make_home_state_select(home_states=[{"id": "HomeStateAtHome"}], active_state=None)
        assert select.current_option is None

    def test_returns_none_when_not_in_options(self):
        states = [{"id": "HomeStateAtHome"}]
        select = _make_home_state_select(home_states=states, active_state="HomeStateUnknown")
        assert select.current_option is None

    def test_optimistic_override(self):
        states = [{"id": "HomeStateAtHome"}, {"id": "HomeStateNight"}]
        select = _make_home_state_select(home_states=states, active_state="HomeStateAtHome")
        select._optimistic_option = "night"
        assert select.current_option == "night"


# ---------------------------------------------------------------------------
# EvonHomeStateSelect — _handle_coordinator_update
# ---------------------------------------------------------------------------


class TestHomeStateSelectHandleUpdate:
    def test_clears_optimistic_when_matches(self):
        states = [{"id": "HomeStateAtHome"}, {"id": "HomeStateNight"}]
        select = _make_home_state_select(home_states=states, active_state="HomeStateAtHome")
        select._optimistic_option = "at_home"
        select._optimistic_state_set_at = 1.0
        select._handle_coordinator_update()
        assert select._optimistic_option is None
        assert select._optimistic_state_set_at is None

    def test_keeps_optimistic_when_differs(self):
        states = [{"id": "HomeStateAtHome"}, {"id": "HomeStateNight"}]
        select = _make_home_state_select(home_states=states, active_state="HomeStateAtHome")
        select._optimistic_option = "night"
        select._optimistic_state_set_at = 1.0
        select._handle_coordinator_update()
        assert select._optimistic_option == "night"

    def test_refreshes_options(self):
        states = [{"id": "HomeStateAtHome"}]
        select = _make_home_state_select(home_states=states)
        # Simulate coordinator returning updated states
        select.coordinator.get_home_states.return_value = [
            {"id": "HomeStateAtHome"},
            {"id": "HomeStateNight"},
        ]
        select._handle_coordinator_update()
        assert "night" in select._attr_options


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


# ---------------------------------------------------------------------------
# EvonHomeStateSelect — option keys
#
# HA translation keys must match [a-z0-9-_]+ (enforced by hassfest), so the
# select exposes lowercase keys (`at_home`, `night`, ...) and maps them to the
# Evon instance IDs (`HomeStateAtHome`, ...) internally.
# ---------------------------------------------------------------------------


def _make_controllable_home_state_select(home_states, active_state):
    from unittest.mock import AsyncMock

    select = _make_home_state_select(home_states=home_states, active_state=active_state)
    select.entity_id = "select.evon_home_state"
    select._api.activate_home_state = AsyncMock()
    select._schedule_post_command_recheck = MagicMock()
    return select


class TestHomeStateSelectOptionKeys:
    def test_options_are_lowercase_keys_in_preferred_order(self):
        states = [
            {"id": "HomeStateHoliday"},
            {"id": "HomeStateAtHome"},
            {"id": "HomeStateNight"},
            {"id": "HomeStateWork"},
        ]
        select = _make_home_state_select(home_states=states)
        assert select._attr_options == ["at_home", "night", "work", "holiday"]

    def test_unknown_evon_id_is_slugified_and_sorted_last(self):
        states = [{"id": "HomeStateMyParty"}, {"id": "HomeStateAtHome"}]
        select = _make_home_state_select(home_states=states)
        assert select._attr_options == ["at_home", "my_party"]

    def test_colliding_evon_ids_keep_first_and_warn(self, caplog):
        states = [{"id": "HomeStateAtHome"}, {"id": "HomeStateAt_Home"}]
        select = _make_home_state_select(home_states=states, active_state="HomeStateAt_Home")
        assert select._attr_options == ["at_home"]
        assert select.current_option is None  # the dropped state is not silently mapped
        assert "HomeStateAt_Home" in caplog.text and "at_home" in caplog.text

    def test_current_option_maps_active_evon_id_to_key(self):
        states = [{"id": "HomeStateAtHome"}, {"id": "HomeStateNight"}]
        select = _make_home_state_select(home_states=states, active_state="HomeStateNight")
        assert select.current_option == "night"

    def test_evon_id_attribute_keeps_raw_id(self):
        states = [{"id": "HomeStateAtHome"}]
        select = _make_home_state_select(home_states=states, active_state="HomeStateAtHome")
        assert select.extra_state_attributes["evon_id"] == "HomeStateAtHome"

    async def test_select_option_activates_mapped_evon_id(self):
        states = [{"id": "HomeStateAtHome"}, {"id": "HomeStateNight"}]
        select = _make_controllable_home_state_select(states, "HomeStateAtHome")
        await select.async_select_option("night")
        select._api.activate_home_state.assert_awaited_once_with("HomeStateNight")
        assert select._optimistic_option == "night"

    async def test_service_handler_accepts_legacy_evon_id_with_warning(self, caplog):
        """The shim must sit in the service handler: HA validates options before async_select_option."""
        states = [{"id": "HomeStateAtHome"}, {"id": "HomeStateNight"}]
        select = _make_controllable_home_state_select(states, "HomeStateAtHome")
        await select.async_handle_select_option("HomeStateNight")
        select._api.activate_home_state.assert_awaited_once_with("HomeStateNight")
        assert select._optimistic_option == "night"
        assert "deprecated" in caplog.text.lower()

    async def test_service_handler_still_rejects_unknown_values(self):
        states = [{"id": "HomeStateAtHome"}, {"id": "HomeStateNight"}]
        select = _make_controllable_home_state_select(states, "HomeStateAtHome")
        with pytest.raises(ValueError):
            await select.async_handle_select_option("party")
        select._api.activate_home_state.assert_not_awaited()

    async def test_select_option_rejects_unknown_value(self):
        states = [{"id": "HomeStateAtHome"}, {"id": "HomeStateNight"}]
        select = _make_controllable_home_state_select(states, "HomeStateAtHome")
        await select.async_select_option("party")
        select._api.activate_home_state.assert_not_awaited()
        assert select._optimistic_option is None

    def test_coordinator_update_clears_optimistic_when_active_id_matches_key(self):
        states = [{"id": "HomeStateAtHome"}, {"id": "HomeStateNight"}]
        select = _make_home_state_select(home_states=states, active_state="HomeStateNight")
        select._optimistic_option = "night"
        select._cancel_post_command_recheck_if_data_changed = MagicMock()
        select._handle_coordinator_update()
        assert select._optimistic_option is None


# ---------------------------------------------------------------------------
# Select device_info — hub link via `via_device_id`
# ---------------------------------------------------------------------------


class TestSelectDeviceInfoViaDeviceId:
    def test_home_state_select_links_to_hub_by_registry_id(self):
        select = _make_home_state_select(home_states=[{"id": "HomeStateAtHome"}])
        select.coordinator.hub_device_id = "hub-device-registry-id"
        info = select.device_info
        assert info["via_device_id"] == "hub-device-registry-id"
        assert "via_device" not in info

    def test_season_mode_select_links_to_hub_by_registry_id(self):
        select = _make_season_mode_select()
        select.coordinator.hub_device_id = "hub-device-registry-id"
        info = select.device_info
        assert info["via_device_id"] == "hub-device-registry-id"
        assert "via_device" not in info

    def test_selects_omit_via_device_id_when_hub_unknown(self):
        home = _make_home_state_select(home_states=[{"id": "HomeStateAtHome"}])
        season = _make_season_mode_select()
        for select in (home, season):
            select.coordinator.hub_device_id = None
            info = select.device_info
            assert "via_device_id" not in info
            assert "via_device" not in info
