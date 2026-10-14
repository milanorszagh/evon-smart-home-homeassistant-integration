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
    from custom_components.evon.const import CONNECTION_TYPE_LOCAL, DOMAIN

    # Step 1: Select connection type
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})

    assert result["type"] == "form"
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"connection_type": CONNECTION_TYPE_LOCAL},
    )

    assert result["type"] == "form"
    assert result["step_id"] == "local"

    # Step 2: Enter credentials
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
    assert result["data"]["connection_type"] == CONNECTION_TYPE_LOCAL


@pytest.mark.asyncio
async def test_config_flow_remote_success(hass):
    """Test successful config flow with remote connection."""
    from custom_components.evon.const import CONNECTION_TYPE_REMOTE, DOMAIN

    # Step 1: Select connection type
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"connection_type": CONNECTION_TYPE_REMOTE},
    )

    assert result["type"] == "form"
    assert result["step_id"] == "remote"

    # Step 2: Enter remote credentials
    with patch("custom_components.evon.config_flow.EvonApi") as mock_api_class:
        mock_api = AsyncMock()
        mock_api.test_connection = AsyncMock(return_value=True)
        mock_api_class.return_value = mock_api

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "engine_id": "123456",
                "username": TEST_USERNAME,
                "password": TEST_PASSWORD,
            },
        )

    assert result["type"] == "create_entry"
    assert result["title"] == "Evon (Remote: 123456)"
    assert result["data"]["engine_id"] == "123456"
    assert result["data"]["username"] == TEST_USERNAME
    assert result["data"]["password"] == TEST_PASSWORD
    assert result["data"]["connection_type"] == CONNECTION_TYPE_REMOTE


@pytest.mark.asyncio
async def test_config_flow_host_normalization(hass):
    """Test that host URL is normalized correctly."""
    from custom_components.evon.const import CONNECTION_TYPE_LOCAL, DOMAIN

    with patch("custom_components.evon.config_flow.EvonApi") as mock_api_class:
        mock_api = AsyncMock()
        mock_api.test_connection = AsyncMock(return_value=True)
        mock_api_class.return_value = mock_api

        # Test with trailing slash
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"connection_type": CONNECTION_TYPE_LOCAL},
        )
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
    from custom_components.evon.const import CONNECTION_TYPE_LOCAL, DOMAIN

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"connection_type": CONNECTION_TYPE_LOCAL},
    )

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
    from custom_components.evon.const import CONNECTION_TYPE_LOCAL, DOMAIN

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"connection_type": CONNECTION_TYPE_LOCAL},
    )

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
    from custom_components.evon.const import CONNECTION_TYPE_LOCAL, DOMAIN

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"connection_type": CONNECTION_TYPE_LOCAL},
    )

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
    from custom_components.evon.const import CONNECTION_TYPE_LOCAL, DOMAIN

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"connection_type": CONNECTION_TYPE_LOCAL},
    )

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

    from custom_components.evon.const import CONNECTION_TYPE_LOCAL, DOMAIN

    # Create existing entry
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "connection_type": CONNECTION_TYPE_LOCAL,
            "host": "http://192.168.1.100",
            "username": TEST_USERNAME,
            "password": TEST_PASSWORD,
        },
        unique_id="local_http://192.168.1.100",
    )
    existing_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"connection_type": CONNECTION_TYPE_LOCAL},
    )

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

    from custom_components.evon.const import CONNECTION_TYPE_LOCAL, DOMAIN

    # Create existing entry (not set up - just for reconfigure flow test)
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "connection_type": CONNECTION_TYPE_LOCAL,
            "host": "http://192.168.1.100",
            "username": "olduser",
            "password": "oldpass",
        },
        unique_id="local_http://192.168.1.100",
    )
    existing_entry.add_to_hass(hass)

    # Start reconfigure flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "reconfigure", "entry_id": existing_entry.entry_id},
    )

    # First step: choose connection type
    assert result["type"] == "form"
    assert result["step_id"] == "reconfigure"

    # Select local connection type
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"connection_type": CONNECTION_TYPE_LOCAL},
    )

    assert result["type"] == "form"
    assert result["step_id"] == "reconfigure_local"

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
    from custom_components.evon.const import CONNECTION_TYPE_LOCAL, DOMAIN

    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "connection_type": CONNECTION_TYPE_LOCAL,
            "host": "http://192.168.1.100",
            "username": "olduser",
            "password": "oldpass",
        },
        unique_id="local_http://192.168.1.100",
    )
    existing_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "reconfigure", "entry_id": existing_entry.entry_id},
    )

    # First step: choose connection type
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"connection_type": CONNECTION_TYPE_LOCAL},
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
async def test_config_flow_invalid_host_empty(hass):
    """Test config flow handles empty host URL."""
    from custom_components.evon.const import CONNECTION_TYPE_LOCAL, DOMAIN

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"connection_type": CONNECTION_TYPE_LOCAL},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "host": "",
            "username": TEST_USERNAME,
            "password": TEST_PASSWORD,
        },
    )

    assert result["type"] == "form"
    assert result["errors"] == {"base": "invalid_host"}


@pytest.mark.asyncio
async def test_config_flow_invalid_host_whitespace(hass):
    """Test config flow handles whitespace-only host URL."""
    from custom_components.evon.const import CONNECTION_TYPE_LOCAL, DOMAIN

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"connection_type": CONNECTION_TYPE_LOCAL},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "host": "   ",
            "username": TEST_USERNAME,
            "password": TEST_PASSWORD,
        },
    )

    assert result["type"] == "form"
    assert result["errors"] == {"base": "invalid_host"}


@pytest.mark.asyncio
async def test_config_flow_reconfigure_invalid_host(hass):
    """Test reconfigure flow handles invalid host URL."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.evon.const import CONNECTION_TYPE_LOCAL, DOMAIN

    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "connection_type": CONNECTION_TYPE_LOCAL,
            "host": "http://192.168.1.100",
            "username": "olduser",
            "password": "oldpass",
        },
        unique_id="local_http://192.168.1.100",
    )
    existing_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "reconfigure", "entry_id": existing_entry.entry_id},
    )

    # First step: choose connection type
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"connection_type": CONNECTION_TYPE_LOCAL},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "host": "",
            "username": "newuser",
            "password": "newpass",
        },
    )

    assert result["type"] == "form"
    assert result["errors"] == {"base": "invalid_host"}


@pytest.mark.asyncio
async def test_config_flow_invalid_engine_id(hass):
    """Test config flow handles empty engine ID."""
    from custom_components.evon.const import CONNECTION_TYPE_REMOTE, DOMAIN

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"connection_type": CONNECTION_TYPE_REMOTE},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "engine_id": "",
            "username": TEST_USERNAME,
            "password": TEST_PASSWORD,
        },
    )

    assert result["type"] == "form"
    assert result["errors"] == {"base": "invalid_engine_id"}


@pytest.mark.asyncio
@pytest.mark.parametrize("expected_lingering_tasks", [True])
@pytest.mark.parametrize("expected_lingering_timers", [True])
async def test_options_flow(
    hass, mock_config_entry_v2, mock_evon_api_class, expected_lingering_tasks, expected_lingering_timers
):
    """Test options flow."""
    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    # Start options flow
    result = await hass.config_entries.options.async_init(mock_config_entry_v2.entry_id)

    assert result["type"] == "form"
    assert result["step_id"] == "init"

    # Submit options with section-grouped data
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "sync_areas": True,
            "buttons": {
                "button_double_click_delay": 0.8,
            },
            "doors": {
                "door_open_seconds": 2,
            },
            "connection": {
                "http_only": False,
                "scan_interval": 60,
            },
            "recording": {
                "max_recording_duration": 300,
                "recording_output_format": "mp4",
            },
            "debug": {
                "debug_api": False,
                "debug_websocket": False,
                "debug_coordinator": False,
            },
        },
    )

    assert result["type"] == "create_entry"
    # Data is flattened from sections before storage
    assert result["data"]["http_only"] is False
    assert result["data"]["scan_interval"] == 60
    assert result["data"]["sync_areas"] is True


@pytest.mark.asyncio
@pytest.mark.parametrize("expected_lingering_tasks", [True])
@pytest.mark.parametrize("expected_lingering_timers", [True])
async def test_options_flow_http_only(
    hass, mock_config_entry_v2, mock_evon_api_class, expected_lingering_tasks, expected_lingering_timers
):
    """Test options flow with HTTP only mode enabled."""
    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    # Start options flow
    result = await hass.config_entries.options.async_init(mock_config_entry_v2.entry_id)

    assert result["type"] == "form"
    assert result["step_id"] == "init"

    # Submit options with HTTP only enabled (disables WebSocket)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "sync_areas": False,
            "buttons": {
                "button_double_click_delay": 0.8,
            },
            "doors": {
                "door_open_seconds": 2,
            },
            "connection": {
                "http_only": True,
                "scan_interval": 30,
            },
            "recording": {
                "max_recording_duration": 300,
                "recording_output_format": "mp4",
            },
            "debug": {
                "debug_api": False,
                "debug_websocket": False,
                "debug_coordinator": False,
            },
        },
    )

    assert result["type"] == "create_entry"
    # Data is flattened from sections before storage
    assert result["data"]["http_only"] is True
    assert result["data"]["scan_interval"] == 30
    assert result["data"]["sync_areas"] is False


@pytest.mark.asyncio
async def test_config_flow_reauth_local_success(hass, mock_evon_api_class):
    """Test reauth flow succeeds for a local connection entry."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.evon.const import CONNECTION_TYPE_LOCAL, DOMAIN

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "connection_type": CONNECTION_TYPE_LOCAL,
            "host": TEST_HOST,
            "username": TEST_USERNAME,
            "password": "oldpass",
        },
        unique_id=f"local_{TEST_HOST}",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "reauth", "entry_id": entry.entry_id},
    )
    assert result["type"] == "form"
    assert result["step_id"] == "reauth_confirm"

    with patch("custom_components.evon.config_flow.EvonApi") as mock_flow_api_class:
        mock_flow_api = AsyncMock()
        mock_flow_api.test_connection = AsyncMock(return_value=True)
        mock_flow_api_class.return_value = mock_flow_api

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": "newuser", "password": "newpass"},
        )
        await hass.async_block_till_done()

    assert result["type"] == "abort"
    assert result["reason"] == "reauth_successful"
    assert entry.data["username"] == "newuser"
    assert entry.data["password"] == "newpass"


@pytest.mark.asyncio
async def test_config_flow_reauth_remote_success(hass, mock_evon_api_class):
    """Test reauth flow succeeds for a remote connection entry."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.evon.const import CONNECTION_TYPE_REMOTE, DOMAIN

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "connection_type": CONNECTION_TYPE_REMOTE,
            "engine_id": "ABCD1234",
            "username": TEST_USERNAME,
            "password": "oldpass",
        },
        unique_id="remote_ABCD1234",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "reauth", "entry_id": entry.entry_id},
    )
    assert result["type"] == "form"
    assert result["step_id"] == "reauth_confirm"

    with patch("custom_components.evon.config_flow.EvonApi") as mock_flow_api_class:
        mock_flow_api = AsyncMock()
        mock_flow_api.test_connection = AsyncMock(return_value=True)
        mock_flow_api_class.return_value = mock_flow_api

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": "newuser", "password": "newpass"},
        )
        await hass.async_block_till_done()

    assert result["type"] == "abort"
    assert result["reason"] == "reauth_successful"
    assert entry.data["username"] == "newuser"
    assert entry.data["password"] == "newpass"


@pytest.mark.asyncio
async def test_config_flow_reauth_invalid_auth(hass):
    """Test reauth flow shows invalid_auth error when credentials are rejected."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.evon.api import EvonAuthError
    from custom_components.evon.const import CONNECTION_TYPE_LOCAL, DOMAIN

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "connection_type": CONNECTION_TYPE_LOCAL,
            "host": TEST_HOST,
            "username": TEST_USERNAME,
            "password": "oldpass",
        },
        unique_id=f"local_{TEST_HOST}",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "reauth", "entry_id": entry.entry_id},
    )

    with patch("custom_components.evon.config_flow.EvonApi") as mock_flow_api_class:
        mock_flow_api = AsyncMock()
        mock_flow_api.test_connection = AsyncMock(side_effect=EvonAuthError("Invalid credentials"))
        mock_flow_api_class.return_value = mock_flow_api

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": TEST_USERNAME, "password": "wrongpass"},
        )

    assert result["type"] == "form"
    assert result["errors"] == {"base": "invalid_auth"}
    # Entry credentials must not have changed
    assert entry.data["password"] == "oldpass"


@pytest.mark.asyncio
async def test_config_flow_reauth_cannot_connect(hass):
    """Test reauth flow shows cannot_connect error on API failure."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.evon.api import EvonApiError
    from custom_components.evon.const import CONNECTION_TYPE_LOCAL, DOMAIN

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "connection_type": CONNECTION_TYPE_LOCAL,
            "host": TEST_HOST,
            "username": TEST_USERNAME,
            "password": "oldpass",
        },
        unique_id=f"local_{TEST_HOST}",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "reauth", "entry_id": entry.entry_id},
    )

    with patch("custom_components.evon.config_flow.EvonApi") as mock_flow_api_class:
        mock_flow_api = AsyncMock()
        mock_flow_api.test_connection = AsyncMock(side_effect=EvonApiError("Timeout"))
        mock_flow_api_class.return_value = mock_flow_api

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": TEST_USERNAME, "password": "newpass"},
        )

    assert result["type"] == "form"
    assert result["errors"] == {"base": "cannot_connect"}


@pytest.mark.asyncio
async def test_config_flow_reconfigure_loaded_entry_reloads_via_listener(
    hass, mock_config_entry_v2, mock_evon_api_class, caplog
):
    """Reconfiguring a LOADED entry reloads it through the update listener.

    `async_update_reload_and_abort` on an entry that has an update listener makes HA
    log "has an update listener and should use it for scheduling a reload" (breaks in
    HA 2026.12). The flow must therefore only update the entry and let the listener
    reload — and the listener must react to `data` changes, not just options.
    """
    import logging

    from homeassistant.config_entries import ConfigEntryState

    from custom_components.evon.const import DOMAIN

    caplog.set_level(logging.WARNING)
    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry_v2.update_listeners
    coordinator_before = hass.data[DOMAIN][mock_config_entry_v2.entry_id]["coordinator"]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "reconfigure", "entry_id": mock_config_entry_v2.entry_id}
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"connection_type": "local"})
    assert result["step_id"] == "reconfigure_local"
    with patch("custom_components.evon.config_flow.EvonApi") as api_cls:
        api_cls.return_value = AsyncMock(test_connection=AsyncMock(return_value=True))
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"host": mock_config_entry_v2.data["host"], "username": "newuser", "password": "newpass"},
        )
        await hass.async_block_till_done()

    assert result["type"] == "abort"
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry_v2.data["username"] == "newuser"
    detected = [r.getMessage() for r in caplog.records if "Detected that custom integration 'evon'" in r.getMessage()]
    assert detected == []
    # The entry was actually reloaded with the new data
    assert mock_config_entry_v2.state is ConfigEntryState.LOADED
    assert hass.data[DOMAIN][mock_config_entry_v2.entry_id]["coordinator"] is not coordinator_before


@pytest.mark.asyncio
async def test_config_flow_reauth_loaded_entry_unchanged_data_still_reloads(
    hass, mock_config_entry_v2, mock_evon_api_class, caplog
):
    """Re-entering identical credentials must still reload the entry (listener won't fire)."""
    import logging

    from custom_components.evon.const import DOMAIN

    caplog.set_level(logging.WARNING)
    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()
    coordinator_before = hass.data[DOMAIN][mock_config_entry_v2.entry_id]["coordinator"]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "reauth", "entry_id": mock_config_entry_v2.entry_id}
    )
    assert result["step_id"] == "reauth_confirm"
    with patch("custom_components.evon.config_flow.EvonApi") as api_cls:
        api_cls.return_value = AsyncMock(test_connection=AsyncMock(return_value=True))
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": mock_config_entry_v2.data["username"], "password": mock_config_entry_v2.data["password"]},
        )
        await hass.async_block_till_done()

    assert result["type"] == "abort"
    assert result["reason"] == "reauth_successful"
    detected = [r.getMessage() for r in caplog.records if "Detected that custom integration 'evon'" in r.getMessage()]
    assert detected == []
    assert hass.data[DOMAIN][mock_config_entry_v2.entry_id]["coordinator"] is not coordinator_before
