"""Integration tests for Evon binary sensor platform."""

from __future__ import annotations

import pytest

from tests.conftest import requires_ha_test_framework

pytestmark = requires_ha_test_framework


@pytest.mark.asyncio
async def test_valve_binary_sensor_setup(hass, mock_config_entry_v2, mock_evon_api_class):
    """Test valve binary sensor is created."""
    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    # Valve binary sensor should exist
    state = hass.states.get("binary_sensor.living_room_valve")
    assert state is not None
    assert state.state == "on"  # ActValue is True in mock data
    assert state.attributes.get("device_class") == "opening"


@pytest.mark.asyncio
async def test_valve_binary_sensor_closed(hass, mock_config_entry_v2, mock_evon_api_class):
    """Test valve binary sensor shows closed state."""
    from tests.conftest import MOCK_INSTANCE_DETAILS

    # Create a modified copy of instance details with closed valve
    modified_details = {**MOCK_INSTANCE_DETAILS, "valve_1": {"ActValue": False}}

    # Override get_instance to return closed valve
    mock_evon_api_class.get_instance.side_effect = lambda instance_id: modified_details.get(
        instance_id, {}
    )

    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.living_room_valve")
    assert state is not None
    assert state.state == "off"  # Valve is closed
