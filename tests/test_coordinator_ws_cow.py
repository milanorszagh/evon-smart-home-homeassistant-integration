"""Tests for copy-on-write semantics in WebSocket entity updates."""

from __future__ import annotations

import ast
import textwrap
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
    source_path = "/Users/milan/www/evon-ha/custom_components/evon/coordinator/__init__.py"
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
            ENTITY_TYPE_INTERCOMS,
            ENTITY_TYPE_SMART_METERS,
        )
        from custom_components.evon.ws_mappings import CLASS_TO_TYPE, ws_to_coordinator_data

        func_source = _load_ws_method()

        # Build namespace with all required names
        ns = {
            "_LOGGER": MagicMock(),
            "ENTITY_TYPE_INTERCOMS": ENTITY_TYPE_INTERCOMS,
            "ENTITY_TYPE_SMART_METERS": ENTITY_TYPE_SMART_METERS,
            "DOMAIN": DOMAIN,
            "_CLASS_TO_TYPE": CLASS_TO_TYPE,
            "_ws_to_coordinator_data": ws_to_coordinator_data,
        }

        exec(compile(func_source, "<test>", "exec"), ns)
        real_method = ns["_handle_ws_values_changed"]

        # Create coordinator-like object
        obj = MagicMock()
        obj._data_index = {}
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
        assert id(new_entity) != original_id, (
            "_data_index should point to the new copy, not the original entity"
        )
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
