"""Integration tests for Evon config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from tests.conftest import (
    TEST_HOST,
    TEST_PASSWORD,
    TEST_USERNAME,
    requires_ha_test_framework,
)

pytestmark = requires_ha_test_framework


@pytest.mark.asyncio
async def test_config_flow_user_success(hass):
    """Test successful config flow from user step."""
    from custom_components.evon.const import DOMAIN

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    with patch("custom_components.evon.config_flow.EvonApi") as mock_api_class:
        mock_api = AsyncMock()
        mock_api.test_connection = AsyncMock(return_value=True)
        mock_api_class.return_value = mock_api

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "192.168.1.100",
                "username": TEST_USERNAME,
                "password": TEST_PASSWORD,
            },
        )

    assert result["type"] == "create_entry"
    assert result["title"] == "Evon (http://192.168.1.100)"
    assert result["data"]["host"] == "http://192.168.1.100"
    assert result["data"]["username"] == TEST_USERNAME
    assert result["data"]["password"] == TEST_PASSWORD


@pytest.mark.asyncio
async def test_config_flow_host_normalization(hass):
    """Test that host URL is normalized correctly."""
    from custom_components.evon.const import DOMAIN

    with patch("custom_components.evon.config_flow.EvonApi") as mock_api_class:
        mock_api = AsyncMock()
        mock_api.test_connection = AsyncMock(return_value=True)
        mock_api_class.return_value = mock_api

        # Test with trailing slash
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "http://192.168.1.200/",
                "username": TEST_USERNAME,
                "password": TEST_PASSWORD,
            },
        )

    assert result["type"] == "create_entry"
    # Trailing slash should be stripped
    assert result["data"]["host"] == "http://192.168.1.200"


@pytest.mark.asyncio
async def test_config_flow_cannot_connect(hass):
    """Test config flow handles connection error."""
    from custom_components.evon.api import EvonApiError
    from custom_components.evon.const import DOMAIN

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})

    with patch("custom_components.evon.config_flow.EvonApi") as mock_api_class:
        mock_api = AsyncMock()
        mock_api.test_connection = AsyncMock(side_effect=EvonApiError("Connection failed"))
        mock_api_class.return_value = mock_api

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": TEST_HOST,
                "username": TEST_USERNAME,
                "password": TEST_PASSWORD,
            },
        )

    assert result["type"] == "form"
    assert result["errors"] == {"base": "cannot_connect"}


@pytest.mark.asyncio
async def test_config_flow_invalid_auth(hass):
    """Test config flow handles authentication error."""
    from custom_components.evon.api import EvonAuthError
    from custom_components.evon.const import DOMAIN

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})

    with patch("custom_components.evon.config_flow.EvonApi") as mock_api_class:
        mock_api = AsyncMock()
        mock_api.test_connection = AsyncMock(side_effect=EvonAuthError("Invalid credentials"))
        mock_api_class.return_value = mock_api

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": TEST_HOST,
                "username": TEST_USERNAME,
                "password": "wrongpassword",
            },
        )

    assert result["type"] == "form"
    assert result["errors"] == {"base": "invalid_auth"}


@pytest.mark.asyncio
async def test_config_flow_unknown_error(hass):
    """Test config flow handles unknown errors."""
    from custom_components.evon.const import DOMAIN

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})

    with patch("custom_components.evon.config_flow.EvonApi") as mock_api_class:
        mock_api = AsyncMock()
        mock_api.test_connection = AsyncMock(side_effect=Exception("Unexpected error"))
        mock_api_class.return_value = mock_api

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": TEST_HOST,
                "username": TEST_USERNAME,
                "password": TEST_PASSWORD,
            },
        )

    assert result["type"] == "form"
    assert result["errors"] == {"base": "unknown"}


@pytest.mark.asyncio
async def test_config_flow_test_connection_false(hass):
    """Test config flow handles test_connection returning False."""
    from custom_components.evon.const import DOMAIN

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})

    with patch("custom_components.evon.config_flow.EvonApi") as mock_api_class:
        mock_api = AsyncMock()
        mock_api.test_connection = AsyncMock(return_value=False)
        mock_api_class.return_value = mock_api

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": TEST_HOST,
                "username": TEST_USERNAME,
                "password": TEST_PASSWORD,
            },
        )

    assert result["type"] == "form"
    assert result["errors"] == {"base": "cannot_connect"}


@pytest.mark.asyncio
async def test_config_flow_already_configured(hass):
    """Test config flow aborts when already configured."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.evon.const import DOMAIN

    # Create existing entry
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": "http://192.168.1.100",
            "username": TEST_USERNAME,
            "password": TEST_PASSWORD,
        },
        unique_id="http://192.168.1.100",
    )
    existing_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})

    with patch("custom_components.evon.config_flow.EvonApi") as mock_api_class:
        mock_api = AsyncMock()
        mock_api.test_connection = AsyncMock(return_value=True)
        mock_api_class.return_value = mock_api

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "192.168.1.100",  # Same host, should be normalized and match
                "username": "newuser",
                "password": "newpass",
            },
        )

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"


@pytest.mark.asyncio
async def test_config_flow_reconfigure(hass, mock_evon_api_class):
    """Test reconfiguration flow.

    Uses mock_evon_api_class fixture so the entry reload after reconfigure
    uses the mocked API instead of the real one.
    """
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.evon.const import DOMAIN

    # Create existing entry (not set up - just for reconfigure flow test)
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": "http://192.168.1.100",
            "username": "olduser",
            "password": "oldpass",
        },
        unique_id="http://192.168.1.100",
    )
    existing_entry.add_to_hass(hass)

    # Start reconfigure flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "reconfigure", "entry_id": existing_entry.entry_id},
    )

    assert result["type"] == "form"
    assert result["step_id"] == "reconfigure"

    # Patch the config flow's EvonApi for connection test
    # The mock_evon_api_class fixture handles the reload
    with patch("custom_components.evon.config_flow.EvonApi") as mock_flow_api_class:
        mock_flow_api = AsyncMock()
        mock_flow_api.test_connection = AsyncMock(return_value=True)
        mock_flow_api_class.return_value = mock_flow_api

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "http://192.168.1.100",
                "username": "newuser",
                "password": "newpass",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == "abort"
    assert result["reason"] == "reconfigure_successful"

    # Verify entry was updated
    assert existing_entry.data["username"] == "newuser"
    assert existing_entry.data["password"] == "newpass"


@pytest.mark.asyncio
async def test_config_flow_reconfigure_auth_error(hass):
    """Test reconfigure flow handles auth error."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.evon.api import EvonAuthError
    from custom_components.evon.const import DOMAIN

    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": "http://192.168.1.100",
            "username": "olduser",
            "password": "oldpass",
        },
        unique_id="http://192.168.1.100",
    )
    existing_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "reconfigure", "entry_id": existing_entry.entry_id},
    )

    with patch("custom_components.evon.config_flow.EvonApi") as mock_api_class:
        mock_api = AsyncMock()
        mock_api.test_connection = AsyncMock(side_effect=EvonAuthError("Invalid"))
        mock_api_class.return_value = mock_api

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "http://192.168.1.100",
                "username": "newuser",
                "password": "wrongpass",
            },
        )

    assert result["type"] == "form"
    assert result["errors"] == {"base": "invalid_auth"}


@pytest.mark.asyncio
async def test_options_flow(hass, mock_config_entry_v2, mock_evon_api_class):
    """Test options flow."""
    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    # Start options flow
    result = await hass.config_entries.options.async_init(mock_config_entry_v2.entry_id)

    assert result["type"] == "form"
    assert result["step_id"] == "init"

    # Submit options
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "scan_interval": 60,
            "sync_areas": True,
        },
    )

    assert result["type"] == "create_entry"
    assert result["data"]["scan_interval"] == 60
    assert result["data"]["sync_areas"] is True
