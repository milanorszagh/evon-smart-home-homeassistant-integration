"""Tests for Evon image platform (doorbell snapshots)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.evon.const import ENTITY_TYPE_SECURITY_DOORS
from tests.conftest import HAS_HA_TEST_FRAMEWORK, requires_ha_test_framework

# Entity classes require proper HA base classes (metaclass inheritance)
if HAS_HA_TEST_FRAMEWORK:
    from custom_components.evon.image import MAX_SNAPSHOTS, EvonDoorbellSnapshot


# =============================================================================
# Unit tests (require HA test framework for entity class imports)
# =============================================================================


def _make_coordinator(doors=None, success=True):
    """Create a mock coordinator with optional door data."""
    coord = MagicMock()
    coord.last_update_success = success
    coord.hass = MagicMock()
    coord.data = {}
    if doors is not None:
        coord.data[ENTITY_TYPE_SECURITY_DOORS] = doors
    coord.api = MagicMock()
    coord.api.fetch_image = AsyncMock(return_value=b"\xff\xd8\xff\xe0JFIF")
    return coord


def _make_entry():
    entry = MagicMock()
    entry.entry_id = "test_entry"
    return entry


SAMPLE_DOOR = {
    "id": "Security.Door1",
    "name": "Front Door",
    "saved_pictures": [
        {"path": "/images/snap1.jpg", "timestamp": 1706900000000},
        {"path": "/images/snap2.jpg", "timestamp": 1706899000000},
    ],
}


@requires_ha_test_framework
class TestEvonDoorbellSnapshot:
    """Test EvonDoorbellSnapshot entity."""

    def test_unique_id(self):
        coord = _make_coordinator(doors=[SAMPLE_DOOR])
        snap = EvonDoorbellSnapshot(coord, "Security.Door1", "Front Door", 0, _make_entry())
        assert snap._attr_unique_id == "evon_snapshot_Security.Door1_0"

    def test_unique_id_index_3(self):
        coord = _make_coordinator(doors=[SAMPLE_DOOR])
        snap = EvonDoorbellSnapshot(coord, "Security.Door1", "Front Door", 3, _make_entry())
        assert snap._attr_unique_id == "evon_snapshot_Security.Door1_3"

    def test_name_1_indexed(self):
        coord = _make_coordinator(doors=[SAMPLE_DOOR])
        snap = EvonDoorbellSnapshot(coord, "Security.Door1", "Front Door", 0, _make_entry())
        assert snap.name == "Snapshot 1"

    def test_name_index_9(self):
        coord = _make_coordinator(doors=[SAMPLE_DOOR])
        snap = EvonDoorbellSnapshot(coord, "Security.Door1", "Front Door", 9, _make_entry())
        assert snap.name == "Snapshot 10"

    def test_available_when_snapshot_exists(self):
        coord = _make_coordinator(doors=[SAMPLE_DOOR])
        snap = EvonDoorbellSnapshot(coord, "Security.Door1", "Front Door", 0, _make_entry())
        assert snap.available is True

    def test_unavailable_when_index_out_of_bounds(self):
        coord = _make_coordinator(doors=[SAMPLE_DOOR])
        snap = EvonDoorbellSnapshot(coord, "Security.Door1", "Front Door", 5, _make_entry())
        assert snap.available is False

    def test_unavailable_when_coordinator_fails(self):
        coord = _make_coordinator(doors=[SAMPLE_DOOR], success=False)
        snap = EvonDoorbellSnapshot(coord, "Security.Door1", "Front Door", 0, _make_entry())
        assert snap.available is False

    def test_unavailable_when_no_doors(self):
        coord = _make_coordinator(doors=None)
        snap = EvonDoorbellSnapshot(coord, "Security.Door1", "Front Door", 0, _make_entry())
        assert snap.available is False

    def test_unavailable_when_door_not_found(self):
        coord = _make_coordinator(doors=[SAMPLE_DOOR])
        snap = EvonDoorbellSnapshot(coord, "Security.OtherDoor", "Other", 0, _make_entry())
        assert snap.available is False

    def test_extra_state_attributes_with_snapshot(self):
        coord = _make_coordinator(doors=[SAMPLE_DOOR])
        snap = EvonDoorbellSnapshot(coord, "Security.Door1", "Front Door", 0, _make_entry())
        attrs = snap.extra_state_attributes
        assert attrs["index"] == 0
        assert attrs["door_id"] == "Security.Door1"
        assert attrs["timestamp"] == 1706900000000
        assert "datetime" in attrs
        assert attrs["path"] == "/images/snap1.jpg"

    def test_extra_state_attributes_no_snapshot(self):
        coord = _make_coordinator(doors=[SAMPLE_DOOR])
        snap = EvonDoorbellSnapshot(coord, "Security.Door1", "Front Door", 5, _make_entry())
        attrs = snap.extra_state_attributes
        assert attrs["index"] == 5
        assert attrs["door_id"] == "Security.Door1"
        assert "timestamp" not in attrs

    def test_image_last_updated_with_timestamp(self):
        coord = _make_coordinator(doors=[SAMPLE_DOOR])
        snap = EvonDoorbellSnapshot(coord, "Security.Door1", "Front Door", 0, _make_entry())
        updated = snap.image_last_updated
        assert updated is not None

    def test_image_last_updated_no_snapshot(self):
        coord = _make_coordinator(doors=[SAMPLE_DOOR])
        snap = EvonDoorbellSnapshot(coord, "Security.Door1", "Front Door", 5, _make_entry())
        assert snap.image_last_updated is None

    def test_image_last_updated_no_timestamp(self):
        door = {
            "id": "Security.Door1",
            "name": "Front Door",
            "saved_pictures": [{"path": "/images/snap1.jpg"}],
        }
        coord = _make_coordinator(doors=[door])
        snap = EvonDoorbellSnapshot(coord, "Security.Door1", "Front Door", 0, _make_entry())
        assert snap.image_last_updated is None

    def test_get_snapshot_returns_correct_index(self):
        coord = _make_coordinator(doors=[SAMPLE_DOOR])
        snap = EvonDoorbellSnapshot(coord, "Security.Door1", "Front Door", 1, _make_entry())
        result = snap._get_snapshot()
        assert result["path"] == "/images/snap2.jpg"

    def test_get_snapshot_returns_none_for_missing_door(self):
        coord = _make_coordinator(doors=[])
        snap = EvonDoorbellSnapshot(coord, "Security.Door1", "Front Door", 0, _make_entry())
        assert snap._get_snapshot() is None

    @pytest.mark.asyncio
    async def test_async_image_returns_bytes(self):
        coord = _make_coordinator(doors=[SAMPLE_DOOR])
        snap = EvonDoorbellSnapshot(coord, "Security.Door1", "Front Door", 0, _make_entry())
        image = await snap.async_image()
        assert image is not None
        coord.api.fetch_image.assert_awaited_once_with("/images/snap1.jpg")

    @pytest.mark.asyncio
    async def test_async_image_caches_on_same_path(self):
        coord = _make_coordinator(doors=[SAMPLE_DOOR])
        snap = EvonDoorbellSnapshot(coord, "Security.Door1", "Front Door", 0, _make_entry())
        await snap.async_image()
        await snap.async_image()
        # Second call should use cache, only one fetch
        assert coord.api.fetch_image.await_count == 1

    @pytest.mark.asyncio
    async def test_async_image_returns_none_when_no_snapshot(self):
        coord = _make_coordinator(doors=[SAMPLE_DOOR])
        snap = EvonDoorbellSnapshot(coord, "Security.Door1", "Front Door", 5, _make_entry())
        assert await snap.async_image() is None

    @pytest.mark.asyncio
    async def test_async_image_returns_none_when_no_path(self):
        door = {
            "id": "Security.Door1",
            "name": "Front Door",
            "saved_pictures": [{"timestamp": 123}],
        }
        coord = _make_coordinator(doors=[door])
        snap = EvonDoorbellSnapshot(coord, "Security.Door1", "Front Door", 0, _make_entry())
        assert await snap.async_image() is None

    @pytest.mark.asyncio
    async def test_async_image_returns_none_on_fetch_failure(self):
        coord = _make_coordinator(doors=[SAMPLE_DOOR])
        coord.api.fetch_image = AsyncMock(return_value=None)
        snap = EvonDoorbellSnapshot(coord, "Security.Door1", "Front Door", 0, _make_entry())
        assert await snap.async_image() is None

    def test_handle_coordinator_update_invalidates_cache_on_path_change(self):
        coord = _make_coordinator(doors=[SAMPLE_DOOR])
        snap = EvonDoorbellSnapshot(coord, "Security.Door1", "Front Door", 0, _make_entry())
        snap.async_write_ha_state = MagicMock()
        snap._cached_path = "/images/old.jpg"
        snap._cached_image = b"old"
        snap._handle_coordinator_update()
        # Path changed: cache invalidated
        assert snap._cached_image is None
        assert snap._cached_path is None

    def test_handle_coordinator_update_keeps_cache_on_same_path(self):
        coord = _make_coordinator(doors=[SAMPLE_DOOR])
        snap = EvonDoorbellSnapshot(coord, "Security.Door1", "Front Door", 0, _make_entry())
        snap.async_write_ha_state = MagicMock()
        snap._cached_path = "/images/snap1.jpg"
        snap._cached_image = b"cached"
        snap._handle_coordinator_update()
        # Path unchanged: cache preserved
        assert snap._cached_image == b"cached"

    def test_device_info(self):
        coord = _make_coordinator(doors=[SAMPLE_DOOR])
        entry = _make_entry()
        snap = EvonDoorbellSnapshot(coord, "Security.Door1", "Front Door", 0, entry)
        info = snap.device_info
        assert info is not None

    def test_max_snapshots_constant(self):
        assert MAX_SNAPSHOTS == 10


# =============================================================================
# Integration tests (require pytest-homeassistant-custom-component)
# =============================================================================


@requires_ha_test_framework
@pytest.mark.asyncio
async def test_image_setup(hass, mock_config_entry_v2, mock_evon_api_class):
    """Test image entities are created for doorbell snapshots."""
    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    # First snapshot entity should exist
    state = hass.states.get("image.front_door_snapshots_snapshot_1")
    assert state is not None


@requires_ha_test_framework
@pytest.mark.asyncio
async def test_image_multiple_snapshots(hass, mock_config_entry_v2, mock_evon_api_class):
    """Test multiple snapshot entities are created."""
    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    # Should have 10 snapshot entities per door (MAX_SNAPSHOTS)
    for i in range(1, 11):
        state = hass.states.get(f"image.front_door_snapshots_snapshot_{i}")
        assert state is not None, f"Snapshot {i} should exist"


@requires_ha_test_framework
@pytest.mark.asyncio
async def test_image_unique_id(hass, mock_config_entry_v2, mock_evon_api_class):
    """Test image has unique ID."""
    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    from homeassistant.helpers import entity_registry as er

    entity_registry = er.async_get(hass)
    entry = entity_registry.async_get("image.front_door_snapshots_snapshot_1")
    assert entry is not None
    assert entry.unique_id == "evon_snapshot_security_door_1_0"


@requires_ha_test_framework
@pytest.mark.asyncio
async def test_image_attributes(hass, mock_config_entry_v2, mock_evon_api_class):
    """Test image extra state attributes."""
    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("image.front_door_snapshots_snapshot_1")
    assert state is not None
    # Should have index and door_id attributes
    assert state.attributes.get("index") == 0
    assert state.attributes.get("door_id") == "security_door_1"
