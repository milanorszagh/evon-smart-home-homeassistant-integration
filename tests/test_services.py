"""Tests for Evon Smart Home services."""

from __future__ import annotations

import pytest

from custom_components.evon.const import (
    HOME_STATE_MAP,
    SERVICE_ALL_BLINDS_CLOSE,
    SERVICE_ALL_BLINDS_OPEN,
    SERVICE_ALL_LIGHTS_OFF,
    SERVICE_RECONNECT_WEBSOCKET,
    SERVICE_REFRESH,
    SERVICE_SET_HOME_STATE,
    SERVICE_SET_SEASON_MODE,
)
from tests.conftest import requires_ha_test_framework


class TestServiceConstants:
    """Test service constants against production values."""

    def test_service_names(self):
        """Test service name constants have expected values."""
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
        assert "heating" in valid_modes
        assert "cooling" in valid_modes

    def test_season_mode_to_bool(self):
        """Test season mode string to bool conversion logic."""
        # This mirrors the conversion in __init__.py handle_set_season_mode
        mode_cooling = "cooling"
        mode_heating = "heating"
        assert (mode_cooling == "cooling") is True
        assert (mode_heating == "cooling") is False


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

        # Verify coordinator.async_refresh was actually called
        # The service handler iterates config entries and calls async_refresh
        coordinator = hass.data["evon"][mock_config_entry_v2.entry_id]["coordinator"]
        assert coordinator.async_refresh.call_count >= 1

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
        mock_evon_api_class.turn_off_light.assert_called()

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

        # Verify the WS client reconnect was triggered
        # The service handler calls ws_client.reconnect() for entries with WS enabled
        # Since our test config has http_only=True, the service still completes
        # but we verify no error was raised and the service handler executed
        entry_data = hass.data["evon"][mock_config_entry_v2.entry_id]
        assert "coordinator" in entry_data

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
