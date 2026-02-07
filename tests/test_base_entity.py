"""Unit tests for base entity (no HA framework required)."""

from __future__ import annotations

from unittest.mock import MagicMock
import sys

import pytest


class TestBaseEntityLogic:
    """Tests for EvonEntity logic using mocked HA dependencies."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self):
        """Set up mocks for Home Assistant modules."""
        # Store original modules
        original_modules = {}
        modules_to_mock = [
            "homeassistant",
            "homeassistant.config_entries",
            "homeassistant.core",
            "homeassistant.helpers",
            "homeassistant.helpers.device_registry",
            "homeassistant.helpers.update_coordinator",
        ]

        # Create mocks
        for mod_name in modules_to_mock:
            if mod_name in sys.modules:
                original_modules[mod_name] = sys.modules[mod_name]
            sys.modules[mod_name] = MagicMock()

        # Set up specific mock behaviors - CoordinatorEntity needs to support subscripting
        class MockCoordinatorEntity:
            def __init__(self, coordinator):
                self.coordinator = coordinator

            def __class_getitem__(cls, item):
                return cls

        sys.modules["homeassistant.helpers.update_coordinator"].CoordinatorEntity = MockCoordinatorEntity
        sys.modules["homeassistant.helpers.device_registry"].DeviceInfo = dict
        sys.modules["homeassistant.core"].callback = lambda f: f

        yield

        # Restore original modules
        for mod_name in modules_to_mock:
            if mod_name in original_modules:
                sys.modules[mod_name] = original_modules[mod_name]
            else:
                del sys.modules[mod_name]

        # Clear any cached imports
        for mod_name in list(sys.modules.keys()):
            if mod_name.startswith("custom_components.evon"):
                del sys.modules[mod_name]

    def test_available_when_data_exists(self, setup_mocks):
        """Test entity is available when coordinator has data."""
        from custom_components.evon.base_entity import EvonEntity

        coordinator = MagicMock()
        coordinator.last_update_success = True
        coordinator.data = {"lights": []}

        entry = MagicMock()
        entry.entry_id = "test_entry"

        entity = EvonEntity(coordinator, "light_1", "Test Light", "Living Room", entry)

        assert entity.available is True

    def test_unavailable_when_no_data(self, setup_mocks):
        """Test entity is unavailable when coordinator has no data."""
        from custom_components.evon.base_entity import EvonEntity

        coordinator = MagicMock()
        coordinator.last_update_success = True
        coordinator.data = None

        entry = MagicMock()
        entry.entry_id = "test_entry"

        entity = EvonEntity(coordinator, "light_1", "Test Light", "", entry)

        assert entity.available is False

    def test_unavailable_when_update_failed(self, setup_mocks):
        """Test entity is unavailable when last update failed."""
        from custom_components.evon.base_entity import EvonEntity

        coordinator = MagicMock()
        coordinator.last_update_success = False
        coordinator.data = {"lights": []}

        entry = MagicMock()
        entry.entry_id = "test_entry"

        entity = EvonEntity(coordinator, "light_1", "Test Light", "", entry)

        assert entity.available is False

    def test_extra_state_attributes_basic(self, setup_mocks):
        """Test basic extra state attributes."""
        from custom_components.evon.base_entity import EvonEntity

        coordinator = MagicMock()
        coordinator.last_update_success = True
        coordinator.data = {}
        # Remove _ws_connected attribute
        coordinator._ws_connected = MagicMock(side_effect=AttributeError)
        del coordinator._ws_connected

        entry = MagicMock()
        entry.entry_id = "test_entry"

        entity = EvonEntity(coordinator, "light_1", "Test Light", "", entry)
        attrs = entity.extra_state_attributes

        assert attrs["evon_id"] == "light_1"
        assert attrs["integration"] == "evon"
        assert "room" not in attrs

    def test_extra_state_attributes_with_room(self, setup_mocks):
        """Test extra state attributes include room name."""
        from custom_components.evon.base_entity import EvonEntity

        coordinator = MagicMock()
        coordinator.last_update_success = True
        coordinator.data = {}
        del coordinator._ws_connected

        entry = MagicMock()
        entry.entry_id = "test_entry"

        entity = EvonEntity(coordinator, "blind_1", "Test Blind", "Living Room", entry)
        attrs = entity.extra_state_attributes

        assert attrs["room"] == "Living Room"

    def test_extra_state_attributes_with_websocket(self, setup_mocks):
        """Test extra state attributes include websocket status."""
        from custom_components.evon.base_entity import EvonEntity

        coordinator = MagicMock()
        coordinator.last_update_success = True
        coordinator.data = {}
        coordinator.ws_connected = True

        entry = MagicMock()
        entry.entry_id = "test_entry"

        entity = EvonEntity(coordinator, "switch_1", "Test Switch", "", entry)
        attrs = entity.extra_state_attributes

        assert attrs["websocket_connected"] is True

    def test_build_device_info_basic(self, setup_mocks):
        """Test building basic device info."""
        from custom_components.evon.base_entity import EvonEntity

        coordinator = MagicMock()

        entry = MagicMock()
        entry.entry_id = "test_entry_123"

        entity = EvonEntity(coordinator, "climate_1", "Living Room Thermostat", "", entry)
        info = entity._build_device_info("Climate Control")

        assert info["identifiers"] == {("evon", "climate_1")}
        assert info["name"] == "Living Room Thermostat"
        assert info["manufacturer"] == "Evon"
        assert info["model"] == "Climate Control"
        assert info["via_device"] == ("evon", "test_entry_123")
        assert "suggested_area" not in info

    def test_build_device_info_with_room(self, setup_mocks):
        """Test building device info with suggested area."""
        from custom_components.evon.base_entity import EvonEntity

        coordinator = MagicMock()

        entry = MagicMock()
        entry.entry_id = "test_entry_456"

        entity = EvonEntity(coordinator, "valve_1", "Bedroom Valve", "Bedroom", entry)
        info = entity._build_device_info("Climate Valve")

        assert info["suggested_area"] == "Bedroom"
        assert info["model"] == "Climate Valve"

    def test_has_entity_name_attribute(self, setup_mocks):
        """Test that EvonEntity has _attr_has_entity_name set to True."""
        from custom_components.evon.base_entity import EvonEntity

        assert EvonEntity._attr_has_entity_name is True

    def test_entity_stores_api(self, setup_mocks):
        """Test that entity stores API reference."""
        from custom_components.evon.base_entity import EvonEntity

        coordinator = MagicMock()
        entry = MagicMock()
        mock_api = MagicMock()

        entity = EvonEntity(coordinator, "device_1", "Device", "", entry, api=mock_api)

        assert entity._api is mock_api
