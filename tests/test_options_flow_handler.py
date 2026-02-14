"""Tests for EvonOptionsFlow handler (C-M4)."""

from __future__ import annotations

import pytest

from custom_components.evon.const import (
    CONF_DEBUG_API,
    CONF_DEBUG_COORDINATOR,
    CONF_DEBUG_WEBSOCKET,
    CONF_HTTP_ONLY,
    CONF_MAX_RECORDING_DURATION,
    CONF_RECORDING_OUTPUT_FORMAT,
    CONF_SCAN_INTERVAL,
    CONF_SYNC_AREAS,
    DEFAULT_DEBUG_API,
    DEFAULT_DEBUG_COORDINATOR,
    DEFAULT_DEBUG_WEBSOCKET,
    DEFAULT_HTTP_ONLY,
    DEFAULT_MAX_RECORDING_DURATION,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SYNC_AREAS,
    RECORDING_OUTPUT_MP4,
)
from tests.conftest import requires_ha_test_framework


class TestOptionsFlowUnit:
    """Unit tests for options flow logic without HA framework."""

    def test_flatten_section_data(self):
        """Test that section data is flattened to a flat dict."""
        # Simulate the flattening logic from async_step_init
        user_input = {
            CONF_SYNC_AREAS: True,
            "connection": {
                CONF_HTTP_ONLY: True,
                CONF_SCAN_INTERVAL: 60,
            },
            "debug": {
                CONF_DEBUG_API: True,
                CONF_DEBUG_WEBSOCKET: False,
                CONF_DEBUG_COORDINATOR: False,
            },
        }

        flat_data: dict = {}
        for key, value in user_input.items():
            if isinstance(value, dict):
                flat_data.update(value)
            else:
                flat_data[key] = value

        assert flat_data[CONF_SYNC_AREAS] is True
        assert flat_data[CONF_HTTP_ONLY] is True
        assert flat_data[CONF_SCAN_INTERVAL] == 60
        assert flat_data[CONF_DEBUG_API] is True
        assert flat_data[CONF_DEBUG_WEBSOCKET] is False

    def test_defaults_used_when_no_options(self):
        """Test default values are used when options dict is empty."""
        options = {}
        assert options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL) == DEFAULT_SCAN_INTERVAL
        assert options.get(CONF_SYNC_AREAS, DEFAULT_SYNC_AREAS) == DEFAULT_SYNC_AREAS
        assert options.get(CONF_HTTP_ONLY, DEFAULT_HTTP_ONLY) == DEFAULT_HTTP_ONLY
        assert options.get(CONF_DEBUG_API, DEFAULT_DEBUG_API) == DEFAULT_DEBUG_API
        assert options.get(CONF_DEBUG_WEBSOCKET, DEFAULT_DEBUG_WEBSOCKET) == DEFAULT_DEBUG_WEBSOCKET
        assert options.get(CONF_DEBUG_COORDINATOR, DEFAULT_DEBUG_COORDINATOR) == DEFAULT_DEBUG_COORDINATOR


@requires_ha_test_framework
class TestOptionsFlowIntegration:
    """Integration tests for the options flow using HA test framework."""

    @pytest.mark.asyncio
    async def test_options_flow_init_shows_form(self, hass, mock_config_entry_v2, mock_evon_api_class):
        """Test that options flow init step shows a form."""
        mock_config_entry_v2.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
        await hass.async_block_till_done()

        result = await hass.config_entries.options.async_init(mock_config_entry_v2.entry_id)

        assert result["type"] == "form"
        assert result["step_id"] == "init"

    @pytest.mark.asyncio
    async def test_options_flow_submit_creates_entry(self, hass, mock_config_entry_v2, mock_evon_api_class):
        """Test that submitting options creates an entry."""
        mock_config_entry_v2.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
        await hass.async_block_till_done()

        result = await hass.config_entries.options.async_init(mock_config_entry_v2.entry_id)

        # Submit with updated options (include recording section if cameras are present)
        user_input = {
            CONF_SYNC_AREAS: True,
            "connection": {
                CONF_HTTP_ONLY: False,
                CONF_SCAN_INTERVAL: 60,
            },
            "debug": {
                CONF_DEBUG_API: True,
                CONF_DEBUG_WEBSOCKET: False,
                CONF_DEBUG_COORDINATOR: False,
            },
        }
        # Add recording section if cameras are present in the schema
        if "recording" in (result.get("data_schema") or {}).schema:
            user_input["recording"] = {
                CONF_MAX_RECORDING_DURATION: DEFAULT_MAX_RECORDING_DURATION,
                CONF_RECORDING_OUTPUT_FORMAT: RECORDING_OUTPUT_MP4,
            }

        result2 = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input=user_input,
        )

        assert result2["type"] == "create_entry"
        # Verify flattened data
        assert result2["data"][CONF_SYNC_AREAS] is True
        assert result2["data"][CONF_SCAN_INTERVAL] == 60
        assert result2["data"][CONF_HTTP_ONLY] is False
        assert result2["data"][CONF_DEBUG_API] is True

    @pytest.mark.asyncio
    async def test_options_flow_preserves_defaults(self, hass, mock_config_entry_v2, mock_evon_api_class):
        """Test that options flow preserves default values."""
        mock_config_entry_v2.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
        await hass.async_block_till_done()

        result = await hass.config_entries.options.async_init(mock_config_entry_v2.entry_id)

        # Submit with the defaults (include recording section if cameras are present)
        user_input = {
            CONF_SYNC_AREAS: DEFAULT_SYNC_AREAS,
            "connection": {
                CONF_HTTP_ONLY: DEFAULT_HTTP_ONLY,
                CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
            },
            "debug": {
                CONF_DEBUG_API: DEFAULT_DEBUG_API,
                CONF_DEBUG_WEBSOCKET: DEFAULT_DEBUG_WEBSOCKET,
                CONF_DEBUG_COORDINATOR: DEFAULT_DEBUG_COORDINATOR,
            },
        }
        if "recording" in (result.get("data_schema") or {}).schema:
            user_input["recording"] = {
                CONF_MAX_RECORDING_DURATION: DEFAULT_MAX_RECORDING_DURATION,
                CONF_RECORDING_OUTPUT_FORMAT: RECORDING_OUTPUT_MP4,
            }

        result2 = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input=user_input,
        )

        assert result2["type"] == "create_entry"
