"""Tests for WebSocket mappings."""

from __future__ import annotations

import logging

import pytest

from custom_components.evon.const import ENTITY_TYPE_CLIMATES, ENTITY_TYPE_SMART_METERS
from custom_components.evon.ws_mappings import ws_to_coordinator_data


def test_ws_climate_recompute_uses_raw_limits() -> None:
    """Use raw min/max setpoint limits when WS update lacks Min/Max values."""
    existing = {
        "is_cooling": False,
        "min_temp": 15,
        "max_temp": 21,
        "min_set_value_heat": 19,
        "max_set_value_heat": 25,
        "comfort_temp": 21,
        "energy_saving_temp": 20,
        "protection_temp": 15,
    }

    ws_props = {
        "SetValueComfortHeating": 22.5,
    }

    result = ws_to_coordinator_data(ENTITY_TYPE_CLIMATES, ws_props, existing)

    assert result["max_temp"] == 25
    assert result["min_temp"] == 15
    assert result["comfort_temp"] == 22.5


def test_ws_climate_updates_raw_limits_from_ws() -> None:
    """Store raw min/max setpoint limits when provided by WS."""
    existing = {
        "is_cooling": True,
        "min_set_value_cool": 20,
        "max_set_value_cool": 26,
        "comfort_temp": 22,
        "energy_saving_temp": 24,
        "protection_temp": 28,
    }

    ws_props = {
        "CoolingMode": True,
        "MinSetValueCool": 21,
        "MaxSetValueCool": 27,
        "SetValueComfortCooling": 23,
    }

    result = ws_to_coordinator_data(ENTITY_TYPE_CLIMATES, ws_props, existing)

    assert result["min_set_value_cool"] == 21
    assert result["max_set_value_cool"] == 27
    assert result["min_temp"] == 21
    assert result["max_temp"] == 28


def test_ws_climate_cooling_max_temp_includes_comfort_and_eco() -> None:
    """Test that cooling mode max_temp includes comfort and eco presets."""
    existing = {
        "is_cooling": True,
        "min_set_value_cool": 18,
        "max_set_value_cool": 26,
        "comfort_temp": 22,
        "energy_saving_temp": 24,
        "protection_temp": 28,
    }

    # Comfort temp exceeds MaxSetValueCool
    ws_props = {
        "CoolingMode": True,
        "SetValueComfortCooling": 32,
    }

    result = ws_to_coordinator_data(ENTITY_TYPE_CLIMATES, ws_props, existing)

    # max_temp should include comfort (32), not just protection (28) and evon_max (26)
    assert result["max_temp"] == 32


def test_ws_climate_cooling_eco_exceeds_max() -> None:
    """Test that cooling mode max_temp includes eco when it exceeds evon_max."""
    existing = {
        "is_cooling": True,
        "min_set_value_cool": 18,
        "max_set_value_cool": 26,
        "comfort_temp": 22,
        "energy_saving_temp": 24,
        "protection_temp": 25,
    }

    ws_props = {
        "CoolingMode": True,
        "SetValueEnergySavingCooling": 35,
    }

    result = ws_to_coordinator_data(ENTITY_TYPE_CLIMATES, ws_props, existing)

    # eco (35) exceeds everything
    assert result["max_temp"] == 35


def test_ws_smart_meter_power_computation_logs_warning(caplog) -> None:
    """Test that invalid smart meter phase values log a warning instead of being silently suppressed."""
    existing = {
        "power_l1": "not_a_number",
        "power_l2": 100.0,
        "power_l3": 200.0,
    }

    ws_props = {
        "P1": "bad_value",
        "P2": 100.0,
        "P3": 200.0,
    }

    with caplog.at_level(logging.WARNING, logger="custom_components.evon.ws_mappings"):
        result = ws_to_coordinator_data(ENTITY_TYPE_SMART_METERS, ws_props, existing)

    # Power should NOT be computed
    assert "power" not in result
    # Warning should be logged
    assert "Failed to compute smart meter power" in caplog.text


def test_ws_smart_meter_power_computation_valid() -> None:
    """Test that valid smart meter phase values compute power correctly."""
    ws_props = {
        "P1": 100.5,
        "P2": 200.3,
        "P3": 150.2,
    }

    result = ws_to_coordinator_data(ENTITY_TYPE_SMART_METERS, ws_props, None)

    assert result["power"] == pytest.approx(451.0, abs=0.1)
