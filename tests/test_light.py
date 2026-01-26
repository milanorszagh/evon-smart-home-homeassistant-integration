"""Integration tests for Evon light platform."""

from __future__ import annotations

import pytest

from tests.conftest import requires_ha_test_framework

pytestmark = requires_ha_test_framework


@pytest.mark.asyncio
async def test_light_setup(hass, mock_config_entry_v2, mock_evon_api_class):
    """Test light platform setup creates entities."""
    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    # Check that dimmable light entity was created
    # Note: SmartCOM.Light.Light (non-dimmable/relay) entities are created as switches, not lights
    state = hass.states.get("light.living_room_light")
    assert state is not None
    assert state.state == "on"
    assert state.attributes.get("brightness") == 191  # 75% of 255


@pytest.mark.asyncio
async def test_light_turn_on(hass, mock_config_entry_v2, mock_evon_api_class):
    """Test turning on a light."""
    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    # Turn on the light
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": "light.living_room_light"},
        blocking=True,
    )

    mock_evon_api_class.turn_on_light.assert_called_once_with("light_1")


@pytest.mark.asyncio
async def test_light_turn_off(hass, mock_config_entry_v2, mock_evon_api_class):
    """Test turning off a light."""
    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    # Turn off the light
    await hass.services.async_call(
        "light",
        "turn_off",
        {"entity_id": "light.living_room_light"},
        blocking=True,
    )

    mock_evon_api_class.turn_off_light.assert_called_once_with("light_1")


@pytest.mark.asyncio
async def test_light_set_brightness(hass, mock_config_entry_v2, mock_evon_api_class):
    """Test setting light brightness."""
    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    # Set brightness to 50%
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": "light.living_room_light", "brightness": 128},
        blocking=True,
    )

    # 128/255 * 100 = 50%
    mock_evon_api_class.set_light_brightness.assert_called_once_with("light_1", 50)


@pytest.mark.asyncio
async def test_light_optimistic_state(hass, mock_config_entry_v2, mock_evon_api_class):
    """Test that optimistic state updates are applied immediately."""
    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    # Initial state is on
    state = hass.states.get("light.living_room_light")
    assert state.state == "on"

    # Turn off - optimistic state should update immediately
    await hass.services.async_call(
        "light",
        "turn_off",
        {"entity_id": "light.living_room_light"},
        blocking=True,
    )

    # State should reflect the optimistic update
    state = hass.states.get("light.living_room_light")
    assert state.state == "off"


@pytest.mark.asyncio
async def test_light_attributes(hass, mock_config_entry_v2, mock_evon_api_class):
    """Test light entity attributes."""
    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("light.living_room_light")
    assert state is not None

    # Check evon_id attribute
    assert state.attributes.get("evon_id") == "light_1"

    # Check color mode (brightness for dimmable lights)
    assert state.attributes.get("color_mode") == "brightness"
    assert "brightness" in state.attributes.get("supported_color_modes", [])
