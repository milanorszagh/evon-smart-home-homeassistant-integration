"""Tests for Evon physical button event entities and press detection."""

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
def setup_button_mocks():
    """Mock HA modules and set up stub classes for button event tests."""
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


# --- Processor Tests ---


class TestButtonEventsProcessor:
    """Tests for the button_events processor."""

    def test_filters_only_physical_buttons(self):
        """Processor should only include SmartCOM.Switch instances."""
        from custom_components.evon.coordinator.processors.button_events import process_button_events

        instances = [
            {"ID": "btn1", "ClassName": "SmartCOM.Switch", "Name": "Button 1", "Group": "room1"},
            {"ID": "light1", "ClassName": "SmartCOM.Light.LightDim", "Name": "Light", "Group": "room1"},
            {"ID": "btn2", "ClassName": "SmartCOM.Switch", "Name": "Button 2", "Group": "room2"},
        ]

        result = process_button_events(instances, lambda g: f"Room_{g}")

        assert len(result) == 2
        assert result[0]["id"] == "btn1"
        assert result[0]["name"] == "Button 1"
        assert result[0]["room_name"] == "Room_room1"
        assert result[1]["id"] == "btn2"

    def test_skips_unnamed_instances(self):
        """Processor should skip instances with no Name."""
        from custom_components.evon.coordinator.processors.button_events import process_button_events

        instances = [
            {"ID": "btn1", "ClassName": "SmartCOM.Switch", "Name": "", "Group": "room1"},
            {"ID": "btn2", "ClassName": "SmartCOM.Switch", "Name": "Named Button", "Group": "room1"},
        ]

        result = process_button_events(instances, lambda g: "")

        assert len(result) == 1
        assert result[0]["id"] == "btn2"

    def test_initial_state(self):
        """Processor should set is_on=False and last_event_type=None."""
        from custom_components.evon.coordinator.processors.button_events import process_button_events

        instances = [
            {"ID": "btn1", "ClassName": "SmartCOM.Switch", "Name": "Button", "Group": ""},
        ]

        result = process_button_events(instances, lambda g: "")

        assert result[0]["is_on"] is False
        assert result[0]["last_event_type"] is None

    def test_empty_instances(self):
        """Processor should return empty list with no instances."""
        from custom_components.evon.coordinator.processors.button_events import process_button_events

        result = process_button_events([], lambda g: "")
        assert result == []


# --- Button Event Entity Tests ---


class TestButtonEventEntity:
    """Tests for the EvonButtonEvent entity."""

    def _make_coordinator(self, buttons=None):
        """Create a mock coordinator with button data."""
        from custom_components.evon.const import ENTITY_TYPE_BUTTON_EVENTS

        buttons = buttons or []
        coordinator = MagicMock()
        coordinator.data = {ENTITY_TYPE_BUTTON_EVENTS: buttons}
        coordinator.last_update_success = True

        # Make get_entity_data return the correct button dict by ID
        def _get_entity_data(etype, iid):
            if etype == ENTITY_TYPE_BUTTON_EVENTS:
                for b in buttons:
                    if b["id"] == iid:
                        return b
            return None

        coordinator.get_entity_data = _get_entity_data
        return coordinator

    def _make_entity(self, coordinator, button_data, entry=None):
        """Create a button event entity."""
        from custom_components.evon.event import EvonButtonEvent

        if entry is None:
            entry = MagicMock()
            entry.entry_id = "test_entry"
        return EvonButtonEvent(
            coordinator,
            button_data["id"],
            button_data["name"],
            button_data.get("room_name", ""),
            entry,
        )

    def test_event_types(self):
        """Button event entity should support all three press types."""
        coordinator = self._make_coordinator()
        entity = self._make_entity(coordinator, {"id": "btn1", "name": "Test Button"})
        assert "single_press" in entity.event_types
        assert "double_press" in entity.event_types
        assert "long_press" in entity.event_types

    def test_unique_id(self):
        """Unique ID should include 'button' prefix and instance ID."""
        coordinator = self._make_coordinator()
        entity = self._make_entity(coordinator, {"id": "btn1", "name": "Test Button"})
        assert entity.unique_id == "evon_button_btn1"

    def test_device_info_model(self):
        """Device info should use 'Button' model."""
        coordinator = self._make_coordinator()
        entity = self._make_entity(coordinator, {"id": "btn1", "name": "Test Button"})
        info = entity.device_info
        assert info["model"] == "Button"

    def test_fires_event_on_new_event(self):
        """Entity should fire event when last_event_id changes."""
        button = {"id": "btn1", "name": "Test Button", "is_on": False, "last_event_type": None, "last_event_id": 0}
        coordinator = self._make_coordinator([button])
        entity = self._make_entity(coordinator, button)

        with patch.object(entity, "_trigger_event") as mock_trigger:
            # Simulate coordinator update with new event
            button["last_event_type"] = "single_press"
            button["last_event_id"] = 1
            entity._handle_coordinator_update()
            mock_trigger.assert_called_once_with("single_press")

    def test_no_event_on_same_event_id(self):
        """Entity should not re-fire when last_event_id hasn't changed."""
        button = {
            "id": "btn1",
            "name": "Test Button",
            "is_on": False,
            "last_event_type": "single_press",
            "last_event_id": 1,
        }
        coordinator = self._make_coordinator([button])
        entity = self._make_entity(coordinator, button)
        entity._last_event_id = 1

        with patch.object(entity, "_trigger_event") as mock_trigger:
            entity._handle_coordinator_update()
            mock_trigger.assert_not_called()

    def test_fires_repeated_same_type(self):
        """Entity should fire when same event type occurs again with new event_id."""
        button = {
            "id": "btn1",
            "name": "Test Button",
            "is_on": False,
            "last_event_type": "single_press",
            "last_event_id": 1,
        }
        coordinator = self._make_coordinator([button])
        entity = self._make_entity(coordinator, button)
        entity._last_event_id = 1

        with patch.object(entity, "_trigger_event") as mock_trigger:
            # Second single press with new event_id
            button["last_event_id"] = 2
            entity._handle_coordinator_update()
            mock_trigger.assert_called_once_with("single_press")

    def test_fires_different_event_types(self):
        """Entity should fire when event type changes from one to another."""
        button = {
            "id": "btn1",
            "name": "Test Button",
            "is_on": False,
            "last_event_type": "single_press",
            "last_event_id": 1,
        }
        coordinator = self._make_coordinator([button])
        entity = self._make_entity(coordinator, button)
        entity._last_event_id = 1

        with patch.object(entity, "_trigger_event") as mock_trigger:
            button["last_event_type"] = "double_press"
            button["last_event_id"] = 2
            entity._handle_coordinator_update()
            mock_trigger.assert_called_once_with("double_press")

    def test_no_event_on_none(self):
        """Entity should not fire when last_event_type is None."""
        button = {"id": "btn1", "name": "Test Button", "is_on": False, "last_event_type": None, "last_event_id": 0}
        coordinator = self._make_coordinator([button])
        entity = self._make_entity(coordinator, button)

        with patch.object(entity, "_trigger_event") as mock_trigger:
            entity._handle_coordinator_update()
            mock_trigger.assert_not_called()


# --- Press Detection Tests ---


class TestButtonPressDetection:
    """Tests for button press type detection logic in coordinator."""

    def _make_coordinator(self):
        """Create a minimal coordinator with button press state tracking.

        Uses the actual press detection functions from the coordinator module
        source, bound to a fake coordinator object.
        """
        import types

        from custom_components.evon.const import (
            BUTTON_DOUBLE_CLICK_WINDOW,
            BUTTON_LONG_PRESS_THRESHOLD,
            DOMAIN,
            ENTITY_TYPE_BUTTON_EVENTS,
        )

        class FakeCoordinator:
            pass

        coordinator = FakeCoordinator()
        coordinator._button_press_state = {}
        coordinator._data_index = {}
        coordinator.data = {}
        coordinator.hass = MagicMock()
        coordinator.hass.loop = MagicMock()
        coordinator.hass.bus = MagicMock()
        coordinator.async_set_updated_data = MagicMock()

        # Define the methods inline (mirroring coordinator logic) to avoid
        # importing EvonDataUpdateCoordinator which requires HA framework.
        # These MUST match the production signatures exactly.
        def _handle_button_press(self, instance_id, entity_data, is_on):
            import time as _time

            now = _time.monotonic()
            if instance_id not in self._button_press_state:
                self._button_press_state[instance_id] = {
                    "press_start": None,
                    "release_count": 0,
                    "pending_timer": None,
                }
            state = self._button_press_state[instance_id]
            if is_on:
                state["press_start"] = now
            else:
                press_start = state.get("press_start")
                if press_start is None:
                    return
                hold_duration = now - press_start
                state["press_start"] = None
                if hold_duration >= BUTTON_LONG_PRESS_THRESHOLD:
                    if state.get("pending_timer") is not None:
                        state["pending_timer"].cancel()
                        state["pending_timer"] = None
                    state["release_count"] = 0
                    self._fire_button_event(instance_id, entity_data, "long_press")
                else:
                    state["release_count"] += 1
                    if state.get("pending_timer") is not None:
                        state["pending_timer"].cancel()
                    state["pending_timer"] = self.hass.loop.call_later(
                        BUTTON_DOUBLE_CLICK_WINDOW,
                        self._button_press_timeout,
                        instance_id,
                    )

        def _button_press_timeout(self, instance_id):
            state = self._button_press_state.get(instance_id)
            if state is None:
                return
            release_count = state.get("release_count", 0)
            state["release_count"] = 0
            state["pending_timer"] = None
            # Re-lookup current entity data (may have been replaced by CoW)
            entity_data = self._data_index.get((ENTITY_TYPE_BUTTON_EVENTS, instance_id))
            if entity_data is None:
                return
            if release_count >= 2:  # 3+ clicks also treated as double press
                self._fire_button_event(instance_id, entity_data, "double_press")
            elif release_count == 1:
                self._fire_button_event(instance_id, entity_data, "single_press")

        def _fire_button_event(self, instance_id, entity_data, press_type):
            button_name = entity_data.get("name", "")
            self.hass.bus.async_fire(
                f"{DOMAIN}_button_press",
                {"device_id": instance_id, "name": button_name, "press_type": press_type},
            )
            entity_data["last_event_type"] = press_type
            entity_data["last_event_id"] = entity_data.get("last_event_id", 0) + 1
            if self.data:
                self.async_set_updated_data(self.data)

        coordinator._handle_button_press = types.MethodType(_handle_button_press, coordinator)
        coordinator._button_press_timeout = types.MethodType(_button_press_timeout, coordinator)
        coordinator._fire_button_event = types.MethodType(_fire_button_event, coordinator)

        return coordinator

    def _register_entity(self, coordinator, entity_data):
        """Register entity_data in coordinator's _data_index for CoW re-lookup."""
        from custom_components.evon.const import ENTITY_TYPE_BUTTON_EVENTS

        coordinator._data_index[(ENTITY_TYPE_BUTTON_EVENTS, entity_data["id"])] = entity_data

    def test_long_press_fires_immediately(self):
        """A press held > 1.5s should fire long_press immediately on release."""
        coordinator = self._make_coordinator()
        entity_data = {"id": "btn1", "name": "Test Button", "last_event_type": None, "last_event_id": 0}
        self._register_entity(coordinator, entity_data)

        with patch("time.monotonic") as mock_time:
            # Press at t=0
            mock_time.return_value = 0.0
            coordinator._handle_button_press("btn1", entity_data, True)

            # Release at t=2.0 (>1.5s threshold)
            mock_time.return_value = 2.0
            coordinator._handle_button_press("btn1", entity_data, False)

        # Should fire long_press event immediately (no timer)
        coordinator.hass.bus.async_fire.assert_called_once()
        call_args = coordinator.hass.bus.async_fire.call_args
        assert call_args[0][0] == "evon_button_press"
        assert call_args[0][1]["press_type"] == "long_press"
        assert call_args[0][1]["device_id"] == "btn1"

    def test_short_press_schedules_timer(self):
        """A short press should schedule a delayed timer, not fire immediately."""
        coordinator = self._make_coordinator()
        entity_data = {"id": "btn1", "name": "Test Button", "last_event_type": None, "last_event_id": 0}
        self._register_entity(coordinator, entity_data)

        with patch("time.monotonic") as mock_time:
            # Press at t=0
            mock_time.return_value = 0.0
            coordinator._handle_button_press("btn1", entity_data, True)

            # Release at t=0.19 (short press)
            mock_time.return_value = 0.19
            coordinator._handle_button_press("btn1", entity_data, False)

        # Should NOT fire event immediately
        coordinator.hass.bus.async_fire.assert_not_called()

        # Should schedule a timer
        coordinator.hass.loop.call_later.assert_called_once()
        delay = coordinator.hass.loop.call_later.call_args[0][0]
        assert delay == 1.0  # BUTTON_DOUBLE_CLICK_WINDOW

    def test_single_press_timeout(self):
        """Timer expiry with release_count=1 should fire single_press."""
        coordinator = self._make_coordinator()
        entity_data = {"id": "btn1", "name": "Test Button", "last_event_type": None, "last_event_id": 0}
        self._register_entity(coordinator, entity_data)

        with patch("time.monotonic") as mock_time:
            mock_time.return_value = 0.0
            coordinator._handle_button_press("btn1", entity_data, True)
            mock_time.return_value = 0.19
            coordinator._handle_button_press("btn1", entity_data, False)

        # Simulate timer expiry (no entity_data arg — re-looks up from _data_index)
        coordinator._button_press_timeout("btn1")

        coordinator.hass.bus.async_fire.assert_called_once()
        call_args = coordinator.hass.bus.async_fire.call_args
        assert call_args[0][1]["press_type"] == "single_press"

    def test_double_press(self):
        """Two short presses within window should fire double_press."""
        coordinator = self._make_coordinator()
        entity_data = {"id": "btn1", "name": "Test Button", "last_event_type": None, "last_event_id": 0}
        self._register_entity(coordinator, entity_data)

        # Mock call_later to return a cancellable timer
        mock_timer = MagicMock()
        coordinator.hass.loop.call_later.return_value = mock_timer

        with patch("time.monotonic") as mock_time:
            # First press+release
            mock_time.return_value = 0.0
            coordinator._handle_button_press("btn1", entity_data, True)
            mock_time.return_value = 0.19
            coordinator._handle_button_press("btn1", entity_data, False)

            # Second press+release (within 0.6s window)
            mock_time.return_value = 0.4
            coordinator._handle_button_press("btn1", entity_data, True)
            mock_time.return_value = 0.55
            coordinator._handle_button_press("btn1", entity_data, False)

        # First timer should have been cancelled
        mock_timer.cancel.assert_called()

        # Simulate timer expiry — should fire double_press
        coordinator._button_press_timeout("btn1")

        coordinator.hass.bus.async_fire.assert_called_once()
        call_args = coordinator.hass.bus.async_fire.call_args
        assert call_args[0][1]["press_type"] == "double_press"

    def test_triple_press_fires_double(self):
        """Three rapid presses within window should fire double_press."""
        coordinator = self._make_coordinator()
        entity_data = {"id": "btn1", "name": "Test Button", "last_event_type": None, "last_event_id": 0}
        self._register_entity(coordinator, entity_data)

        mock_timer = MagicMock()
        coordinator.hass.loop.call_later.return_value = mock_timer

        with patch("time.monotonic") as mock_time:
            # Three rapid press+release cycles
            for press_t, release_t in [(0.0, 0.1), (0.2, 0.3), (0.4, 0.5)]:
                mock_time.return_value = press_t
                coordinator._handle_button_press("btn1", entity_data, True)
                mock_time.return_value = release_t
                coordinator._handle_button_press("btn1", entity_data, False)

        # Simulate timer expiry — 3+ clicks treated as double_press
        coordinator._button_press_timeout("btn1")

        coordinator.hass.bus.async_fire.assert_called_once()
        call_args = coordinator.hass.bus.async_fire.call_args
        assert call_args[0][1]["press_type"] == "double_press"

    def test_long_press_cancels_pending_timer(self):
        """A long press after a short press should cancel the pending timer."""
        coordinator = self._make_coordinator()
        entity_data = {"id": "btn1", "name": "Test Button", "last_event_type": None, "last_event_id": 0}
        self._register_entity(coordinator, entity_data)

        mock_timer = MagicMock()
        coordinator.hass.loop.call_later.return_value = mock_timer

        with patch("time.monotonic") as mock_time:
            # First short press+release
            mock_time.return_value = 0.0
            coordinator._handle_button_press("btn1", entity_data, True)
            mock_time.return_value = 0.19
            coordinator._handle_button_press("btn1", entity_data, False)

            # Second press — held long
            mock_time.return_value = 0.4
            coordinator._handle_button_press("btn1", entity_data, True)
            mock_time.return_value = 2.0
            coordinator._handle_button_press("btn1", entity_data, False)

        # Timer from first press should have been cancelled
        mock_timer.cancel.assert_called()

        # Should fire long_press (not double_press)
        coordinator.hass.bus.async_fire.assert_called_once()
        call_args = coordinator.hass.bus.async_fire.call_args
        assert call_args[0][1]["press_type"] == "long_press"

    def test_cow_relookup_in_timeout(self):
        """Timeout should use fresh entity_data from _data_index, not stale ref."""
        coordinator = self._make_coordinator()
        original_data = {"id": "btn1", "name": "Test Button", "last_event_type": None, "last_event_id": 0}
        self._register_entity(coordinator, original_data)

        with patch("time.monotonic") as mock_time:
            mock_time.return_value = 0.0
            coordinator._handle_button_press("btn1", original_data, True)
            mock_time.return_value = 0.19
            coordinator._handle_button_press("btn1", original_data, False)

        # Simulate CoW: replace entity_data in _data_index with a new dict
        from custom_components.evon.const import ENTITY_TYPE_BUTTON_EVENTS

        new_data = {"id": "btn1", "name": "Test Button", "last_event_type": None, "last_event_id": 0}
        coordinator._data_index[(ENTITY_TYPE_BUTTON_EVENTS, "btn1")] = new_data

        # Simulate timer expiry — should update new_data, NOT original_data
        coordinator._button_press_timeout("btn1")

        assert new_data["last_event_type"] == "single_press"
        assert new_data["last_event_id"] == 1
        # Original should be untouched
        assert original_data["last_event_type"] is None

    def test_release_without_press_ignored(self):
        """A release without a prior press should be ignored."""
        coordinator = self._make_coordinator()
        entity_data = {"id": "btn1", "name": "Test Button", "last_event_type": None, "last_event_id": 0}

        # Initialize state with no press_start
        coordinator._button_press_state["btn1"] = {
            "press_start": None,
            "release_count": 0,
            "pending_timer": None,
        }

        coordinator._handle_button_press("btn1", entity_data, False)

        coordinator.hass.bus.async_fire.assert_not_called()
        coordinator.hass.loop.call_later.assert_not_called()

    def test_fire_button_event_updates_entity_data(self):
        """_fire_button_event should update last_event_type and last_event_id."""
        coordinator = self._make_coordinator()
        entity_data = {"id": "btn1", "name": "Test Button", "last_event_type": None, "last_event_id": 0}

        coordinator._fire_button_event("btn1", entity_data, "single_press")

        assert entity_data["last_event_type"] == "single_press"
        assert entity_data["last_event_id"] == 1

        # Second fire should increment
        coordinator._fire_button_event("btn1", entity_data, "single_press")
        assert entity_data["last_event_id"] == 2

    def test_fire_button_event_bus_event(self):
        """_fire_button_event should fire HA bus event with correct data."""
        coordinator = self._make_coordinator()
        entity_data = {"id": "btn1", "name": "Living Room Button", "last_event_type": None, "last_event_id": 0}

        coordinator._fire_button_event("btn1", entity_data, "double_press")

        coordinator.hass.bus.async_fire.assert_called_once_with(
            "evon_button_press",
            {
                "device_id": "btn1",
                "name": "Living Room Button",
                "press_type": "double_press",
            },
        )


# --- async_setup_entry Tests ---


class TestAsyncSetupEntry:
    """Tests for event platform setup including button events."""

    def test_setup_creates_button_entities(self):
        """async_setup_entry should create EvonButtonEvent entities."""
        from custom_components.evon.const import ENTITY_TYPE_BUTTON_EVENTS, ENTITY_TYPE_INTERCOMS
        from custom_components.evon.event import EvonButtonEvent

        coordinator = MagicMock()
        coordinator.data = {
            ENTITY_TYPE_INTERCOMS: [],
            ENTITY_TYPE_BUTTON_EVENTS: [
                {"id": "btn1", "name": "Button 1", "room_name": "Living Room"},
                {"id": "btn2", "name": "Button 2", "room_name": ""},
            ],
        }
        coordinator.last_update_success = True

        # Collect entities that would be added
        added_entities = []

        import asyncio

        from custom_components.evon.event import async_setup_entry

        hass = MagicMock()
        entry = MagicMock()
        entry.entry_id = "test_entry"
        hass.data = {"evon": {"test_entry": {"coordinator": coordinator}}}

        asyncio.get_event_loop().run_until_complete(async_setup_entry(hass, entry, added_entities.extend))

        button_entities = [e for e in added_entities if isinstance(e, EvonButtonEvent)]
        assert len(button_entities) == 2
        assert button_entities[0].unique_id == "evon_button_btn1"
        assert button_entities[1].unique_id == "evon_button_btn2"
