"""Integration tests for Evon switch platform."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from tests.conftest import MOCK_INSTANCE_DETAILS, requires_ha_test_framework

pytestmark = requires_ha_test_framework


@pytest.mark.asyncio
async def test_bathroom_radiator_setup(hass, mock_config_entry_v2, mock_evon_api_class):
    """Test bathroom radiator switch is created."""
    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("switch.bathroom_radiator")
    assert state is not None
    # Output is True in mock data
    assert state.state == "on"


@pytest.mark.asyncio
async def test_bathroom_radiator_turn_on(hass, mock_config_entry_v2, mock_evon_api_class):
    """Test turning on bathroom radiator."""
    # Modify the mock to return radiator as off initially
    mock_instance_details = MOCK_INSTANCE_DETAILS.copy()
    mock_instance_details["bathroom_radiator_1"] = {
        "Output": False,
        "NextSwitchPoint": 0,
        "EnableForMins": 30,
    }
    mock_evon_api_class.get_instance = AsyncMock(
        side_effect=lambda instance_id: mock_instance_details.get(instance_id, {})
    )

    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        "switch",
        "turn_on",
        {"entity_id": "switch.bathroom_radiator"},
        blocking=True,
    )

    mock_evon_api_class.toggle_bathroom_radiator.assert_called_once_with("bathroom_radiator_1")


@pytest.mark.asyncio
async def test_bathroom_radiator_turn_off(hass, mock_config_entry_v2, mock_evon_api_class):
    """Test turning off bathroom radiator."""
    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        "switch",
        "turn_off",
        {"entity_id": "switch.bathroom_radiator"},
        blocking=True,
    )

    mock_evon_api_class.toggle_bathroom_radiator.assert_called_once_with("bathroom_radiator_1")


@pytest.mark.asyncio
async def test_bathroom_radiator_attributes(hass, mock_config_entry_v2, mock_evon_api_class):
    """Test bathroom radiator attributes."""
    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("switch.bathroom_radiator")
    assert state is not None

    # Check evon_id attribute
    assert state.attributes.get("evon_id") == "bathroom_radiator_1"

    # Check timer attributes
    assert state.attributes.get("time_remaining_mins") == 25
    assert state.attributes.get("duration_mins") == 30
