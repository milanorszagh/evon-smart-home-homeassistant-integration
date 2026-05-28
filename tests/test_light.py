"""Integration tests for Evon light platform."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

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
async def test_light_brightness_minimum_clamp(hass, mock_config_entry_v2, mock_evon_api_class):
    """Test that brightness=1 (HA min) maps to 1% on Evon, not 0%."""
    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    # Set brightness to 1 (HA minimum non-zero brightness)
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": "light.living_room_light", "brightness": 1},
        blocking=True,
    )

    # round(1 * 100 / 255) = round(0.392) = 0, but we clamp to min 1
    mock_evon_api_class.set_light_brightness.assert_called_once_with("light_1", 1)


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


@pytest.mark.asyncio
async def test_rgbw_light_setup(hass, mock_config_entry_v2, mock_evon_api_class):
    """Test that RGBW light entity is created with color_temp support."""
    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("light.rgbw_light")
    assert state is not None
    assert state.state == "on"
    assert state.attributes.get("brightness") == 255  # 100% of 255
    assert state.attributes.get("color_mode") == "color_temp"


@pytest.mark.asyncio
async def test_rgbw_light_set_color_temp(hass, mock_config_entry_v2, mock_evon_api_class):
    """Test setting color temperature on RGBW light."""
    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": "light.rgbw_light", "color_temp_kelvin": 3000},
        blocking=True,
    )

    mock_evon_api_class.set_light_color_temp.assert_called_once_with("rgbw_light_1", 3000)


@pytest.mark.asyncio
async def test_rgbw_light_color_temp_value(hass, mock_config_entry_v2, mock_evon_api_class):
    """Check that the color_temp_kelvin attribute matches the mock data (4000K)."""
    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("light.rgbw_light")
    assert state is not None
    assert state.attributes.get("color_temp_kelvin") == 4000


@pytest.mark.asyncio
async def test_rgbw_light_min_max_color_temp(hass, mock_config_entry_v2, mock_evon_api_class):
    """Check min/max color temp attributes from mock data."""
    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("light.rgbw_light")
    assert state is not None
    assert state.attributes.get("min_color_temp_kelvin") == 2700
    assert state.attributes.get("max_color_temp_kelvin") == 6500


@pytest.mark.asyncio
async def test_light_group_setup(hass, mock_config_entry_v2, mock_evon_api_class):
    """Test that light group entity is created."""
    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("light.all_living_room_lights")
    assert state is not None
    assert state.state == "on"
    # 80% of 255 = 204
    assert state.attributes.get("brightness") == 204


@pytest.mark.asyncio
async def test_light_turn_on_with_brightness(hass, mock_config_entry_v2, mock_evon_api_class):
    """Test turning on light with explicit brightness parameter."""
    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": "light.living_room_light", "brightness": 200},
        blocking=True,
    )

    # 200/255 * 100 = 78%
    mock_evon_api_class.set_light_brightness.assert_called_once_with("light_1", 78)


@pytest.mark.asyncio
async def test_light_optimistic_brightness(hass, mock_config_entry_v2, mock_evon_api_class):
    """After calling turn_on with brightness=128, state should show brightness=128 immediately."""
    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": "light.living_room_light", "brightness": 128},
        blocking=True,
    )

    state = hass.states.get("light.living_room_light")
    assert state.state == "on"
    assert state.attributes.get("brightness") == 128


@pytest.mark.asyncio
async def test_light_api_error_resets_state(hass, mock_config_entry_v2, mock_evon_api_class):
    """When turn_on_light raises EvonApiError, optimistic state should be cleared."""
    from custom_components.evon.api import EvonApiError

    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    # Make turn_on_light raise an error
    mock_evon_api_class.turn_on_light = AsyncMock(side_effect=EvonApiError("API error"))

    # Turn off first so we can test turn_on error
    await hass.services.async_call(
        "light",
        "turn_off",
        {"entity_id": "light.living_room_light"},
        blocking=True,
    )

    # Reset the turn_off mock so it doesn't interfere
    mock_evon_api_class.turn_off_light.reset_mock()

    with pytest.raises(EvonApiError):
        await hass.services.async_call(
            "light",
            "turn_on",
            {"entity_id": "light.living_room_light"},
            blocking=True,
        )

    # After error, optimistic state should be cleared, reverting to coordinator data
    state = hass.states.get("light.living_room_light")
    assert state.state == "on"  # Coordinator data has IsOn=True


@pytest.mark.asyncio
async def test_light_api_error_on_brightness(hass, mock_config_entry_v2, mock_evon_api_class):
    """When set_light_brightness raises EvonApiError during turn_on with brightness, all optimistic state should be cleared."""
    from custom_components.evon.api import EvonApiError

    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    # Make set_light_brightness raise an error
    mock_evon_api_class.set_light_brightness = AsyncMock(side_effect=EvonApiError("API error"))

    with pytest.raises(EvonApiError):
        await hass.services.async_call(
            "light",
            "turn_on",
            {"entity_id": "light.living_room_light", "brightness": 200},
            blocking=True,
        )

    # After error, optimistic state should be cleared, reverting to coordinator data
    state = hass.states.get("light.living_room_light")
    assert state.state == "on"  # Coordinator data has IsOn=True
    # Brightness should revert to coordinator value: 75% of 255 = 191
    assert state.attributes.get("brightness") == 191


@pytest.mark.asyncio
async def test_light_turn_off_optimistic(hass, mock_config_entry_v2, mock_evon_api_class):
    """After turn_off, state should show 'off' and if turned on again, should show 'on' with last brightness."""
    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    # Verify initial state is on
    state = hass.states.get("light.living_room_light")
    assert state.state == "on"

    # Turn off
    await hass.services.async_call(
        "light",
        "turn_off",
        {"entity_id": "light.living_room_light"},
        blocking=True,
    )

    state = hass.states.get("light.living_room_light")
    assert state.state == "off"

    # Turn back on
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": "light.living_room_light"},
        blocking=True,
    )

    state = hass.states.get("light.living_room_light")
    assert state.state == "on"


@pytest.mark.asyncio
async def test_dimmable_light_brightness_is_zero_when_off_via_physical_switch(
    hass, mock_config_entry_v2, mock_evon_api_class
):
    """When a dimmable light is turned off via physical switch or evon app, brightness
    should report 0, not the stale ScaledBrightness value.

    Physical switches and the evon app send IsOn=False via WS but do NOT reset
    ScaledBrightness. Without this fix the entity returns the stale brightness
    (e.g. 191 for 75%) while already reporting state=off.
    """
    from custom_components.evon.const import DOMAIN

    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    # Precondition: light is on with 75% brightness
    state = hass.states.get("light.living_room_light")
    assert state.state == "on"
    assert state.attributes.get("brightness") == 191  # 75% of 255

    # Simulate physical switch turning off: WS sends IsOn=False
    # ScaledBrightness is NOT sent (physical switches don't reset it)
    coordinator = hass.data[DOMAIN][mock_config_entry_v2.entry_id]["coordinator"]
    coordinator._handle_ws_values_changed("light_1", {"IsOn": False})
    await hass.async_block_till_done()

    state = hass.states.get("light.living_room_light")
    assert state.state == "off"
    assert state.attributes.get("brightness") == 0


@pytest.mark.asyncio
async def test_light_brightness_pct_attribute(hass, mock_config_entry_v2, mock_evon_api_class):
    """Check the brightness_pct extra attribute matches the Evon native percentage."""
    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("light.living_room_light")
    assert state is not None
    # light_1 has ScaledBrightness=75 in MOCK_INSTANCE_DETAILS
    assert state.attributes.get("brightness_pct") == 75


# =============================================================================
# On/Off Light (SmartCOM.Light.Light relay) Tests
# =============================================================================


@pytest.mark.asyncio
async def test_onoff_light_setup(hass, mock_config_entry_v2, mock_evon_api_class):
    """Test that SmartCOM.Light.Light is created as a light entity with ColorMode.ONOFF."""
    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("light.kitchen_relay")
    assert state is not None
    # IsOn=False in mock data → state should be "off"
    assert state.state == "off"
    assert state.attributes.get("color_mode") is None  # off lights don't report color_mode
    assert "onoff" in state.attributes.get("supported_color_modes", [])
    assert state.attributes.get("brightness") is None


@pytest.mark.asyncio
async def test_onoff_light_turn_on(hass, mock_config_entry_v2, mock_evon_api_class):
    """Test turning on an on/off light uses turn_on_light API."""
    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": "light.kitchen_relay"},
        blocking=True,
    )

    mock_evon_api_class.turn_on_light.assert_any_call("light_2")


@pytest.mark.asyncio
async def test_onoff_light_turn_off(hass, mock_config_entry_v2, mock_evon_api_class):
    """Test turning off an on/off light uses turn_off_light API."""
    from tests.conftest import MOCK_INSTANCE_DETAILS

    mock_instance_details = MOCK_INSTANCE_DETAILS.copy()
    mock_instance_details["light_2"] = {"IsOn": True, "ScaledBrightness": 0}
    mock_evon_api_class.get_instance = AsyncMock(
        side_effect=lambda instance_id: mock_instance_details.get(instance_id, {})
    )

    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        "light",
        "turn_off",
        {"entity_id": "light.kitchen_relay"},
        blocking=True,
    )

    mock_evon_api_class.turn_off_light.assert_any_call("light_2")


@pytest.mark.asyncio
async def test_onoff_light_no_brightness(hass, mock_config_entry_v2, mock_evon_api_class):
    """Test that on/off light does not report brightness even when on."""
    from tests.conftest import MOCK_INSTANCE_DETAILS

    mock_instance_details = MOCK_INSTANCE_DETAILS.copy()
    mock_instance_details["light_2"] = {"IsOn": True, "ScaledBrightness": 0}
    mock_evon_api_class.get_instance = AsyncMock(
        side_effect=lambda instance_id: mock_instance_details.get(instance_id, {})
    )

    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("light.kitchen_relay")
    assert state is not None
    assert state.state == "on"
    assert state.attributes.get("brightness") is None
    assert state.attributes.get("color_mode") == "onoff"


@pytest.mark.asyncio
async def test_onoff_light_attributes(hass, mock_config_entry_v2, mock_evon_api_class):
    """Test on/off light attributes include evon_id."""
    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("light.kitchen_relay")
    assert state is not None
    assert state.attributes.get("evon_id") == "light_2"


# =============================================================================
# Post-Command Recheck Tests
# =============================================================================


class TestLightPostCommandRecheck:
    """Test that light commands schedule a deferred recheck instead of immediate refresh."""

    @pytest.mark.asyncio
    async def test_turn_off_schedules_recheck_not_immediate_refresh(
        self, hass, mock_config_entry_v2, mock_evon_api_class
    ):
        """turn_off schedules a recheck; does not fire immediate HTTP poll."""
        from custom_components.evon.const import DOMAIN, POST_COMMAND_QUIESCE_PERIOD

        mock_config_entry_v2.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
        await hass.async_block_till_done()

        coordinator = hass.data[DOMAIN][mock_config_entry_v2.entry_id]["coordinator"]
        coordinator.async_request_refresh = AsyncMock()

        with patch("custom_components.evon.base_entity.async_call_later") as mock_schedule:
            await hass.services.async_call(
                "light",
                "turn_off",
                {"entity_id": "light.living_room_light"},
                blocking=True,
            )

        # No immediate refresh
        coordinator.async_request_refresh.assert_not_called()
        # One recheck scheduled with the correct quiesce delay
        mock_schedule.assert_called_once()
        assert mock_schedule.call_args[0][1] == POST_COMMAND_QUIESCE_PERIOD

    @pytest.mark.asyncio
    async def test_turn_on_schedules_recheck_not_immediate_refresh(
        self, hass, mock_config_entry_v2, mock_evon_api_class
    ):
        """turn_on schedules a recheck; does not fire immediate HTTP poll."""
        from custom_components.evon.const import DOMAIN, POST_COMMAND_QUIESCE_PERIOD

        mock_config_entry_v2.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
        await hass.async_block_till_done()

        coordinator = hass.data[DOMAIN][mock_config_entry_v2.entry_id]["coordinator"]
        coordinator.async_request_refresh = AsyncMock()

        with patch("custom_components.evon.base_entity.async_call_later") as mock_schedule:
            await hass.services.async_call(
                "light",
                "turn_on",
                {"entity_id": "light.living_room_light"},
                blocking=True,
            )

        # No immediate refresh
        coordinator.async_request_refresh.assert_not_called()
        # One recheck scheduled with the correct quiesce delay
        mock_schedule.assert_called_once()
        assert mock_schedule.call_args[0][1] == POST_COMMAND_QUIESCE_PERIOD

    def test_matching_ws_during_quiesce_clears_optimistic(self):
        """If a WS event matches optimistic during the quiesce window, the comparison-clear
        runs before the early-return so the entity exits quiesce promptly instead of
        waiting for the next update outside the 5s window."""
        import time
        from unittest.mock import MagicMock

        from custom_components.evon.light import EvonLight

        coordinator = MagicMock()
        coordinator.last_update_success = True
        # Initial coordinator data: light off
        data_dict = {"id": "light_1", "is_on": False, "brightness": 0}
        coordinator.get_entity_data = MagicMock(return_value=data_dict)
        entry = MagicMock()
        entry.entry_id = "test_entry"

        light = EvonLight(coordinator, "light_1", "Test", "", entry, MagicMock())
        light.hass = MagicMock()
        light.async_write_ha_state = MagicMock()

        # Simulate the user turning the light ON: optimistic state set, timestamp recorded.
        light._optimistic_is_on = True
        light._optimistic_state_set_at = time.monotonic()  # well within quiesce window

        # Now a WS event arrives during quiesce with matching values (light actually on).
        coordinator.get_entity_data.return_value = {"id": "light_1", "is_on": True, "brightness": 50}

        light._handle_coordinator_update()

        # Fix #1: comparison-clear runs even during quiesce → optimistic cleared.
        assert light._optimistic_is_on is None
        assert light._optimistic_state_set_at is None

    def test_disagreeing_ws_during_quiesce_keeps_optimistic(self):
        """If a WS event disagrees with optimistic during quiesce, optimistic is preserved
        and `async_write_ha_state` is suppressed to prevent UI flicker."""
        import time
        from unittest.mock import MagicMock

        from custom_components.evon.light import EvonLight

        coordinator = MagicMock()
        coordinator.last_update_success = True
        data_dict = {"id": "light_1", "is_on": False, "brightness": 0}
        coordinator.get_entity_data = MagicMock(return_value=data_dict)
        entry = MagicMock()
        entry.entry_id = "test_entry"

        light = EvonLight(coordinator, "light_1", "Test", "", entry, MagicMock())
        light.hass = MagicMock()
        light.async_write_ha_state = MagicMock()

        # User turned light OFF; WS arrives mid-fade reporting still on, brightness=50.
        light._optimistic_is_on = False
        timestamp = time.monotonic()
        light._optimistic_state_set_at = timestamp
        coordinator.get_entity_data.return_value = {"id": "light_1", "is_on": True, "brightness": 50}

        light._handle_coordinator_update()

        # Optimistic preserved (Evon disagrees with user intent — keep the UI showing OFF).
        assert light._optimistic_is_on is False
        assert light._optimistic_state_set_at == timestamp
        # async_write_ha_state suppressed during quiesce to prevent attribute flicker.
        light.async_write_ha_state.assert_not_called()
