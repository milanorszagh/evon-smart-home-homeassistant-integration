"""Unit tests for coordinator processors (no HA framework required)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest


class TestCameraProcessor:
    """Tests for camera data processor."""

    @pytest.fixture
    def mock_api(self):
        """Create a mock API."""
        api = MagicMock()
        api.get_instance = AsyncMock()
        return api

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

    @pytest.mark.asyncio
    async def test_process_cameras(self, mock_api, camera_instances, camera_details):
        """Test camera processor extracts data correctly."""
        from custom_components.evon.coordinator.processors.cameras import process_cameras

        mock_api.get_instance.return_value = camera_details

        def get_room_name(group_id):
            return "Living Room" if group_id == "room_living" else ""

        result = await process_cameras(mock_api, camera_instances, get_room_name)

        assert len(result) == 1
        camera = result[0]
        assert camera["id"] == "intercom_1.Cam"
        assert camera["name"] == "Intercom Camera"
        assert camera["room_name"] == "Living Room"
        assert camera["image_path"] == "/images/current.jpg"
        assert camera["ip_address"] == "192.168.1.50"
        assert camera["error"] is False

    @pytest.mark.asyncio
    async def test_process_cameras_empty(self, mock_api):
        """Test camera processor with no cameras."""
        from custom_components.evon.coordinator.processors.cameras import process_cameras

        result = await process_cameras(mock_api, [], lambda x: "")

        assert result == []

    @pytest.mark.asyncio
    async def test_process_cameras_filters_by_class(self, mock_api):
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

        mock_api.get_instance.return_value = {"ImagePath": "/img.jpg"}

        result = await process_cameras(mock_api, instances, lambda x: "")

        assert len(result) == 1
        assert result[0]["id"] == "intercom_1.Cam"


class TestSecurityDoorProcessor:
    """Tests for security door data processor."""

    @pytest.fixture
    def mock_api(self):
        """Create a mock API."""
        api = MagicMock()
        api.get_instance = AsyncMock()
        return api

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

    @pytest.mark.asyncio
    async def test_process_security_doors(self, mock_api, door_instances, door_details):
        """Test security door processor extracts data correctly."""
        from custom_components.evon.coordinator.processors.security_doors import process_security_doors

        mock_api.get_instance.return_value = door_details

        def get_room_name(group_id):
            return "Living Room" if group_id == "room_living" else ""

        result = await process_security_doors(mock_api, door_instances, get_room_name)

        assert len(result) == 1
        door = result[0]
        assert door["id"] == "security_door_1"
        assert door["name"] == "Front Door"
        assert door["is_open"] is False
        assert door["call_in_progress"] is False
        assert door["cam_instance_name"] == "intercom_1.Cam"
        assert len(door["saved_pictures"]) == 2

    @pytest.mark.asyncio
    async def test_process_security_doors_saved_pictures_lowercase(self, mock_api, door_instances, door_details):
        """Test security door processor converts saved pictures keys to lowercase."""
        from custom_components.evon.coordinator.processors.security_doors import process_security_doors

        mock_api.get_instance.return_value = door_details

        result = await process_security_doors(mock_api, door_instances, lambda x: "")

        # Keys should be lowercase
        saved_pictures = result[0]["saved_pictures"]
        assert "path" in saved_pictures[0]
        assert "timestamp" in saved_pictures[0]
        assert saved_pictures[0]["path"] == "/images/snap1.jpg"


class TestIntercomProcessor:
    """Tests for intercom data processor."""

    @pytest.fixture
    def mock_api(self):
        """Create a mock API."""
        api = MagicMock()
        api.get_instance = AsyncMock()
        return api

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

    @pytest.mark.asyncio
    async def test_process_intercoms(self, mock_api, intercom_instances, intercom_details):
        """Test intercom processor extracts data correctly."""
        from custom_components.evon.coordinator.processors.intercoms import process_intercoms

        mock_api.get_instance.return_value = intercom_details

        def get_room_name(group_id):
            return "Living Room" if group_id == "room_living" else ""

        result = await process_intercoms(mock_api, intercom_instances, get_room_name)

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

    @pytest.fixture
    def mock_api(self):
        """Create a mock API."""
        api = MagicMock()
        api.get_instance = AsyncMock()
        return api

    @pytest.mark.asyncio
    async def test_process_lights(self, mock_api):
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
        mock_api.get_instance.return_value = {
            "IsOn": True,
            "ScaledBrightness": 75,
        }

        result = await process_lights(mock_api, instances, lambda x: "Living Room")

        assert len(result) == 1
        light = result[0]
        assert light["id"] == "light_1"
        assert light["name"] == "Living Room Light"
        assert light["is_on"] is True
        assert light["brightness"] == 75
        assert light["supports_color_temp"] is False

    @pytest.mark.asyncio
    async def test_process_lights_rgbw(self, mock_api):
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
        mock_api.get_instance.return_value = {
            "IsOn": True,
            "ScaledBrightness": 100,
            "ColorTemp": 4000,
            "MinColorTemperature": 2700,
            "MaxColorTemperature": 6500,
        }

        result = await process_lights(mock_api, instances, lambda x: "")

        assert len(result) == 1
        light = result[0]
        assert light["supports_color_temp"] is True
        assert light["color_temp"] == 4000
        assert light["min_color_temp"] == 2700
        assert light["max_color_temp"] == 6500

    @pytest.mark.asyncio
    async def test_process_lights_filters_by_class(self, mock_api):
        """Test light processor only includes light classes."""
        from custom_components.evon.coordinator.processors.lights import process_lights

        instances = [
            {"ID": "switch_1", "ClassName": "SmartCOM.Light.Light", "Name": "Switch"},
            {"ID": "light_1", "ClassName": "SmartCOM.Light.LightDim", "Name": "Light"},
        ]
        mock_api.get_instance.return_value = {"IsOn": True, "ScaledBrightness": 50}

        result = await process_lights(mock_api, instances, lambda x: "")

        # Should only include LightDim, not Light (which is a switch)
        assert len(result) == 1
        assert result[0]["id"] == "light_1"

    @pytest.mark.asyncio
    async def test_process_lights_skips_unnamed(self, mock_api):
        """Test light processor skips instances without names."""
        from custom_components.evon.coordinator.processors.lights import process_lights

        instances = [
            {"ID": "light_1", "ClassName": "SmartCOM.Light.LightDim", "Name": ""},
            {"ID": "light_2", "ClassName": "SmartCOM.Light.LightDim", "Name": "Named"},
        ]
        mock_api.get_instance.return_value = {"IsOn": False, "ScaledBrightness": 0}

        result = await process_lights(mock_api, instances, lambda x: "")

        assert len(result) == 1
        assert result[0]["id"] == "light_2"


class TestBlindProcessor:
    """Tests for blind data processor."""

    @pytest.fixture
    def mock_api(self):
        """Create a mock API."""
        api = MagicMock()
        api.get_instance = AsyncMock()
        return api

    @pytest.mark.asyncio
    async def test_process_blinds(self, mock_api):
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
        mock_api.get_instance.return_value = {
            "Position": 50,
            "Angle": 45,
            "IsMoving": False,
        }

        result = await process_blinds(mock_api, instances, lambda x: "Living Room")

        assert len(result) == 1
        blind = result[0]
        assert blind["id"] == "blind_1"
        assert blind["name"] == "Living Room Blind"
        assert blind["position"] == 50
        assert blind["angle"] == 45
        assert blind["is_moving"] is False
        assert blind["is_group"] is False

    @pytest.mark.asyncio
    async def test_process_blinds_group(self, mock_api):
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
        mock_api.get_instance.return_value = {"Position": 100, "Angle": 0, "IsMoving": True}

        result = await process_blinds(mock_api, instances, lambda x: "")

        assert len(result) == 1
        assert result[0]["is_group"] is True
        assert result[0]["is_moving"] is True


class TestClimateProcessor:
    """Tests for climate data processor."""

    @pytest.fixture
    def mock_api(self):
        """Create a mock API."""
        api = MagicMock()
        api.get_instance = AsyncMock()
        return api

    @pytest.mark.asyncio
    async def test_process_climates_heating(self, mock_api):
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
        mock_api.get_instance.return_value = {
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
        }

        result = await process_climates(mock_api, instances, lambda x: "Living Room", season_mode=False)

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

    @pytest.mark.asyncio
    async def test_process_climates_cooling(self, mock_api):
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
        mock_api.get_instance.return_value = {
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
        }

        result = await process_climates(mock_api, instances, lambda x: "", season_mode=True)

        assert len(result) == 1
        climate = result[0]
        assert climate["min_temp"] == 18
        assert climate["max_temp"] == 30
        assert climate["comfort_temp"] == 25
        assert climate["protection_temp"] == 29
        assert climate["is_cooling"] is True


class TestSwitchProcessor:
    """Tests for switch data processor."""

    @pytest.fixture
    def mock_api(self):
        """Create a mock API."""
        api = MagicMock()
        api.get_instance = AsyncMock()
        return api

    @pytest.mark.asyncio
    async def test_process_switches(self, mock_api):
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
        mock_api.get_instance.return_value = {"IsOn": True}

        result = await process_switches(mock_api, instances, lambda x: "Kitchen")

        assert len(result) == 1
        switch = result[0]
        assert switch["id"] == "switch_1"
        assert switch["name"] == "Kitchen Outlet"
        assert switch["room_name"] == "Kitchen"
        assert switch["is_on"] is True

    @pytest.mark.asyncio
    async def test_process_switches_filters_dim_lights(self, mock_api):
        """Test switch processor excludes dimmable lights."""
        from custom_components.evon.coordinator.processors.switches import process_switches

        instances = [
            {"ID": "switch_1", "ClassName": "SmartCOM.Light.Light", "Name": "Switch"},
            {"ID": "light_1", "ClassName": "SmartCOM.Light.DimLight", "Name": "Dim Light"},
        ]
        mock_api.get_instance.return_value = {"IsOn": False}

        result = await process_switches(mock_api, instances, lambda x: "")

        # Should only include SmartCOM.Light.Light
        assert len(result) == 1
        assert result[0]["id"] == "switch_1"


class TestSceneProcessor:
    """Tests for scene data processor."""

    @pytest.mark.asyncio
    async def test_process_scenes(self):
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

        result = await process_scenes(instances)

        assert len(result) == 2
        assert result[0]["id"] == "scene_1"
        assert result[0]["name"] == "Movie Night"
        assert result[1]["id"] == "scene_2"
        assert result[1]["name"] == "Good Morning"

    @pytest.mark.asyncio
    async def test_process_scenes_filters_by_class(self):
        """Test scene processor only includes scene class."""
        from custom_components.evon.coordinator.processors.scenes import process_scenes

        instances = [
            {"ID": "scene_1", "ClassName": "System.SceneApp", "Name": "Scene"},
            {"ID": "light_1", "ClassName": "SmartCOM.Light.Light", "Name": "Light"},
        ]

        result = await process_scenes(instances)

        assert len(result) == 1
        assert result[0]["id"] == "scene_1"

    @pytest.mark.asyncio
    async def test_process_scenes_empty(self):
        """Test scene processor with no scenes."""
        from custom_components.evon.coordinator.processors.scenes import process_scenes

        result = await process_scenes([])

        assert result == []


class TestValveProcessor:
    """Tests for valve data processor."""

    @pytest.fixture
    def mock_api(self):
        """Create a mock API."""
        api = MagicMock()
        api.get_instance = AsyncMock()
        return api

    @pytest.mark.asyncio
    async def test_process_valves(self, mock_api):
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
        mock_api.get_instance.return_value = {
            "ActValue": True,
            "Type": 1,
        }

        result = await process_valves(mock_api, instances, lambda x: "Bedroom")

        assert len(result) == 1
        valve = result[0]
        assert valve["id"] == "valve_1"
        assert valve["name"] == "Heating Valve"
        assert valve["room_name"] == "Bedroom"
        assert valve["is_open"] is True
        assert valve["valve_type"] == 1


class TestHomeStateProcessor:
    """Tests for home state data processor."""

    @pytest.fixture
    def mock_api(self):
        """Create a mock API."""
        api = MagicMock()
        api.get_instance = AsyncMock()
        return api

    @pytest.mark.asyncio
    async def test_process_home_states(self, mock_api):
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
        mock_api.get_instance.side_effect = [
            {"Active": False},
            {"Active": True},
        ]

        result = await process_home_states(mock_api, instances)

        assert len(result) == 2
        assert result[0]["id"] == "home_state_1"
        assert result[0]["active"] is False
        assert result[1]["id"] == "home_state_2"
        assert result[1]["active"] is True

    @pytest.mark.asyncio
    async def test_process_home_states_skips_system(self, mock_api):
        """Test home state processor skips System.* templates."""
        from custom_components.evon.coordinator.processors.home_states import process_home_states

        instances = [
            {"ID": "System.HomeState", "ClassName": "System.HomeState", "Name": "Template"},
            {"ID": "user_state", "ClassName": "System.HomeState", "Name": "User State"},
        ]
        mock_api.get_instance.return_value = {"Active": True}

        result = await process_home_states(mock_api, instances)

        assert len(result) == 1
        assert result[0]["id"] == "user_state"


class TestAirQualityProcessor:
    """Tests for air quality data processor."""

    @pytest.fixture
    def mock_api(self):
        """Create a mock API."""
        api = MagicMock()
        api.get_instance = AsyncMock()
        return api

    @pytest.mark.asyncio
    async def test_process_air_quality(self, mock_api):
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
        mock_api.get_instance.return_value = {
            "CO2Value": 800,
            "Humidity": 55,
            "ActualTemperature": 22.5,
            "HealthIndex": 85,
            "CO2Index": 80,
            "HumidityIndex": 90,
        }

        result = await process_air_quality(mock_api, instances, lambda x: "Bedroom")

        assert len(result) == 1
        aq = result[0]
        assert aq["id"] == "aq_1"
        assert aq["co2"] == 800
        assert aq["humidity"] == 55
        assert aq["temperature"] == 22.5
        assert aq["health_index"] == 85

    @pytest.mark.asyncio
    async def test_process_air_quality_skips_invalid_data(self, mock_api):
        """Test air quality processor skips sensors with no valid data."""
        from custom_components.evon.coordinator.processors.air_quality import process_air_quality

        instances = [
            {"ID": "aq_1", "ClassName": "System.Location.AirQuality", "Name": "Invalid Sensor", "Group": ""},
        ]
        mock_api.get_instance.return_value = {
            "CO2Value": -999,
            "Humidity": -999,
            "ActualTemperature": -999,
        }

        result = await process_air_quality(mock_api, instances, lambda x: "")

        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_process_air_quality_partial_data(self, mock_api):
        """Test air quality processor handles partial data (some -999 values)."""
        from custom_components.evon.coordinator.processors.air_quality import process_air_quality

        instances = [
            {"ID": "aq_1", "ClassName": "System.Location.AirQuality", "Name": "Partial Sensor", "Group": ""},
        ]
        mock_api.get_instance.return_value = {
            "CO2Value": 600,
            "Humidity": -999,
            "ActualTemperature": -999,
        }

        result = await process_air_quality(mock_api, instances, lambda x: "")

        assert len(result) == 1
        assert result[0]["co2"] == 600
        assert result[0]["humidity"] is None
        assert result[0]["temperature"] is None


class TestSmartMeterProcessor:
    """Tests for smart meter data processor."""

    @pytest.fixture
    def mock_api(self):
        """Create a mock API."""
        api = MagicMock()
        api.get_instance = AsyncMock()
        return api

    @pytest.mark.asyncio
    async def test_process_smart_meters(self, mock_api):
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
        mock_api.get_instance.return_value = {
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
        }

        result = await process_smart_meters(mock_api, instances, lambda x: "")

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

    @pytest.fixture
    def mock_api(self):
        """Create a mock API."""
        api = MagicMock()
        api.get_instance = AsyncMock()
        return api

    @pytest.mark.asyncio
    async def test_process_bathroom_radiators(self, mock_api):
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
        mock_api.get_instance.return_value = {
            "Output": True,
            "NextSwitchPoint": 1800,
            "EnableForMins": 60,
            "PermanentlyOn": False,
            "PermanentlyOff": False,
            "Deactivated": False,
        }

        result = await process_bathroom_radiators(mock_api, instances, lambda x: "Bathroom")

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
