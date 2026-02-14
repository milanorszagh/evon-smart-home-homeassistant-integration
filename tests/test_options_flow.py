"""Tests for _async_update_listener in __init__.py."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from tests.conftest import requires_ha_test_framework


@requires_ha_test_framework
class TestAsyncUpdateListener:
    """Integration tests for the options update listener."""

    @pytest.mark.asyncio
    async def test_options_change_triggers_reload(self, hass, mock_config_entry_v2, mock_evon_api_class):
        """Test that changing options triggers an integration reload."""
        mock_config_entry_v2.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
        await hass.async_block_till_done()

        # Verify the integration is loaded
        assert mock_config_entry_v2.entry_id in hass.data["evon"]

        # Trigger an options update (simulates user changing options in UI)
        # The update listener should call async_reload
        with patch.object(hass.config_entries, "async_reload", new_callable=AsyncMock) as mock_reload:
            hass.config_entries.async_update_entry(
                mock_config_entry_v2,
                options={**mock_config_entry_v2.options, "scan_interval": 60},
            )
            await hass.async_block_till_done()

            # The listener should have triggered a reload
            mock_reload.assert_called_once_with(mock_config_entry_v2.entry_id)

    @pytest.mark.asyncio
    async def test_debug_logging_applied_on_options_change(self, hass, mock_config_entry_v2, mock_evon_api_class):
        """Test that debug logging settings are applied immediately on options change."""
        mock_config_entry_v2.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
        await hass.async_block_till_done()

        with (
            patch("custom_components.evon._apply_debug_logging") as mock_apply_debug,
            patch.object(hass.config_entries, "async_reload", new_callable=AsyncMock),
        ):
            hass.config_entries.async_update_entry(
                mock_config_entry_v2,
                options={**mock_config_entry_v2.options, "debug_api": True},
            )
            await hass.async_block_till_done()

            # Debug logging should be applied before reload
            mock_apply_debug.assert_called_once()
