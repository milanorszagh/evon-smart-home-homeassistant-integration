"""Integration tests for Evon cover (blind) platform."""

from __future__ import annotations

import pytest

from tests.conftest import requires_ha_test_framework

pytestmark = requires_ha_test_framework


@pytest.mark.asyncio
async def test_cover_setup(hass, mock_config_entry_v2, mock_evon_api_class):
    """Test cover platform setup creates entities."""
    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    # Check that cover entity was created
    state = hass.states.get("cover.living_room_blind")
    assert state is not None
    # Evon position 50 -> HA position 50 (100 - 50 = 50)
    # Evon angle 45 -> HA tilt 55 (100 - 45 = 55)
    assert state.attributes.get("current_position") == 50
    assert state.attributes.get("current_tilt_position") == 55


@pytest.mark.asyncio
async def test_cover_open(hass, mock_config_entry_v2, mock_evon_api_class):
    """Test opening a cover."""
    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        "cover",
        "open_cover",
        {"entity_id": "cover.living_room_blind"},
        blocking=True,
    )

    mock_evon_api_class.open_blind.assert_called_once_with("blind_1")


@pytest.mark.asyncio
async def test_cover_close(hass, mock_config_entry_v2, mock_evon_api_class):
    """Test closing a cover."""
    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        "cover",
        "close_cover",
        {"entity_id": "cover.living_room_blind"},
        blocking=True,
    )

    mock_evon_api_class.close_blind.assert_called_once_with("blind_1")


@pytest.mark.asyncio
async def test_cover_stop(hass, mock_config_entry_v2, mock_evon_api_class):
    """Test stopping a cover."""
    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        "cover",
        "stop_cover",
        {"entity_id": "cover.living_room_blind"},
        blocking=True,
    )

    mock_evon_api_class.stop_blind.assert_called_once_with("blind_1")


@pytest.mark.asyncio
async def test_cover_set_position(hass, mock_config_entry_v2, mock_evon_api_class):
    """Test setting cover position."""
    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    # Set position to 75% open (HA) = 25% closed (Evon)
    await hass.services.async_call(
        "cover",
        "set_cover_position",
        {"entity_id": "cover.living_room_blind", "position": 75},
        blocking=True,
    )

    # HA position 75 = Evon position 25 (inverted)
    mock_evon_api_class.set_blind_position.assert_called_once_with("blind_1", 25)


@pytest.mark.asyncio
async def test_cover_set_tilt(hass, mock_config_entry_v2, mock_evon_api_class):
    """Test setting cover tilt position."""
    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    # Set HA tilt to 60% open -> Evon angle 40 (100 - 60 = 40)
    await hass.services.async_call(
        "cover",
        "set_cover_tilt_position",
        {"entity_id": "cover.living_room_blind", "tilt_position": 60},
        blocking=True,
    )

    # HA tilt 60 = Evon angle 40 (inverted)
    mock_evon_api_class.set_blind_tilt.assert_called_once_with("blind_1", 40)


@pytest.mark.asyncio
async def test_cover_optimistic_position(hass, mock_config_entry_v2, mock_evon_api_class):
    """Test that optimistic position updates are applied immediately."""
    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    # Initial position
    state = hass.states.get("cover.living_room_blind")
    assert state.attributes.get("current_position") == 50

    # Set new position - optimistic update
    await hass.services.async_call(
        "cover",
        "set_cover_position",
        {"entity_id": "cover.living_room_blind", "position": 100},
        blocking=True,
    )

    # State should reflect the optimistic update
    state = hass.states.get("cover.living_room_blind")
    assert state.attributes.get("current_position") == 100


@pytest.mark.asyncio
async def test_cover_open_tilt(hass, mock_config_entry_v2, mock_evon_api_class):
    """Test opening cover tilt (slats horizontal)."""
    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        "cover",
        "open_cover_tilt",
        {"entity_id": "cover.living_room_blind"},
        blocking=True,
    )

    # HA open tilt (100) = Evon angle 0 (horizontal/open)
    mock_evon_api_class.set_blind_tilt.assert_called_once_with("blind_1", 0)


@pytest.mark.asyncio
async def test_cover_close_tilt(hass, mock_config_entry_v2, mock_evon_api_class):
    """Test closing cover tilt (slats blocking)."""
    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        "cover",
        "close_cover_tilt",
        {"entity_id": "cover.living_room_blind"},
        blocking=True,
    )

    # HA close tilt (0) = Evon angle 100 (closed/blocking)
    mock_evon_api_class.set_blind_tilt.assert_called_once_with("blind_1", 100)


@pytest.mark.asyncio
async def test_cover_attributes(hass, mock_config_entry_v2, mock_evon_api_class):
    """Test cover entity attributes."""
    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("cover.living_room_blind")
    assert state is not None

    # Check evon_id attribute
    assert state.attributes.get("evon_id") == "blind_1"

    # Check device class
    assert state.attributes.get("device_class") == "blind"

    # Check evon_angle attribute (raw Evon value)
    assert state.attributes.get("evon_angle") == 45
