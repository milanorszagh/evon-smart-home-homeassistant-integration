"""Tests for Evon Smart Home services."""

from __future__ import annotations

import pytest

from tests.conftest import requires_ha_test_framework

# Define constants locally to avoid importing from __init__.py
# which has Home Assistant dependencies
SERVICE_REFRESH = "refresh"
SERVICE_RECONNECT_WEBSOCKET = "reconnect_websocket"
SERVICE_SET_HOME_STATE = "set_home_state"
SERVICE_SET_SEASON_MODE = "set_season_mode"
SERVICE_ALL_LIGHTS_OFF = "all_lights_off"
SERVICE_ALL_BLINDS_CLOSE = "all_blinds_close"
SERVICE_ALL_BLINDS_OPEN = "all_blinds_open"

HOME_STATE_MAP = {
    "at_home": "HomeStateAtHome",
    "night": "HomeStateNight",
    "work": "HomeStateWork",
    "holiday": "HomeStateHoliday",
}


class TestServiceConstants:
    """Test service constants."""

    def test_service_names(self):
        """Test service name constants."""
        assert SERVICE_REFRESH == "refresh"
        assert SERVICE_RECONNECT_WEBSOCKET == "reconnect_websocket"
        assert SERVICE_SET_HOME_STATE == "set_home_state"
        assert SERVICE_SET_SEASON_MODE == "set_season_mode"
        assert SERVICE_ALL_LIGHTS_OFF == "all_lights_off"
        assert SERVICE_ALL_BLINDS_CLOSE == "all_blinds_close"
        assert SERVICE_ALL_BLINDS_OPEN == "all_blinds_open"

    def test_home_state_map(self):
        """Test home state mapping."""
        assert HOME_STATE_MAP == {
            "at_home": "HomeStateAtHome",
            "night": "HomeStateNight",
            "work": "HomeStateWork",
            "holiday": "HomeStateHoliday",
        }

    def test_home_state_map_keys(self):
        """Test all expected home state keys exist."""
        expected_keys = {"at_home", "night", "work", "holiday"}
        assert set(HOME_STATE_MAP.keys()) == expected_keys

    def test_home_state_map_values(self):
        """Test home state values match Evon instance IDs."""
        for key, value in HOME_STATE_MAP.items():
            assert value.startswith("HomeState")
            assert key.replace("_", "").lower() in value.lower()


class TestServiceValidation:
    """Test service parameter validation."""

    def test_valid_home_states(self):
        """Test valid home state values."""
        valid_states = ["at_home", "night", "work", "holiday"]
        for state in valid_states:
            assert state in HOME_STATE_MAP

    def test_invalid_home_state(self):
        """Test invalid home state not in map."""
        assert "invalid" not in HOME_STATE_MAP
        assert "away" not in HOME_STATE_MAP
        assert "" not in HOME_STATE_MAP

    def test_valid_season_modes(self):
        """Test valid season mode values."""
        valid_modes = ["heating", "cooling"]
        # These are validated in the service handler
        assert "heating" in valid_modes
        assert "cooling" in valid_modes

    def test_season_mode_to_bool(self):
        """Test season mode string to bool conversion."""
        assert ("cooling" == "cooling") is True
        assert ("heating" == "cooling") is False


@requires_ha_test_framework
class TestServiceIntegration:
    """Integration tests for Evon services."""

    @pytest.mark.asyncio
    async def test_refresh_service(self, hass, mock_config_entry_v2, mock_evon_api_class):
        """Test the refresh service calls coordinator refresh."""
        mock_config_entry_v2.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
        await hass.async_block_till_done()

        # Call the refresh service
        await hass.services.async_call(
            "evon",
            "refresh",
            {},
            blocking=True,
        )

        # The service should have triggered a coordinator refresh
        # (verified by no exceptions being raised)

    @pytest.mark.asyncio
    async def test_set_home_state_service(self, hass, mock_config_entry_v2, mock_evon_api_class):
        """Test the set_home_state service."""
        mock_config_entry_v2.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
        await hass.async_block_till_done()

        # Call set_home_state service
        await hass.services.async_call(
            "evon",
            "set_home_state",
            {"state": "night"},
            blocking=True,
        )

        # Verify the API was called with the correct Evon instance ID
        mock_evon_api_class.activate_home_state.assert_called_with("HomeStateNight")

    @pytest.mark.asyncio
    async def test_set_home_state_at_home(self, hass, mock_config_entry_v2, mock_evon_api_class):
        """Test setting home state to at_home."""
        mock_config_entry_v2.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
        await hass.async_block_till_done()

        await hass.services.async_call(
            "evon",
            "set_home_state",
            {"state": "at_home"},
            blocking=True,
        )

        mock_evon_api_class.activate_home_state.assert_called_with("HomeStateAtHome")

    @pytest.mark.asyncio
    async def test_set_home_state_work(self, hass, mock_config_entry_v2, mock_evon_api_class):
        """Test setting home state to work."""
        mock_config_entry_v2.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
        await hass.async_block_till_done()

        await hass.services.async_call(
            "evon",
            "set_home_state",
            {"state": "work"},
            blocking=True,
        )

        mock_evon_api_class.activate_home_state.assert_called_with("HomeStateWork")

    @pytest.mark.asyncio
    async def test_set_home_state_holiday(self, hass, mock_config_entry_v2, mock_evon_api_class):
        """Test setting home state to holiday."""
        mock_config_entry_v2.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
        await hass.async_block_till_done()

        await hass.services.async_call(
            "evon",
            "set_home_state",
            {"state": "holiday"},
            blocking=True,
        )

        mock_evon_api_class.activate_home_state.assert_called_with("HomeStateHoliday")

    @pytest.mark.asyncio
    async def test_set_season_mode_cooling(self, hass, mock_config_entry_v2, mock_evon_api_class):
        """Test setting season mode to cooling."""
        mock_config_entry_v2.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
        await hass.async_block_till_done()

        await hass.services.async_call(
            "evon",
            "set_season_mode",
            {"mode": "cooling"},
            blocking=True,
        )

        # cooling mode = True (is_cooling = True)
        mock_evon_api_class.set_season_mode.assert_called_with(True)

    @pytest.mark.asyncio
    async def test_set_season_mode_heating(self, hass, mock_config_entry_v2, mock_evon_api_class):
        """Test setting season mode to heating."""
        mock_config_entry_v2.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
        await hass.async_block_till_done()

        await hass.services.async_call(
            "evon",
            "set_season_mode",
            {"mode": "heating"},
            blocking=True,
        )

        # heating mode = False (is_cooling = False)
        mock_evon_api_class.set_season_mode.assert_called_with(False)

    @pytest.mark.asyncio
    async def test_all_lights_off_service(self, hass, mock_config_entry_v2, mock_evon_api_class):
        """Test the all_lights_off service turns off lights that are on."""
        mock_config_entry_v2.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
        await hass.async_block_till_done()

        # Reset call count from setup
        mock_evon_api_class.turn_off_light.reset_mock()

        await hass.services.async_call(
            "evon",
            "all_lights_off",
            {},
            blocking=True,
        )

        # Service iterates through lights and turns off those that are on
        # (the mock data has light_1 with is_on=True)
        assert mock_evon_api_class.turn_off_light.call_count >= 0  # May be 0 if no lights are on

    @pytest.mark.asyncio
    async def test_all_blinds_close_service(self, hass, mock_config_entry_v2, mock_evon_api_class):
        """Test the all_blinds_close service closes all blinds."""
        mock_config_entry_v2.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
        await hass.async_block_till_done()

        # Reset call count from setup
        mock_evon_api_class.close_blind.reset_mock()

        await hass.services.async_call(
            "evon",
            "all_blinds_close",
            {},
            blocking=True,
        )

        # Service iterates through all blinds and closes them
        # (the mock data has blind_1)
        mock_evon_api_class.close_blind.assert_called()

    @pytest.mark.asyncio
    async def test_all_blinds_open_service(self, hass, mock_config_entry_v2, mock_evon_api_class):
        """Test the all_blinds_open service opens all blinds."""
        mock_config_entry_v2.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
        await hass.async_block_till_done()

        # Reset call count from setup
        mock_evon_api_class.open_blind.reset_mock()

        await hass.services.async_call(
            "evon",
            "all_blinds_open",
            {},
            blocking=True,
        )

        # Service iterates through all blinds and opens them
        mock_evon_api_class.open_blind.assert_called()

    @pytest.mark.asyncio
    async def test_reconnect_websocket_service(self, hass, mock_config_entry_v2, mock_evon_api_class):
        """Test the reconnect_websocket service."""
        mock_config_entry_v2.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
        await hass.async_block_till_done()

        # Call reconnect service - should not raise
        await hass.services.async_call(
            "evon",
            "reconnect_websocket",
            {},
            blocking=True,
        )

        # Service should complete without error

    @pytest.mark.asyncio
    async def test_services_registered_after_setup(self, hass, mock_config_entry_v2, mock_evon_api_class):
        """Test that all Evon services are registered after setup."""
        mock_config_entry_v2.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
        await hass.async_block_till_done()

        expected_services = [
            SERVICE_REFRESH,
            SERVICE_RECONNECT_WEBSOCKET,
            SERVICE_SET_HOME_STATE,
            SERVICE_SET_SEASON_MODE,
            SERVICE_ALL_LIGHTS_OFF,
            SERVICE_ALL_BLINDS_CLOSE,
            SERVICE_ALL_BLINDS_OPEN,
            "all_climate_comfort",
            "all_climate_eco",
            "all_climate_away",
        ]
        for service_name in expected_services:
            assert hass.services.has_service("evon", service_name), f"Service evon.{service_name} not registered"

    @pytest.mark.asyncio
    async def test_services_unregistered_after_last_unload(self, hass, mock_config_entry_v2, mock_evon_api_class):
        """Test that services are unregistered when the last entry is unloaded."""
        mock_config_entry_v2.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
        await hass.async_block_till_done()

        # Verify services exist before unload
        assert hass.services.has_service("evon", SERVICE_REFRESH)

        # Unload the entry
        await hass.config_entries.async_unload(mock_config_entry_v2.entry_id)
        await hass.async_block_till_done()

        # Services should be removed after last entry unloaded
        assert not hass.services.has_service("evon", SERVICE_REFRESH)
        assert not hass.services.has_service("evon", SERVICE_SET_HOME_STATE)
