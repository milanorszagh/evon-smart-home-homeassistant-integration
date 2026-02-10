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


@pytest.mark.asyncio
async def test_climate_set_hvac_mode_off(hass, mock_config_entry_v2, mock_evon_api_class):
    """Test setting HVAC mode to off calls freeze protection mode."""
    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {"entity_id": "climate.living_room_climate", "hvac_mode": "off"},
        blocking=True,
    )

    mock_evon_api_class.set_climate_freeze_protection_mode.assert_called_once_with("climate_1")


@pytest.mark.asyncio
async def test_climate_set_hvac_mode_heat(hass, mock_config_entry_v2, mock_evon_api_class):
    """Test setting HVAC mode to heat calls comfort mode."""
    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {"entity_id": "climate.living_room_climate", "hvac_mode": "heat"},
        blocking=True,
    )

    mock_evon_api_class.set_climate_comfort_mode.assert_called_once_with("climate_1")


@pytest.mark.asyncio
async def test_climate_temperature_clamping(hass, mock_config_entry_v2, mock_evon_api_class):
    """Test that setting temperature above max_temp gets clamped to max."""
    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    # max_temp is 25 in mock data; setting 30 should clamp to 25.0
    await hass.services.async_call(
        "climate",
        "set_temperature",
        {"entity_id": "climate.living_room_climate", "temperature": 30},
        blocking=True,
    )

    mock_evon_api_class.set_climate_temperature.assert_called_once_with("climate_1", 25.0)


@pytest.mark.asyncio
async def test_climate_temperature_clamping_below_min(hass, mock_config_entry_v2, mock_evon_api_class):
    """Test that setting temperature below min_temp gets clamped to min."""
    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    # min_temp is 15 in mock data; setting 10 should clamp to 15.0
    await hass.services.async_call(
        "climate",
        "set_temperature",
        {"entity_id": "climate.living_room_climate", "temperature": 10},
        blocking=True,
    )

    mock_evon_api_class.set_climate_temperature.assert_called_once_with("climate_1", 15.0)


@pytest.mark.asyncio
async def test_climate_hvac_modes_heating(hass, mock_config_entry_v2, mock_evon_api_class):
    """Test that hvac_modes returns [heat, off] when cooling is not enabled."""
    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("climate.living_room_climate")
    assert state is not None
    # Default mock data has DisableCooling not set (defaults to True), so cooling_enabled=False
    hvac_modes = state.attributes.get("hvac_modes")
    assert "heat" in hvac_modes
    assert "off" in hvac_modes
    assert "cool" not in hvac_modes


@pytest.mark.asyncio
async def test_climate_hvac_modes_cooling_enabled(hass, mock_config_entry_v2, mock_evon_api_class):
    """Test that hvac_modes returns [heat, cool, off] when cooling is enabled."""
    from tests.conftest import MOCK_INSTANCE_DETAILS

    # DisableCooling=False → cooling_enabled=True; CoolingMode=True → is_cooling=True
    MOCK_INSTANCE_DETAILS["climate_1"]["DisableCooling"] = False
    MOCK_INSTANCE_DETAILS["climate_1"]["CoolingMode"] = True

    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("climate.living_room_climate")
    assert state is not None
    hvac_modes = state.attributes.get("hvac_modes")
    assert "heat" in hvac_modes
    assert "cool" in hvac_modes
    assert "off" in hvac_modes

    # Reset mock data for other tests
    MOCK_INSTANCE_DETAILS["climate_1"].pop("DisableCooling", None)
    MOCK_INSTANCE_DETAILS["climate_1"]["CoolingMode"] = False


@pytest.mark.asyncio
async def test_climate_humidity(hass, mock_config_entry_v2, mock_evon_api_class):
    """Test that current_humidity returns the humidity value from mock data."""
    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("climate.living_room_climate")
    assert state is not None
    # Humidity is 45.0 in mock data, returned as int
    assert state.attributes.get("current_humidity") == 45


@pytest.mark.asyncio
async def test_climate_hvac_mode_off_when_not_on(hass, mock_config_entry_v2, mock_evon_api_class):
    """Test that hvac_mode is 'off' when IsOn is False."""
    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    # sensor_temp_1 (Bedroom Climate) has IsOn=False in mock data
    state = hass.states.get("climate.bedroom_climate")
    assert state is not None
    assert state.state == "off"


@pytest.mark.asyncio
async def test_climate_api_error_resets_optimistic_preset(hass, mock_config_entry_v2, mock_evon_api_class):
    """Test that EvonApiError during set_preset_mode resets optimistic preset."""
    from custom_components.evon.api import EvonApiError

    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    # Initial preset should be "comfort" (ModeSaved=4 in heating mode)
    state = hass.states.get("climate.living_room_climate")
    assert state.attributes.get("preset_mode") == "comfort"

    # Make the API call raise EvonApiError
    mock_evon_api_class.set_climate_comfort_mode.side_effect = EvonApiError("API error")

    with pytest.raises(EvonApiError):
        await hass.services.async_call(
            "climate",
            "set_preset_mode",
            {"entity_id": "climate.living_room_climate", "preset_mode": "comfort"},
            blocking=True,
        )

    # After error, optimistic preset should be cleared, reverting to coordinator data
    state = hass.states.get("climate.living_room_climate")
    assert state.attributes.get("preset_mode") == "comfort"

    # Reset side effect
    mock_evon_api_class.set_climate_comfort_mode.side_effect = None


@pytest.mark.asyncio
async def test_climate_api_error_resets_optimistic_temperature(hass, mock_config_entry_v2, mock_evon_api_class):
    """Test that EvonApiError during set_temperature resets optimistic temperature."""
    from custom_components.evon.api import EvonApiError

    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    # Initial temperature
    state = hass.states.get("climate.living_room_climate")
    assert state.attributes.get("temperature") == 22.0

    # Make the API call raise EvonApiError
    mock_evon_api_class.set_climate_temperature.side_effect = EvonApiError("API error")

    with pytest.raises(EvonApiError):
        await hass.services.async_call(
            "climate",
            "set_temperature",
            {"entity_id": "climate.living_room_climate", "temperature": 24.0},
            blocking=True,
        )

    # After error, optimistic temp should be cleared, reverting to coordinator data (22.0)
    state = hass.states.get("climate.living_room_climate")
    assert state.attributes.get("temperature") == 22.0

    # Reset side effect
    mock_evon_api_class.set_climate_temperature.side_effect = None


@pytest.mark.asyncio
async def test_climate_optimistic_preset(hass, mock_config_entry_v2, mock_evon_api_class):
    """Test that set_preset_mode immediately shows the new preset optimistically."""
    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    # Initial preset is "comfort" (ModeSaved=4 in heating mode)
    state = hass.states.get("climate.living_room_climate")
    assert state.attributes.get("preset_mode") == "comfort"

    # Set preset to "eco" - should be reflected immediately (optimistic update)
    await hass.services.async_call(
        "climate",
        "set_preset_mode",
        {"entity_id": "climate.living_room_climate", "preset_mode": "eco"},
        blocking=True,
    )

    # State should reflect the optimistic preset update
    state = hass.states.get("climate.living_room_climate")
    assert state.attributes.get("preset_mode") == "eco"
