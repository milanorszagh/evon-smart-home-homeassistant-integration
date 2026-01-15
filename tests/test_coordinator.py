"""Tests for Evon data coordinator."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest


class TestEvonDataUpdateCoordinator:
    """Test EvonDataUpdateCoordinator."""

    @pytest.mark.asyncio
    async def test_coordinator_init(self):
        """Test coordinator initialization."""
        from custom_components.evon.coordinator import EvonDataUpdateCoordinator

        hass = MagicMock()
        api = MagicMock()

        coordinator = EvonDataUpdateCoordinator(hass, api, scan_interval=30)

        assert coordinator.api == api
        assert coordinator.update_interval == timedelta(seconds=30)

    @pytest.mark.asyncio
    async def test_coordinator_custom_interval(self):
        """Test coordinator with custom scan interval."""
        from custom_components.evon.coordinator import EvonDataUpdateCoordinator

        hass = MagicMock()
        api = MagicMock()

        coordinator = EvonDataUpdateCoordinator(hass, api, scan_interval=60)

        assert coordinator.update_interval == timedelta(seconds=60)

    def test_set_update_interval(self):
        """Test setting update interval."""
        from custom_components.evon.coordinator import EvonDataUpdateCoordinator

        hass = MagicMock()
        api = MagicMock()

        coordinator = EvonDataUpdateCoordinator(hass, api, scan_interval=30)
        coordinator.set_update_interval(120)

        assert coordinator.update_interval == timedelta(seconds=120)

    @pytest.mark.asyncio
    async def test_update_data_organizes_devices(self):
        """Test that update data correctly organizes devices by type."""
        from custom_components.evon.coordinator import EvonDataUpdateCoordinator

        hass = MagicMock()
        api = AsyncMock()
        api.get_instances = AsyncMock(
            return_value=[
                {"ID": "light_1", "ClassName": "SmartCOM.Light.LightDim", "Name": "Light 1"},
                {"ID": "blind_1", "ClassName": "SmartCOM.Blind.Blind", "Name": "Blind 1"},
                {"ID": "climate_1", "ClassName": "SmartCOM.Clima.ClimateControl", "Name": "Climate 1"},
                {"ID": "switch_1", "ClassName": "SmartCOM.Light.Light", "Name": "Switch 1"},
            ]
        )
        api.get_instance = AsyncMock(
            side_effect=lambda id: {
                "light_1": {"IsOn": True, "ScaledBrightness": 50},
                "blind_1": {"Position": 25, "Angle": 90, "IsMoving": False},
                "climate_1": {
                    "ActualTemperature": 21.0,
                    "SetTemperature": 22.0,
                    "MinSetValueHeat": 15,
                    "MaxSetValueHeat": 25,
                    "SetValueComfortHeating": 22,
                    "SetValueEnergySavingHeating": 20,
                    "SetValueFreezeProtection": 15,
                },
                "switch_1": {"IsOn": False, "LastClickType": None},
            }.get(id, {})
        )

        coordinator = EvonDataUpdateCoordinator(hass, api)
        data = await coordinator._async_update_data()

        assert len(data["lights"]) == 1
        assert len(data["blinds"]) == 1
        assert len(data["climates"]) == 1
        assert len(data["switches"]) == 1

        assert data["lights"][0]["id"] == "light_1"
        assert data["lights"][0]["is_on"] is True
        assert data["lights"][0]["brightness"] == 50

        assert data["blinds"][0]["id"] == "blind_1"
        assert data["blinds"][0]["position"] == 25
        assert data["blinds"][0]["angle"] == 90

        assert data["climates"][0]["id"] == "climate_1"
        assert data["climates"][0]["current_temperature"] == 21.0
        assert data["climates"][0]["target_temperature"] == 22.0

    @pytest.mark.asyncio
    async def test_update_data_skips_unnamed_instances(self):
        """Test that instances without names are skipped."""
        from custom_components.evon.coordinator import EvonDataUpdateCoordinator

        hass = MagicMock()
        api = AsyncMock()
        api.get_instances = AsyncMock(
            return_value=[
                {"ID": "light_1", "ClassName": "SmartCOM.Light.LightDim", "Name": "Light 1"},
                {"ID": "light_2", "ClassName": "SmartCOM.Light.LightDim", "Name": ""},  # No name
            ]
        )
        api.get_instance = AsyncMock(return_value={"IsOn": True, "ScaledBrightness": 50})

        coordinator = EvonDataUpdateCoordinator(hass, api)
        data = await coordinator._async_update_data()

        # Only one light should be added (the one with a name)
        assert len(data["lights"]) == 1
        assert data["lights"][0]["id"] == "light_1"

    def test_get_light_data(self):
        """Test getting light data."""
        from custom_components.evon.coordinator import EvonDataUpdateCoordinator

        hass = MagicMock()
        api = MagicMock()

        coordinator = EvonDataUpdateCoordinator(hass, api)
        coordinator.data = {
            "lights": [
                {"id": "light_1", "name": "Light 1", "is_on": True, "brightness": 50},
                {"id": "light_2", "name": "Light 2", "is_on": False, "brightness": 0},
            ]
        }

        light_data = coordinator.get_light_data("light_1")
        assert light_data["id"] == "light_1"
        assert light_data["is_on"] is True

        light_data = coordinator.get_light_data("light_2")
        assert light_data["id"] == "light_2"
        assert light_data["is_on"] is False

        # Non-existent light
        assert coordinator.get_light_data("light_999") is None

    def test_get_blind_data(self):
        """Test getting blind data."""
        from custom_components.evon.coordinator import EvonDataUpdateCoordinator

        hass = MagicMock()
        api = MagicMock()

        coordinator = EvonDataUpdateCoordinator(hass, api)
        coordinator.data = {
            "blinds": [
                {"id": "blind_1", "name": "Blind 1", "position": 25, "angle": 45},
            ]
        }

        blind_data = coordinator.get_blind_data("blind_1")
        assert blind_data["id"] == "blind_1"
        assert blind_data["position"] == 25
        assert blind_data["angle"] == 45

    def test_get_climate_data(self):
        """Test getting climate data."""
        from custom_components.evon.coordinator import EvonDataUpdateCoordinator

        hass = MagicMock()
        api = MagicMock()

        coordinator = EvonDataUpdateCoordinator(hass, api)
        coordinator.data = {
            "climates": [
                {
                    "id": "climate_1",
                    "name": "Climate 1",
                    "current_temperature": 21.5,
                    "target_temperature": 22.0,
                },
            ]
        }

        climate_data = coordinator.get_climate_data("climate_1")
        assert climate_data["id"] == "climate_1"
        assert climate_data["current_temperature"] == 21.5
        assert climate_data["target_temperature"] == 22.0

    def test_get_switch_data(self):
        """Test getting switch data."""
        from custom_components.evon.coordinator import EvonDataUpdateCoordinator

        hass = MagicMock()
        api = MagicMock()

        coordinator = EvonDataUpdateCoordinator(hass, api)
        coordinator.data = {
            "switches": [
                {"id": "switch_1", "name": "Switch 1", "is_on": True, "last_click": None},
            ]
        }

        switch_data = coordinator.get_switch_data("switch_1")
        assert switch_data["id"] == "switch_1"
        assert switch_data["is_on"] is True
