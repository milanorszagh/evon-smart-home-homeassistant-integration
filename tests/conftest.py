"""Pytest fixtures for Evon Smart Home tests."""

from __future__ import annotations

import sys
from pathlib import Path

# Add repo root to path so custom_components can be found
REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

from collections.abc import Generator
import importlib.util
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
        event_loop: asyncio.AbstractEventLoop,
        expected_lingering_tasks: bool,
        expected_lingering_timers: bool,
    ) -> Generator[None]:
        """Verify that the test has cleaned up resources correctly.

        This overrides the fixture from pytest-homeassistant-custom-component
        to also allow _run_safe_shutdown_loop threads which are created by
        asyncio during event loop handling.
        """
        threads_before = frozenset(threading.enumerate())
        tasks_before = asyncio.all_tasks(event_loop)
        yield

        event_loop.run_until_complete(event_loop.shutdown_default_executor())

        if len(INSTANCES) >= 2:
            count = len(INSTANCES)
            for inst in INSTANCES:
                inst.stop()
            pytest.exit(f"Detected non stopped instances ({count}), aborting test run")

        # Warn and clean-up lingering tasks and timers
        tasks = asyncio.all_tasks(event_loop) - tasks_before
        for task in tasks:
            if expected_lingering_tasks:
                _LOGGER.warning("Lingering task after test %r", task)
            else:
                pytest.fail(f"Lingering task after test {task!r}")
            task.cancel()
        if tasks:
            event_loop.run_until_complete(asyncio.wait(tasks))

        for handle in get_scheduled_timer_handles(event_loop):
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
            side_effect=lambda instance_id: MOCK_INSTANCE_DETAILS.get(instance_id, {})
        )
        # Light methods
        mock_api.turn_on_light = AsyncMock()
        mock_api.turn_off_light = AsyncMock()
        mock_api.set_light_brightness = AsyncMock()
        # Blind methods
        mock_api.open_blind = AsyncMock()
        mock_api.close_blind = AsyncMock()
        mock_api.stop_blind = AsyncMock()
        mock_api.set_blind_position = AsyncMock()
        mock_api.set_blind_tilt = AsyncMock()
        # Climate methods
        mock_api.set_climate_comfort_mode = AsyncMock()
        mock_api.set_climate_energy_saving_mode = AsyncMock()
        mock_api.set_climate_freeze_protection_mode = AsyncMock()
        mock_api.set_climate_temperature = AsyncMock()
        # Home state methods
        mock_api.activate_home_state = AsyncMock()
        # Season mode methods
        mock_api.get_season_mode = AsyncMock(return_value=False)  # False = heating mode
        mock_api.set_season_mode = AsyncMock()
        # Bathroom radiator methods
        mock_api.toggle_bathroom_radiator = AsyncMock()
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
            await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()

    @pytest.fixture
    def mock_config_entry_v2() -> MockConfigEntry:
        """Create a MockConfigEntry for integration tests."""
        return MockConfigEntry(
            domain="evon",
            title="Evon Smart Home",
            data={
                "host": TEST_HOST,
                "username": TEST_USERNAME,
                "password": TEST_PASSWORD,
            },
            options={
                "scan_interval": 30,
                "sync_areas": False,
                "non_dimmable_lights": [],
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
        with patch("custom_components.evon.api.EvonApi", return_value=mock_api), \
             patch("custom_components.evon.EvonApi", return_value=mock_api):
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
}


