"""Tests for Evon camera platform."""

from __future__ import annotations

import pytest

from tests.conftest import requires_ha_test_framework

# Integration tests that require pytest-homeassistant-custom-component
pytestmark = requires_ha_test_framework


@pytest.mark.asyncio
async def test_camera_setup(hass, mock_config_entry_v2, mock_evon_api_class):
    """Test camera entity is created."""
    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    # Camera entity should exist
    state = hass.states.get("camera.intercom_camera")
    assert state is not None


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
