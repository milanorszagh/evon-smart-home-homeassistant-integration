"""Tests for Evon camera platform."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.evon.const import ENTITY_TYPE_CAMERAS, ENTITY_TYPE_SECURITY_DOORS
from tests.conftest import HAS_HA_TEST_FRAMEWORK, requires_ha_test_framework

# Entity classes require proper HA base classes (metaclass inheritance)
if HAS_HA_TEST_FRAMEWORK:
    from custom_components.evon.camera import EvonCamera


# =============================================================================
# Unit tests (require HA test framework for entity class imports)
# =============================================================================


def _make_coordinator(cam_data=None, door_data=None):
    """Create a mock coordinator with optional camera/door data."""
    coord = MagicMock()
    coord.last_update_success = True
    coord.data = {}
    if cam_data is not None:
        coord.data[ENTITY_TYPE_CAMERAS] = cam_data
    if door_data is not None:
        coord.data[ENTITY_TYPE_SECURITY_DOORS] = door_data
    coord.hass = MagicMock()
    coord.api = MagicMock()
    coord.api.fetch_image = AsyncMock(return_value=b"\xff\xd8\xff\xe0JFIF")
    coord.ws_client = None  # No WS by default

    def _get_entity_data(entity_type, instance_id):
        for entity in coord.data.get(entity_type, []):
            if entity.get("id") == instance_id:
                return entity
        return None

    coord.get_entity_data = MagicMock(side_effect=_get_entity_data)
    return coord


def _make_entry():
    entry = MagicMock()
    entry.entry_id = "test_entry"
    entry.options = {}
    return entry


SAMPLE_CAM = {
    "id": "Intercom1.Cam",
    "name": "Intercom Camera",
    "room_name": "Hallway",
    "image_path": "/images/current.jpg",
    "ip_address": "192.168.1.50",
    "error": False,
}

SAMPLE_DOOR = {
    "id": "Security.Door1",
    "name": "Front Door",
    "cam_instance_name": "Intercom1.Cam",
    "saved_pictures": [
        {"path": "/images/snap1.jpg", "timestamp": 1706900000000},
        {"path": "/images/snap2.jpg", "timestamp": 1706899000000},
    ],
}


@requires_ha_test_framework
class TestEvonCamera:
    """Test EvonCamera entity properties."""

    def test_unique_id(self):
        coord = _make_coordinator(cam_data=[SAMPLE_CAM])
        cam = EvonCamera(coord, "Intercom1.Cam", "Intercom Camera", "Hallway", _make_entry())
        assert cam._attr_unique_id == "evon_camera_Intercom1.Cam"

    def test_is_on_when_no_error(self):
        coord = _make_coordinator(cam_data=[SAMPLE_CAM])
        cam = EvonCamera(coord, "Intercom1.Cam", "Intercom Camera", "Hallway", _make_entry())
        assert cam.is_on is True

    def test_is_off_when_error(self):
        cam_data = {**SAMPLE_CAM, "error": True}
        coord = _make_coordinator(cam_data=[cam_data])
        cam = EvonCamera(coord, "Intercom1.Cam", "Intercom Camera", "Hallway", _make_entry())
        assert cam.is_on is False

    def test_is_off_when_no_data(self):
        coord = _make_coordinator(cam_data=[])
        cam = EvonCamera(coord, "Intercom1.Cam", "Intercom Camera", "Hallway", _make_entry())
        assert cam.is_on is False

    def test_is_streaming_default_false(self):
        coord = _make_coordinator(cam_data=[SAMPLE_CAM])
        cam = EvonCamera(coord, "Intercom1.Cam", "Intercom Camera", "Hallway", _make_entry())
        assert cam.is_streaming is False

    def test_recorder_property(self):
        coord = _make_coordinator(cam_data=[SAMPLE_CAM])
        cam = EvonCamera(coord, "Intercom1.Cam", "Intercom Camera", "Hallway", _make_entry())
        assert cam.recorder is not None

    def test_get_saved_pictures_finds_linked_door(self):
        coord = _make_coordinator(cam_data=[SAMPLE_CAM], door_data=[SAMPLE_DOOR])
        cam = EvonCamera(coord, "Intercom1.Cam", "Intercom Camera", "Hallway", _make_entry())
        pics = cam._get_saved_pictures()
        assert len(pics) == 2

    def test_get_saved_pictures_no_doors(self):
        coord = _make_coordinator(cam_data=[SAMPLE_CAM])
        cam = EvonCamera(coord, "Intercom1.Cam", "Intercom Camera", "Hallway", _make_entry())
        pics = cam._get_saved_pictures()
        assert pics == []

    def test_get_saved_pictures_no_matching_door(self):
        other_door = {**SAMPLE_DOOR, "cam_instance_name": "OtherCam"}
        coord = _make_coordinator(cam_data=[SAMPLE_CAM], door_data=[other_door])
        cam = EvonCamera(coord, "Intercom1.Cam", "Intercom Camera", "Hallway", _make_entry())
        pics = cam._get_saved_pictures()
        assert pics == []

    def test_get_saved_pictures_partial_cam_match(self):
        """Door with cam_instance_name='Cam' should match 'Intercom1.Cam'."""
        door = {**SAMPLE_DOOR, "cam_instance_name": "Cam"}
        coord = _make_coordinator(cam_data=[SAMPLE_CAM], door_data=[door])
        cam = EvonCamera(coord, "Intercom1.Cam", "Intercom Camera", "Hallway", _make_entry())
        pics = cam._get_saved_pictures()
        assert len(pics) == 2


@requires_ha_test_framework
class TestEvonCameraImage:
    """Test async_camera_image method."""

    @pytest.mark.asyncio
    async def test_returns_image_without_ws(self):
        coord = _make_coordinator(cam_data=[SAMPLE_CAM])
        cam = EvonCamera(coord, "Intercom1.Cam", "Intercom Camera", "Hallway", _make_entry())
        image = await cam.async_camera_image()
        assert image is not None
        coord.api.fetch_image.assert_awaited_once_with("/images/current.jpg")

    @pytest.mark.asyncio
    async def test_caches_last_image(self):
        coord = _make_coordinator(cam_data=[SAMPLE_CAM])
        cam = EvonCamera(coord, "Intercom1.Cam", "Intercom Camera", "Hallway", _make_entry())
        await cam.async_camera_image()
        assert cam._last_image is not None

    @pytest.mark.asyncio
    async def test_returns_cached_on_no_data(self):
        coord = _make_coordinator(cam_data=[])
        cam = EvonCamera(coord, "Intercom1.Cam", "Intercom Camera", "Hallway", _make_entry())
        cam._last_image = b"cached"
        image = await cam.async_camera_image()
        assert image == b"cached"

    @pytest.mark.asyncio
    async def test_returns_cached_on_empty_path(self):
        cam_data = {**SAMPLE_CAM, "image_path": ""}
        coord = _make_coordinator(cam_data=[cam_data])
        cam = EvonCamera(coord, "Intercom1.Cam", "Intercom Camera", "Hallway", _make_entry())
        cam._last_image = b"cached"
        image = await cam.async_camera_image()
        assert image == b"cached"

    @pytest.mark.asyncio
    async def test_returns_cached_on_fetch_failure(self):
        coord = _make_coordinator(cam_data=[SAMPLE_CAM])
        coord.api.fetch_image = AsyncMock(return_value=None)
        cam = EvonCamera(coord, "Intercom1.Cam", "Intercom Camera", "Hallway", _make_entry())
        cam._last_image = b"old"
        image = await cam.async_camera_image()
        assert image == b"old"


@requires_ha_test_framework
class TestEvonCameraSavedPictures:
    """Test async_get_saved_picture method."""

    @pytest.mark.asyncio
    async def test_get_saved_picture_index_0(self):
        coord = _make_coordinator(cam_data=[SAMPLE_CAM], door_data=[SAMPLE_DOOR])
        cam = EvonCamera(coord, "Intercom1.Cam", "Intercom Camera", "Hallway", _make_entry())
        image = await cam.async_get_saved_picture(0)
        assert image is not None
        coord.api.fetch_image.assert_awaited_once_with("/images/snap1.jpg")

    @pytest.mark.asyncio
    async def test_get_saved_picture_index_out_of_bounds(self):
        coord = _make_coordinator(cam_data=[SAMPLE_CAM], door_data=[SAMPLE_DOOR])
        cam = EvonCamera(coord, "Intercom1.Cam", "Intercom Camera", "Hallway", _make_entry())
        image = await cam.async_get_saved_picture(10)
        assert image is None

    @pytest.mark.asyncio
    async def test_get_saved_picture_no_pictures(self):
        coord = _make_coordinator(cam_data=[SAMPLE_CAM])
        cam = EvonCamera(coord, "Intercom1.Cam", "Intercom Camera", "Hallway", _make_entry())
        image = await cam.async_get_saved_picture(0)
        assert image is None

    @pytest.mark.asyncio
    async def test_get_saved_picture_empty_path(self):
        door = {**SAMPLE_DOOR, "saved_pictures": [{"timestamp": 123}]}
        coord = _make_coordinator(cam_data=[SAMPLE_CAM], door_data=[door])
        cam = EvonCamera(coord, "Intercom1.Cam", "Intercom Camera", "Hallway", _make_entry())
        image = await cam.async_get_saved_picture(0)
        assert image is None


@requires_ha_test_framework
class TestEvonCameraTurnOnOff:
    """Test async_turn_on/async_turn_off methods."""

    @pytest.mark.asyncio
    async def test_turn_on_sets_streaming(self):
        coord = _make_coordinator(cam_data=[SAMPLE_CAM])
        cam = EvonCamera(coord, "Intercom1.Cam", "Intercom Camera", "Hallway", _make_entry())
        cam.async_write_ha_state = MagicMock()
        await cam.async_turn_on()
        assert cam.is_streaming is True

    @pytest.mark.asyncio
    async def test_turn_off_clears_streaming(self):
        coord = _make_coordinator(cam_data=[SAMPLE_CAM])
        cam = EvonCamera(coord, "Intercom1.Cam", "Intercom Camera", "Hallway", _make_entry())
        cam.async_write_ha_state = MagicMock()
        cam._is_streaming = True
        await cam.async_turn_off()
        assert cam.is_streaming is False


# =============================================================================
# Integration tests (require pytest-homeassistant-custom-component)
# =============================================================================


@requires_ha_test_framework
@pytest.mark.asyncio
async def test_camera_setup(hass, mock_config_entry_v2, mock_evon_api_class):
    """Test camera entity is created."""
    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    # Camera entity should exist
    state = hass.states.get("camera.intercom_camera")
    assert state is not None


@requires_ha_test_framework
@pytest.mark.asyncio
async def test_camera_attributes(hass, mock_config_entry_v2, mock_evon_api_class):
    """Test camera extra state attributes."""
    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("camera.intercom_camera")
    assert state is not None
    # Camera should have IP address attribute
    assert "ip_address" in state.attributes or state.attributes.get("ip_address") is not None


@requires_ha_test_framework
@pytest.mark.asyncio
async def test_camera_unique_id(hass, mock_config_entry_v2, mock_evon_api_class):
    """Test camera has unique ID."""
    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    from homeassistant.helpers import entity_registry as er

    entity_registry = er.async_get(hass)
    entry = entity_registry.async_get("camera.intercom_camera")
    assert entry is not None
    assert entry.unique_id == "evon_camera_intercom_1.Cam"
