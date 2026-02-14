"""Pytest fixtures for Evon Smart Home tests."""

from __future__ import annotations

import copy
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

# Add repo root to path so custom_components can be found
REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

import importlib.util

# Mock homeassistant module BEFORE importing custom_components
# This allows tests to run without the full homeassistant package installed
if not importlib.util.find_spec("homeassistant"):
    # Create mock homeassistant modules
    mock_ha = MagicMock()
    mock_ha.config_entries = MagicMock()
    mock_ha.config_entries.ConfigEntry = MagicMock()
    mock_ha.const = MagicMock()
    mock_ha.const.Platform = MagicMock()
    mock_ha.const.ATTR_TEMPERATURE = "temperature"
    mock_ha.const.UnitOfTemperature = MagicMock()
    mock_ha.core = MagicMock()
    mock_ha.core.HomeAssistant = MagicMock()
    mock_ha.core.ServiceCall = MagicMock()
    mock_ha.helpers = MagicMock()
    mock_ha.helpers.device_registry = MagicMock()
    mock_ha.helpers.entity_registry = MagicMock()
    mock_ha.helpers.issue_registry = MagicMock()
    mock_ha.helpers.aiohttp_client = MagicMock()
    mock_ha.helpers.entity_platform = MagicMock()
    mock_ha.helpers.entity = MagicMock()
    mock_ha.helpers.update_coordinator = MagicMock()
    mock_ha.components = MagicMock()
    # Climate component with real string constants matching HA
    mock_climate = MagicMock()
    mock_climate.HVACMode = SimpleNamespace(
        HEAT="heat",
        COOL="cool",
        OFF="off",
        AUTO="auto",
        HEAT_COOL="heat_cool",
        DRY="dry",
        FAN_ONLY="fan_only",
    )
    mock_climate.ClimateEntityFeature = SimpleNamespace(
        TARGET_TEMPERATURE=1,
        PRESET_MODE=16,
        TARGET_TEMPERATURE_RANGE=2,
        FAN_MODE=8,
    )
    mock_climate.ATTR_TEMPERATURE = "temperature"
    mock_ha.components.climate = mock_climate

    # Light component with real string constants matching HA
    mock_light = MagicMock()
    mock_light.ColorMode = SimpleNamespace(
        ONOFF="onoff",
        BRIGHTNESS="brightness",
        COLOR_TEMP="color_temp",
        HS="hs",
        RGB="rgb",
        RGBW="rgbw",
        RGBWW="rgbww",
        XY="xy",
        WHITE="white",
        UNKNOWN="unknown",
    )
    mock_light.LightEntityFeature = SimpleNamespace(
        EFFECT=4,
        FLASH=8,
        TRANSITION=32,
    )
    mock_ha.components.light = mock_light
    mock_ha.components.cover = MagicMock()
    mock_ha.components.sensor = MagicMock()
    mock_ha.components.binary_sensor = MagicMock()
    mock_ha.components.switch = MagicMock()
    mock_ha.components.select = MagicMock()
    mock_ha.components.button = MagicMock()
    mock_ha.components.scene = MagicMock()
    # Camera component with proper base class
    mock_camera = MagicMock()
    mock_camera.Camera = type("Camera", (), {"__init__": lambda self: None})
    mock_camera.CameraEntityFeature = MagicMock()
    mock_camera.CameraEntityFeature.ON_OFF = 1
    mock_ha.components.camera = mock_camera

    # Image component with proper base class
    mock_image = MagicMock()
    mock_image.ImageEntity = type("ImageEntity", (), {"__init__": lambda self, hass: None})
    mock_ha.components.image = mock_image
    # Exceptions need to be real exception classes so they can be raised/caught
    mock_exceptions = MagicMock()

    class _HomeAssistantError(Exception):
        """Mock HomeAssistantError."""

    mock_exceptions.HomeAssistantError = _HomeAssistantError
    mock_ha.exceptions = mock_exceptions
    mock_ha.util = MagicMock()
    # Provide real dt_util functions so camera_recorder gets real datetimes
    from datetime import datetime, timezone

    mock_dt = MagicMock()
    mock_dt.now = lambda: datetime.now(tz=timezone.utc)  # noqa: UP017
    mock_dt.utc_from_timestamp = lambda ts: datetime.fromtimestamp(ts, tz=timezone.utc)  # noqa: UP017
    mock_ha.util.dt = mock_dt
    mock_ha.components.repairs = MagicMock()
    mock_ha.loader = MagicMock()
    mock_ha.helpers.config_validation = MagicMock()
    mock_ha.data_entry_flow = MagicMock()

    # Register the mocks in sys.modules
    sys.modules["homeassistant"] = mock_ha
    sys.modules["homeassistant.config_entries"] = mock_ha.config_entries
    sys.modules["homeassistant.const"] = mock_ha.const
    sys.modules["homeassistant.core"] = mock_ha.core
    sys.modules["homeassistant.helpers"] = mock_ha.helpers
    sys.modules["homeassistant.helpers.device_registry"] = mock_ha.helpers.device_registry
    sys.modules["homeassistant.helpers.entity_registry"] = mock_ha.helpers.entity_registry
    sys.modules["homeassistant.helpers.issue_registry"] = mock_ha.helpers.issue_registry
    sys.modules["homeassistant.helpers.aiohttp_client"] = mock_ha.helpers.aiohttp_client
    sys.modules["homeassistant.helpers.entity_platform"] = mock_ha.helpers.entity_platform
    sys.modules["homeassistant.helpers.entity"] = mock_ha.helpers.entity
    sys.modules["homeassistant.helpers.update_coordinator"] = mock_ha.helpers.update_coordinator
    sys.modules["homeassistant.components"] = mock_ha.components
    sys.modules["homeassistant.components.climate"] = mock_ha.components.climate
    sys.modules["homeassistant.components.light"] = mock_ha.components.light
    sys.modules["homeassistant.components.cover"] = mock_ha.components.cover
    sys.modules["homeassistant.components.sensor"] = mock_ha.components.sensor
    sys.modules["homeassistant.components.binary_sensor"] = mock_ha.components.binary_sensor
    sys.modules["homeassistant.components.switch"] = mock_ha.components.switch
    sys.modules["homeassistant.components.select"] = mock_ha.components.select
    sys.modules["homeassistant.components.button"] = mock_ha.components.button
    sys.modules["homeassistant.components.scene"] = mock_ha.components.scene
    sys.modules["homeassistant.components.camera"] = mock_ha.components.camera
    sys.modules["homeassistant.components.image"] = mock_ha.components.image

    # Recorder component for statistics (used by energy sensors)
    mock_recorder = MagicMock()
    mock_recorder_statistics = MagicMock()
    mock_recorder_statistics.statistics_during_period = MagicMock(return_value={})
    mock_recorder.statistics = mock_recorder_statistics

    # Recorder models for StatisticData/StatisticMetaData (used by statistics.py)
    mock_recorder_models = MagicMock()
    # StatisticData should behave like a dict-like dataclass
    mock_recorder_models.StatisticData = lambda **kwargs: kwargs
    mock_recorder_models.StatisticMetaData = lambda **kwargs: kwargs
    mock_recorder.models = mock_recorder_models

    # Recorder models.statistics for StatisticMeanType
    mock_recorder_models_statistics = MagicMock()
    mock_recorder_models_statistics.StatisticMeanType = MagicMock()
    mock_recorder_models_statistics.StatisticMeanType.NONE = 0
    mock_recorder_models.statistics = mock_recorder_models_statistics

    mock_ha.components.recorder = mock_recorder
    sys.modules["homeassistant.components.recorder"] = mock_ha.components.recorder
    sys.modules["homeassistant.components.recorder.statistics"] = mock_recorder_statistics
    sys.modules["homeassistant.components.recorder.models"] = mock_recorder_models
    sys.modules["homeassistant.components.recorder.models.statistics"] = mock_recorder_models_statistics

    sys.modules["homeassistant.exceptions"] = mock_ha.exceptions
    sys.modules["homeassistant.util"] = mock_ha.util
    sys.modules["homeassistant.util.dt"] = mock_ha.util.dt
    sys.modules["homeassistant.components.repairs"] = mock_ha.components.repairs
    sys.modules["homeassistant.loader"] = mock_ha.loader
    sys.modules["homeassistant.helpers.config_validation"] = mock_ha.helpers.config_validation
    sys.modules["homeassistant.data_entry_flow"] = mock_ha.data_entry_flow

    # Device automation and trigger modules (used by device_trigger.py)
    mock_device_automation = MagicMock()
    mock_device_automation.DEVICE_TRIGGER_BASE_SCHEMA = MagicMock()
    sys.modules["homeassistant.components.device_automation"] = mock_device_automation

    mock_ha_triggers = MagicMock()
    sys.modules["homeassistant.components.homeassistant"] = MagicMock()
    sys.modules["homeassistant.components.homeassistant.triggers"] = MagicMock()
    sys.modules["homeassistant.components.homeassistant.triggers.event"] = mock_ha_triggers

    mock_trigger_helpers = MagicMock()
    sys.modules["homeassistant.helpers.trigger"] = mock_trigger_helpers
    sys.modules["homeassistant.helpers.typing"] = MagicMock()

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

# Load pytest_homeassistant_custom_component plugin if available
# This must be at module level for pytest to pick it up
if importlib.util.find_spec("pytest_homeassistant_custom_component"):
    pytest_plugins = ["pytest_homeassistant_custom_component"]

# Test constants - these are placeholders, not real credentials
TEST_HOST = "http://192.168.1.100"
TEST_USERNAME = "testuser"
TEST_PASSWORD = "testpass"
TEST_ENTRY_ID = "test_entry_id"

# Check if pytest-homeassistant-custom-component is available
HAS_HA_TEST_FRAMEWORK = importlib.util.find_spec("pytest_homeassistant_custom_component") is not None

# Skip marker for tests requiring the HA test framework
requires_ha_test_framework = pytest.mark.skipif(
    not HAS_HA_TEST_FRAMEWORK,
    reason="Test requires pytest-homeassistant-custom-component",
)


# Import pytest-homeassistant-custom-component fixtures if available
if HAS_HA_TEST_FRAMEWORK:
    import asyncio
    import contextlib
    import logging
    import threading

    from pytest_homeassistant_custom_component.common import (
        INSTANCES,
        MockConfigEntry,
        get_scheduled_timer_handles,
    )
    from homeassistant.core import HassJob

    _LOGGER = logging.getLogger(__name__)

    # long_repr_strings may not be available in older versions
    try:
        from pytest_homeassistant_custom_component.common import long_repr_strings
    except ImportError:

        @contextlib.contextmanager
        def long_repr_strings():
            """Fallback no-op context manager."""
            yield

    @pytest.fixture(autouse=True)
    def verify_cleanup(
        expected_lingering_tasks: bool,
        expected_lingering_timers: bool,
    ) -> Generator[None]:
        """Verify that the test has cleaned up resources correctly.

        This overrides the fixture from pytest-homeassistant-custom-component
        to also allow _run_safe_shutdown_loop threads which are created by
        asyncio during event loop handling.
        """
        loop = asyncio.get_event_loop()
        threads_before = frozenset(threading.enumerate())
        tasks_before = asyncio.all_tasks(loop)
        yield

        loop.run_until_complete(loop.shutdown_default_executor())

        if len(INSTANCES) >= 2:
            count = len(INSTANCES)
            for inst in INSTANCES:
                inst.stop()
            pytest.exit(f"Detected non stopped instances ({count}), aborting test run")

        # Warn and clean-up lingering tasks and timers
        tasks = asyncio.all_tasks(loop) - tasks_before
        for task in tasks:
            if expected_lingering_tasks:
                _LOGGER.warning("Lingering task after test %r", task)
            else:
                pytest.fail(f"Lingering task after test {task!r}")
            task.cancel()
        if tasks:
            loop.run_until_complete(asyncio.wait(tasks))

        for handle in get_scheduled_timer_handles(loop):
            if not handle.cancelled():
                with long_repr_strings():
                    if expected_lingering_timers:
                        _LOGGER.warning("Lingering timer after test %r", handle)
                    elif handle._args and isinstance(job := handle._args[-1], HassJob):
                        if job.cancel_on_shutdown:
                            continue
                        pytest.fail(f"Lingering timer after job {job!r}")
                    else:
                        pytest.fail(f"Lingering timer after test {handle!r}")

        # Verify no threads were left behind
        threads = frozenset(threading.enumerate()) - threads_before
        for thread in threads:
            # Allow DummyThread, waitpid threads, and _run_safe_shutdown_loop threads
            assert (
                isinstance(thread, threading._DummyThread)
                or thread.name.startswith("waitpid-")
                or "_run_safe_shutdown_loop" in thread.name
            ), f"Lingering thread after test: {thread.name}"

    # Global mock API that persists across tests in a module
    # This ensures consistent mocking even when module imports are cached
    _MOCK_API_INSTANCE = None

    def _create_mock_api():
        """Create a fresh mock API instance."""
        mock_api = AsyncMock()
        mock_api.test_connection = AsyncMock(return_value=True)
        mock_api.login = AsyncMock(return_value="test_token")
        mock_api.get_instances = AsyncMock(return_value=MOCK_INSTANCES)
        mock_api.get_instance = AsyncMock(
            side_effect=lambda instance_id: copy.deepcopy(MOCK_INSTANCE_DETAILS.get(instance_id, {}))
        )
        # Light methods
        mock_api.turn_on_light = AsyncMock()
        mock_api.turn_off_light = AsyncMock()
        mock_api.set_light_brightness = AsyncMock()
        mock_api.set_light_color_temp = AsyncMock()
        # Switch methods
        mock_api.turn_on_switch = AsyncMock()
        mock_api.turn_off_switch = AsyncMock()
        # Blind methods
        mock_api.open_blind = AsyncMock()
        mock_api.close_blind = AsyncMock()
        mock_api.stop_blind = AsyncMock()
        mock_api.set_blind_position = AsyncMock()
        mock_api.set_blind_tilt = AsyncMock()
        # Blind group methods
        mock_api.open_all_blinds = AsyncMock()
        mock_api.close_all_blinds = AsyncMock()
        mock_api.stop_all_blinds = AsyncMock()
        # Climate methods
        mock_api.set_climate_comfort_mode = AsyncMock()
        mock_api.set_climate_energy_saving_mode = AsyncMock()
        mock_api.set_climate_freeze_protection_mode = AsyncMock()

        async def _validated_set_climate_temperature(instance_id, temperature):
            if not 5 <= temperature <= 40:
                raise ValueError(f"Temperature {temperature} out of valid range 5-40")

        mock_api.set_climate_temperature = AsyncMock(side_effect=_validated_set_climate_temperature)
        # Home state methods
        mock_api.activate_home_state = AsyncMock()
        # Season mode methods
        mock_api.get_season_mode = AsyncMock(return_value=False)  # False = heating mode
        mock_api.set_season_mode = AsyncMock()
        # Rooms for sync_areas
        mock_api.get_rooms = AsyncMock(
            return_value={
                "room_living": "Living Room",
                "room_kitchen": "Kitchen",
                "room_bedroom": "Bedroom",
                "room_bathroom": "Bathroom",
            }
        )
        # Bathroom radiator methods
        mock_api.toggle_bathroom_radiator = AsyncMock()
        mock_api.turn_on_bathroom_radiator = AsyncMock()
        mock_api.turn_off_bathroom_radiator = AsyncMock()
        # Scene methods
        mock_api.execute_scene = AsyncMock()
        # Global control methods
        mock_api.all_lights_off = AsyncMock()
        mock_api.all_blinds_close = AsyncMock()
        mock_api.all_blinds_open = AsyncMock()
        # Image fetch method
        mock_api.fetch_image = AsyncMock(return_value=b"\xff\xd8\xff\xe0\x00\x10JFIF")  # JPEG header bytes
        # WebSocket control support methods
        mock_api.set_ws_client = MagicMock()
        mock_api.set_instance_classes = MagicMock()
        # Blind position/angle cache methods (synchronous, not async)
        mock_api._blind_positions = {}
        mock_api._blind_angles = {}
        mock_api.update_blind_position = lambda instance_id, position: mock_api._blind_positions.update(
            {instance_id: position}
        )
        mock_api.update_blind_angle = lambda instance_id, angle: mock_api._blind_angles.update({instance_id: angle})
        mock_api.get_blind_position = lambda instance_id: mock_api._blind_positions.get(instance_id)
        mock_api.get_blind_angle = lambda instance_id: mock_api._blind_angles.get(instance_id)
        return mock_api

    @pytest.fixture(autouse=True)
    async def auto_enable_custom_integrations(hass, enable_custom_integrations):
        """Enable custom integrations for all tests automatically.

        This fixture patches HA's loader to find our custom_components directory.
        It also ensures proper cleanup of config entries to avoid lingering tasks.
        """
        import homeassistant.loader as loader

        # Get the path to our custom_components directory
        custom_components_path = REPO_ROOT / "custom_components"

        # Clear cached integrations to force rediscovery
        if hasattr(loader, "DATA_CUSTOM_COMPONENTS") and loader.DATA_CUSTOM_COMPONENTS in hass.data:
            del hass.data[loader.DATA_CUSTOM_COMPONENTS]

        # Ensure custom_components module is available in sys.modules with correct path
        # This is critical for pytest-homeassistant-custom-component to find our integration
        if "custom_components" in sys.modules:
            # Extend the path to include our custom_components
            existing_module = sys.modules["custom_components"]
            if hasattr(existing_module, "__path__"):
                if str(custom_components_path) not in existing_module.__path__:
                    existing_module.__path__.insert(0, str(custom_components_path))
        else:
            # Create a new custom_components module pointing to our directory
            import types

            custom_components_module = types.ModuleType("custom_components")
            custom_components_module.__path__ = [str(custom_components_path)]
            custom_components_module.__file__ = str(custom_components_path / "__init__.py")
            sys.modules["custom_components"] = custom_components_module

        yield

        # Cleanup: Unload any evon config entries to stop coordinator tasks
        # This prevents "lingering tasks" errors from pytest-homeassistant-custom-component
        for entry in list(hass.config_entries.async_entries("evon")):
            with contextlib.suppress(Exception):
                await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()

    @pytest.fixture
    def mock_config_entry_v2() -> MockConfigEntry:
        """Create a MockConfigEntry for integration tests."""
        return MockConfigEntry(
            domain="evon",
            title="Evon Smart Home",
            data={
                "connection_type": "local",
                "host": TEST_HOST,
                "username": TEST_USERNAME,
                "password": TEST_PASSWORD,
            },
            options={
                "scan_interval": 30,
                "sync_areas": False,
                "non_dimmable_lights": [],
                "http_only": True,  # Disable WebSocket for tests since it's not mocked
            },
            entry_id=TEST_ENTRY_ID,
        )

    @pytest.fixture
    def mock_evon_api_class(hass):
        """Fixture that patches EvonApi class and returns a mock instance.

        This fixture depends on hass to ensure the custom_components paths are set up
        by pytest-homeassistant-custom-component before we try to patch.
        """
        global _MOCK_API_INSTANCE
        # Create fresh mock for each test to reset call counts
        mock_api = _create_mock_api()
        _MOCK_API_INSTANCE = mock_api

        # Patch at both the api module and the __init__.py import location
        # This ensures the mock is used regardless of import order
        with (
            patch("custom_components.evon.api.EvonApi", return_value=mock_api),
            patch("custom_components.evon.EvonApi", return_value=mock_api),
        ):
            yield mock_api


# =============================================================================
# Mock API Data
# =============================================================================

MOCK_INSTANCES = [
    # Lights
    {
        "ID": "light_1",
        "ClassName": "SmartCOM.Light.LightDim",
        "Name": "Living Room Light",
        "Group": "room_living",
    },
    {
        "ID": "light_2",
        "ClassName": "SmartCOM.Light.Light",
        "Name": "Kitchen Relay",
        "Group": "room_kitchen",
    },
    # Blinds
    {
        "ID": "blind_1",
        "ClassName": "SmartCOM.Blind.Blind",
        "Name": "Living Room Blind",
        "Group": "room_living",
    },
    # Climate
    {
        "ID": "climate_1",
        "ClassName": "SmartCOM.Clima.ClimateControl",
        "Name": "Living Room Climate",
        "Group": "room_living",
    },
    # Home States
    {
        "ID": "HomeStateAtHome",
        "ClassName": "System.HomeState",
        "Name": "At Home",
        "Active": True,
    },
    {
        "ID": "HomeStateNight",
        "ClassName": "System.HomeState",
        "Name": "Night",
        "Active": False,
    },
    {
        "ID": "HomeStateWork",
        "ClassName": "System.HomeState",
        "Name": "Work",
        "Active": False,
    },
    {
        "ID": "HomeStateHoliday",
        "ClassName": "System.HomeState",
        "Name": "Holiday",
        "Active": False,
    },
    # Season Mode (ehThermostat)
    {
        "ID": "Base.ehThermostat",
        "ClassName": "Base.ehThermostat",
        "Name": "Season Mode",
        "IsCool": False,
    },
    # Sensors
    {
        "ID": "sensor_temp_1",
        "ClassName": "SmartCOM.Clima.ClimateControl",
        "Name": "Bedroom Climate",
        "Group": "room_bedroom",
    },
    # Smart Meter
    {
        "ID": "smart_meter_1",
        "ClassName": "Energy.SmartMeterModbus",
        "Name": "Smart Meter",
    },
    # Air Quality
    {
        "ID": "air_quality_1",
        "ClassName": "System.Location.AirQuality",
        "Name": "Air Quality",
    },
    # Bathroom Radiator
    {
        "ID": "bathroom_radiator_1",
        "ClassName": "Heating.BathroomRadiator",
        "Name": "Bathroom Radiator",
        "Group": "room_bathroom",
    },
    # Valve
    {
        "ID": "valve_1",
        "ClassName": "SmartCOM.Clima.Valve",
        "Name": "Living Room Valve",
        "Group": "room_living",
    },
    # Scenes
    {
        "ID": "SceneApp1234",
        "ClassName": "System.SceneApp",
        "Name": "All Lights Off",
    },
    # Security Door
    {
        "ID": "security_door_1",
        "ClassName": "Security.Door",
        "Name": "Front Door",
        "Group": "room_living",
    },
    # Intercom
    {
        "ID": "intercom_1",
        "ClassName": "Security.Intercom.2N.Intercom2N",
        "Name": "Main Intercom",
        "Group": "room_living",
    },
    # Camera (2N Intercom Camera)
    {
        "ID": "intercom_1.Cam",
        "ClassName": "Security.Intercom.2N.Intercom2NCam",
        "Name": "Intercom Camera",
        "Group": "room_living",
    },
    # Light Group
    {
        "ID": "light_group_1",
        "ClassName": "SmartCOM.Light.LightGroup",
        "Name": "All Living Room Lights",
        "Group": "room_living",
    },
    # Blind Group
    {
        "ID": "blind_group_1",
        "ClassName": "SmartCOM.Blind.BlindGroup",
        "Name": "All Living Room Blinds",
        "Group": "room_living",
    },
    # RGBW Light
    {
        "ID": "rgbw_light_1",
        "ClassName": "SmartCOM.Light.DynamicRGBWLight",
        "Name": "RGBW Light",
        "Group": "room_living",
    },
    # Rooms
    {
        "ID": "room_living",
        "ClassName": "System.Location.Room",
        "Name": "Living Room",
    },
    {
        "ID": "room_kitchen",
        "ClassName": "System.Location.Room",
        "Name": "Kitchen",
    },
    {
        "ID": "room_bedroom",
        "ClassName": "System.Location.Room",
        "Name": "Bedroom",
    },
    {
        "ID": "room_bathroom",
        "ClassName": "System.Location.Room",
        "Name": "Bathroom",
    },
]

MOCK_INSTANCE_DETAILS = {
    "light_1": {
        "IsOn": True,
        "ScaledBrightness": 75,
    },
    "light_2": {
        "IsOn": False,
        "ScaledBrightness": 0,
    },
    "blind_1": {
        "Position": 50,
        "Angle": 45,
        "IsMoving": False,
    },
    "climate_1": {
        "ActualTemperature": 21.5,
        "SetTemperature": 22.0,
        "MinSetValueHeat": 15,
        "MaxSetValueHeat": 25,
        "SetValueComfortHeating": 22,
        "SetValueEnergySavingHeating": 20,
        "SetValueFreezeProtection": 15,
        "ModeSaved": 4,  # Comfort in heating mode
        "CoolingMode": False,
        "IsOn": True,
        "Humidity": 45.0,
    },
    "sensor_temp_1": {
        "ActualTemperature": 20.0,
        "SetTemperature": 21.0,
        "MinSetValueHeat": 15,
        "MaxSetValueHeat": 25,
        "SetValueComfortHeating": 21,
        "SetValueEnergySavingHeating": 19,
        "SetValueFreezeProtection": 15,
        "ModeSaved": 3,  # Eco in heating mode
        "CoolingMode": False,
        "IsOn": False,
    },
    "smart_meter_1": {
        "PowerActual": 1500.0,
        "Energy": 12345.67,
        "Energy24h": 45.5,
        "UL1N": 230.1,
        "UL2N": 229.8,
        "UL3N": 230.5,
        "IL1": 2.5,
        "IL2": 1.8,
        "IL3": 2.1,
        "Frequency": 50.0,
        "FeedInEnergy": 100.5,
        # Per-phase power for WebSocket real-time updates
        "P1": 500.0,
        "P2": 480.0,
        "P3": 520.0,
    },
    "air_quality_1": {
        "CO2Value": 650,
        "Humidity": 45.5,
    },
    "bathroom_radiator_1": {
        "Output": True,
        "NextSwitchPoint": 25,
        "EnableForMins": 30,
    },
    "valve_1": {
        "ActValue": True,
    },
    "Base.ehThermostat": {
        "IsCool": False,
    },
    "HomeStateAtHome": {
        "Active": True,
        "Name": "At Home",
    },
    "HomeStateNight": {
        "Active": False,
        "Name": "Night",
    },
    "HomeStateWork": {
        "Active": False,
        "Name": "Work",
    },
    "HomeStateHoliday": {
        "Active": False,
        "Name": "Holiday",
    },
    "security_door_1": {
        "IsOpen": False,
        "DoorIsOpen": False,
        "CallInProgress": False,
        "CamInstanceName": "intercom_1.Cam",
        "SavedPictures": [
            {"imageUrlClient": "/images/snapshot_1.jpg", "datetime": 1706900000000},
            {"imageUrlClient": "/images/snapshot_2.jpg", "datetime": 1706899000000},
        ],
    },
    "intercom_1": {
        "DoorBellTriggered": False,
        "DoorOpenTriggered": False,
        "IsDoorOpen": False,
        "ConnectionToIntercomHasBeenLost": False,
        "CamInstanceName": "intercom_1.Cam",
        "SavedPictures": [
            {"imageUrlClient": "/images/snapshot_1.jpg", "datetime": 1706900000000},
            {"imageUrlClient": "/images/snapshot_2.jpg", "datetime": 1706899000000},
        ],
    },
    "intercom_1.Cam": {
        "ImagePath": "/images/current.jpg",
        "IpAddress": "192.168.1.50",
        "Error": False,
    },
    "light_group_1": {
        "IsOn": True,
        "ScaledBrightness": 80,
    },
    "blind_group_1": {
        "Position": 30,
        "Angle": 50,
        "IsMoving": False,
    },
    "rgbw_light_1": {
        "IsOn": True,
        "ScaledBrightness": 100,
        "ColorTemp": 4000,
        "MinColorTemperature": 2700,
        "MaxColorTemperature": 6500,
    },
}
