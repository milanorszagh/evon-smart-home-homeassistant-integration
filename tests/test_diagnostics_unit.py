"""Unit tests for diagnostics (no HA framework required)."""

from __future__ import annotations

import asyncio
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
def setup_diagnostics_mocks():
    """Mock HA modules for diagnostics tests."""
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

    sys.modules["homeassistant.helpers.update_coordinator"].CoordinatorEntity = MockCoordinatorEntity
    sys.modules["homeassistant.helpers.device_registry"].DeviceInfo = dict
    sys.modules["homeassistant.core"].callback = lambda f: f
    # async_redact_data is a regular function; make it pass-through
    sys.modules["homeassistant.components.diagnostics"].async_redact_data = lambda data, keys: data

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


def _make_coordinator_data():
    """Return sample coordinator.data with all entity types."""
    return {
        "lights": [{"id": "l1", "name": "Light 1", "is_on": True, "brightness": 100}],
        "blinds": [{"id": "b1", "name": "Blind 1", "position": 50, "angle": 30}],
        "climates": [
            {
                "id": "c1",
                "name": "Climate 1",
                "current_temperature": 21,
                "target_temperature": 22,
            }
        ],
        "switches": [{"id": "s1", "name": "Switch 1", "is_on": False}],
        "smart_meters": [{"id": "m1", "name": "Meter 1", "power": 1500, "energy": 42.5}],
        "air_quality": [{"id": "aq1", "name": "AQ 1", "co2": 800, "humidity": 55}],
        "valves": [{"id": "v1", "name": "Valve 1", "is_open": True}],
        "scenes": [{"id": "sc1", "name": "Scene 1"}],
        "bathroom_radiators": [{"id": "br1", "name": "Radiator 1", "is_on": True}],
        "security_doors": [{"id": "sd1", "name": "Door 1", "is_locked": True}],
        "intercoms": [{"id": "ic1", "name": "Intercom 1"}],
        "cameras": [{"id": "cam1", "name": "Camera 1", "error": None}],
        "rooms": {"living_room": {}, "bedroom": {}},
    }


def _run_diagnostics(coordinator_data=None, has_coordinator=True):
    """Run async_get_config_entry_diagnostics and return result."""
    from custom_components.evon.const import DOMAIN
    from custom_components.evon.diagnostics import (
        async_get_config_entry_diagnostics,
    )

    hass = MagicMock()
    entry = MagicMock()
    entry.entry_id = "test_entry"
    entry.data = {"host": "1.2.3.4", "username": "admin", "password": "secret"}
    entry.options = {}

    if has_coordinator:
        coordinator = MagicMock()
        coordinator.data = coordinator_data
        coordinator.last_update_success = True
        coordinator.update_interval = "30s"
        hass.data = {DOMAIN: {entry.entry_id: {"coordinator": coordinator}}}
    else:
        hass.data = {}

    return asyncio.run(async_get_config_entry_diagnostics(hass, entry))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestDiagnosticsUnit:
    def test_returns_error_when_no_coordinator(self):
        result = _run_diagnostics(has_coordinator=False)
        assert result == {"error": "Integration not fully loaded"}

    def test_result_structure(self):
        result = _run_diagnostics(coordinator_data=_make_coordinator_data())
        assert "entry" in result
        assert "coordinator" in result
        assert "device_counts" in result
        assert "devices" in result

    def test_device_counts_all_entity_types(self):
        result = _run_diagnostics(coordinator_data=_make_coordinator_data())
        counts = result["device_counts"]
        expected_keys = [
            "lights",
            "blinds",
            "climates",
            "switches",
            "smart_meters",
            "air_quality",
            "valves",
            "scenes",
            "bathroom_radiators",
            "security_doors",
            "intercoms",
            "cameras",
            "rooms",
        ]
        for key in expected_keys:
            assert key in counts, f"Missing key: {key}"

    def test_device_counts_correct_values(self):
        result = _run_diagnostics(coordinator_data=_make_coordinator_data())
        counts = result["device_counts"]
        assert counts["lights"] == 1
        assert counts["blinds"] == 1
        assert counts["rooms"] == 2

    def test_light_summary_fields(self):
        result = _run_diagnostics(coordinator_data=_make_coordinator_data())
        lights = result["devices"]["lights"]
        assert len(lights) == 1
        assert lights[0]["id"] == "l1"
        assert lights[0]["name"] == "Light 1"
        assert lights[0]["is_on"] is True
        assert lights[0]["has_brightness"] is True

    def test_blind_summary_fields(self):
        result = _run_diagnostics(coordinator_data=_make_coordinator_data())
        blinds = result["devices"]["blinds"]
        assert len(blinds) == 1
        assert blinds[0]["position"] == 50
        assert blinds[0]["has_tilt"] is True

    def test_climate_summary_fields(self):
        result = _run_diagnostics(coordinator_data=_make_coordinator_data())
        climates = result["devices"]["climates"]
        assert len(climates) == 1
        assert climates[0]["current_temp"] == 21
        assert climates[0]["target_temp"] == 22

    def test_empty_coordinator_data(self):
        result = _run_diagnostics(coordinator_data={})
        assert result["device_counts"] == {}
        assert result["devices"] == {}
