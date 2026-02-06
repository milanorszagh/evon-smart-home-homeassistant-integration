"""Tests for WebSocket mappings."""

from __future__ import annotations

from custom_components.evon.const import ENTITY_TYPE_CLIMATES
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
