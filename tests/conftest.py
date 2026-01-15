"""Pytest fixtures for Evon Smart Home tests."""
from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.evon.api import EvonApi
from custom_components.evon.const import DOMAIN

# Test constants - these are placeholders, not real credentials
TEST_HOST = "http://192.168.1.100"
TEST_USERNAME = "testuser"
TEST_PASSWORD = "testpass"


@pytest.fixture
def mock_api() -> Generator[AsyncMock]:
    """Create a mock EvonApi."""
    with patch(
        "custom_components.evon.api.EvonApi", autospec=True
    ) as mock_api_class:
        api = mock_api_class.return_value
        api.test_connection = AsyncMock(return_value=True)
        api.login = AsyncMock(return_value="test_token")
        api.get_instances = AsyncMock(
            return_value=[
                {
                    "ID": "light_1",
                    "ClassName": "SmartCOM.Light.LightDim",
                    "Name": "Living Room Light",
                },
                {
                    "ID": "blind_1",
                    "ClassName": "SmartCOM.Blind.Blind",
                    "Name": "Living Room Blind",
                },
                {
                    "ID": "climate_1",
                    "ClassName": "SmartCOM.Clima.ClimateControl",
                    "Name": "Living Room Climate",
                },
            ]
        )
        api.get_instance = AsyncMock(
            side_effect=lambda instance_id: {
                "light_1": {
                    "IsOn": True,
                    "ScaledBrightness": 75,
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
                },
            }.get(instance_id, {})
        )
        api.turn_on_light = AsyncMock()
        api.turn_off_light = AsyncMock()
        api.set_light_brightness = AsyncMock()
        api.open_blind = AsyncMock()
        api.close_blind = AsyncMock()
        api.stop_blind = AsyncMock()
        api.set_blind_position = AsyncMock()
        api.set_blind_tilt = AsyncMock()
        api.set_climate_comfort_mode = AsyncMock()
        api.set_climate_energy_saving_mode = AsyncMock()
        api.set_climate_freeze_protection_mode = AsyncMock()
        api.set_climate_temperature = AsyncMock()
        yield api


@pytest.fixture
def mock_config_entry() -> MagicMock:
    """Create a mock config entry."""
    entry = MagicMock()
    entry.entry_id = "test_entry_id"
    entry.data = {
        "host": TEST_HOST,
        "username": TEST_USERNAME,
        "password": TEST_PASSWORD,
    }
    entry.options = {"scan_interval": 30}
    return entry


@pytest.fixture
def mock_hass() -> MagicMock:
    """Create a mock Home Assistant instance."""
    hass = MagicMock()
    hass.data = {}
    return hass
