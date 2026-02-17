"""Tests for concurrent WS + HTTP updates (C-M12)."""

from __future__ import annotations

import ast
from pathlib import Path
import textwrap
import types
from unittest.mock import MagicMock

import pytest


def _load_ws_method():
    """Load _handle_ws_values_changed from source and compile it."""
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
            func_source = func_source.replace(
                "from ..ws_mappings import CLASS_TO_TYPE, ws_to_coordinator_data",
                "CLASS_TO_TYPE = _CLASS_TO_TYPE; ws_to_coordinator_data = _ws_to_coordinator_data",
            )
            return func_source

    raise RuntimeError("Could not find _handle_ws_values_changed in source")


@pytest.fixture
def coordinator_and_method():
    """Create a coordinator-like object with the real WS handler."""
    from custom_components.evon.const import (
        DOMAIN,
        ENTITY_TYPE_BUTTON_EVENTS,
        ENTITY_TYPE_INTERCOMS,
        ENTITY_TYPE_SMART_METERS,
    )
    from custom_components.evon.ws_mappings import CLASS_TO_TYPE, ws_to_coordinator_data

    func_source = _load_ws_method()

    ns = {
        "_LOGGER": MagicMock(),
        "ENTITY_TYPE_BUTTON_EVENTS": ENTITY_TYPE_BUTTON_EVENTS,
        "ENTITY_TYPE_INTERCOMS": ENTITY_TYPE_INTERCOMS,
        "ENTITY_TYPE_SMART_METERS": ENTITY_TYPE_SMART_METERS,
        "DOMAIN": DOMAIN,
        "_CLASS_TO_TYPE": CLASS_TO_TYPE,
        "_ws_to_coordinator_data": ws_to_coordinator_data,
    }

    exec(compile(func_source, "<test>", "exec"), ns)
    real_method = ns["_handle_ws_values_changed"]

    obj = MagicMock()
    obj._data_index = {}
    obj.async_set_updated_data = MagicMock()
    obj.async_request_refresh = MagicMock(return_value=MagicMock())
    obj.hass = MagicMock()
    obj.hass.bus = MagicMock()
    obj.hass.async_create_task = MagicMock()

    bound = types.MethodType(real_method, obj)
    return obj, bound


class TestConcurrentWSAndHTTP:
    """Test WS value update arriving during/after HTTP poll."""

    def test_ws_update_applies_to_current_data(self, coordinator_and_method):
        """Test that WS update correctly modifies the entity in data."""
        coordinator, handle_ws = coordinator_and_method

        light_entity = {"id": "light_1", "is_on": False, "brightness": 0, "name": "Test Light"}
        data = {"lights": [light_entity]}

        coordinator.data = data
        coordinator._data_index = {("lights", "light_1"): light_entity}

        # Simulate WS update: light turned on
        handle_ws("light_1", {"IsOn": True, "ScaledBrightness": 80})

        # The original entity should NOT be mutated (copy-on-write)
        assert light_entity["is_on"] is False

        # But the data list should contain the updated copy
        updated = data["lights"][0]
        assert updated["is_on"] is True
        assert updated["brightness"] == 80

        coordinator.async_set_updated_data.assert_called_once_with(data)

    def test_data_replaced_during_ws_processing(self, coordinator_and_method):
        """Test that WS update re-targets when data is replaced mid-processing."""
        coordinator, handle_ws = coordinator_and_method

        # Original data
        light_entity = {"id": "light_1", "is_on": True, "brightness": 50, "name": "Test Light"}
        old_data = {"lights": [light_entity]}
        coordinator._data_index = {("lights", "light_1"): light_entity}

        # New data from HTTP poll (simulated by changing self.data mid-processing)
        new_light = {"id": "light_1", "is_on": True, "brightness": 60, "name": "Test Light"}
        new_data = {"lights": [new_light]}

        call_count = 0
        original_data = old_data

        @property
        def data_prop(self_obj):
            """Simulate data being replaced after first access."""
            nonlocal call_count
            call_count += 1
            if call_count <= 1:
                return original_data
            return new_data

        # Patch data property to simulate mid-processing replacement
        type(coordinator).data = data_prop

        # Update _data_index to point to new entity on re-target
        coordinator._data_index = {("lights", "light_1"): new_light}

        handle_ws("light_1", {"IsOn": False})

        # Should have re-targeted to new data
        assert new_data["lights"][0]["is_on"] is False

        # Clean up property mock
        type(coordinator).data = MagicMock(return_value=new_data)

    def test_ws_update_for_unknown_instance_ignored(self, coordinator_and_method):
        """Test that WS updates for unknown instances are silently ignored."""
        coordinator, handle_ws = coordinator_and_method

        coordinator.data = {"lights": []}
        coordinator._data_index = {}

        # This should not raise
        handle_ws("unknown_device", {"IsOn": True})

        coordinator.async_set_updated_data.assert_not_called()

    def test_ws_update_with_empty_properties_ignored(self, coordinator_and_method):
        """Test that WS updates with empty properties are ignored."""
        coordinator, handle_ws = coordinator_and_method

        coordinator.data = {"lights": [{"id": "light_1", "is_on": True}]}
        coordinator._data_index = {("lights", "light_1"): {"id": "light_1", "is_on": True}}

        handle_ws("light_1", {})

        coordinator.async_set_updated_data.assert_not_called()

    def test_ws_update_with_none_data_ignored(self, coordinator_and_method):
        """Test that WS update is ignored when coordinator data is None."""
        coordinator, handle_ws = coordinator_and_method

        coordinator.data = None

        handle_ws("light_1", {"IsOn": True})

        coordinator.async_set_updated_data.assert_not_called()

    def test_conversion_failure_triggers_refresh(self, coordinator_and_method):
        """Test that ws_to_coordinator_data failure triggers HTTP refresh."""
        coordinator, _ = coordinator_and_method

        from custom_components.evon.const import ENTITY_TYPE_SMART_METERS
        from custom_components.evon.ws_mappings import CLASS_TO_TYPE

        func_source = _load_ws_method()

        def bad_converter(entity_type, properties, entity):
            raise ValueError("conversion failed")

        ns = {
            "_LOGGER": MagicMock(),
            "ENTITY_TYPE_BUTTON_EVENTS": "button_events",
            "ENTITY_TYPE_INTERCOMS": "intercoms",
            "ENTITY_TYPE_SMART_METERS": ENTITY_TYPE_SMART_METERS,
            "DOMAIN": "evon",
            "_CLASS_TO_TYPE": CLASS_TO_TYPE,
            "_ws_to_coordinator_data": bad_converter,
        }

        exec(compile(func_source, "<test>", "exec"), ns)
        handle_ws = types.MethodType(ns["_handle_ws_values_changed"], coordinator)

        light = {"id": "light_1", "is_on": True, "brightness": 50, "name": "Light"}
        coordinator.data = {"lights": [light]}
        coordinator._data_index = {("lights", "light_1"): light}

        handle_ws("light_1", {"IsOn": False})

        # Should schedule a refresh to recover
        coordinator.hass.async_create_task.assert_called()
