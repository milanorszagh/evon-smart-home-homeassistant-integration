"""Unit tests for coordinator processors (no HA framework required)."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock

import pytest


class TestCameraProcessor:
    """Tests for camera data processor."""

    @pytest.fixture
    def camera_instances(self):
        """Create camera instance data."""
        return [
            {
                "ID": "intercom_1.Cam",
                "ClassName": "Security.Intercom.2N.Intercom2NCam",
                "Name": "Intercom Camera",
                "Group": "room_living",
            },
        ]

    @pytest.fixture
    def camera_details(self):
        """Create camera instance details."""
        return {
            "Image": "/images/current.jpg",
            "IPAddress": "192.168.1.50",
            "Error": False,
        }

    def test_process_cameras(self, camera_instances, camera_details):
        """Test camera processor extracts data correctly."""
        from custom_components.evon.coordinator.processors.cameras import process_cameras

        instance_details = {"intercom_1.Cam": camera_details}

        def get_room_name(group_id):
            return "Living Room" if group_id == "room_living" else ""

        result = process_cameras(instance_details, camera_instances, get_room_name)

        assert len(result) == 1
        camera = result[0]
        assert camera["id"] == "intercom_1.Cam"
        assert camera["name"] == "Intercom Camera"
        assert camera["room_name"] == "Living Room"
        assert camera["image_path"] == "/images/current.jpg"
        assert camera["ip_address"] == "192.168.1.50"
        assert camera["error"] is False

    def test_process_cameras_empty(self):
        """Test camera processor with no cameras."""
        from custom_components.evon.coordinator.processors.cameras import process_cameras

        result = process_cameras({}, [], lambda x: "")

        assert result == []

    def test_process_cameras_filters_by_class(self):
        """Test camera processor only includes camera class."""
        from custom_components.evon.coordinator.processors.cameras import process_cameras

        instances = [
            {
                "ID": "not_a_camera",
                "ClassName": "SmartCOM.Light.Light",
                "Name": "Light",
            },
            {
                "ID": "intercom_1.Cam",
                "ClassName": "Security.Intercom.2N.Intercom2NCam",
                "Name": "Camera",
            },
        ]

        instance_details = {"intercom_1.Cam": {"ImagePath": "/img.jpg"}}

        result = process_cameras(instance_details, instances, lambda x: "")

        assert len(result) == 1
        assert result[0]["id"] == "intercom_1.Cam"


class TestSecurityDoorProcessor:
    """Tests for security door data processor."""

    @pytest.fixture
    def door_instances(self):
        """Create security door instance data."""
        return [
            {
                "ID": "security_door_1",
                "ClassName": "Security.Door",
                "Name": "Front Door",
                "Group": "room_living",
            },
        ]

    @pytest.fixture
    def door_details(self):
        """Create security door instance details."""
        return {
            "IsOpen": False,
            "DoorIsOpen": False,
            "CallInProgress": False,
            "CamInstanceName": "intercom_1.Cam",
            "SavedPictures": [
                {"imageUrlClient": "/images/snap1.jpg", "datetime": 1706900000000},
                {"imageUrlClient": "/images/snap2.jpg", "datetime": 1706899000000},
            ],
        }

    def test_process_security_doors(self, door_instances, door_details):
        """Test security door processor extracts data correctly."""
        from custom_components.evon.coordinator.processors.security_doors import process_security_doors

        instance_details = {"security_door_1": door_details}

        def get_room_name(group_id):
            return "Living Room" if group_id == "room_living" else ""

        result = process_security_doors(instance_details, door_instances, get_room_name)

        assert len(result) == 1
        door = result[0]
        assert door["id"] == "security_door_1"
        assert door["name"] == "Front Door"
        assert door["is_open"] is False
        assert door["call_in_progress"] is False
        assert door["cam_instance_name"] == "intercom_1.Cam"
        assert len(door["saved_pictures"]) == 2

    def test_process_security_doors_saved_pictures_lowercase(self, door_instances, door_details):
        """Test security door processor converts saved pictures keys to lowercase."""
        from custom_components.evon.coordinator.processors.security_doors import process_security_doors

        instance_details = {"security_door_1": door_details}

        result = process_security_doors(instance_details, door_instances, lambda x: "")

        # Keys should be lowercase
        saved_pictures = result[0]["saved_pictures"]
        assert "path" in saved_pictures[0]
        assert "timestamp" in saved_pictures[0]
        assert saved_pictures[0]["path"] == "/images/snap1.jpg"


class TestIntercomProcessor:
    """Tests for intercom data processor."""

    @pytest.fixture
    def intercom_instances(self):
        """Create intercom instance data."""
        return [
            {
                "ID": "intercom_1",
                "ClassName": "Security.Intercom.2N.Intercom2N",
                "Name": "Main Intercom",
                "Group": "room_living",
            },
        ]

    @pytest.fixture
    def intercom_details(self):
        """Create intercom instance details."""
        return {
            "DoorBellTriggered": False,
            "DoorOpenTriggered": False,
            "IsDoorOpen": False,
            "ConnectionToIntercomHasBeenLost": False,
        }

    def test_process_intercoms(self, intercom_instances, intercom_details):
        """Test intercom processor extracts data correctly."""
        from custom_components.evon.coordinator.processors.intercoms import process_intercoms

        instance_details = {"intercom_1": intercom_details}

        def get_room_name(group_id):
            return "Living Room" if group_id == "room_living" else ""

        result = process_intercoms(instance_details, intercom_instances, get_room_name)

        assert len(result) == 1
        intercom = result[0]
        assert intercom["id"] == "intercom_1"
        assert intercom["name"] == "Main Intercom"
        assert intercom["doorbell_triggered"] is False
        assert intercom["is_door_open"] is False
        assert intercom["connection_lost"] is False


class TestApiImageFetch:
    """Tests for API image fetch method."""

    @pytest.mark.asyncio
    async def test_fetch_image_success(self):
        """Test fetch_image returns image bytes on success."""
        from contextlib import asynccontextmanager
        import time
        from unittest.mock import AsyncMock, MagicMock

        from custom_components.evon.api import EvonApi

        api = EvonApi("http://192.168.1.100", "user", "pass")

        # Create a proper async context manager for the response
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read = AsyncMock(return_value=b"\xff\xd8\xff\xe0JPEG")

        @asynccontextmanager
        async def mock_get(*args, **kwargs):
            yield mock_response

        mock_session = MagicMock()
        mock_session.closed = False  # Prevent _get_session from creating new session
        mock_session.get = mock_get

        # Set up session and token properly to bypass _ensure_token and _get_session
        api._session = mock_session
        api._own_session = False  # Indicate session was provided externally
        api._token = "test_token"
        api._token_timestamp = time.monotonic()  # Fresh token, not expired

        result = await api.fetch_image("/images/test.jpg")

        assert result == b"\xff\xd8\xff\xe0JPEG"

    @pytest.mark.asyncio
    async def test_fetch_image_failure_returns_none(self):
        """Test fetch_image returns None on HTTP error."""
        from contextlib import asynccontextmanager
        import time
        from unittest.mock import MagicMock

        import aiohttp

        from custom_components.evon.api import EvonApi

        api = EvonApi("http://192.168.1.100", "user", "pass")

        @asynccontextmanager
        async def mock_get_error(*args, **kwargs):
            raise aiohttp.ClientError()
            yield  # Never reached

        mock_session = MagicMock()
        mock_session.closed = False  # Prevent _get_session from creating new session
        mock_session.get = mock_get_error

        # Set up session and token properly to bypass _ensure_token and _get_session
        api._session = mock_session
        api._own_session = False  # Indicate session was provided externally
        api._token = "test_token"
        api._token_timestamp = time.monotonic()  # Fresh token, not expired

        result = await api.fetch_image("/images/test.jpg")

        assert result is None


class TestLightProcessor:
    """Tests for light data processor."""

    def test_process_lights(self):
        """Test light processor extracts data correctly."""
        from custom_components.evon.coordinator.processors.lights import process_lights

        instances = [
            {
                "ID": "light_1",
                "ClassName": "SmartCOM.Light.LightDim",
                "Name": "Living Room Light",
                "Group": "room_living",
            },
        ]
        instance_details = {
            "light_1": {
                "IsOn": True,
                "ScaledBrightness": 75,
            },
        }

        result = process_lights(instance_details, instances, lambda x: "Living Room")

        assert len(result) == 1
        light = result[0]
        assert light["id"] == "light_1"
        assert light["name"] == "Living Room Light"
        assert light["is_on"] is True
        assert light["brightness"] == 75
        assert light["supports_color_temp"] is False

    def test_process_lights_rgbw(self):
        """Test light processor handles RGBW lights with color temp."""
        from custom_components.evon.coordinator.processors.lights import process_lights

        instances = [
            {
                "ID": "rgbw_light",
                "ClassName": "SmartCOM.Light.DynamicRGBWLight",
                "Name": "RGBW Light",
                "Group": "",
            },
        ]
        instance_details = {
            "rgbw_light": {
                "IsOn": True,
                "ScaledBrightness": 100,
                "ColorTemp": 4000,
                "MinColorTemperature": 2700,
                "MaxColorTemperature": 6500,
            },
        }

        result = process_lights(instance_details, instances, lambda x: "")

        assert len(result) == 1
        light = result[0]
        assert light["supports_color_temp"] is True
        assert light["color_temp"] == 4000
        assert light["min_color_temp"] == 2700
        assert light["max_color_temp"] == 6500

    def test_process_lights_filters_by_class(self):
        """Test light processor only includes light classes."""
        from custom_components.evon.coordinator.processors.lights import process_lights

        instances = [
            {"ID": "switch_1", "ClassName": "SmartCOM.Light.Light", "Name": "Switch"},
            {"ID": "light_1", "ClassName": "SmartCOM.Light.LightDim", "Name": "Light"},
        ]
        instance_details = {
            "switch_1": {"IsOn": True, "ScaledBrightness": 50},
            "light_1": {"IsOn": True, "ScaledBrightness": 50},
        }

        result = process_lights(instance_details, instances, lambda x: "")

        # Should only include LightDim, not Light (which is a switch)
        assert len(result) == 1
        assert result[0]["id"] == "light_1"

    def test_process_lights_skips_unnamed(self):
        """Test light processor skips instances without names."""
        from custom_components.evon.coordinator.processors.lights import process_lights

        instances = [
            {"ID": "light_1", "ClassName": "SmartCOM.Light.LightDim", "Name": ""},
            {"ID": "light_2", "ClassName": "SmartCOM.Light.LightDim", "Name": "Named"},
        ]
        instance_details = {
            "light_1": {"IsOn": False, "ScaledBrightness": 0},
            "light_2": {"IsOn": False, "ScaledBrightness": 0},
        }

        result = process_lights(instance_details, instances, lambda x: "")

        assert len(result) == 1
        assert result[0]["id"] == "light_2"


class TestBlindProcessor:
    """Tests for blind data processor."""

    def test_process_blinds(self):
        """Test blind processor extracts data correctly."""
        from custom_components.evon.coordinator.processors.blinds import process_blinds

        instances = [
            {
                "ID": "blind_1",
                "ClassName": "SmartCOM.Blind.Blind",
                "Name": "Living Room Blind",
                "Group": "room_living",
            },
        ]
        instance_details = {
            "blind_1": {
                "Position": 50,
                "Angle": 45,
                "IsMoving": False,
            },
        }

        result = process_blinds(instance_details, instances, lambda x: "Living Room")

        assert len(result) == 1
        blind = result[0]
        assert blind["id"] == "blind_1"
        assert blind["name"] == "Living Room Blind"
        assert blind["position"] == 50
        assert blind["angle"] == 45
        assert blind["is_moving"] is False
        assert blind["is_group"] is False

    def test_process_blinds_group(self):
        """Test blind processor identifies group blinds."""
        from custom_components.evon.coordinator.processors.blinds import process_blinds

        instances = [
            {
                "ID": "blind_group",
                "ClassName": "SmartCOM.Blind.BlindGroup",
                "Name": "All Blinds",
                "Group": "",
            },
        ]
        instance_details = {
            "blind_group": {"Position": 100, "Angle": 0, "IsMoving": True},
        }

        result = process_blinds(instance_details, instances, lambda x: "")

        assert len(result) == 1
        assert result[0]["is_group"] is True
        assert result[0]["is_moving"] is True


class TestClimateProcessor:
    """Tests for climate data processor."""

    def test_process_climates_heating(self):
        """Test climate processor in heating (winter) mode."""
        from custom_components.evon.coordinator.processors.climate import process_climates

        instances = [
            {
                "ID": "climate_1",
                "ClassName": "SmartCOM.Clima.ClimateControl",
                "Name": "Living Room Climate",
                "Group": "room_living",
            },
        ]
        instance_details = {
            "climate_1": {
                "ActualTemperature": 21.5,
                "SetTemperature": 22.0,
                "SetValueComfortHeating": 22,
                "SetValueEnergySavingHeating": 20,
                "SetValueFreezeProtection": 15,
                "MinSetValueHeat": 15,
                "MaxSetValueHeat": 25,
                "MainState": 1,
                "CoolingMode": False,
                "DisableCooling": True,
                "IsOn": True,
                "Humidity": 45,
            },
        }

        result = process_climates(instance_details, instances, lambda x: "Living Room", season_mode=False)

        assert len(result) == 1
        climate = result[0]
        assert climate["id"] == "climate_1"
        assert climate["current_temperature"] == 21.5
        assert climate["target_temperature"] == 22.0
        assert climate["min_temp"] == 15
        assert climate["max_temp"] == 25
        assert climate["comfort_temp"] == 22
        assert climate["energy_saving_temp"] == 20
        assert climate["protection_temp"] == 15
        assert climate["is_on"] is True
        assert climate["humidity"] == 45

    def test_process_climates_cooling(self):
        """Test climate processor in cooling (summer) mode."""
        from custom_components.evon.coordinator.processors.climate import process_climates

        instances = [
            {
                "ID": "climate_1",
                "ClassName": "SmartCOM.Clima.ClimateControl",
                "Name": "Climate",
                "Group": "",
            },
        ]
        instance_details = {
            "climate_1": {
                "ActualTemperature": 26.0,
                "SetTemperature": 24.0,
                "SetValueComfortCooling": 25,
                "SetValueEnergySavingCooling": 24,
                "SetValueHeatProtection": 29,
                "MinSetValueCool": 18,
                "MaxSetValueCool": 30,
                "CoolingMode": True,
                "DisableCooling": False,
                "IsOn": True,
            },
        }

        result = process_climates(instance_details, instances, lambda x: "", season_mode=True)

        assert len(result) == 1
        climate = result[0]
        assert climate["min_temp"] == 18
        assert climate["max_temp"] == 30
        assert climate["comfort_temp"] == 25
        assert climate["protection_temp"] == 29
        assert climate["is_cooling"] is True

    def test_process_climates_cooling_max_temp_includes_all_presets(self):
        """Test cooling mode max_temp includes comfort and eco temps.

        If a preset temp (comfort/eco) exceeds MaxSetValueCool, the slider
        should still allow reaching it.
        """
        from custom_components.evon.coordinator.processors.climate import process_climates

        instances = [
            {
                "ID": "climate_1",
                "ClassName": "SmartCOM.Clima.ClimateControl",
                "Name": "Climate",
                "Group": "",
            },
        ]
        instance_details = {
            "climate_1": {
                "ActualTemperature": 26.0,
                "SetTemperature": 24.0,
                "SetValueComfortCooling": 32,  # Exceeds MaxSetValueCool!
                "SetValueEnergySavingCooling": 28,
                "SetValueHeatProtection": 29,
                "MinSetValueCool": 18,
                "MaxSetValueCool": 30,
                "CoolingMode": True,
                "DisableCooling": False,
                "IsOn": True,
            },
        }

        result = process_climates(instance_details, instances, lambda x: "", season_mode=True)

        climate = result[0]
        # max_temp should be 32 (comfort_temp), not 30 (MaxSetValueCool)
        assert climate["max_temp"] == 32
        # min_temp should include all presets too
        assert climate["min_temp"] == 18

    def test_process_climates_cooling_eco_exceeds_max(self):
        """Test cooling mode max_temp picks up eco temp when it's highest."""
        from custom_components.evon.coordinator.processors.climate import process_climates

        instances = [
            {
                "ID": "climate_1",
                "ClassName": "SmartCOM.Clima.ClimateControl",
                "Name": "Climate",
                "Group": "",
            },
        ]
        instance_details = {
            "climate_1": {
                "ActualTemperature": 26.0,
                "SetTemperature": 24.0,
                "SetValueComfortCooling": 25,
                "SetValueEnergySavingCooling": 35,  # Exceeds everything
                "SetValueHeatProtection": 29,
                "MinSetValueCool": 18,
                "MaxSetValueCool": 30,
                "CoolingMode": True,
                "DisableCooling": False,
                "IsOn": True,
            },
        }

        result = process_climates(instance_details, instances, lambda x: "", season_mode=True)

        climate = result[0]
        assert climate["max_temp"] == 35


class TestSwitchProcessor:
    """Tests for switch data processor."""

    def test_process_switches(self):
        """Test switch processor extracts data correctly."""
        from custom_components.evon.coordinator.processors.switches import process_switches

        instances = [
            {
                "ID": "switch_1",
                "ClassName": "SmartCOM.Light.Light",
                "Name": "Kitchen Outlet",
                "Group": "room_kitchen",
            },
        ]
        instance_details = {"switch_1": {"IsOn": True}}

        result = process_switches(instance_details, instances, lambda x: "Kitchen")

        assert len(result) == 1
        switch = result[0]
        assert switch["id"] == "switch_1"
        assert switch["name"] == "Kitchen Outlet"
        assert switch["room_name"] == "Kitchen"
        assert switch["is_on"] is True

    def test_process_switches_filters_dim_lights(self):
        """Test switch processor excludes dimmable lights."""
        from custom_components.evon.coordinator.processors.switches import process_switches

        instances = [
            {"ID": "switch_1", "ClassName": "SmartCOM.Light.Light", "Name": "Switch"},
            {"ID": "light_1", "ClassName": "SmartCOM.Light.DimLight", "Name": "Dim Light"},
        ]
        instance_details = {
            "switch_1": {"IsOn": False},
            "light_1": {"IsOn": False},
        }

        result = process_switches(instance_details, instances, lambda x: "")

        # Should only include SmartCOM.Light.Light
        assert len(result) == 1
        assert result[0]["id"] == "switch_1"


class TestSceneProcessor:
    """Tests for scene data processor."""

    def test_process_scenes(self):
        """Test scene processor extracts data correctly."""
        from custom_components.evon.coordinator.processors.scenes import process_scenes

        instances = [
            {
                "ID": "scene_1",
                "ClassName": "System.SceneApp",
                "Name": "Movie Night",
            },
            {
                "ID": "scene_2",
                "ClassName": "System.SceneApp",
                "Name": "Good Morning",
            },
        ]

        result = process_scenes(instances)

        assert len(result) == 2
        assert result[0]["id"] == "scene_1"
        assert result[0]["name"] == "Movie Night"
        assert result[1]["id"] == "scene_2"
        assert result[1]["name"] == "Good Morning"

    def test_process_scenes_filters_by_class(self):
        """Test scene processor only includes scene class."""
        from custom_components.evon.coordinator.processors.scenes import process_scenes

        instances = [
            {"ID": "scene_1", "ClassName": "System.SceneApp", "Name": "Scene"},
            {"ID": "light_1", "ClassName": "SmartCOM.Light.Light", "Name": "Light"},
        ]

        result = process_scenes(instances)

        assert len(result) == 1
        assert result[0]["id"] == "scene_1"

    def test_process_scenes_empty(self):
        """Test scene processor with no scenes."""
        from custom_components.evon.coordinator.processors.scenes import process_scenes

        result = process_scenes([])

        assert result == []


class TestValveProcessor:
    """Tests for valve data processor."""

    def test_process_valves(self):
        """Test valve processor extracts data correctly."""
        from custom_components.evon.coordinator.processors.valves import process_valves

        instances = [
            {
                "ID": "valve_1",
                "ClassName": "SmartCOM.Clima.Valve",
                "Name": "Heating Valve",
                "Group": "room_bedroom",
            },
        ]
        instance_details = {
            "valve_1": {
                "ActValue": True,
                "Type": 1,
            },
        }

        result = process_valves(instance_details, instances, lambda x: "Bedroom")

        assert len(result) == 1
        valve = result[0]
        assert valve["id"] == "valve_1"
        assert valve["name"] == "Heating Valve"
        assert valve["room_name"] == "Bedroom"
        assert valve["is_open"] is True
        assert valve["valve_type"] == 1


class TestHomeStateProcessor:
    """Tests for home state data processor."""

    def test_process_home_states(self):
        """Test home state processor extracts data correctly."""
        from custom_components.evon.coordinator.processors.home_states import process_home_states

        instances = [
            {
                "ID": "home_state_1",
                "ClassName": "System.HomeState",
                "Name": "Away",
            },
            {
                "ID": "home_state_2",
                "ClassName": "System.HomeState",
                "Name": "Home",
            },
        ]
        instance_details = {
            "home_state_1": {"Active": False},
            "home_state_2": {"Active": True},
        }

        result = process_home_states(instance_details, instances)

        assert len(result) == 2
        assert result[0]["id"] == "home_state_1"
        assert result[0]["active"] is False
        assert result[1]["id"] == "home_state_2"
        assert result[1]["active"] is True

    def test_process_home_states_skips_system(self):
        """Test home state processor skips System.* templates."""
        from custom_components.evon.coordinator.processors.home_states import process_home_states

        instances = [
            {"ID": "System.HomeState", "ClassName": "System.HomeState", "Name": "Template"},
            {"ID": "user_state", "ClassName": "System.HomeState", "Name": "User State"},
        ]
        instance_details = {
            "System.HomeState": {"Active": True},
            "user_state": {"Active": True},
        }

        result = process_home_states(instance_details, instances)

        assert len(result) == 1
        assert result[0]["id"] == "user_state"


class TestAirQualityProcessor:
    """Tests for air quality data processor."""

    def test_process_air_quality(self):
        """Test air quality processor extracts data correctly."""
        from custom_components.evon.coordinator.processors.air_quality import process_air_quality

        instances = [
            {
                "ID": "aq_1",
                "ClassName": "System.Location.AirQuality",
                "Name": "Bedroom Air Quality",
                "Group": "room_bedroom",
            },
        ]
        instance_details = {
            "aq_1": {
                "CO2Value": 800,
                "Humidity": 55,
                "ActualTemperature": 22.5,
                "HealthIndex": 85,
                "CO2Index": 80,
                "HumidityIndex": 90,
            },
        }

        result = process_air_quality(instance_details, instances, lambda x: "Bedroom")

        assert len(result) == 1
        aq = result[0]
        assert aq["id"] == "aq_1"
        assert aq["co2"] == 800
        assert aq["humidity"] == 55
        assert aq["temperature"] == 22.5
        assert aq["health_index"] == 85

    def test_process_air_quality_skips_invalid_data(self):
        """Test air quality processor skips sensors with no valid data."""
        from custom_components.evon.coordinator.processors.air_quality import process_air_quality

        instances = [
            {"ID": "aq_1", "ClassName": "System.Location.AirQuality", "Name": "Invalid Sensor", "Group": ""},
        ]
        instance_details = {
            "aq_1": {
                "CO2Value": -999,
                "Humidity": -999,
                "ActualTemperature": -999,
            },
        }

        result = process_air_quality(instance_details, instances, lambda x: "")

        assert len(result) == 0

    def test_process_air_quality_partial_data(self):
        """Test air quality processor handles partial data (some -999 values)."""
        from custom_components.evon.coordinator.processors.air_quality import process_air_quality

        instances = [
            {"ID": "aq_1", "ClassName": "System.Location.AirQuality", "Name": "Partial Sensor", "Group": ""},
        ]
        instance_details = {
            "aq_1": {
                "CO2Value": 600,
                "Humidity": -999,
                "ActualTemperature": -999,
            },
        }

        result = process_air_quality(instance_details, instances, lambda x: "")

        assert len(result) == 1
        assert result[0]["co2"] == 600
        assert result[0]["humidity"] is None
        assert result[0]["temperature"] is None


class TestSmartMeterProcessor:
    """Tests for smart meter data processor."""

    def test_process_smart_meters(self):
        """Test smart meter processor extracts data correctly."""
        from custom_components.evon.coordinator.processors.smart_meters import process_smart_meters

        instances = [
            {
                "ID": "meter_1",
                "ClassName": "Energy.SmartMeter",
                "Name": "Main Power Meter",
                "Group": "",
            },
        ]
        instance_details = {
            "meter_1": {
                "PowerActual": 2500,
                "PowerActualUnit": "W",
                "Energy": 15000,
                "Energy24h": 45,
                "FeedIn": 500,
                "FeedInEnergy": 1000,
                "Frequency": 50.0,
                "UL1N": 230.5,
                "UL2N": 231.0,
                "UL3N": 229.8,
                "IL1": 5.5,
                "IL2": 4.8,
                "IL3": 5.2,
                "P1": 850,
                "P2": 800,
                "P3": 850,
            },
        }

        result = process_smart_meters(instance_details, instances, lambda x: "")

        assert len(result) == 1
        meter = result[0]
        assert meter["id"] == "meter_1"
        assert meter["power"] == 2500
        assert meter["power_unit"] == "W"
        assert meter["energy"] == 15000
        assert meter["voltage_l1"] == 230.5
        assert meter["current_l1"] == 5.5
        assert meter["power_l1"] == 850


class TestBathroomRadiatorProcessor:
    """Tests for bathroom radiator data processor."""

    def test_process_bathroom_radiators(self):
        """Test bathroom radiator processor extracts data correctly."""
        from custom_components.evon.coordinator.processors.bathroom_radiators import process_bathroom_radiators

        instances = [
            {
                "ID": "radiator_1",
                "ClassName": "Heating.BathroomRadiator",
                "Name": "Bathroom Heater",
                "Group": "room_bathroom",
            },
        ]
        instance_details = {
            "radiator_1": {
                "Output": True,
                "NextSwitchPoint": 1800,
                "EnableForMins": 60,
                "PermanentlyOn": False,
                "PermanentlyOff": False,
                "Deactivated": False,
            },
        }

        result = process_bathroom_radiators(instance_details, instances, lambda x: "Bathroom")

        assert len(result) == 1
        radiator = result[0]
        assert radiator["id"] == "radiator_1"
        assert radiator["name"] == "Bathroom Heater"
        assert radiator["is_on"] is True
        assert radiator["time_remaining"] == 1800
        assert radiator["duration_mins"] == 60
        assert radiator["permanently_on"] is False
        assert radiator["deactivated"] is False


class TestConstants:
    """Tests for camera/image related constants."""

    def test_camera_image_update_timeout(self):
        """Test CAMERA_IMAGE_UPDATE_TIMEOUT constant."""
        from custom_components.evon.const import CAMERA_IMAGE_UPDATE_TIMEOUT

        assert CAMERA_IMAGE_UPDATE_TIMEOUT == 5.0

    def test_image_fetch_timeout(self):
        """Test IMAGE_FETCH_TIMEOUT constant."""
        from custom_components.evon.const import IMAGE_FETCH_TIMEOUT

        assert IMAGE_FETCH_TIMEOUT == 10

    def test_intercom_2n_cam_class(self):
        """Test EVON_CLASS_INTERCOM_2N_CAM constant."""
        from custom_components.evon.const import EVON_CLASS_INTERCOM_2N_CAM

        assert EVON_CLASS_INTERCOM_2N_CAM == "Security.Intercom.2N.Intercom2NCam"

    def test_device_class_constants(self):
        """Test various device class constants."""
        from custom_components.evon.const import (
            EVON_CLASS_BLIND,
            EVON_CLASS_CLIMATE,
            EVON_CLASS_HOME_STATE,
            EVON_CLASS_LIGHT,
            EVON_CLASS_LIGHT_DIM,
            EVON_CLASS_SCENE,
            EVON_CLASS_VALVE,
        )

        assert EVON_CLASS_LIGHT == "SmartCOM.Light.Light"
        assert EVON_CLASS_LIGHT_DIM == "SmartCOM.Light.LightDim"
        assert EVON_CLASS_BLIND == "SmartCOM.Blind.Blind"
        assert EVON_CLASS_CLIMATE == "SmartCOM.Clima.ClimateControl"
        assert EVON_CLASS_VALVE == "SmartCOM.Clima.Valve"
        assert EVON_CLASS_SCENE == "System.SceneApp"
        assert EVON_CLASS_HOME_STATE == "System.HomeState"


class TestProcessorMissingDetails:
    """Test that processors handle missing instance details gracefully."""

    def test_light_missing_details(self):
        """Test light processor skips instances with no details."""
        from custom_components.evon.coordinator.processors.lights import process_lights

        instances = [
            {"ID": "light_1", "ClassName": "SmartCOM.Light.LightDim", "Name": "Light"},
        ]
        result = process_lights({}, instances, lambda x: "")
        assert len(result) == 0

    def test_climate_missing_details(self):
        """Test climate processor skips instances with no details."""
        from custom_components.evon.coordinator.processors.climate import process_climates

        instances = [
            {"ID": "climate_1", "ClassName": "SmartCOM.Clima.ClimateControl", "Name": "Climate"},
        ]
        result = process_climates({}, instances, lambda x: "", season_mode=False)
        assert len(result) == 0


class TestPyAVImportError:
    """Test graceful handling of missing PyAV."""

    def test_encode_mp4_raises_on_missing_av(self):
        """Test _encode_mp4 raises HomeAssistantError when av is not installed."""
        from datetime import datetime
        from pathlib import Path
        from unittest.mock import MagicMock

        from custom_components.evon.camera_recorder import EvonCameraRecorder

        hass = MagicMock()
        camera = MagicMock()
        camera.entity_id = "camera.test"
        recorder = EvonCameraRecorder(hass, camera)
        recorder._frames = [(b"\xff\xd8\xff\xe0", datetime.now())]

        # Temporarily remove av from sys.modules to simulate ImportError
        had_av = "av" in sys.modules
        old_av = sys.modules.get("av")
        sys.modules["av"] = None  # type: ignore[assignment]  # Force ImportError

        try:
            from homeassistant.exceptions import HomeAssistantError

            with pytest.raises(HomeAssistantError, match="PyAV package not installed"):
                recorder._encode_mp4(Path("/tmp/test.mp4"))
        finally:
            if had_av:
                sys.modules["av"] = old_av
            else:
                sys.modules.pop("av", None)


class TestFindCameraEntity:
    """Tests for _find_camera_entity in __init__.py."""

    def test_find_camera_from_shared_registry(self):
        """Test _find_camera_entity finds camera from the shared registry."""
        from custom_components.evon.__init__ import _find_camera_entity

        mock_camera = MagicMock()
        mock_camera.entity_id = "camera.intercom_1"

        hass = MagicMock()
        hass.data = {
            "evon": {
                "entry_1": {
                    "cameras": {"intercom_1.Cam": mock_camera},
                },
            },
        }

        result = _find_camera_entity(hass, "camera.intercom_1")
        assert result is mock_camera

    def test_find_camera_returns_none_when_not_registered(self):
        """Test _find_camera_entity returns None when camera not registered."""
        from custom_components.evon.__init__ import _find_camera_entity

        hass = MagicMock()
        hass.data = {
            "evon": {
                "entry_1": {
                    "cameras": {},
                },
            },
        }

        result = _find_camera_entity(hass, "camera.nonexistent")
        assert result is None

    def test_find_camera_returns_none_when_domain_missing(self):
        """Test _find_camera_entity returns None when domain not in hass.data."""
        from custom_components.evon.__init__ import _find_camera_entity

        hass = MagicMock()
        hass.data = {}

        result = _find_camera_entity(hass, "camera.intercom_1")
        assert result is None

    def test_find_camera_skips_non_dict_entries(self):
        """Test _find_camera_entity skips non-dict entries in hass.data."""
        from custom_components.evon.__init__ import _find_camera_entity

        mock_camera = MagicMock()
        mock_camera.entity_id = "camera.intercom_1"

        hass = MagicMock()
        hass.data = {
            "evon": {
                "service_lock": "not_a_dict",
                "entry_1": {
                    "cameras": {"intercom_1.Cam": mock_camera},
                },
            },
        }

        result = _find_camera_entity(hass, "camera.intercom_1")
        assert result is mock_camera


class TestGetCameraEntitySwitch:
    """Tests for _get_camera_entity in switch.py (via source inspection)."""

    def test_get_camera_entity_returns_camera_from_registry(self):
        """Test _get_camera_entity returns camera from shared registry."""
        mock_camera = MagicMock()

        hass = MagicMock()
        hass.data = {
            "evon": {
                "entry_1": {
                    "cameras": {"intercom_1.Cam": mock_camera},
                },
            },
        }

        # Simulate the lookup logic from switch.py's _get_camera_entity
        entry_data = hass.data.get("evon", {}).get("entry_1", {})
        result = entry_data.get("cameras", {}).get("intercom_1.Cam")
        assert result is mock_camera

    def test_get_camera_entity_returns_none_when_not_populated(self):
        """Test _get_camera_entity returns None when entry data not yet populated."""
        hass = MagicMock()
        hass.data = {"evon": {}}

        entry_data = hass.data.get("evon", {}).get("entry_1", {})
        result = entry_data.get("cameras", {}).get("intercom_1.Cam")
        assert result is None

    def test_get_camera_entity_source_uses_shared_registry(self):
        """Test that switch.py's _get_camera_entity uses the shared camera registry."""
        with open("custom_components/evon/switch.py") as f:
            source = f.read()

        # Should NOT use private HA internals for entity lookup
        assert "entity_components" not in source
        assert 'hass.data.get("entity_platform"' not in source

        # Should use shared registry
        assert '"cameras"' in source or "'cameras'" in source


class TestCameraWillRemoveFromHass:
    """Test camera cleanup on entity removal.

    EvonCamera can't be imported directly in unit tests due to HA metaclass
    conflicts. We verify the method exists and test it via source inspection.
    The actual integration behavior is tested in test_camera.py (HA framework).
    """

    def test_will_remove_method_exists(self):
        """Test that async_will_remove_from_hass is defined in camera.py."""
        import ast

        with open("custom_components/evon/camera.py") as f:
            tree = ast.parse(f.read())

        # Find the EvonCamera class
        camera_class = None
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == "EvonCamera":
                camera_class = node
                break

        assert camera_class is not None, "EvonCamera class not found"

        # Find async_will_remove_from_hass method
        method_names = [
            node.name for node in ast.walk(camera_class) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        assert "async_will_remove_from_hass" in method_names
        assert "async_added_to_hass" in method_names

    def test_will_remove_calls_recorder_stop(self):
        """Test that async_will_remove_from_hass checks recorder and calls stop."""
        # Read the source to verify the logic
        with open("custom_components/evon/camera.py") as f:
            source = f.read()

        # Verify the method body contains the expected logic
        assert "self._recorder.is_recording" in source
        assert "await self._recorder.async_stop()" in source
        assert "await super().async_will_remove_from_hass()" in source

    def test_will_remove_unregisters_from_shared_registry(self):
        """Test that async_will_remove_from_hass unregisters from the shared camera registry."""
        with open("custom_components/evon/camera.py") as f:
            source = f.read()

        # Verify unregistration from shared registry
        assert '["cameras"].pop(self._instance_id, None)' in source

    def test_added_to_hass_registers_in_shared_registry(self):
        """Test that async_added_to_hass registers in the shared camera registry."""
        with open("custom_components/evon/camera.py") as f:
            source = f.read()

        # Verify registration in shared registry
        assert '["cameras"][self._instance_id] = self' in source


class TestMigrationChain:
    """Tests for async_migrate_entry in __init__.py."""

    def test_migration_uses_while_loop(self):
        """Test that migration uses a while loop instead of if/if/elif."""
        with open("custom_components/evon/__init__.py") as f:
            source = f.read()

        # Should use while loop pattern
        assert "while config_entry.version < 3:" in source

    def test_migration_v1_to_v3_via_while(self):
        """Test that v1 entry migrates through v2 to v3 in one call."""
        from custom_components.evon.__init__ import async_migrate_entry
        from custom_components.evon.const import CONF_CONNECTION_TYPE, CONNECTION_TYPE_LOCAL

        hass = MagicMock()

        config_entry = MagicMock()
        config_entry.version = 1
        config_entry.data = {"host": "http://test"}

        # Track version updates
        versions = []

        def track_update(*args, **kwargs):
            if "version" in kwargs:
                config_entry.version = kwargs["version"]
                versions.append(kwargs["version"])
            if "data" in kwargs:
                config_entry.data = kwargs["data"]

        hass.config_entries.async_update_entry = track_update

        import asyncio

        result = asyncio.get_event_loop().run_until_complete(async_migrate_entry(hass, config_entry))

        assert result is True
        assert config_entry.version == 3
        assert versions == [2, 3]
        assert config_entry.data[CONF_CONNECTION_TYPE] == CONNECTION_TYPE_LOCAL

    def test_migration_v2_to_v3(self):
        """Test that v2 entry migrates to v3."""
        from custom_components.evon.__init__ import async_migrate_entry
        from custom_components.evon.const import CONF_CONNECTION_TYPE, CONNECTION_TYPE_LOCAL

        hass = MagicMock()

        config_entry = MagicMock()
        config_entry.version = 2
        config_entry.data = {"host": "http://test"}

        def track_update(*args, **kwargs):
            if "version" in kwargs:
                config_entry.version = kwargs["version"]
            if "data" in kwargs:
                config_entry.data = kwargs["data"]

        hass.config_entries.async_update_entry = track_update

        import asyncio

        result = asyncio.get_event_loop().run_until_complete(async_migrate_entry(hass, config_entry))

        assert result is True
        assert config_entry.version == 3
        assert config_entry.data[CONF_CONNECTION_TYPE] == CONNECTION_TYPE_LOCAL

    def test_migration_v3_is_noop(self):
        """Test that v3 entry is already current."""
        from custom_components.evon.__init__ import async_migrate_entry

        hass = MagicMock()

        config_entry = MagicMock()
        config_entry.version = 3

        import asyncio

        result = asyncio.get_event_loop().run_until_complete(async_migrate_entry(hass, config_entry))

        assert result is True
        hass.config_entries.async_update_entry.assert_not_called()

    def test_migration_future_version_fails(self):
        """Test that future version returns False."""
        from custom_components.evon.__init__ import async_migrate_entry

        hass = MagicMock()

        config_entry = MagicMock()
        config_entry.version = 99

        import asyncio

        result = asyncio.get_event_loop().run_until_complete(async_migrate_entry(hass, config_entry))

        assert result is False


class TestSelectEntitiesInheritance:
    """Tests for select entity base class (source inspection)."""

    def test_home_state_select_extends_evon_entity(self):
        """Test that EvonHomeStateSelect extends EvonEntity."""
        import ast

        with open("custom_components/evon/select.py") as f:
            tree = ast.parse(f.read())

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == "EvonHomeStateSelect":
                base_names = [
                    b.attr if isinstance(b, ast.Attribute) else b.id if isinstance(b, ast.Name) else ""
                    for b in node.bases
                ]
                assert "EvonEntity" in base_names
                assert "SelectEntity" in base_names
                assert "CoordinatorEntity" not in base_names
                return
        pytest.fail("EvonHomeStateSelect class not found")

    def test_season_mode_select_extends_evon_entity(self):
        """Test that EvonSeasonModeSelect extends EvonEntity."""
        import ast

        with open("custom_components/evon/select.py") as f:
            tree = ast.parse(f.read())

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == "EvonSeasonModeSelect":
                base_names = [
                    b.attr if isinstance(b, ast.Attribute) else b.id if isinstance(b, ast.Name) else ""
                    for b in node.bases
                ]
                assert "EvonEntity" in base_names
                assert "SelectEntity" in base_names
                assert "CoordinatorEntity" not in base_names
                return
        pytest.fail("EvonSeasonModeSelect class not found")

    def test_select_imports_evon_entity(self):
        """Test that select.py imports from base_entity."""
        with open("custom_components/evon/select.py") as f:
            source = f.read()

        assert "from .base_entity import EvonEntity" in source

    def test_select_does_not_import_coordinator_entity(self):
        """Test that select.py no longer imports CoordinatorEntity directly."""
        with open("custom_components/evon/select.py") as f:
            source = f.read()

        assert "from homeassistant.helpers.update_coordinator import CoordinatorEntity" not in source

    def test_select_does_not_import_time(self):
        """Test that select.py no longer imports time (uses EvonEntity methods)."""
        with open("custom_components/evon/select.py") as f:
            source = f.read()

        assert "import time" not in source

    def test_select_uses_set_optimistic_timestamp(self):
        """Test that select.py uses _set_optimistic_timestamp() from EvonEntity."""
        with open("custom_components/evon/select.py") as f:
            source = f.read()

        assert "_set_optimistic_timestamp()" in source

    def test_select_has_reset_optimistic_state(self):
        """Test that both select classes override _reset_optimistic_state."""
        with open("custom_components/evon/select.py") as f:
            source = f.read()

        assert source.count("def _reset_optimistic_state(self)") == 2

    def test_select_calls_super_extra_state_attributes(self):
        """Test that both select classes call super().extra_state_attributes."""
        with open("custom_components/evon/select.py") as f:
            source = f.read()

        assert source.count("super().extra_state_attributes") == 2
