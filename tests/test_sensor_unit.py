"""Unit tests for sensor platform (no HA framework required)."""

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
def setup_sensor_mocks():
    """Mock HA modules and set up stub classes for sensor tests."""
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

    class MockSensorEntity:
        pass

    @dataclasses.dataclass(frozen=True)
    class MockSensorEntityDescription:
        key: str = ""
        name: str | None = None
        device_class: Any = None
        state_class: Any = None
        native_unit_of_measurement: str | None = None
        suggested_display_precision: int | None = None
        entity_category: Any = None
        translation_key: str | None = None

    sys.modules["homeassistant.helpers.update_coordinator"].CoordinatorEntity = (
        MockCoordinatorEntity
    )
    sys.modules["homeassistant.helpers.device_registry"].DeviceInfo = dict
    sys.modules["homeassistant.core"].callback = lambda f: f
    sys.modules["homeassistant.components.sensor"].SensorEntity = MockSensorEntity
    sys.modules["homeassistant.components.sensor"].SensorEntityDescription = (
        MockSensorEntityDescription
    )

    # Patch dataclass to accept kw_only on Python < 3.10
    _original_dataclass = dataclasses.dataclass

    def _compat_dataclass(*args, **kwargs):
        kwargs.pop("kw_only", None)
        return _original_dataclass(*args, **kwargs)

    dataclasses.dataclass = _compat_dataclass

    yield

    # Restore dataclass
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


def _make_temp_sensor(entity_data=None, instance_id="climate_1"):
    from custom_components.evon.sensor import EvonTemperatureSensor

    coordinator = MagicMock()
    coordinator.get_entity_data.return_value = entity_data
    entry = MagicMock()
    entry.entry_id = "test_entry"
    return EvonTemperatureSensor(coordinator, instance_id, "Test Climate", "", entry)


def _make_smart_meter_sensor(entity_data=None, description=None, instance_id="meter_1"):
    from custom_components.evon.sensor import EvonSmartMeterSensor

    coordinator = MagicMock()
    coordinator.get_entity_data.return_value = entity_data
    entry = MagicMock()
    entry.entry_id = "test_entry"
    if description is None:
        description = MagicMock()
        description.key = "power"
        description.value_fn = lambda data: data.get("power")
    return EvonSmartMeterSensor(
        coordinator, instance_id, "Test Meter", "", entry, description
    )


def _make_air_quality_sensor(
    entity_data=None, description=None, instance_id="aq_1"
):
    from custom_components.evon.sensor import EvonAirQualitySensor

    coordinator = MagicMock()
    coordinator.get_entity_data.return_value = entity_data
    entry = MagicMock()
    entry.entry_id = "test_entry"
    if description is None:
        description = MagicMock()
        description.key = "co2"
        description.value_fn = lambda data: data.get("co2")
    return EvonAirQualitySensor(
        coordinator, instance_id, "Test AQ", "", entry, description
    )


def _make_energy_today_sensor(entity_data=None, instance_id="meter_1"):
    from custom_components.evon.sensor import EvonEnergyTodaySensor

    coordinator = MagicMock()
    coordinator.get_entity_data.return_value = entity_data
    entry = MagicMock()
    entry.entry_id = "test_entry"
    return EvonEnergyTodaySensor(
        coordinator, instance_id, "Test Meter", "", entry
    )


def _make_energy_month_sensor(entity_data=None, instance_id="meter_1"):
    from custom_components.evon.sensor import EvonEnergyThisMonthSensor

    coordinator = MagicMock()
    coordinator.get_entity_data.return_value = entity_data
    entry = MagicMock()
    entry.entry_id = "test_entry"
    return EvonEnergyThisMonthSensor(
        coordinator, instance_id, "Test Meter", "", entry
    )


# ---------------------------------------------------------------------------
# SMART_METER_SENSORS entity descriptions
# ---------------------------------------------------------------------------


class TestSmartMeterDescriptions:
    def test_count(self):
        from custom_components.evon.sensor import SMART_METER_SENSORS

        assert len(SMART_METER_SENSORS) == 11

    def test_all_have_value_fn(self):
        from custom_components.evon.sensor import SMART_METER_SENSORS

        for desc in SMART_METER_SENSORS:
            assert desc.value_fn is not None, f"{desc.key} missing value_fn"

    def test_unique_keys(self):
        from custom_components.evon.sensor import SMART_METER_SENSORS

        keys = [d.key for d in SMART_METER_SENSORS]
        assert len(keys) == len(set(keys))

    def test_power_extracts_power(self):
        from custom_components.evon.sensor import SMART_METER_SENSORS

        desc = next(d for d in SMART_METER_SENSORS if d.key == "power")
        assert desc.value_fn({"power": 1500}) == 1500

    def test_energy_extracts_energy(self):
        from custom_components.evon.sensor import SMART_METER_SENSORS

        desc = next(d for d in SMART_METER_SENSORS if d.key == "energy")
        assert desc.value_fn({"energy": 42.5}) == 42.5

    def test_voltage_l1_extracts(self):
        from custom_components.evon.sensor import SMART_METER_SENSORS

        desc = next(d for d in SMART_METER_SENSORS if d.key == "voltage_l1")
        assert desc.value_fn({"voltage_l1": 230.5}) == 230.5


# ---------------------------------------------------------------------------
# AIR_QUALITY_SENSORS entity descriptions
# ---------------------------------------------------------------------------


class TestAirQualityDescriptions:
    def test_count(self):
        from custom_components.evon.sensor import AIR_QUALITY_SENSORS

        assert len(AIR_QUALITY_SENSORS) == 2

    def test_co2_extracts(self):
        from custom_components.evon.sensor import AIR_QUALITY_SENSORS

        desc = next(d for d in AIR_QUALITY_SENSORS if d.key == "co2")
        assert desc.value_fn({"co2": 800}) == 800

    def test_humidity_extracts(self):
        from custom_components.evon.sensor import AIR_QUALITY_SENSORS

        desc = next(d for d in AIR_QUALITY_SENSORS if d.key == "humidity")
        assert desc.value_fn({"humidity": 55}) == 55


# ---------------------------------------------------------------------------
# EvonTemperatureSensor
# ---------------------------------------------------------------------------


class TestTemperatureSensor:
    def test_native_value(self):
        sensor = _make_temp_sensor({"current_temperature": 21.5})
        assert sensor.native_value == 21.5

    def test_native_value_none_when_no_data(self):
        sensor = _make_temp_sensor(None)
        assert sensor.native_value is None

    def test_native_value_none_when_key_missing(self):
        sensor = _make_temp_sensor({})
        assert sensor.native_value is None

    def test_extra_attrs_target_temperature(self):
        sensor = _make_temp_sensor(
            {"current_temperature": 21.5, "target_temperature": 22.0}
        )
        attrs = sensor.extra_state_attributes
        assert attrs["target_temperature"] == 22.0

    def test_unique_id(self):
        sensor = _make_temp_sensor({}, instance_id="c42")
        assert sensor._attr_unique_id == "evon_temp_c42"


# ---------------------------------------------------------------------------
# EvonSmartMeterSensor
# ---------------------------------------------------------------------------


class TestSmartMeterSensor:
    def test_native_value(self):
        sensor = _make_smart_meter_sensor({"power": 1500})
        assert sensor.native_value == 1500

    def test_native_value_none_when_no_data(self):
        sensor = _make_smart_meter_sensor(None)
        assert sensor.native_value is None

    def test_native_value_none_when_key_missing(self):
        sensor = _make_smart_meter_sensor({})
        assert sensor.native_value is None


# ---------------------------------------------------------------------------
# EvonAirQualitySensor
# ---------------------------------------------------------------------------


class TestAirQualitySensor:
    def test_native_value(self):
        sensor = _make_air_quality_sensor({"co2": 800})
        assert sensor.native_value == 800

    def test_native_value_none_when_no_data(self):
        sensor = _make_air_quality_sensor(None)
        assert sensor.native_value is None

    def test_co2_extra_attrs(self):
        desc = MagicMock()
        desc.key = "co2"
        desc.value_fn = lambda data: data.get("co2")
        sensor = _make_air_quality_sensor(
            {"co2": 800, "health_index": 2, "co2_index": 1},
            description=desc,
        )
        attrs = sensor.extra_state_attributes
        assert attrs["health_index"] == 2
        assert attrs["co2_index"] == 1

    def test_humidity_extra_attrs(self):
        desc = MagicMock()
        desc.key = "humidity"
        desc.value_fn = lambda data: data.get("humidity")
        sensor = _make_air_quality_sensor(
            {"humidity": 55, "humidity_index": 3},
            description=desc,
        )
        attrs = sensor.extra_state_attributes
        assert attrs["humidity_index"] == 3


# ---------------------------------------------------------------------------
# EvonEnergyTodaySensor
# ---------------------------------------------------------------------------


class TestEnergyTodaySensor:
    def test_native_value(self):
        sensor = _make_energy_today_sensor({"energy_today_calculated": 15.2})
        assert sensor.native_value == 15.2

    def test_native_value_none_when_no_data(self):
        sensor = _make_energy_today_sensor(None)
        assert sensor.native_value is None

    def test_native_value_none_when_key_missing(self):
        sensor = _make_energy_today_sensor({})
        assert sensor.native_value is None

    def test_native_value_none_when_value_is_none(self):
        sensor = _make_energy_today_sensor({"energy_today_calculated": None})
        assert sensor.native_value is None


# ---------------------------------------------------------------------------
# EvonEnergyThisMonthSensor
# ---------------------------------------------------------------------------


class TestEnergyThisMonthSensor:
    def test_native_value(self):
        sensor = _make_energy_month_sensor({"energy_this_month_calculated": 450.0})
        assert sensor.native_value == 450.0

    def test_native_value_none_when_no_data(self):
        sensor = _make_energy_month_sensor(None)
        assert sensor.native_value is None

    def test_native_value_none_when_key_missing(self):
        sensor = _make_energy_month_sensor({})
        assert sensor.native_value is None

    def test_native_value_none_when_value_is_none(self):
        sensor = _make_energy_month_sensor({"energy_this_month_calculated": None})
        assert sensor.native_value is None
