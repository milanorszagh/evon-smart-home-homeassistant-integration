"""Tests for the safety-net poll: detail prefetch selection, WS-updatable keys and
the poll-correction diagnostics that show whether the poll ever catches something
the WebSocket missed.

No Home Assistant runtime needed — the conftest stand-ins cover the imports.
"""

from __future__ import annotations

import types
from unittest.mock import MagicMock

from custom_components.evon.const import (
    ENTITY_TYPE_CLIMATES,
    ENTITY_TYPE_LIGHTS,
    ENTITY_TYPE_SMART_METERS,
    ENTITY_TYPE_WEATHER,
)
from custom_components.evon.coordinator import (
    EvonDataUpdateCoordinator,
    select_instances_for_detail_fetch,
)
from custom_components.evon.ws_mappings import get_ws_mapped_keys


def _inst(iid: str, class_name: str, name: str = "x") -> dict:
    return {"ID": iid, "ClassName": class_name, "Name": name}


class TestSelectInstancesForDetailFetch:
    """Only instances a processor reads details for are fetched (89 of 930 on a real controller)."""

    def test_fetches_only_classes_that_become_entities(self):
        instances = [
            _inst("L1", "SmartCOM.Light.LightDim"),
            _inst("R1", "SmartCOM.Light.Light"),
            _inst("B1", "SmartCOM.Blind.Blind"),
            _inst("C1", "SmartCOM.Clima.ClimateControl"),
            _inst("CU1", "Heating.ClimateControlUniversal"),
            _inst("M1", "Energy.SmartMeter300"),
            _inst("HomeStateNight", "System.HomeState"),
            _inst("Rad1", "Heating.BathroomRadiator"),
            _inst("AQ1", "System.Location.AirQuality"),
            _inst("V1", "SmartCOM.Clima.Valve"),
            _inst("D1", "Security.Door"),
            _inst("I1", "Security.Intercom.2N.Intercom2N"),
            _inst("I1.Cam", "Security.Intercom.2N.Intercom2NCam"),
            # Unnamed instances of entity classes are templates / unused channels;
            # every processor skips them, so their details are never read.
            _inst("Base.bLight", "Base.bLight", name=""),
            _inst("SC1_M05.Thermostat2", "SmartCOM.Clima.ClimateControl", name=""),
            # Not needed: WS-only buttons, fire-and-forget scenes, and the hundreds
            # of logic / config / notification / room objects on a controller.
            _inst("SC1_M01.Switch1", "SmartCOM.Switch"),
            _inst("SceneApp1", "System.SceneApp"),
            _inst("Notification5430", "System.Notification"),
            _inst("Logic1", "Logic.AssignBlock"),
            _inst("room_1", "System.Location.Room"),
            _inst("evonHomeConnect4939", "Rest.evonHomeConnect.evonHomeConnect"),
        ]

        ids = select_instances_for_detail_fetch(instances)

        assert ids == [
            "L1",
            "R1",
            "B1",
            "C1",
            "CU1",
            "M1",
            "HomeStateNight",
            "Rad1",
            "AQ1",
            "V1",
            "D1",
            "I1",
            "I1.Cam",
            "Base.ehThermostat",
        ]

    def test_season_mode_instance_added_exactly_once(self):
        instances = [_inst("Base.ehThermostat", "Base.ehThermostat"), _inst("L1", "SmartCOM.Light.LightDim")]

        ids = select_instances_for_detail_fetch(instances)

        assert ids.count("Base.ehThermostat") == 1
        assert "L1" in ids

    def test_skips_unnamed_instances_of_entity_classes(self):
        instances = [_inst("L1", "SmartCOM.Light.LightDim", name=""), _inst("L2", "SmartCOM.Light.LightDim")]

        assert select_instances_for_detail_fetch(instances) == ["L2", "Base.ehThermostat"]

    def test_skips_instances_without_id(self):
        assert select_instances_for_detail_fetch([{"ClassName": "SmartCOM.Light.LightDim"}]) == ["Base.ehThermostat"]


class TestWsMappedKeys:
    """The coordinator keys the WebSocket delivers 1:1 for an entity type."""

    def test_smart_meter_keys(self):
        keys = get_ws_mapped_keys(ENTITY_TYPE_SMART_METERS)

        assert {"energy", "feed_in_energy", "power_l1"} <= keys
        # Poll-only inputs and poll-derived outputs are not WS keys
        assert not {"feed_in", "power_unit", "energy_today_calculated", "energy_this_month_calculated", "name"} & keys

    def test_poll_only_type_has_no_keys(self):
        assert get_ws_mapped_keys(ENTITY_TYPE_WEATHER) == frozenset()

    def test_mapped_keys_exclude_values_the_websocket_derives(self):
        """The summed meter ``power`` and the climate setpoint summaries are
        computed and differ from HTTP by float rounding."""
        assert "power" not in get_ws_mapped_keys(ENTITY_TYPE_SMART_METERS)
        assert "comfort_temp" not in get_ws_mapped_keys(ENTITY_TYPE_CLIMATES)
        assert "current_temperature" in get_ws_mapped_keys(ENTITY_TYPE_CLIMATES)


def _coordinator_for_corrections() -> MagicMock:
    obj = MagicMock(spec=EvonDataUpdateCoordinator)
    obj._data_index = {}
    obj._ws_update_timestamps = {}
    obj._ws_connected = True
    obj.poll_correction_count = 0
    obj.last_poll_correction = None
    obj.last_poll_correction_at = None
    obj._record_poll_corrections = types.MethodType(EvonDataUpdateCoordinator._record_poll_corrections, obj)
    return obj


class TestPollCorrections:
    """A 'correction' is a WS-covered value the poll found different although no WS
    event for that entity arrived during the poll — i.e. the safety net was used."""

    def test_counts_value_the_websocket_did_not_deliver(self):
        coord = _coordinator_for_corrections()
        coord._data_index[(ENTITY_TYPE_LIGHTS, "L1")] = {"id": "L1", "name": "Lamp", "is_on": False}
        result = {ENTITY_TYPE_LIGHTS: [{"id": "L1", "name": "Lamp", "is_on": True}]}

        assert coord._record_poll_corrections(result, 100.0) == 1

        assert coord.poll_correction_count == 1
        assert coord.last_poll_correction == "lights/L1 is_on: False -> True"
        assert coord.last_poll_correction_at is not None

    def test_counts_each_changed_field(self):
        coord = _coordinator_for_corrections()
        coord._data_index[(ENTITY_TYPE_CLIMATES, "C1")] = {
            "id": "C1",
            "current_temperature": 21.0,
            "target_temperature": 22.0,
        }
        result = {ENTITY_TYPE_CLIMATES: [{"id": "C1", "current_temperature": 21.5, "target_temperature": 23.0}]}

        assert coord._record_poll_corrections(result, 100.0) == 2
        assert coord.poll_correction_count == 2

    def test_ignores_entity_updated_by_websocket_during_poll(self):
        coord = _coordinator_for_corrections()
        coord._data_index[(ENTITY_TYPE_LIGHTS, "L1")] = {"id": "L1", "is_on": True}
        coord._ws_update_timestamps[(ENTITY_TYPE_LIGHTS, "L1")] = 105.0  # after the poll started
        result = {ENTITY_TYPE_LIGHTS: [{"id": "L1", "is_on": False}]}  # poll snapshot is the stale one

        assert coord._record_poll_corrections(result, 100.0) == 0
        assert coord.poll_correction_count == 0

    def test_ignores_fields_only_the_poll_delivers(self):
        coord = _coordinator_for_corrections()
        coord._data_index[(ENTITY_TYPE_SMART_METERS, "M1")] = {
            "id": "M1",
            "energy": 10.0,
            "feed_in": 10,
            "energy_today_calculated": 4.0,
        }
        result = {
            ENTITY_TYPE_SMART_METERS: [{"id": "M1", "energy": 10.0, "feed_in": 12, "energy_today_calculated": 5.5}]
        }

        assert coord._record_poll_corrections(result, 100.0) == 0

    def test_ignores_values_the_websocket_derives(self):
        """Seen live 2026-10-15: WS power = P1+P2+P3 = 319.79999999999995, HTTP
        PowerActual = 319.9 — a representation difference, not a missed event."""
        coord = _coordinator_for_corrections()
        coord._data_index[(ENTITY_TYPE_SMART_METERS, "M1")] = {"id": "M1", "energy": 10.0, "power": 319.79999999999995}
        result = {ENTITY_TYPE_SMART_METERS: [{"id": "M1", "energy": 10.0, "power": 319.9}]}

        assert coord._record_poll_corrections(result, 100.0) == 0

    def test_counts_nothing_while_websocket_is_disconnected(self):
        coord = _coordinator_for_corrections()
        coord._ws_connected = False
        coord._data_index[(ENTITY_TYPE_LIGHTS, "L1")] = {"id": "L1", "is_on": False}
        result = {ENTITY_TYPE_LIGHTS: [{"id": "L1", "is_on": True}]}

        assert coord._record_poll_corrections(result, 100.0) == 0
        assert coord.last_poll_correction is None

    def test_ignores_entities_not_seen_before(self):
        coord = _coordinator_for_corrections()
        result = {ENTITY_TYPE_LIGHTS: [{"id": "new", "is_on": True}], "rooms": {"r1": "Living"}}

        assert coord._record_poll_corrections(result, 100.0) == 0
