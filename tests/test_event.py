"""Tests for Evon doorbell event entity."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest

_HA_MODULES = [
    "homeassistant",
    "homeassistant.components",
    "homeassistant.components.binary_sensor",
    "homeassistant.components.cover",
    "homeassistant.components.diagnostics",
    "homeassistant.components.event",
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
def setup_event_mocks():
    """Mock HA modules and set up stub classes for event tests."""
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

    class MockEventEntity:
        def _trigger_event(self, event_type, event_attributes=None):
            pass

    sys.modules["homeassistant.helpers.update_coordinator"].CoordinatorEntity = MockCoordinatorEntity
    sys.modules["homeassistant.helpers.device_registry"].DeviceInfo = dict
    sys.modules["homeassistant.core"].callback = lambda f: f
    sys.modules["homeassistant.components.event"].EventEntity = MockEventEntity
    sys.modules["homeassistant.components.event"].EventDeviceClass = MagicMock()

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


class TestDoorbellEvent:
    """Tests for doorbell event entity."""

    def _make_coordinator(self, intercoms=None):
        """Create a mock coordinator with intercom data."""
        from custom_components.evon.const import ENTITY_TYPE_INTERCOMS

        coordinator = MagicMock()
        coordinator.data = {
            ENTITY_TYPE_INTERCOMS: intercoms or []
        }
        coordinator.last_update_success = True
        return coordinator

    def _make_entity(self, coordinator, intercom_data, entry=None):
        """Create a doorbell event entity."""
        from custom_components.evon.event import EvonDoorbellEvent

        if entry is None:
            entry = MagicMock()
            entry.entry_id = "test_entry"
        return EvonDoorbellEvent(
            coordinator,
            intercom_data["id"],
            intercom_data["name"],
            intercom_data.get("room_name", ""),
            entry,
        )

    def test_event_types(self):
        """Event entity should support 'ring' event type."""
        coordinator = self._make_coordinator()
        entity = self._make_entity(coordinator, {"id": "Intercom1", "name": "Front Door"})
        assert "ring" in entity.event_types

    def test_unique_id(self):
        """Unique ID should include instance ID."""
        coordinator = self._make_coordinator()
        entity = self._make_entity(coordinator, {"id": "Intercom1", "name": "Front Door"})
        assert entity.unique_id == "evon_doorbell_Intercom1"

    def test_doorbell_transition_fires_event(self):
        """False->True transition of doorbell_triggered should fire 'ring' event."""
        intercom = {"id": "Intercom1", "name": "Front Door", "doorbell_triggered": False}
        coordinator = self._make_coordinator([intercom])
        entity = self._make_entity(coordinator, intercom)

        with patch.object(entity, "_trigger_event") as mock_trigger:
            entity._last_doorbell_state = False

            # Now doorbell triggers
            intercom["doorbell_triggered"] = True
            entity._handle_coordinator_update()

            mock_trigger.assert_called_once_with("ring")

    def test_no_event_on_same_state(self):
        """No event should fire when doorbell_triggered stays True."""
        intercom = {"id": "Intercom1", "name": "Front Door", "doorbell_triggered": True}
        coordinator = self._make_coordinator([intercom])
        entity = self._make_entity(coordinator, intercom)

        with patch.object(entity, "_trigger_event") as mock_trigger:
            entity._last_doorbell_state = True
            entity._handle_coordinator_update()
            mock_trigger.assert_not_called()

    def test_no_event_on_release(self):
        """No event should fire on True->False transition."""
        intercom = {"id": "Intercom1", "name": "Front Door", "doorbell_triggered": False}
        coordinator = self._make_coordinator([intercom])
        entity = self._make_entity(coordinator, intercom)

        with patch.object(entity, "_trigger_event") as mock_trigger:
            entity._last_doorbell_state = True
            entity._handle_coordinator_update()
            mock_trigger.assert_not_called()
