"""Tests for copy-on-write semantics in WebSocket entity updates."""

from __future__ import annotations

import ast
from pathlib import Path
import textwrap
import time
import types
from unittest.mock import MagicMock

import pytest


def _load_ws_method():
    """Load _handle_ws_values_changed from source and compile it.

    The conftest mocks homeassistant.helpers.update_coordinator.DataUpdateCoordinator,
    which means EvonDataUpdateCoordinator becomes a MagicMock. We extract the method
    from source and compile it with the required namespace.

    The method contains a `from ..ws_mappings import ...` statement. Since we compile
    it outside of its package, we replace that import with direct references injected
    into the namespace.
    """
    source_path = str(
        Path(__file__).resolve().parent.parent / "custom_components" / "evon" / "coordinator" / "__init__.py"
    )
    with open(source_path) as f:
        source = f.read()

    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_handle_ws_values_changed":
            lines = source.splitlines()
            func_lines = lines[node.lineno - 1 : node.end_lineno]
            func_source = "\n".join(func_lines)
            func_source = textwrap.dedent(func_source)
            # Replace the relative import with globals lookup
            func_source = func_source.replace(
                "from ..ws_mappings import CLASS_TO_TYPE, ws_to_coordinator_data",
                "CLASS_TO_TYPE = _CLASS_TO_TYPE; ws_to_coordinator_data = _ws_to_coordinator_data",
            )
            return func_source

    raise RuntimeError("Could not find _handle_ws_values_changed in source")


class TestCopyOnWriteWSUpdates:
    """Test that WS updates use copy-on-write instead of in-place mutation."""

    @pytest.fixture
    def coordinator_and_method(self):
        """Create a coordinator-like object with the real WS handler bound."""
        from custom_components.evon.const import (
            DOMAIN,
            ENTITY_TYPE_BUTTON_EVENTS,
            ENTITY_TYPE_INTERCOMS,
            ENTITY_TYPE_SMART_METERS,
        )
        from custom_components.evon.ws_mappings import CLASS_TO_TYPE, ws_to_coordinator_data

        func_source = _load_ws_method()

        # Build namespace with all required names
        ns = {
            "_LOGGER": MagicMock(),
            "ENTITY_TYPE_BUTTON_EVENTS": ENTITY_TYPE_BUTTON_EVENTS,
            "ENTITY_TYPE_INTERCOMS": ENTITY_TYPE_INTERCOMS,
            "ENTITY_TYPE_SMART_METERS": ENTITY_TYPE_SMART_METERS,
            "DOMAIN": DOMAIN,
            "_CLASS_TO_TYPE": CLASS_TO_TYPE,
            "_ws_to_coordinator_data": ws_to_coordinator_data,
            "time": time,
        }

        exec(compile(func_source, "<test>", "exec"), ns)
        real_method = ns["_handle_ws_values_changed"]

        # Create coordinator-like object
        obj = MagicMock()
        obj._data_index = {}
        obj._ws_update_timestamps = {}
        obj.async_set_updated_data = MagicMock()
        obj.async_request_refresh = MagicMock(return_value=MagicMock())
        obj.hass = MagicMock()
        obj.hass.bus = MagicMock()
        obj.hass.async_create_task = MagicMock()
        obj._maybe_import_energy_statistics = MagicMock()

        # Bind the real method
        obj._handle_ws_values_changed = types.MethodType(real_method, obj)

        return obj

    def _setup_data(self, coordinator, entity_type, entities):
        """Set up coordinator data and index for testing."""
        data = {entity_type: entities}
        coordinator.data = data

        # Build the index
        for entity in entities:
            if entity and "id" in entity:
                coordinator._data_index[(entity_type, entity["id"])] = entity

        return data

    def test_ws_update_calls_async_update_listeners_not_async_set_updated_data(self, coordinator_and_method):
        """WS updates should call async_update_listeners, NOT async_set_updated_data.

        async_set_updated_data cancels and reschedules the REST poll timer.
        If WS events for other devices fire frequently (every few seconds), the
        60-second REST poll timer is continuously reset and never actually fires,
        leaving stale state indefinitely (e.g., light showing 'on' when it's off).

        Using async_update_listeners notifies entities without touching the timer.
        """
        coordinator = coordinator_and_method

        light_entity = {"id": "light_1", "name": "Test Light", "is_on": False, "brightness": 0}
        self._setup_data(coordinator, "lights", [light_entity])

        coordinator._handle_ws_values_changed("light_1", {"IsOn": True})

        coordinator.async_update_listeners.assert_called_once()
        coordinator.async_set_updated_data.assert_not_called()

    def test_ws_update_creates_new_entity_dict(self, coordinator_and_method):
        """After a WS update, the entity dict should be a different object (copy-on-write)."""
        coordinator = coordinator_and_method

        # Set up a light entity
        light_entity = {"id": "light_1", "name": "Test Light", "is_on": False, "brightness": 0}
        data = self._setup_data(coordinator, "lights", [light_entity])

        # Capture the original entity identity
        original_id = id(light_entity)

        # Simulate WS update: turn on the light
        coordinator._handle_ws_values_changed("light_1", {"IsOn": True, "ScaledBrightness": 75})

        # The entity in the list should be a DIFFERENT object (copy-on-write)
        updated_entity = data["lights"][0]
        assert id(updated_entity) != original_id, (
            "Entity dict should be a new object after WS update (copy-on-write), "
            "but it's the same object (in-place mutation)"
        )

        # The updated entity should have the new values
        assert updated_entity["is_on"] is True
        assert updated_entity["brightness"] == 75

        # The original dict should NOT have been mutated
        assert light_entity["is_on"] is False
        assert light_entity["brightness"] == 0

    def test_data_index_updated_with_new_entity(self, coordinator_and_method):
        """After a WS update, _data_index should point to the new entity copy."""
        coordinator = coordinator_and_method

        light_entity = {"id": "light_1", "name": "Test Light", "is_on": False, "brightness": 0}
        self._setup_data(coordinator, "lights", [light_entity])

        original_id = id(coordinator._data_index[("lights", "light_1")])

        coordinator._handle_ws_values_changed("light_1", {"IsOn": True})

        new_entity = coordinator._data_index[("lights", "light_1")]
        assert id(new_entity) != original_id, "_data_index should point to the new copy, not the original entity"
        assert new_entity["is_on"] is True

    def test_concurrent_reader_sees_consistent_data(self, coordinator_and_method):
        """Simulate a concurrent reader holding a reference to the old entity."""
        coordinator = coordinator_and_method

        light_entity = {"id": "light_1", "name": "Test Light", "is_on": False, "brightness": 50}
        self._setup_data(coordinator, "lights", [light_entity])

        # A concurrent reader grabs a reference to the entity
        reader_ref = light_entity

        # WS update happens
        coordinator._handle_ws_values_changed("light_1", {"IsOn": True, "ScaledBrightness": 100})

        # The reader's reference should still have the OLD values (no partial update)
        assert reader_ref["is_on"] is False
        assert reader_ref["brightness"] == 50

    def test_doorbell_event_fires_with_cow(self, coordinator_and_method):
        """Doorbell events should still fire correctly with copy-on-write."""
        coordinator = coordinator_and_method

        intercom_entity = {
            "id": "intercom_1",
            "name": "Main Intercom",
            "doorbell_triggered": False,
        }
        self._setup_data(coordinator, "intercoms", [intercom_entity])

        coordinator._handle_ws_values_changed("intercom_1", {"DoorBellTriggered": True})

        # Doorbell event should have been fired
        coordinator.hass.bus.async_fire.assert_called_once()
        call_args = coordinator.hass.bus.async_fire.call_args
        assert call_args[0][0] == "evon_doorbell"
        assert call_args[0][1]["device_id"] == "intercom_1"

    def test_smart_meter_statistics_import_with_cow(self, coordinator_and_method):
        """Energy statistics import should use the new entity copy."""
        coordinator = coordinator_and_method

        meter_entity = {
            "id": "meter_1",
            "name": "Smart Meter",
            "power_l1": 100.0,
            "power_l2": 200.0,
            "power_l3": 300.0,
        }
        self._setup_data(coordinator, "smart_meters", [meter_entity])

        coordinator._handle_ws_values_changed("meter_1", {"P1": 150.0})

        # _maybe_import_energy_statistics should be called with the updated copy
        coordinator._maybe_import_energy_statistics.assert_called_once()
        call_args = coordinator._maybe_import_energy_statistics.call_args
        assert call_args[0][0] == "meter_1"
        # The entity passed should be the updated copy, not the original
        passed_entity = call_args[0][1]
        assert passed_entity["power_l1"] == 150.0

    def test_unknown_instance_ignored(self, coordinator_and_method):
        """WS updates for unknown instances should be silently ignored."""
        coordinator = coordinator_and_method

        light_entity = {"id": "light_1", "name": "Test Light", "is_on": False}
        self._setup_data(coordinator, "lights", [light_entity])

        # Update for an unknown instance should not crash
        coordinator._handle_ws_values_changed("unknown_id", {"IsOn": True})

        # No data update should have been triggered
        coordinator.async_set_updated_data.assert_not_called()

    def test_empty_coord_data_no_copy(self, coordinator_and_method):
        """If ws_to_coordinator_data returns nothing, no copy should be created."""
        coordinator = coordinator_and_method

        light_entity = {"id": "light_1", "name": "Test Light", "is_on": False}
        self._setup_data(coordinator, "lights", [light_entity])

        original_id = id(light_entity)

        # Send a property that doesn't map to any coordinator key
        coordinator._handle_ws_values_changed("light_1", {"UnknownProp": 42})

        # Entity should not have been replaced (no changes to apply)
        assert id(coordinator._data_index[("lights", "light_1")]) == original_id
        coordinator.async_set_updated_data.assert_not_called()

    def test_ws_update_records_timestamp(self, coordinator_and_method):
        """Each WS update records a per-entity timestamp used by the poll-merge step."""
        coordinator = coordinator_and_method

        light_entity = {"id": "light_1", "name": "Test Light", "is_on": False}
        self._setup_data(coordinator, "lights", [light_entity])

        before = time.monotonic()
        coordinator._handle_ws_values_changed("light_1", {"IsOn": True})
        after = time.monotonic()

        ts = coordinator._ws_update_timestamps.get(("lights", "light_1"))
        assert ts is not None
        assert before <= ts <= after


class TestPollWsMerge:
    """Test that the periodic HTTP poll preserves WS updates that arrived during it."""

    def _make_coordinator(self):
        """Build a real EvonDataUpdateCoordinator-like object with the merge method bound."""
        from custom_components.evon.coordinator import EvonDataUpdateCoordinator

        obj = MagicMock(spec=EvonDataUpdateCoordinator)
        obj._data_index = {}
        obj._ws_update_timestamps = {}
        # Bind the real method we want to test
        obj._merge_ws_updates_into_poll_result = types.MethodType(
            EvonDataUpdateCoordinator._merge_ws_updates_into_poll_result, obj
        )
        return obj

    def test_merge_preserves_ws_update_after_poll_start(self):
        """A WS update with timestamp > poll_start_time replaces the poll's entity."""
        coord = self._make_coordinator()
        poll_start = 100.0
        # Poll's stale result for this light
        result = {"lights": [{"id": "light_1", "name": "Test Light", "is_on": False, "brightness": 0}]}
        # WS-updated version in _data_index (different dict object)
        ws_entity = {"id": "light_1", "name": "Test Light", "is_on": True, "brightness": 75}
        coord._data_index[("lights", "light_1")] = ws_entity
        coord._ws_update_timestamps[("lights", "light_1")] = poll_start + 5.0  # arrived 5s into poll

        coord._merge_ws_updates_into_poll_result(result, poll_start)

        # Poll's stale entity replaced with WS-updated one
        assert result["lights"][0] is ws_entity
        assert result["lights"][0]["is_on"] is True
        assert result["lights"][0]["brightness"] == 75

    def test_merge_ignores_ws_update_from_before_poll(self):
        """A WS update with timestamp < poll_start_time is older than poll data — poll wins."""
        coord = self._make_coordinator()
        poll_start = 100.0
        result = {"lights": [{"id": "light_1", "name": "Fresh Poll", "is_on": True}]}
        coord._data_index[("lights", "light_1")] = {"id": "light_1", "name": "Old WS", "is_on": False}
        coord._ws_update_timestamps[("lights", "light_1")] = poll_start - 10.0  # older than poll

        coord._merge_ws_updates_into_poll_result(result, poll_start)

        # Poll's entity untouched
        assert result["lights"][0]["name"] == "Fresh Poll"
        assert result["lights"][0]["is_on"] is True

    def test_merge_excludes_smart_meters(self):
        """Smart meters skip the merge so the poll's energy_today_calculated stays accurate."""
        from custom_components.evon.const import ENTITY_TYPE_SMART_METERS

        coord = self._make_coordinator()
        poll_start = 100.0
        # Poll calculated fresh energy_today
        result = {ENTITY_TYPE_SMART_METERS: [{"id": "m1", "power": 200, "energy_today_calculated": 5.5}]}
        # WS-updated meter has fresh power but stale energy_today_calculated
        coord._data_index[(ENTITY_TYPE_SMART_METERS, "m1")] = {
            "id": "m1",
            "power": 195,
            "energy_today_calculated": 4.0,
        }
        coord._ws_update_timestamps[(ENTITY_TYPE_SMART_METERS, "m1")] = poll_start + 3.0

        coord._merge_ws_updates_into_poll_result(result, poll_start)

        # Poll wins for smart meters — energy_today_calculated stays fresh
        assert result[ENTITY_TYPE_SMART_METERS][0]["energy_today_calculated"] == 5.5
        assert result[ENTITY_TYPE_SMART_METERS][0]["power"] == 200

    def test_merge_handles_missing_entity_in_index(self):
        """If a tracked timestamp points to an entity no longer in _data_index, skip it."""
        coord = self._make_coordinator()
        poll_start = 100.0
        result = {"lights": [{"id": "light_1", "is_on": False}]}
        # Timestamp recorded but entity gone from index (e.g. removed)
        coord._ws_update_timestamps[("lights", "ghost")] = poll_start + 5.0

        # Must not raise
        coord._merge_ws_updates_into_poll_result(result, poll_start)
        assert result["lights"][0]["is_on"] is False

    def test_merge_handles_missing_entity_in_result(self):
        """If a WS-tracked entity isn't in this poll's result, skip it (no crash)."""
        coord = self._make_coordinator()
        poll_start = 100.0
        result = {"lights": []}  # poll returned no lights at all
        coord._data_index[("lights", "light_1")] = {"id": "light_1", "is_on": True}
        coord._ws_update_timestamps[("lights", "light_1")] = poll_start + 5.0

        # Must not raise
        coord._merge_ws_updates_into_poll_result(result, poll_start)
        assert result["lights"] == []

    def test_merge_noop_when_no_timestamps(self):
        """No WS timestamps recorded → merge is a no-op."""
        coord = self._make_coordinator()
        original_result = {"lights": [{"id": "light_1", "is_on": False}]}
        result = original_result

        coord._merge_ws_updates_into_poll_result(result, 100.0)

        assert result is original_result
        assert result["lights"][0]["is_on"] is False
