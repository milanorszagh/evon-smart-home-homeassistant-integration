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
        _attr_unique_id: str | None = None

        def __init__(self, coordinator):
            self.coordinator = coordinator

        def __class_getitem__(cls, item):
            return cls

        @property
        def unique_id(self) -> str | None:
            return self._attr_unique_id

        def async_write_ha_state(self):
            pass

    class MockEventEntity:
        _attr_event_types: list[str] = []

        @property
        def event_types(self) -> list[str]:
            return self._attr_event_types

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
    """Tests for button press type detection logic using ButtonPressDetector."""

    def _make_detector(self, double_click_delay=None):
        """Create a ButtonPressDetector with a mock callback and timer scheduler.

        Uses the real production ButtonPressDetector class directly.
        """
        from custom_components.evon.const import DEFAULT_BUTTON_DOUBLE_CLICK_DELAY
        from custom_components.evon.coordinator.button_press import ButtonPressDetector

        callback = MagicMock()
        scheduler = MagicMock()

        delay = double_click_delay if double_click_delay is not None else DEFAULT_BUTTON_DOUBLE_CLICK_DELAY

        detector = ButtonPressDetector(
            on_press=callback,
            schedule_timer=scheduler,
            double_click_delay=delay,
        )

        return detector, callback, scheduler

    def test_long_press_fires_immediately(self):
        """A press held > 1.5s should fire long_press immediately on release."""
        detector, callback, scheduler = self._make_detector()
        entity_data = {"id": "btn1", "name": "Test Button"}

        with patch("custom_components.evon.coordinator.button_press.time.monotonic") as mock_time:
            mock_time.return_value = 0.0
            detector.handle_event("btn1", entity_data, True)
            mock_time.return_value = 2.0
            detector.handle_event("btn1", entity_data, False)

        callback.assert_called_once_with("btn1", entity_data, "long_press")

    def test_short_press_schedules_timer(self):
        """A short press should schedule a delayed timer, not fire immediately."""
        detector, callback, scheduler = self._make_detector()
        entity_data = {"id": "btn1", "name": "Test Button"}

        with patch("custom_components.evon.coordinator.button_press.time.monotonic") as mock_time:
            mock_time.return_value = 0.0
            detector.handle_event("btn1", entity_data, True)
            mock_time.return_value = 0.19
            detector.handle_event("btn1", entity_data, False)

        callback.assert_not_called()
        scheduler.assert_called_once()
        delay = scheduler.call_args[0][0]
        assert delay == 0.8  # DEFAULT_BUTTON_DOUBLE_CLICK_DELAY

    def test_single_press_timeout(self):
        """Timer expiry with release_count=1 should fire single_press."""
        detector, callback, scheduler = self._make_detector()
        entity_data = {"id": "btn1", "name": "Test Button"}

        with patch("custom_components.evon.coordinator.button_press.time.monotonic") as mock_time:
            mock_time.return_value = 0.0
            detector.handle_event("btn1", entity_data, True)
            mock_time.return_value = 0.19
            detector.handle_event("btn1", entity_data, False)

        detector.timeout("btn1", entity_data)

        callback.assert_called_once_with("btn1", entity_data, "single_press")

    def test_double_press(self):
        """Two short presses within window should fire double_press."""
        detector, callback, scheduler = self._make_detector()
        entity_data = {"id": "btn1", "name": "Test Button"}

        mock_timer = MagicMock()
        scheduler.return_value = mock_timer

        with patch("custom_components.evon.coordinator.button_press.time.monotonic") as mock_time:
            mock_time.return_value = 0.0
            detector.handle_event("btn1", entity_data, True)
            mock_time.return_value = 0.19
            detector.handle_event("btn1", entity_data, False)

            mock_time.return_value = 0.4
            detector.handle_event("btn1", entity_data, True)
            mock_time.return_value = 0.55
            detector.handle_event("btn1", entity_data, False)

        mock_timer.cancel.assert_called()

        detector.timeout("btn1", entity_data)

        callback.assert_called_once_with("btn1", entity_data, "double_press")

    def test_triple_press_fires_double(self):
        """Three rapid presses within window should fire double_press."""
        detector, callback, scheduler = self._make_detector()
        entity_data = {"id": "btn1", "name": "Test Button"}

        mock_timer = MagicMock()
        scheduler.return_value = mock_timer

        with patch("custom_components.evon.coordinator.button_press.time.monotonic") as mock_time:
            for press_t, release_t in [(0.0, 0.1), (0.2, 0.3), (0.4, 0.5)]:
                mock_time.return_value = press_t
                detector.handle_event("btn1", entity_data, True)
                mock_time.return_value = release_t
                detector.handle_event("btn1", entity_data, False)

        detector.timeout("btn1", entity_data)

        callback.assert_called_once_with("btn1", entity_data, "double_press")

    def test_double_press_true_true_false_pattern(self):
        """Evon controller sends True, True, False for double-press (coalesced release)."""
        detector, callback, scheduler = self._make_detector()
        entity_data = {"id": "btn1", "name": "Test Button"}

        mock_timer = MagicMock()
        scheduler.return_value = mock_timer

        with patch("custom_components.evon.coordinator.button_press.time.monotonic") as mock_time:
            mock_time.return_value = 0.0
            detector.handle_event("btn1", entity_data, True)
            mock_time.return_value = 0.2
            detector.handle_event("btn1", entity_data, True)
            mock_time.return_value = 0.4
            detector.handle_event("btn1", entity_data, False)

        detector.timeout("btn1", entity_data)

        callback.assert_called_once_with("btn1", entity_data, "double_press")

    def test_double_press_true_false_false_pattern(self):
        """Evon controller sends True, False, False for double-press (coalesced press)."""
        detector, callback, scheduler = self._make_detector()
        entity_data = {"id": "btn1", "name": "Test Button"}

        mock_timer = MagicMock()
        scheduler.return_value = mock_timer

        with patch("custom_components.evon.coordinator.button_press.time.monotonic") as mock_time:
            mock_time.return_value = 0.0
            detector.handle_event("btn1", entity_data, True)
            mock_time.return_value = 0.2
            detector.handle_event("btn1", entity_data, False)
            mock_time.return_value = 0.4
            detector.handle_event("btn1", entity_data, False)

        detector.timeout("btn1", entity_data)

        callback.assert_called_once_with("btn1", entity_data, "double_press")

    def test_long_press_cancels_pending_timer(self):
        """A long press after a short press should cancel the pending timer."""
        detector, callback, scheduler = self._make_detector()
        entity_data = {"id": "btn1", "name": "Test Button"}

        mock_timer = MagicMock()
        scheduler.return_value = mock_timer

        with patch("custom_components.evon.coordinator.button_press.time.monotonic") as mock_time:
            mock_time.return_value = 0.0
            detector.handle_event("btn1", entity_data, True)
            mock_time.return_value = 0.19
            detector.handle_event("btn1", entity_data, False)

            mock_time.return_value = 0.4
            detector.handle_event("btn1", entity_data, True)
            mock_time.return_value = 2.0
            detector.handle_event("btn1", entity_data, False)

        mock_timer.cancel.assert_called()

        callback.assert_called_once_with("btn1", entity_data, "long_press")

    def test_cow_relookup_in_timeout(self):
        """Timeout with different entity_data should use the provided data."""
        detector, callback, scheduler = self._make_detector()
        original_data = {"id": "btn1", "name": "Test Button"}

        with patch("custom_components.evon.coordinator.button_press.time.monotonic") as mock_time:
            mock_time.return_value = 0.0
            detector.handle_event("btn1", original_data, True)
            mock_time.return_value = 0.19
            detector.handle_event("btn1", original_data, False)

        # Simulate CoW: pass different entity_data to timeout
        new_data = {"id": "btn1", "name": "Test Button"}
        detector.timeout("btn1", new_data)

        # Callback should receive new_data, not original_data
        callback.assert_called_once_with("btn1", new_data, "single_press")

    def test_release_without_press_ignored(self):
        """A release without a prior press and no timer should be ignored."""
        detector, callback, scheduler = self._make_detector()
        entity_data = {"id": "btn1", "name": "Test Button"}

        # Initialize state with no press_start and no timer
        detector.state["btn1"] = {
            "press_start": None,
            "release_count": 0,
            "pending_timer": None,
        }

        detector.handle_event("btn1", entity_data, False)

        callback.assert_not_called()
        scheduler.assert_not_called()

    def test_cancel_all_timers(self):
        """cancel_all_timers should cancel pending timers and clear state."""
        detector, callback, scheduler = self._make_detector()
        entity_data = {"id": "btn1", "name": "Test Button"}

        mock_timer = MagicMock()
        scheduler.return_value = mock_timer

        with patch("custom_components.evon.coordinator.button_press.time.monotonic") as mock_time:
            mock_time.return_value = 0.0
            detector.handle_event("btn1", entity_data, True)
            mock_time.return_value = 0.19
            detector.handle_event("btn1", entity_data, False)

        assert len(detector.state) == 1

        detector.cancel_all_timers()

        mock_timer.cancel.assert_called()
        assert len(detector.state) == 0

    def test_custom_double_click_delay(self):
        """Non-default double_click_delay should be used in timer scheduling."""
        detector, callback, scheduler = self._make_detector(double_click_delay=0.3)
        entity_data = {"id": "btn1", "name": "Test Button"}

        with patch("custom_components.evon.coordinator.button_press.time.monotonic") as mock_time:
            mock_time.return_value = 0.0
            detector.handle_event("btn1", entity_data, True)
            mock_time.return_value = 0.19
            detector.handle_event("btn1", entity_data, False)

        scheduler.assert_called_once()
        delay = scheduler.call_args[0][0]
        assert delay == 0.3

    def test_max_double_click_delay(self):
        """Maximum double_click_delay (1.4s) should be used correctly."""
        detector, callback, scheduler = self._make_detector(double_click_delay=1.4)
        entity_data = {"id": "btn1", "name": "Test Button"}

        mock_timer = MagicMock()
        scheduler.return_value = mock_timer

        with patch("custom_components.evon.coordinator.button_press.time.monotonic") as mock_time:
            # Two short presses
            mock_time.return_value = 0.0
            detector.handle_event("btn1", entity_data, True)
            mock_time.return_value = 0.19
            detector.handle_event("btn1", entity_data, False)

            mock_time.return_value = 0.4
            detector.handle_event("btn1", entity_data, True)
            mock_time.return_value = 0.55
            detector.handle_event("btn1", entity_data, False)

        # All timer calls should use 1.4s delay
        for call in scheduler.call_args_list:
            assert call[0][0] == 1.4

        detector.timeout("btn1", entity_data)
        callback.assert_called_once_with("btn1", entity_data, "double_press")


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

        asyncio.run(async_setup_entry(hass, entry, added_entities.extend))

        button_entities = [e for e in added_entities if isinstance(e, EvonButtonEvent)]
        assert len(button_entities) == 2
        assert button_entities[0].unique_id == "evon_button_btn1"
        assert button_entities[1].unique_id == "evon_button_btn2"
