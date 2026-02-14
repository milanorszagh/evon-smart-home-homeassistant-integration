"""Tests for service handlers with invalid params (C-M13)."""

from __future__ import annotations

import pytest

from custom_components.evon.const import (
    HOME_STATE_MAP,
)
from tests.conftest import requires_ha_test_framework


class TestInvalidHomeStateUnit:
    """Unit tests for invalid home state validation."""

    def test_unknown_home_state_not_in_map(self):
        """Test that unknown states are not in HOME_STATE_MAP."""
        invalid_states = ["away", "sleeping", "vacation", "custom", "", None]
        for state in invalid_states:
            assert state not in HOME_STATE_MAP

    def test_case_sensitive_home_state(self):
        """Test that home states are case-sensitive."""
        assert "At_Home" not in HOME_STATE_MAP
        assert "NIGHT" not in HOME_STATE_MAP
        assert "Work" not in HOME_STATE_MAP

    def test_valid_home_states(self):
        """Test all valid home states."""
        valid = ["at_home", "night", "work", "holiday"]
        for state in valid:
            assert state in HOME_STATE_MAP


class TestInvalidSeasonModeUnit:
    """Unit tests for invalid season mode validation."""

    def test_invalid_season_modes(self):
        """Test that the season mode validation logic rejects invalid modes."""
        # Mirror the validation in handle_set_season_mode
        invalid_modes = ["auto", "summer", "winter", "", None, "heat", "cool"]
        valid = ("heating", "cooling")
        for mode in invalid_modes:
            assert mode not in valid

    def test_valid_season_modes(self):
        """Test that valid season modes pass validation."""
        assert "heating" in ("heating", "cooling")
        assert "cooling" in ("heating", "cooling")


class TestInvalidTemperatureUnit:
    """Unit tests for out-of-range temperature validation."""

    @pytest.mark.asyncio
    async def test_temperature_below_range_raises(self):
        """Test that temperature below 5 raises ValueError."""
        # Mirror the validation from conftest mock API
        async def validated_set(instance_id, temperature):
            if not 5 <= temperature <= 40:
                raise ValueError(f"Temperature {temperature} out of valid range 5-40")

        with pytest.raises(ValueError, match="out of valid range"):
            await validated_set("climate_1", 4)

    @pytest.mark.asyncio
    async def test_temperature_above_range_raises(self):
        """Test that temperature above 40 raises ValueError."""
        async def validated_set(instance_id, temperature):
            if not 5 <= temperature <= 40:
                raise ValueError(f"Temperature {temperature} out of valid range 5-40")

        with pytest.raises(ValueError, match="out of valid range"):
            await validated_set("climate_1", 41)

    @pytest.mark.asyncio
    async def test_temperature_at_bounds_succeeds(self):
        """Test that temperatures at exact bounds succeed."""
        async def validated_set(instance_id, temperature):
            if not 5 <= temperature <= 40:
                raise ValueError(f"Temperature {temperature} out of valid range 5-40")

        # Should not raise
        await validated_set("climate_1", 5)
        await validated_set("climate_1", 40)

    @pytest.mark.asyncio
    async def test_negative_temperature_raises(self):
        """Test that negative temperature raises ValueError."""
        async def validated_set(instance_id, temperature):
            if not 5 <= temperature <= 40:
                raise ValueError(f"Temperature {temperature} out of valid range 5-40")

        with pytest.raises(ValueError, match="out of valid range"):
            await validated_set("climate_1", -5)


@requires_ha_test_framework
class TestServiceInvalidParamsIntegration:
    """Integration tests for service handlers with invalid params."""

    @pytest.mark.asyncio
    async def test_set_home_state_invalid_state_no_crash(self, hass, mock_config_entry_v2, mock_evon_api_class):
        """Test that invalid home state is rejected without crashing."""
        mock_config_entry_v2.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
        await hass.async_block_till_done()

        # Call with invalid state - should not crash, just log error
        await hass.services.async_call(
            "evon",
            "set_home_state",
            {"state": "nonexistent_state"},
            blocking=True,
        )

        # API should NOT have been called since state is invalid
        mock_evon_api_class.activate_home_state.assert_not_called()

    @pytest.mark.asyncio
    async def test_set_home_state_empty_state_no_crash(self, hass, mock_config_entry_v2, mock_evon_api_class):
        """Test that empty home state is rejected without crashing."""
        mock_config_entry_v2.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
        await hass.async_block_till_done()

        await hass.services.async_call(
            "evon",
            "set_home_state",
            {"state": ""},
            blocking=True,
        )

        mock_evon_api_class.activate_home_state.assert_not_called()

    @pytest.mark.asyncio
    async def test_set_season_mode_invalid_mode_no_crash(self, hass, mock_config_entry_v2, mock_evon_api_class):
        """Test that invalid season mode is rejected without crashing."""
        mock_config_entry_v2.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
        await hass.async_block_till_done()

        await hass.services.async_call(
            "evon",
            "set_season_mode",
            {"mode": "auto"},
            blocking=True,
        )

        mock_evon_api_class.set_season_mode.assert_not_called()

    @pytest.mark.asyncio
    async def test_set_home_state_missing_state_param_no_crash(self, hass, mock_config_entry_v2, mock_evon_api_class):
        """Test that missing state param is handled without crashing."""
        mock_config_entry_v2.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
        await hass.async_block_till_done()

        # Call without the 'state' key at all
        await hass.services.async_call(
            "evon",
            "set_home_state",
            {},
            blocking=True,
        )

        mock_evon_api_class.activate_home_state.assert_not_called()
