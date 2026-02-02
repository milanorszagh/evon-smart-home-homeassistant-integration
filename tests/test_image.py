"""Tests for Evon image platform (doorbell snapshots)."""

from __future__ import annotations

import pytest

from tests.conftest import requires_ha_test_framework

# Integration tests that require pytest-homeassistant-custom-component
pytestmark = requires_ha_test_framework


@pytest.mark.asyncio
async def test_image_setup(hass, mock_config_entry_v2, mock_evon_api_class):
    """Test image entities are created for doorbell snapshots."""
    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    # First snapshot entity should exist
    state = hass.states.get("image.front_door_snapshots_snapshot_1")
    assert state is not None


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


@pytest.mark.asyncio
async def test_image_unique_id(hass, mock_config_entry_v2, mock_evon_api_class):
    """Test image has unique ID."""
    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    entity_registry = hass.helpers.entity_registry.async_get(hass)
    entry = entity_registry.async_get("image.front_door_snapshots_snapshot_1")
    assert entry is not None
    assert entry.unique_id == "evon_snapshot_security_door_1_0"


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
