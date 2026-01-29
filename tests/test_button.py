"""Integration tests for Evon button platform (scenes)."""

from __future__ import annotations

import pytest

from tests.conftest import requires_ha_test_framework

pytestmark = requires_ha_test_framework


@pytest.mark.asyncio
async def test_scene_button_setup(hass, mock_config_entry_v2, mock_evon_api_class):
    """Test scene button is created from scene device."""
    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    # Scene button should exist
    state = hass.states.get("button.all_lights_off")
    assert state is not None


@pytest.mark.asyncio
async def test_scene_button_press(hass, mock_config_entry_v2, mock_evon_api_class):
    """Test pressing scene button calls execute_scene API."""
    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    # Press the button
    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": "button.all_lights_off"},
        blocking=True,
    )

    # Verify API was called
    mock_evon_api_class.execute_scene.assert_called_once_with("SceneApp1234")
