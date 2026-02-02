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
        from unittest.mock import AsyncMock, MagicMock
        from contextlib import asynccontextmanager

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
        mock_session.get = mock_get

        api._session = mock_session
        api._token = "test_token"

        result = await api.fetch_image("/images/test.jpg")

        assert result == b"\xff\xd8\xff\xe0JPEG"

    @pytest.mark.asyncio
    async def test_fetch_image_failure_returns_none(self):
        """Test fetch_image returns None on HTTP error."""
        from unittest.mock import MagicMock
        from contextlib import asynccontextmanager
        import aiohttp

        from custom_components.evon.api import EvonApi

        api = EvonApi("http://192.168.1.100", "user", "pass")

        @asynccontextmanager
        async def mock_get_error(*args, **kwargs):
            raise aiohttp.ClientError()
            yield  # Never reached

        mock_session = MagicMock()
        mock_session.get = mock_get_error

        api._session = mock_session
        api._token = "test_token"

        result = await api.fetch_image("/images/test.jpg")

        assert result is None


class TestConstants:
    """Tests for camera/image related constants."""

    def test_camera_image_capture_delay(self):
        """Test CAMERA_IMAGE_CAPTURE_DELAY constant."""
        from custom_components.evon.const import CAMERA_IMAGE_CAPTURE_DELAY

        assert CAMERA_IMAGE_CAPTURE_DELAY == 0.5

    def test_image_fetch_timeout(self):
        """Test IMAGE_FETCH_TIMEOUT constant."""
        from custom_components.evon.const import IMAGE_FETCH_TIMEOUT

        assert IMAGE_FETCH_TIMEOUT == 10

    def test_intercom_2n_cam_class(self):
        """Test EVON_CLASS_INTERCOM_2N_CAM constant."""
        from custom_components.evon.const import EVON_CLASS_INTERCOM_2N_CAM

        assert EVON_CLASS_INTERCOM_2N_CAM == "Security.Intercom.2N.Intercom2NCam"
