"""Integration tests for Evon switch platform."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

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

    # SwitchOneTime is used for explicit turn on
    mock_evon_api_class.turn_on_bathroom_radiator.assert_called_once_with("bathroom_radiator_1")


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

    # Switch (toggle) is used for turn off when radiator is on
    mock_evon_api_class.turn_off_bathroom_radiator.assert_called_once_with("bathroom_radiator_1")


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


@pytest.mark.asyncio
async def test_bathroom_radiator_double_toggle_guard(hass, mock_config_entry_v2, mock_evon_api_class):
    """Test that calling turn_off twice doesn't send a second toggle.

    The radiator uses Switch() (toggle) for turn_off. If the user taps off
    twice quickly, the second toggle would turn it back ON. The optimistic
    state guard should prevent this.
    """
    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    # First turn_off - should call the API
    await hass.services.async_call(
        "switch",
        "turn_off",
        {"entity_id": "switch.bathroom_radiator"},
        blocking=True,
    )
    mock_evon_api_class.turn_off_bathroom_radiator.assert_called_once()

    # Second turn_off - should be blocked by optimistic guard
    mock_evon_api_class.turn_off_bathroom_radiator.reset_mock()
    await hass.services.async_call(
        "switch",
        "turn_off",
        {"entity_id": "switch.bathroom_radiator"},
        blocking=True,
    )
    mock_evon_api_class.turn_off_bathroom_radiator.assert_not_called()


@pytest.mark.asyncio
async def test_bathroom_radiator_turn_off_skips_when_already_off(hass, mock_config_entry_v2, mock_evon_api_class):
    """Test turn_off does nothing when radiator is already off."""
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
        "turn_off",
        {"entity_id": "switch.bathroom_radiator"},
        blocking=True,
    )

    # Should not call API since radiator is already off
    mock_evon_api_class.turn_off_bathroom_radiator.assert_not_called()


# =============================================================================
# Additional Bathroom Radiator Tests
# =============================================================================


@pytest.mark.asyncio
async def test_bathroom_radiator_optimistic_on_shows_time(hass, mock_config_entry_v2, mock_evon_api_class):
    """Test that after turning on a radiator, extra_state_attributes show optimistic time_remaining_mins."""
    # Start with radiator off
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

    state = hass.states.get("switch.bathroom_radiator")
    assert state is not None
    # Optimistic time_remaining_mins should equal duration_mins (30)
    assert state.attributes.get("time_remaining_mins") == 30


@pytest.mark.asyncio
async def test_bathroom_radiator_api_error_resets_state(hass, mock_config_entry_v2, mock_evon_api_class):
    """Test that when turn_on_bathroom_radiator raises EvonApiError, optimistic state is cleared."""
    from custom_components.evon.api import EvonApiError

    # Start with radiator off
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

    # Make turn_on_bathroom_radiator raise an error
    mock_evon_api_class.turn_on_bathroom_radiator = AsyncMock(side_effect=EvonApiError("API error"))

    with pytest.raises(EvonApiError):
        await hass.services.async_call(
            "switch",
            "turn_on",
            {"entity_id": "switch.bathroom_radiator"},
            blocking=True,
        )

    # After error, state should revert to original "off" (optimistic cleared)
    state = hass.states.get("switch.bathroom_radiator")
    assert state.state == "off"


# =============================================================================
# Post-Command Recheck Tests (EvonSwitch)
# =============================================================================


class TestSwitchPostCommandRecheck:
    """Test that EvonSwitch commands schedule a deferred recheck instead of immediate refresh.

    These tests directly instantiate EvonSwitch because process_switches() returns []
    (no real Evon switch class exists yet) so no switch entities appear in the HA
    integration setup.  Direct instantiation lets us test the entity logic without
    needing the full HA service layer.
    """

    @pytest.fixture
    def switch_entity(self, hass, mock_config_entry_v2, mock_evon_api_class):
        """Create an EvonSwitch with a wired-up mock coordinator."""
        from unittest.mock import MagicMock

        from custom_components.evon.switch import EvonSwitch

        coordinator = MagicMock()
        coordinator.async_request_refresh = AsyncMock()
        coordinator.data = {
            "switches": [{"id": "switch_1", "name": "Test Switch", "is_on": False}]
        }
        coordinator.get_entity_data = MagicMock(
            return_value={"id": "switch_1", "name": "Test Switch", "is_on": False}
        )

        entry = mock_config_entry_v2
        api = mock_evon_api_class

        switch = EvonSwitch(coordinator, "switch_1", "Test Switch", "Living Room", entry, api)
        switch.hass = hass
        switch.entity_id = "switch.test_switch"
        # Bypass state writing: entity is not registered in the state machine
        switch.async_write_ha_state = MagicMock()
        return switch

    @pytest.mark.asyncio
    async def test_turn_on_schedules_recheck_not_immediate_refresh(
        self, switch_entity, mock_evon_api_class
    ):
        """turn_on schedules a recheck; does not fire immediate HTTP poll."""
        from custom_components.evon.const import POST_COMMAND_QUIESCE_PERIOD

        switch = switch_entity
        switch.coordinator.async_request_refresh = AsyncMock()

        with patch("custom_components.evon.base_entity.async_call_later") as mock_schedule:
            await switch.async_turn_on()

        # No immediate refresh
        switch.coordinator.async_request_refresh.assert_not_called()
        # One recheck scheduled with the correct quiesce delay
        mock_schedule.assert_called_once()
        assert mock_schedule.call_args[0][1] == POST_COMMAND_QUIESCE_PERIOD

    @pytest.mark.asyncio
    async def test_turn_off_schedules_recheck_not_immediate_refresh(
        self, switch_entity, mock_evon_api_class
    ):
        """turn_off schedules a recheck; does not fire immediate HTTP poll."""
        from custom_components.evon.const import POST_COMMAND_QUIESCE_PERIOD

        switch = switch_entity
        switch.coordinator.async_request_refresh = AsyncMock()

        with patch("custom_components.evon.base_entity.async_call_later") as mock_schedule:
            await switch.async_turn_off()

        # No immediate refresh
        switch.coordinator.async_request_refresh.assert_not_called()
        # One recheck scheduled with the correct quiesce delay
        mock_schedule.assert_called_once()
        assert mock_schedule.call_args[0][1] == POST_COMMAND_QUIESCE_PERIOD


# =============================================================================
# Post-Command Recheck Tests (EvonBathroomRadiatorSwitch)
# =============================================================================


class TestRadiatorPostCommandRecheck:
    """Test that EvonBathroomRadiatorSwitch commands schedule a deferred recheck.

    These tests directly instantiate EvonBathroomRadiatorSwitch to verify that
    both turn_on and turn_off call _schedule_post_command_recheck (via
    async_call_later) instead of triggering an immediate coordinator refresh.
    """

    @pytest.fixture
    def radiator_entity(self, hass, mock_config_entry_v2, mock_evon_api_class):
        """Create an EvonBathroomRadiatorSwitch with a wired-up mock coordinator."""
        from unittest.mock import MagicMock

        from custom_components.evon.switch import EvonBathroomRadiatorSwitch

        coordinator = MagicMock()
        coordinator.async_request_refresh = AsyncMock()
        coordinator.data = {
            "bathroom_radiators": [
                {
                    "id": "radiator_1",
                    "name": "Test Radiator",
                    "is_on": False,
                    "duration_mins": 30,
                    "time_remaining": -1,
                }
            ]
        }
        coordinator.get_entity_data = MagicMock(
            return_value={
                "id": "radiator_1",
                "name": "Test Radiator",
                "is_on": False,
                "duration_mins": 30,
                "time_remaining": -1,
            }
        )

        entry = mock_config_entry_v2
        api = mock_evon_api_class

        radiator = EvonBathroomRadiatorSwitch(
            coordinator, "radiator_1", "Test Radiator", "Bathroom", entry, api
        )
        radiator.hass = hass
        radiator.entity_id = "switch.test_radiator"
        # Bypass state writing: entity is not registered in the state machine
        radiator.async_write_ha_state = MagicMock()
        return radiator

    @pytest.mark.asyncio
    async def test_turn_on_schedules_recheck(self, radiator_entity, mock_evon_api_class):
        """turn_on schedules a recheck; does not fire immediate HTTP poll."""
        from custom_components.evon.const import POST_COMMAND_QUIESCE_PERIOD

        radiator = radiator_entity
        radiator.coordinator.async_request_refresh = AsyncMock()

        with patch("custom_components.evon.base_entity.async_call_later") as mock_schedule:
            await radiator.async_turn_on()

        # No immediate refresh
        radiator.coordinator.async_request_refresh.assert_not_called()
        # One recheck scheduled with the correct quiesce delay
        mock_schedule.assert_called_once()
        assert mock_schedule.call_args[0][1] == POST_COMMAND_QUIESCE_PERIOD

    @pytest.mark.asyncio
    async def test_turn_off_schedules_single_recheck(self, radiator_entity, mock_evon_api_class):
        """turn_off schedules exactly one recheck (not an immediate refresh + 3s verify)."""
        from unittest.mock import MagicMock

        from custom_components.evon.const import POST_COMMAND_QUIESCE_PERIOD

        # Radiator must be on so turn_off doesn't exit early
        radiator = radiator_entity
        radiator.coordinator.get_entity_data = MagicMock(
            return_value={
                "id": "radiator_1",
                "name": "Test Radiator",
                "is_on": True,
                "duration_mins": 30,
                "time_remaining": 25.0,
            }
        )
        radiator.coordinator.async_request_refresh = AsyncMock()

        with patch("custom_components.evon.base_entity.async_call_later") as mock_schedule:
            await radiator.async_turn_off()

        # No immediate refresh
        radiator.coordinator.async_request_refresh.assert_not_called()
        # Exactly one recheck scheduled (old code also had 3s verify = two calls total)
        mock_schedule.assert_called_once()
        assert mock_schedule.call_args[0][1] == POST_COMMAND_QUIESCE_PERIOD
