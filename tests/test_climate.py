"""Integration tests for Evon climate platform."""

from __future__ import annotations

import pytest

from tests.conftest import requires_ha_test_framework

pytestmark = requires_ha_test_framework


@pytest.mark.asyncio
async def test_climate_setup(hass, mock_config_entry_v2, mock_evon_api_class):
    """Test climate platform setup creates entities."""
    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    # Check that climate entity was created
    state = hass.states.get("climate.living_room_climate")
    assert state is not None
    assert state.attributes.get("current_temperature") == 21.5
    assert state.attributes.get("temperature") == 22.0


@pytest.mark.asyncio
async def test_climate_set_temperature(hass, mock_config_entry_v2, mock_evon_api_class):
    """Test setting climate target temperature."""
    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        "climate",
        "set_temperature",
        {"entity_id": "climate.living_room_climate", "temperature": 23.0},
        blocking=True,
    )

    mock_evon_api_class.set_climate_temperature.assert_called_once_with("climate_1", 23.0)


@pytest.mark.asyncio
async def test_climate_set_preset_comfort(hass, mock_config_entry_v2, mock_evon_api_class):
    """Test setting comfort preset mode."""
    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        "climate",
        "set_preset_mode",
        {"entity_id": "climate.living_room_climate", "preset_mode": "comfort"},
        blocking=True,
    )

    mock_evon_api_class.set_climate_comfort_mode.assert_called_once_with("climate_1")


@pytest.mark.asyncio
async def test_climate_set_preset_eco(hass, mock_config_entry_v2, mock_evon_api_class):
    """Test setting eco preset mode."""
    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        "climate",
        "set_preset_mode",
        {"entity_id": "climate.living_room_climate", "preset_mode": "eco"},
        blocking=True,
    )

    mock_evon_api_class.set_climate_energy_saving_mode.assert_called_once_with("climate_1")


@pytest.mark.asyncio
async def test_climate_set_preset_away(hass, mock_config_entry_v2, mock_evon_api_class):
    """Test setting away preset mode."""
    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        "climate",
        "set_preset_mode",
        {"entity_id": "climate.living_room_climate", "preset_mode": "away"},
        blocking=True,
    )

    mock_evon_api_class.set_climate_freeze_protection_mode.assert_called_once_with("climate_1")


@pytest.mark.asyncio
async def test_climate_hvac_action(hass, mock_config_entry_v2, mock_evon_api_class):
    """Test climate hvac_action shows heating when IsOn is true."""
    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("climate.living_room_climate")
    assert state is not None
    # IsOn is True in mock data, season mode is heating
    assert state.attributes.get("hvac_action") == "heating"


@pytest.mark.asyncio
async def test_climate_preset_mode(hass, mock_config_entry_v2, mock_evon_api_class):
    """Test climate preset_mode is read correctly from ModeSaved."""
    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("climate.living_room_climate")
    assert state is not None
    # ModeSaved is 4 in mock data = comfort in heating mode
    assert state.attributes.get("preset_mode") == "comfort"


@pytest.mark.asyncio
async def test_climate_min_max_temp(hass, mock_config_entry_v2, mock_evon_api_class):
    """Test climate min/max temperature limits."""
    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("climate.living_room_climate")
    assert state is not None
    assert state.attributes.get("min_temp") == 15
    assert state.attributes.get("max_temp") == 25


@pytest.mark.asyncio
async def test_climate_attributes(hass, mock_config_entry_v2, mock_evon_api_class):
    """Test climate extra state attributes."""
    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("climate.living_room_climate")
    assert state is not None

    # Check evon_id attribute
    assert state.attributes.get("evon_id") == "climate_1"

    # Check preset temperatures in attributes
    assert state.attributes.get("comfort_temperature") == 22
    assert state.attributes.get("eco_temperature") == 20
    assert state.attributes.get("protection_temperature") == 15

    # Check season mode
    assert state.attributes.get("season_mode") == "heating"


@pytest.mark.asyncio
async def test_climate_optimistic_temperature(hass, mock_config_entry_v2, mock_evon_api_class):
    """Test that optimistic temperature updates are applied immediately."""
    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    # Initial temperature
    state = hass.states.get("climate.living_room_climate")
    assert state.attributes.get("temperature") == 22.0

    # Set new temperature - optimistic update
    await hass.services.async_call(
        "climate",
        "set_temperature",
        {"entity_id": "climate.living_room_climate", "temperature": 24.0},
        blocking=True,
    )

    # State should reflect the optimistic update
    state = hass.states.get("climate.living_room_climate")
    assert state.attributes.get("temperature") == 24.0


@pytest.mark.asyncio
async def test_climate_cooling_mode_preset(hass, mock_config_entry_v2, mock_evon_api_class):
    """Test climate preset_mode is correct in cooling mode (regression test).

    This tests the fix for issue where ModeSaved 7 in cooling mode was not
    correctly mapped to "comfort" preset. In cooling mode, the mapping is:
    5=away, 6=eco, 7=comfort (vs heating: 2=away, 3=eco, 4=comfort).
    """
    from tests.conftest import MOCK_INSTANCE_DETAILS

    # Set season mode to cooling
    mock_evon_api_class.get_season_mode.return_value = True  # True = cooling mode

    # Update climate mock data for cooling mode
    MOCK_INSTANCE_DETAILS["climate_1"]["ModeSaved"] = 7  # Comfort in cooling mode
    MOCK_INSTANCE_DETAILS["climate_1"]["CoolingMode"] = True

    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("climate.living_room_climate")
    assert state is not None

    # ModeSaved 7 in cooling mode should map to "comfort"
    assert state.attributes.get("preset_mode") == "comfort"
    # Season mode should be cooling
    assert state.attributes.get("season_mode") == "cooling"
    # When IsOn is True and in cooling mode, hvac_action should be "cooling"
    assert state.attributes.get("hvac_action") == "cooling"

    # Reset mock data for other tests
    MOCK_INSTANCE_DETAILS["climate_1"]["ModeSaved"] = 4
    MOCK_INSTANCE_DETAILS["climate_1"]["CoolingMode"] = False
