"""Tests for EvonOptionsFlow handler (C-M4)."""

from __future__ import annotations

import pytest

from custom_components.evon.const import (
    CONF_BUTTON_DOUBLE_CLICK_DELAY,
    CONF_DEBUG_API,
    CONF_DEBUG_COORDINATOR,
    CONF_DEBUG_WEBSOCKET,
    CONF_HTTP_ONLY,
    CONF_MAX_RECORDING_DURATION,
    CONF_RECORDING_OUTPUT_FORMAT,
    CONF_SCAN_INTERVAL,
    CONF_SYNC_AREAS,
    DEFAULT_BUTTON_DOUBLE_CLICK_DELAY,
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
        from custom_components.evon.const import CONF_DOOR_OPEN_SECONDS, DEFAULT_DOOR_OPEN_SECONDS

        assert options.get(CONF_DOOR_OPEN_SECONDS, DEFAULT_DOOR_OPEN_SECONDS) == 2


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

        # Submit with updated options (include conditional sections if present)
        schema_keys = [str(k) for k in result["data_schema"].schema]
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
        if "buttons" in schema_keys:
            user_input["buttons"] = {
                CONF_BUTTON_DOUBLE_CLICK_DELAY: DEFAULT_BUTTON_DOUBLE_CLICK_DELAY,
            }
        if "recording" in schema_keys:
            user_input["recording"] = {
                CONF_MAX_RECORDING_DURATION: DEFAULT_MAX_RECORDING_DURATION,
                CONF_RECORDING_OUTPUT_FORMAT: RECORDING_OUTPUT_MP4,
            }

        if "doors" in [str(k) for k in result["data_schema"].schema] and "doors" not in user_input:
            user_input["doors"] = {"door_open_seconds": 2}
        if "weather" in [str(k) for k in result["data_schema"].schema] and "weather" not in user_input:
            user_input["weather"] = {}

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
    async def test_options_flow_shows_buttons_section(self, hass, mock_config_entry_v2, mock_evon_api_class):
        """Test that buttons section appears when physical buttons exist."""
        mock_config_entry_v2.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
        await hass.async_block_till_done()

        result = await hass.config_entries.options.async_init(mock_config_entry_v2.entry_id)

        assert result["type"] == "form"
        schema = result.get("data_schema")
        assert schema is not None
        schema_keys = [str(k) for k in schema.schema]
        assert "buttons" in schema_keys

    @pytest.mark.asyncio
    async def test_options_flow_shows_doors_section(self, hass, mock_config_entry_v2, mock_evon_api_class):
        """The door-opener section is offered when the system has an intercom (mock data has one)."""
        mock_config_entry_v2.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
        await hass.async_block_till_done()

        result = await hass.config_entries.options.async_init(mock_config_entry_v2.entry_id)
        assert "doors" in [str(k) for k in result["data_schema"].schema]

    @pytest.mark.asyncio
    async def test_options_flow_submit_with_doors(self, hass, mock_config_entry_v2, mock_evon_api_class):
        """The door pulse length is stored flat under door_open_seconds."""
        from custom_components.evon.const import CONF_DOOR_OPEN_SECONDS

        mock_config_entry_v2.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
        await hass.async_block_till_done()

        result = await hass.config_entries.options.async_init(mock_config_entry_v2.entry_id)
        schema_keys = [str(k) for k in result["data_schema"].schema]
        user_input = {
            CONF_SYNC_AREAS: True,
            "doors": {CONF_DOOR_OPEN_SECONDS: 5},
            "connection": {CONF_HTTP_ONLY: False, CONF_SCAN_INTERVAL: 60},
            "debug": {CONF_DEBUG_API: False, CONF_DEBUG_WEBSOCKET: False, CONF_DEBUG_COORDINATOR: False},
        }
        if "buttons" in schema_keys:
            user_input["buttons"] = {CONF_BUTTON_DOUBLE_CLICK_DELAY: DEFAULT_BUTTON_DOUBLE_CLICK_DELAY}
        if "recording" in schema_keys:
            user_input["recording"] = {
                CONF_MAX_RECORDING_DURATION: DEFAULT_MAX_RECORDING_DURATION,
                CONF_RECORDING_OUTPUT_FORMAT: RECORDING_OUTPUT_MP4,
            }

        if "doors" in [str(k) for k in result["data_schema"].schema] and "doors" not in user_input:
            user_input["doors"] = {"door_open_seconds": 2}
        if "weather" in [str(k) for k in result["data_schema"].schema] and "weather" not in user_input:
            user_input["weather"] = {}

        result2 = await hass.config_entries.options.async_configure(result["flow_id"], user_input=user_input)

        assert result2["type"] == "create_entry"
        assert result2["data"][CONF_DOOR_OPEN_SECONDS] == 5

    @pytest.mark.asyncio
    async def test_options_flow_submit_with_buttons(self, hass, mock_config_entry_v2, mock_evon_api_class):
        """Test that submitting options with buttons section includes delay in flattened data."""
        mock_config_entry_v2.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
        await hass.async_block_till_done()

        result = await hass.config_entries.options.async_init(mock_config_entry_v2.entry_id)

        user_input = {
            CONF_SYNC_AREAS: True,
            "buttons": {
                CONF_BUTTON_DOUBLE_CLICK_DELAY: 0.5,
            },
            "connection": {
                CONF_HTTP_ONLY: False,
                CONF_SCAN_INTERVAL: 60,
            },
            "debug": {
                CONF_DEBUG_API: False,
                CONF_DEBUG_WEBSOCKET: False,
                CONF_DEBUG_COORDINATOR: False,
            },
        }
        if "recording" in [str(k) for k in result["data_schema"].schema]:
            user_input["recording"] = {
                CONF_MAX_RECORDING_DURATION: DEFAULT_MAX_RECORDING_DURATION,
                CONF_RECORDING_OUTPUT_FORMAT: RECORDING_OUTPUT_MP4,
            }

        if "doors" in [str(k) for k in result["data_schema"].schema] and "doors" not in user_input:
            user_input["doors"] = {"door_open_seconds": 2}
        if "weather" in [str(k) for k in result["data_schema"].schema] and "weather" not in user_input:
            user_input["weather"] = {}

        result2 = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input=user_input,
        )

        assert result2["type"] == "create_entry"
        assert result2["data"][CONF_BUTTON_DOUBLE_CLICK_DELAY] == 0.5

    @pytest.mark.asyncio
    async def test_options_flow_preserves_defaults(self, hass, mock_config_entry_v2, mock_evon_api_class):
        """Test that options flow preserves default values."""
        mock_config_entry_v2.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
        await hass.async_block_till_done()

        result = await hass.config_entries.options.async_init(mock_config_entry_v2.entry_id)

        # Submit with the defaults (include conditional sections if present)
        schema_keys = [str(k) for k in result["data_schema"].schema]
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
        if "buttons" in schema_keys:
            user_input["buttons"] = {
                CONF_BUTTON_DOUBLE_CLICK_DELAY: DEFAULT_BUTTON_DOUBLE_CLICK_DELAY,
            }
        if "recording" in schema_keys:
            user_input["recording"] = {
                CONF_MAX_RECORDING_DURATION: DEFAULT_MAX_RECORDING_DURATION,
                CONF_RECORDING_OUTPUT_FORMAT: RECORDING_OUTPUT_MP4,
            }

        if "doors" in [str(k) for k in result["data_schema"].schema] and "doors" not in user_input:
            user_input["doors"] = {"door_open_seconds": 2}
        if "weather" in [str(k) for k in result["data_schema"].schema] and "weather" not in user_input:
            user_input["weather"] = {}

        result2 = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input=user_input,
        )

        assert result2["type"] == "create_entry"


def _minimal_options_input(schema_keys: list[str]) -> dict:
    """A valid submission for whatever sections the form rendered."""
    user_input: dict = {
        CONF_SYNC_AREAS: False,
        "connection": {CONF_HTTP_ONLY: True, CONF_SCAN_INTERVAL: 30},
        "debug": {CONF_DEBUG_API: False, CONF_DEBUG_WEBSOCKET: False, CONF_DEBUG_COORDINATOR: False},
    }
    if "buttons" in schema_keys:
        user_input["buttons"] = {CONF_BUTTON_DOUBLE_CLICK_DELAY: 0.8}
    if "recording" in schema_keys:
        user_input["recording"] = {CONF_MAX_RECORDING_DURATION: 300, CONF_RECORDING_OUTPUT_FORMAT: "mp4"}
    if "doors" in schema_keys:
        user_input["doors"] = {"door_open_seconds": 2}
    return user_input


@requires_ha_test_framework
class TestOptionsFlowHiddenSections:
    """Sections are shown only when the controller has the matching devices. Saving
    the form while a section is hidden (controller offline, device fetch failed)
    must not delete that section's stored settings, and the weather overrides must
    be clearable."""

    @pytest.mark.asyncio
    async def test_hidden_section_keeps_its_stored_options(self, hass, mock_config_entry_v2, mock_evon_api_class):
        from custom_components.evon.const import CONF_WEATHER_HOME_CONNECT_ID, CONF_WEATHER_STATION_ID

        mock_config_entry_v2.add_to_hass(hass)
        hass.config_entries.async_update_entry(
            mock_config_entry_v2,
            options={
                **mock_config_entry_v2.options,
                CONF_WEATHER_HOME_CONNECT_ID: "evonHomeConnect4939",
                CONF_WEATHER_STATION_ID: "WeatherStation1525",
            },
        )
        await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
        await hass.async_block_till_done()

        result = await hass.config_entries.options.async_init(mock_config_entry_v2.entry_id)
        schema_keys = [str(k) for k in result["data_schema"].schema]
        assert "weather" not in schema_keys  # no Home Connect proxy in the mock data

        result2 = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input=_minimal_options_input(schema_keys)
        )

        assert result2["data"][CONF_WEATHER_HOME_CONNECT_ID] == "evonHomeConnect4939"
        assert result2["data"][CONF_WEATHER_STATION_ID] == "WeatherStation1525"

    @pytest.mark.asyncio
    async def test_weather_overrides_can_be_cleared(self, hass, mock_config_entry_v2, mock_evon_api_class):
        from unittest.mock import AsyncMock

        from custom_components.evon.const import (
            CONF_WEATHER_HOME_CONNECT_ID,
            CONF_WEATHER_STATION_ID,
            EVON_CLASS_HOME_CONNECT,
        )
        from tests.conftest import MOCK_INSTANCES

        proxy = {"ID": "evonHomeConnect4939", "Name": "Allgemein", "ClassName": EVON_CLASS_HOME_CONNECT}
        mock_evon_api_class.get_instances = AsyncMock(return_value=[*MOCK_INSTANCES, proxy])
        mock_evon_api_class.get_via_home_connect = AsyncMock(return_value=None)
        mock_config_entry_v2.add_to_hass(hass)
        hass.config_entries.async_update_entry(
            mock_config_entry_v2,
            options={
                **mock_config_entry_v2.options,
                CONF_WEATHER_HOME_CONNECT_ID: "evonHomeConnect4939",
                CONF_WEATHER_STATION_ID: "WeatherStation1525",
            },
        )
        await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
        await hass.async_block_till_done()

        result = await hass.config_entries.options.async_init(mock_config_entry_v2.entry_id)
        schema_keys = [str(k) for k in result["data_schema"].schema]
        assert "weather" in schema_keys
        user_input = _minimal_options_input(schema_keys)
        user_input["weather"] = {}  # the frontend omits emptied optional text fields

        result2 = await hass.config_entries.options.async_configure(result["flow_id"], user_input=user_input)

        assert not result2["data"].get(CONF_WEATHER_HOME_CONNECT_ID)
        assert not result2["data"].get(CONF_WEATHER_STATION_ID)
