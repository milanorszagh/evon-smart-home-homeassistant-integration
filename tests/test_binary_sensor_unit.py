"""Unit tests for binary_sensor platform (no HA framework required)."""

from __future__ import annotations

import dataclasses
import sys
from typing import Any
from unittest.mock import MagicMock

import pytest

_HA_MODULES = [
    "homeassistant",
    "homeassistant.components",
    "homeassistant.components.binary_sensor",
    "homeassistant.components.cover",
    "homeassistant.components.diagnostics",
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
def setup_binary_sensor_mocks():
    """Mock HA modules and set up stub classes for binary sensor tests."""
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

    class MockBinarySensorEntity:
        pass

    @dataclasses.dataclass(frozen=True)
    class MockBinarySensorEntityDescription:
        key: str = ""
        name: str | None = None
        device_class: Any = None
        entity_category: Any = None
        translation_key: str | None = None
        icon: str | None = None

    sys.modules["homeassistant.helpers.update_coordinator"].CoordinatorEntity = MockCoordinatorEntity
    sys.modules["homeassistant.helpers.device_registry"].DeviceInfo = dict
    sys.modules["homeassistant.core"].callback = lambda f: f
    sys.modules["homeassistant.components.binary_sensor"].BinarySensorEntity = MockBinarySensorEntity
    sys.modules[
        "homeassistant.components.binary_sensor"
    ].BinarySensorEntityDescription = MockBinarySensorEntityDescription

    # Patch dataclass to accept kw_only on Python < 3.10
    _original_dataclass = dataclasses.dataclass

    def _compat_dataclass(*args, **kwargs):
        kwargs.pop("kw_only", None)
        return _original_dataclass(*args, **kwargs)

    dataclasses.dataclass = _compat_dataclass

    yield

    dataclasses.dataclass = _original_dataclass

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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_valve(entity_data=None, instance_id="valve_1"):
    from custom_components.evon.binary_sensor import EvonValveSensor

    coordinator = MagicMock()
    coordinator.get_entity_data.return_value = entity_data
    entry = MagicMock()
    entry.entry_id = "test_entry"
    return EvonValveSensor(coordinator, instance_id, "Test Valve", "", entry)


def _make_security_door(entity_data=None, instance_id="door_1"):
    from custom_components.evon.binary_sensor import EvonSecurityDoorSensor

    coordinator = MagicMock()
    coordinator.get_entity_data.return_value = entity_data
    entry = MagicMock()
    entry.entry_id = "test_entry"
    return EvonSecurityDoorSensor(coordinator, instance_id, "Test Door", "", entry)


def _make_security_door_call(entity_data=None, instance_id="door_1"):
    from custom_components.evon.binary_sensor import EvonSecurityDoorCallSensor

    coordinator = MagicMock()
    coordinator.get_entity_data.return_value = entity_data
    entry = MagicMock()
    entry.entry_id = "test_entry"
    return EvonSecurityDoorCallSensor(coordinator, instance_id, "Test Door", "", entry)


def _make_intercom_door(entity_data=None, instance_id="intercom_1"):
    from custom_components.evon.binary_sensor import EvonIntercomDoorSensor

    coordinator = MagicMock()
    coordinator.get_entity_data.return_value = entity_data
    entry = MagicMock()
    entry.entry_id = "test_entry"
    return EvonIntercomDoorSensor(coordinator, instance_id, "Test Intercom", "", entry)


def _make_intercom_connection(entity_data=None, instance_id="intercom_1"):
    from custom_components.evon.binary_sensor import EvonIntercomConnectionSensor

    coordinator = MagicMock()
    coordinator.get_entity_data.return_value = entity_data
    entry = MagicMock()
    entry.entry_id = "test_entry"
    return EvonIntercomConnectionSensor(coordinator, instance_id, "Test Intercom", "", entry)


def _make_weather_binary(entity_data=None, description=None, instance_id="WeatherStation1525"):
    from custom_components.evon.binary_sensor import EvonWeatherBinarySensor

    coordinator = MagicMock()
    coordinator.get_entity_data.return_value = entity_data
    entry = MagicMock()
    entry.entry_id = "test_entry"
    if description is None:
        description = MagicMock()
        description.key = "rain"
    return EvonWeatherBinarySensor(coordinator, instance_id, "Weather Dining", "", entry, description)


def _make_ws_status(ws_connected=True, last_update_success=True, use_websocket=True):
    from custom_components.evon.binary_sensor import EvonWebSocketStatusSensor

    coordinator = MagicMock()
    coordinator.ws_connected = ws_connected
    coordinator.last_update_success = last_update_success
    coordinator.use_websocket = use_websocket
    entry = MagicMock()
    entry.entry_id = "test_entry"
    return EvonWebSocketStatusSensor(coordinator, entry)


# ---------------------------------------------------------------------------
# EvonValveSensor
# ---------------------------------------------------------------------------


class TestValveSensor:
    def test_is_on_true(self):
        sensor = _make_valve({"is_open": True})
        assert sensor.is_on is True

    def test_is_on_false(self):
        sensor = _make_valve({"is_open": False})
        assert sensor.is_on is False

    def test_is_on_none_when_no_data(self):
        sensor = _make_valve(None)
        assert sensor.is_on is None

    def test_is_on_default_false_when_key_missing(self):
        sensor = _make_valve({"id": "valve_1"})
        assert sensor.is_on is False

    def test_unique_id(self):
        sensor = _make_valve({"is_open": False}, instance_id="v42")
        assert sensor._attr_unique_id == "evon_valve_v42"

    def test_extra_attrs_valve_type(self):
        sensor = _make_valve({"is_open": False, "valve_type": "heating"})
        attrs = sensor.extra_state_attributes
        assert attrs["valve_type"] == "heating"


# ---------------------------------------------------------------------------
# EvonSecurityDoorSensor
# ---------------------------------------------------------------------------


class TestSecurityDoorSensor:
    def test_is_on_true(self):
        sensor = _make_security_door({"is_open": True})
        assert sensor.is_on is True

    def test_is_on_false(self):
        sensor = _make_security_door({"is_open": False})
        assert sensor.is_on is False

    def test_is_on_none_when_no_data(self):
        sensor = _make_security_door(None)
        assert sensor.is_on is None

    def test_unique_id(self):
        sensor = _make_security_door({"is_open": False}, instance_id="d99")
        assert sensor._attr_unique_id == "evon_security_door_d99"


# ---------------------------------------------------------------------------
# EvonSecurityDoorCallSensor
# ---------------------------------------------------------------------------


class TestSecurityDoorCallSensor:
    def test_is_on_true(self):
        sensor = _make_security_door_call({"call_in_progress": True})
        assert sensor.is_on is True

    def test_is_on_false(self):
        sensor = _make_security_door_call({"call_in_progress": False})
        assert sensor.is_on is False

    def test_is_on_none_when_no_data(self):
        sensor = _make_security_door_call(None)
        assert sensor.is_on is None

    def test_unique_id(self):
        sensor = _make_security_door_call({"call_in_progress": False}, instance_id="d5")
        assert sensor._attr_unique_id == "evon_security_door_d5_call"


# ---------------------------------------------------------------------------
# EvonIntercomDoorSensor
# ---------------------------------------------------------------------------


class TestIntercomDoorSensor:
    def test_is_on_true(self):
        sensor = _make_intercom_door({"is_door_open": True})
        assert sensor.is_on is True

    def test_is_on_false(self):
        sensor = _make_intercom_door({"is_door_open": False})
        assert sensor.is_on is False

    def test_is_on_none_when_no_data(self):
        sensor = _make_intercom_door(None)
        assert sensor.is_on is None

    def test_extra_attrs(self):
        sensor = _make_intercom_door(
            {
                "is_door_open": True,
                "doorbell_triggered": True,
                "door_open_triggered": False,
            }
        )
        attrs = sensor.extra_state_attributes
        assert attrs["doorbell_triggered"] is True
        assert attrs["door_open_triggered"] is False

    def test_unique_id(self):
        sensor = _make_intercom_door({}, instance_id="ic3")
        assert sensor._attr_unique_id == "evon_intercom_ic3"


# ---------------------------------------------------------------------------
# EvonIntercomConnectionSensor (inverted: is_on = NOT connection_lost)
# ---------------------------------------------------------------------------


class TestIntercomConnectionSensor:
    def test_connected_when_not_lost(self):
        sensor = _make_intercom_connection({"connection_lost": False})
        assert sensor.is_on is True

    def test_disconnected_when_lost(self):
        sensor = _make_intercom_connection({"connection_lost": True})
        assert sensor.is_on is False

    def test_connected_when_none(self):
        # None is not True -> connected
        sensor = _make_intercom_connection({"connection_lost": None})
        assert sensor.is_on is True

    def test_connected_when_key_missing(self):
        # .get returns None -> None is not True -> connected
        sensor = _make_intercom_connection({"id": "intercom_1"})
        assert sensor.is_on is True

    def test_none_when_no_data(self):
        sensor = _make_intercom_connection(None)
        assert sensor.is_on is None

    def test_unique_id(self):
        sensor = _make_intercom_connection({}, instance_id="ic7")
        assert sensor._attr_unique_id == "evon_intercom_ic7_connection"


# ---------------------------------------------------------------------------
# EvonWebSocketStatusSensor (standalone, not EvonEntity-based)
# ---------------------------------------------------------------------------


class TestWebSocketStatusSensor:
    def test_is_on_when_connected(self):
        sensor = _make_ws_status(ws_connected=True)
        assert sensor.is_on is True

    def test_is_on_when_disconnected(self):
        sensor = _make_ws_status(ws_connected=False)
        assert sensor.is_on is False

    def test_available_when_update_success(self):
        sensor = _make_ws_status(last_update_success=True)
        assert sensor.available is True

    def test_unavailable_when_update_failed(self):
        sensor = _make_ws_status(last_update_success=False)
        assert sensor.available is False

    def test_extra_attrs_use_websocket(self):
        sensor = _make_ws_status(use_websocket=True)
        attrs = sensor.extra_state_attributes
        assert attrs["use_websocket"] is True

    def test_unique_id(self):
        sensor = _make_ws_status()
        assert sensor._attr_unique_id == "evon_websocket_test_entry"


# ---------------------------------------------------------------------------
# WEATHER_BINARY_SENSORS + EvonWeatherBinarySensor
# ---------------------------------------------------------------------------


class TestWeatherBinarySensors:
    def test_count_and_keys(self):
        from custom_components.evon.binary_sensor import WEATHER_BINARY_SENSORS

        keys = [d.key for d in WEATHER_BINARY_SENSORS]
        assert len(keys) == 8
        assert keys == [
            "rain",
            "twilight",
            "wind_alarm",
            "wind_alarm_1",
            "wind_alarm_2",
            "connected",
            "temperature_valid",
            "polling_activated",
        ]

    def test_translation_keys(self):
        from custom_components.evon.binary_sensor import WEATHER_BINARY_SENSORS

        for d in WEATHER_BINARY_SENSORS:
            assert d.translation_key == f"weather_{d.key}"

    def test_is_on_true(self):
        description = MagicMock()
        description.key = "rain"
        sensor = _make_weather_binary({"rain": True}, description)
        assert sensor.is_on is True

    def test_is_on_false(self):
        description = MagicMock()
        description.key = "rain"
        sensor = _make_weather_binary({"rain": False}, description)
        assert sensor.is_on is False

    def test_is_on_none_when_field_missing(self):
        description = MagicMock()
        description.key = "rain"
        sensor = _make_weather_binary({"temperature": 1.0}, description)
        assert sensor.is_on is None

    def test_is_on_none_when_no_data(self):
        sensor = _make_weather_binary(None)
        assert sensor.is_on is None

    def test_unique_id_format(self):
        description = MagicMock()
        description.key = "wind_alarm_2"
        sensor = _make_weather_binary({"wind_alarm_2": True}, description, instance_id="WeatherStation1525")
        assert sensor._attr_unique_id == "evon_weather_WeatherStation1525_wind_alarm_2"

    def test_device_info_model(self):
        sensor = _make_weather_binary({"rain": False})
        sensor.coordinator.hub_device_id = None
        info = sensor.device_info
        assert info["model"] == "Weather Station"
        assert info["manufacturer"] == "Evon"
