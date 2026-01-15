"""Tests for Evon config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.conftest import TEST_HOST, TEST_PASSWORD, TEST_USERNAME


class TestConfigFlow:
    """Test config flow."""

    @pytest.mark.asyncio
    async def test_user_form_shown(self):
        """Test that user form is shown on initial step."""
        from custom_components.evon.config_flow import EvonConfigFlow

        flow = EvonConfigFlow()
        flow.hass = MagicMock()

        result = await flow.async_step_user(user_input=None)

        assert result["type"] == "form"
        assert result["step_id"] == "user"
        assert "host" in result["data_schema"].schema
        assert "username" in result["data_schema"].schema
        assert "password" in result["data_schema"].schema

    @pytest.mark.asyncio
    async def test_successful_connection(self):
        """Test successful connection creates entry."""
        from custom_components.evon.config_flow import EvonConfigFlow

        flow = EvonConfigFlow()
        flow.hass = MagicMock()
        flow.hass.config_entries = MagicMock()
        flow.hass.config_entries.async_entries = MagicMock(return_value=[])

        # Mock async_set_unique_id and _abort_if_unique_id_configured
        flow.async_set_unique_id = AsyncMock()
        flow._abort_if_unique_id_configured = MagicMock()

        with (
            patch("custom_components.evon.config_flow.async_get_clientsession") as mock_session,
            patch("custom_components.evon.config_flow.EvonApi") as mock_api_class,
        ):
            mock_api = mock_api_class.return_value
            mock_api.test_connection = AsyncMock(return_value=True)

            result = await flow.async_step_user(
                user_input={
                    "host": TEST_HOST,
                    "username": TEST_USERNAME,
                    "password": TEST_PASSWORD,
                }
            )

            assert result["type"] == "create_entry"
            assert result["title"] == f"Evon ({TEST_HOST})"
            assert result["data"]["host"] == TEST_HOST
            assert result["data"]["username"] == TEST_USERNAME
            assert result["data"]["password"] == TEST_PASSWORD

    @pytest.mark.asyncio
    async def test_connection_error(self):
        """Test connection error shows error."""
        from custom_components.evon.config_flow import EvonConfigFlow

        flow = EvonConfigFlow()
        flow.hass = MagicMock()

        with (
            patch("custom_components.evon.config_flow.async_get_clientsession"),
            patch("custom_components.evon.config_flow.EvonApi") as mock_api_class,
        ):
            mock_api = mock_api_class.return_value
            mock_api.test_connection = AsyncMock(return_value=False)

            result = await flow.async_step_user(
                user_input={
                    "host": TEST_HOST,
                    "username": TEST_USERNAME,
                    "password": TEST_PASSWORD,
                }
            )

            assert result["type"] == "form"
            assert result["errors"]["base"] == "cannot_connect"

    @pytest.mark.asyncio
    async def test_auth_error(self):
        """Test authentication error shows error."""
        from custom_components.evon.api import EvonAuthError
        from custom_components.evon.config_flow import EvonConfigFlow

        flow = EvonConfigFlow()
        flow.hass = MagicMock()

        with (
            patch("custom_components.evon.config_flow.async_get_clientsession"),
            patch("custom_components.evon.config_flow.EvonApi") as mock_api_class,
        ):
            mock_api = mock_api_class.return_value
            mock_api.test_connection = AsyncMock(side_effect=EvonAuthError("Invalid"))

            result = await flow.async_step_user(
                user_input={
                    "host": TEST_HOST,
                    "username": TEST_USERNAME,
                    "password": "wrongpass",
                }
            )

            assert result["type"] == "form"
            assert result["errors"]["base"] == "invalid_auth"


class TestOptionsFlow:
    """Test options flow."""

    @pytest.mark.asyncio
    async def test_options_form_shown(self):
        """Test that options form is shown."""
        from custom_components.evon.config_flow import EvonOptionsFlow

        config_entry = MagicMock()
        config_entry.options = {}

        flow = EvonOptionsFlow(config_entry)

        result = await flow.async_step_init(user_input=None)

        assert result["type"] == "form"
        assert result["step_id"] == "init"

    @pytest.mark.asyncio
    async def test_options_saved(self):
        """Test that options are saved."""
        from custom_components.evon.config_flow import EvonOptionsFlow

        config_entry = MagicMock()
        config_entry.options = {}

        flow = EvonOptionsFlow(config_entry)

        result = await flow.async_step_init(user_input={"scan_interval": 60})

        assert result["type"] == "create_entry"
        assert result["data"]["scan_interval"] == 60

    @pytest.mark.asyncio
    async def test_options_shows_current_value(self):
        """Test that options form shows current value."""
        from custom_components.evon.config_flow import EvonOptionsFlow

        config_entry = MagicMock()
        config_entry.options = {"scan_interval": 45}

        flow = EvonOptionsFlow(config_entry)

        result = await flow.async_step_init(user_input=None)

        # The default value should be the current option
        schema = result["data_schema"].schema
        assert "scan_interval" in schema
