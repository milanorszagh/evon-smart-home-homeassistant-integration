"""Integration tests for Evon select platform."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.conftest import requires_ha_test_framework

pytestmark = requires_ha_test_framework


@pytest.mark.asyncio
async def test_home_state_select_setup(hass, mock_config_entry_v2, mock_evon_api_class):
    """Test home state select entity is created."""
    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("select.evon_home_state_home_state")
    assert state is not None
    # HomeStateAtHome is active in mock data
    assert state.state == "HomeStateAtHome"

    # Check options include all home states
    options = state.attributes.get("options", [])
    assert "HomeStateAtHome" in options
    assert "HomeStateNight" in options
    assert "HomeStateWork" in options
    assert "HomeStateHoliday" in options


@pytest.mark.asyncio
async def test_home_state_select_option(hass, mock_config_entry_v2, mock_evon_api_class):
    """Test selecting a home state."""
    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": "select.evon_home_state_home_state", "option": "HomeStateNight"},
        blocking=True,
    )

    mock_evon_api_class.activate_home_state.assert_called_once_with("HomeStateNight")


@pytest.mark.asyncio
async def test_home_state_optimistic_update(hass, mock_config_entry_v2, mock_evon_api_class):
    """Test home state optimistic update."""
    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    # Initial state
    state = hass.states.get("select.evon_home_state_home_state")
    assert state.state == "HomeStateAtHome"

    # Select new option - optimistic update
    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": "select.evon_home_state_home_state", "option": "HomeStateWork"},
        blocking=True,
    )

    # State should reflect the optimistic update
    state = hass.states.get("select.evon_home_state_home_state")
    assert state.state == "HomeStateWork"


@pytest.mark.asyncio
async def test_season_mode_select_setup(hass, mock_config_entry_v2, mock_evon_api_class):
    """Test season mode select entity is created."""
    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("select.evon_season_mode_season_mode")
    assert state is not None
    # IsCool is False in mock data = heating mode
    assert state.state == "heating"

    # Check options
    options = state.attributes.get("options", [])
    assert "heating" in options
    assert "cooling" in options


@pytest.mark.asyncio
async def test_season_mode_select_heating(hass, mock_config_entry_v2, mock_evon_api_class):
    """Test selecting heating mode."""
    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": "select.evon_season_mode_season_mode", "option": "heating"},
        blocking=True,
    )

    # heating = IsCool False
    mock_evon_api_class.set_season_mode.assert_called_once_with(False)


@pytest.mark.asyncio
async def test_season_mode_select_cooling(hass, mock_config_entry_v2, mock_evon_api_class):
    """Test selecting cooling mode."""
    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": "select.evon_season_mode_season_mode", "option": "cooling"},
        blocking=True,
    )

    # cooling = IsCool True
    mock_evon_api_class.set_season_mode.assert_called_once_with(True)


@pytest.mark.asyncio
async def test_season_mode_optimistic_update(hass, mock_config_entry_v2, mock_evon_api_class):
    """Test season mode optimistic update."""
    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    # Initial state
    state = hass.states.get("select.evon_season_mode_season_mode")
    assert state.state == "heating"

    # Select cooling - optimistic update
    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": "select.evon_season_mode_season_mode", "option": "cooling"},
        blocking=True,
    )

    # State should reflect the optimistic update
    state = hass.states.get("select.evon_season_mode_season_mode")
    assert state.state == "cooling"


class TestSelectPostCommandRecheck:
    """Test that EvonHomeStateSelect and EvonSeasonModeSelect schedule a deferred recheck."""

    @pytest.fixture
    def home_state_entity(self, hass, mock_config_entry_v2, mock_evon_api_class):
        """Create an EvonHomeStateSelect with a wired-up mock coordinator."""
        from custom_components.evon.select import EvonHomeStateSelect

        coordinator = MagicMock()
        coordinator.async_request_refresh = AsyncMock()
        coordinator.get_home_states = MagicMock(
            return_value=[
                {"id": "HomeStateAtHome"},
                {"id": "HomeStateNight"},
                {"id": "HomeStateWork"},
                {"id": "HomeStateHoliday"},
            ]
        )
        coordinator.get_active_home_state = MagicMock(return_value="HomeStateAtHome")

        entry = mock_config_entry_v2
        api = mock_evon_api_class

        entity = EvonHomeStateSelect(coordinator, entry, api)
        entity.hass = hass
        entity.entity_id = "select.evon_home_state"
        entity.async_write_ha_state = MagicMock()
        return entity

    @pytest.fixture
    def season_mode_entity(self, hass, mock_config_entry_v2, mock_evon_api_class):
        """Create an EvonSeasonModeSelect with a wired-up mock coordinator."""
        from custom_components.evon.select import EvonSeasonModeSelect

        coordinator = MagicMock()
        coordinator.async_request_refresh = AsyncMock()
        coordinator.get_season_mode = MagicMock(return_value=False)

        entry = mock_config_entry_v2
        api = mock_evon_api_class

        entity = EvonSeasonModeSelect(coordinator, entry, api)
        entity.hass = hass
        entity.entity_id = "select.evon_season_mode"
        entity.async_write_ha_state = MagicMock()
        return entity

    @pytest.mark.asyncio
    async def test_home_state_select_schedules_recheck(self, home_state_entity, mock_evon_api_class):
        """async_select_option schedules a recheck; does not fire immediate HTTP poll."""
        from custom_components.evon.const import POST_COMMAND_QUIESCE_PERIOD

        entity = home_state_entity
        entity.coordinator.async_request_refresh = AsyncMock()

        with patch("custom_components.evon.base_entity.async_call_later") as mock_schedule:
            await entity.async_select_option("HomeStateNight")

        # No immediate refresh
        entity.coordinator.async_request_refresh.assert_not_called()
        # One recheck scheduled with the correct quiesce delay
        mock_schedule.assert_called_once()
        assert mock_schedule.call_args[0][1] == POST_COMMAND_QUIESCE_PERIOD

    @pytest.mark.asyncio
    async def test_season_mode_select_schedules_recheck(self, season_mode_entity, mock_evon_api_class):
        """async_select_option schedules a recheck; does not fire immediate HTTP poll."""
        from custom_components.evon.const import POST_COMMAND_QUIESCE_PERIOD

        entity = season_mode_entity
        entity.coordinator.async_request_refresh = AsyncMock()

        with patch("custom_components.evon.base_entity.async_call_later") as mock_schedule:
            await entity.async_select_option("cooling")

        # No immediate refresh
        entity.coordinator.async_request_refresh.assert_not_called()
        # One recheck scheduled with the correct quiesce delay
        mock_schedule.assert_called_once()
        assert mock_schedule.call_args[0][1] == POST_COMMAND_QUIESCE_PERIOD
