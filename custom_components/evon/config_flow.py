"""Config flow for Evon Smart Home integration."""

from __future__ import annotations

import logging
import re
from typing import Any
from urllib.parse import urlparse

from homeassistant import config_entries
from homeassistant.components.repairs import RepairsFlow
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import voluptuous as vol

from .api import EvonApi, EvonApiError, EvonAuthError
from .const import (
    CONF_CONNECTION_TYPE,
    CONF_ENGINE_ID,
    CONF_HTTP_ONLY,
    CONF_NON_DIMMABLE_LIGHTS,
    CONF_SCAN_INTERVAL,
    CONF_SYNC_AREAS,
    CONNECTION_TYPE_LOCAL,
    CONNECTION_TYPE_REMOTE,
    DEFAULT_HTTP_ONLY,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SYNC_AREAS,
    DOMAIN,
    ENGINE_ID_MAX_LENGTH,
    ENGINE_ID_MIN_LENGTH,
    ENTITY_TYPE_LIGHTS,
    MAX_POLL_INTERVAL,
    MIN_PASSWORD_LENGTH,
    MIN_POLL_INTERVAL,
)

# Validation constants
MAX_USERNAME_LENGTH = 64
MAX_PASSWORD_LENGTH = 128
MAX_HOST_LENGTH = 253  # Max DNS hostname length

_LOGGER = logging.getLogger(__name__)


class InvalidHostError(ValueError):
    """Exception raised when host URL is invalid."""


def normalize_host(host: str) -> str:
    """Normalize host input to a proper URL.

    Handles various input formats:
    - "192.168.1.4" -> "http://192.168.1.4"
    - "192.168.1.4:8080" -> "http://192.168.1.4:8080"
    - "http://192.168.1.4" -> "http://192.168.1.4"
    - "http://192.168.1.4/" -> "http://192.168.1.4"

    Raises:
        InvalidHostError: If the host URL is invalid (empty, no valid netloc, or invalid port)
    """
    host = host.strip()

    if not host:
        raise InvalidHostError("Host cannot be empty")

    # Check for maximum length before processing
    if len(host) > MAX_HOST_LENGTH + 10:  # Allow extra for scheme prefix
        raise InvalidHostError("Host URL is too long")

    # If no scheme, add http://
    if not host.startswith(("http://", "https://")):
        host = f"http://{host}"

    # Parse and reconstruct to normalize
    parsed = urlparse(host)

    # Validate that we have a valid netloc (host)
    if not parsed.netloc:
        raise InvalidHostError("Invalid host URL: No valid host found")

    # Extract hostname without port
    hostname = parsed.hostname or ""

    # Validate hostname length
    if len(hostname) > MAX_HOST_LENGTH:
        raise InvalidHostError("Hostname is too long")

    # Validate hostname format (basic check for valid characters)
    # Allows: alphanumeric, dots, hyphens (for hostnames)
    # Also allows valid IPv4 addresses
    if hostname and not re.match(r"^[a-zA-Z0-9]([a-zA-Z0-9\-\.]*[a-zA-Z0-9])?$|^\d{1,3}(\.\d{1,3}){3}$", hostname):
        raise InvalidHostError("Invalid hostname format")

    # Validate port if specified (must be 1-65535)
    if parsed.port is not None and (parsed.port < 1 or parsed.port > 65535):
        raise InvalidHostError(f"Invalid port number: {parsed.port}")

    # Reconstruct URL without trailing slash
    normalized = f"{parsed.scheme}://{parsed.netloc}"

    return normalized


def validate_engine_id(engine_id: str) -> str | None:
    """Validate Engine ID format.

    Args:
        engine_id: The engine ID to validate

    Returns:
        Error key if invalid, None if valid
    """
    engine_id = engine_id.strip()

    if not engine_id:
        return "invalid_engine_id"

    # Check length constraints
    if len(engine_id) < ENGINE_ID_MIN_LENGTH or len(engine_id) > ENGINE_ID_MAX_LENGTH:
        return "invalid_engine_id"

    # Engine IDs are typically numeric (e.g., "985315")
    # Allow alphanumeric for flexibility but no special characters
    if not re.match(r"^[a-zA-Z0-9]+$", engine_id):
        return "invalid_engine_id"

    return None


def validate_password(password: str) -> str | None:
    """Validate password is not empty and not too long.

    Args:
        password: The password to validate

    Returns:
        Error key if invalid, None if valid
    """
    if not password or len(password.strip()) < MIN_PASSWORD_LENGTH:
        return "invalid_password"
    if len(password) > MAX_PASSWORD_LENGTH:
        return "invalid_password"
    return None


def validate_username(username: str) -> str | None:
    """Validate username is not empty, whitespace-only, or too long.

    Args:
        username: The username to validate

    Returns:
        Error key if invalid, None if valid
    """
    if not username or not username.strip():
        return "invalid_username"
    if len(username.strip()) > MAX_USERNAME_LENGTH:
        return "invalid_username"
    return None


STEP_CONNECTION_TYPE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_CONNECTION_TYPE, default=CONNECTION_TYPE_LOCAL): vol.In(
            {
                CONNECTION_TYPE_LOCAL: "Local network (recommended)",
                CONNECTION_TYPE_REMOTE: "Remote access (via my.evon-smarthome.com)",
            }
        ),
    }
)

STEP_LOCAL_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)

STEP_REMOTE_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ENGINE_ID): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class EvonConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Evon Smart Home."""

    VERSION = 3
    MINOR_VERSION = 0

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._connection_type: str = CONNECTION_TYPE_LOCAL

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> EvonOptionsFlow:
        """Get the options flow for this handler."""
        return EvonOptionsFlow()

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle the initial step - connection type selection."""
        if user_input is not None:
            self._connection_type = user_input[CONF_CONNECTION_TYPE]
            if self._connection_type == CONNECTION_TYPE_LOCAL:
                return await self.async_step_local()
            else:
                return await self.async_step_remote()

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_CONNECTION_TYPE_SCHEMA,
        )

    async def async_step_local(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle local connection configuration."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Strip username
            username = user_input[CONF_USERNAME].strip()

            # Validate username first
            username_error = validate_username(username)
            if username_error:
                errors["base"] = username_error

            # Validate password
            if not errors:
                password_error = validate_password(user_input[CONF_PASSWORD])
                if password_error:
                    errors["base"] = password_error

            # Validate host
            if not errors:
                try:
                    # Normalize and validate the host URL
                    user_input[CONF_HOST] = normalize_host(user_input[CONF_HOST])
                except InvalidHostError:
                    errors["base"] = "invalid_host"

            if not errors:
                # Test connection
                session = async_get_clientsession(self.hass)
                api = EvonApi(
                    host=user_input[CONF_HOST],
                    username=username,
                    password=user_input[CONF_PASSWORD],
                    session=session,
                )

                try:
                    if await api.test_connection():
                        # Check if already configured
                        await self.async_set_unique_id(f"local_{user_input[CONF_HOST]}")
                        self._abort_if_unique_id_configured()

                        return self.async_create_entry(
                            title=f"Evon ({user_input[CONF_HOST]})",
                            data={
                                CONF_CONNECTION_TYPE: CONNECTION_TYPE_LOCAL,
                                CONF_HOST: user_input[CONF_HOST],
                                CONF_USERNAME: username,
                                CONF_PASSWORD: user_input[CONF_PASSWORD],
                            },
                        )
                    else:
                        errors["base"] = "cannot_connect"
                except EvonAuthError:
                    errors["base"] = "invalid_auth"
                except EvonApiError:
                    errors["base"] = "cannot_connect"
                except AbortFlow:
                    raise  # Re-raise flow control exceptions
                except Exception as ex:  # pylint: disable=broad-except
                    _LOGGER.exception("Unexpected exception: %s", ex)
                    errors["base"] = "unknown"

        return self.async_show_form(
            step_id="local",
            data_schema=STEP_LOCAL_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_remote(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle remote connection configuration."""
        errors: dict[str, str] = {}

        if user_input is not None:
            engine_id = user_input[CONF_ENGINE_ID].strip()
            username = user_input[CONF_USERNAME].strip()

            # Validate username first
            username_error = validate_username(username)
            if username_error:
                errors["base"] = username_error

            # Validate password
            if not errors:
                password_error = validate_password(user_input[CONF_PASSWORD])
                if password_error:
                    errors["base"] = password_error

            # Validate engine ID format
            if not errors:
                engine_id_error = validate_engine_id(engine_id)
                if engine_id_error:
                    errors["base"] = engine_id_error

            if not errors:
                # Test connection
                session = async_get_clientsession(self.hass)
                api = EvonApi(
                    engine_id=engine_id,
                    username=username,
                    password=user_input[CONF_PASSWORD],
                    session=session,
                )

                try:
                    if await api.test_connection():
                        # Check if already configured
                        await self.async_set_unique_id(f"remote_{engine_id}")
                        self._abort_if_unique_id_configured()

                        return self.async_create_entry(
                            title=f"Evon (Remote: {engine_id})",
                            data={
                                CONF_CONNECTION_TYPE: CONNECTION_TYPE_REMOTE,
                                CONF_ENGINE_ID: engine_id,
                                CONF_USERNAME: username,
                                CONF_PASSWORD: user_input[CONF_PASSWORD],
                            },
                        )
                    else:
                        errors["base"] = "cannot_connect"
                except EvonAuthError:
                    errors["base"] = "invalid_auth"
                except EvonApiError:
                    errors["base"] = "cannot_connect"
                except AbortFlow:
                    raise  # Re-raise flow control exceptions
                except Exception as ex:  # pylint: disable=broad-except
                    _LOGGER.exception("Unexpected exception: %s", ex)
                    errors["base"] = "unknown"

        return self.async_show_form(
            step_id="remote",
            data_schema=STEP_REMOTE_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle reconfiguration - allow changing connection type."""
        reconfigure_entry = self._get_reconfigure_entry()
        current_data = reconfigure_entry.data
        current_type = current_data.get(CONF_CONNECTION_TYPE, CONNECTION_TYPE_LOCAL)

        if user_input is not None:
            self._connection_type = user_input[CONF_CONNECTION_TYPE]
            if self._connection_type == CONNECTION_TYPE_LOCAL:
                return await self.async_step_reconfigure_local()
            else:
                return await self.async_step_reconfigure_remote()

        # Show current connection type in description with details
        if current_type == CONNECTION_TYPE_LOCAL:
            host = current_data.get(CONF_HOST, "")
            current_type_label = f"Local network ({host})" if host else "Local network"
        else:
            engine_id = current_data.get(CONF_ENGINE_ID, "")
            current_type_label = f"Remote access ({engine_id})" if engine_id else "Remote access"

        # Show connection type selection with current type as default
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_CONNECTION_TYPE, default=current_type): vol.In(
                        {
                            CONNECTION_TYPE_LOCAL: "Local network (recommended)",
                            CONNECTION_TYPE_REMOTE: "Remote access (via my.evon-smarthome.com)",
                        }
                    ),
                }
            ),
            description_placeholders={"current_connection": current_type_label},
        )

    async def async_step_reconfigure_local(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle local reconfiguration."""
        errors: dict[str, str] = {}
        reconfigure_entry = self._get_reconfigure_entry()
        current_data = reconfigure_entry.data

        if user_input is not None:
            # Strip username
            username = user_input[CONF_USERNAME].strip()

            # Validate username first
            username_error = validate_username(username)
            if username_error:
                errors["base"] = username_error

            # Validate password
            if not errors:
                password_error = validate_password(user_input[CONF_PASSWORD])
                if password_error:
                    errors["base"] = password_error

            # Validate host
            if not errors:
                try:
                    # Normalize and validate the host URL
                    user_input[CONF_HOST] = normalize_host(user_input[CONF_HOST])
                except InvalidHostError:
                    errors["base"] = "invalid_host"

            if not errors:
                # Test connection with new credentials
                session = async_get_clientsession(self.hass)
                api = EvonApi(
                    host=user_input[CONF_HOST],
                    username=username,
                    password=user_input[CONF_PASSWORD],
                    session=session,
                )

                try:
                    if await api.test_connection():
                        # Update and reload the config entry
                        # Remove remote-specific fields when switching to local
                        new_data = {
                            CONF_CONNECTION_TYPE: CONNECTION_TYPE_LOCAL,
                            CONF_HOST: user_input[CONF_HOST],
                            CONF_USERNAME: username,
                            CONF_PASSWORD: user_input[CONF_PASSWORD],
                        }
                        return self.async_update_reload_and_abort(
                            reconfigure_entry,
                            data=new_data,  # Replace all data
                        )
                    else:
                        errors["base"] = "cannot_connect"
                except EvonAuthError:
                    errors["base"] = "invalid_auth"
                except EvonApiError:
                    errors["base"] = "cannot_connect"
                except AbortFlow:
                    raise  # Re-raise flow control exceptions
                except Exception as ex:  # pylint: disable=broad-except
                    _LOGGER.exception("Unexpected exception during reconfigure: %s", ex)
                    errors["base"] = "unknown"

        # Pre-fill with current values if available (may be empty when switching from remote)
        reconfigure_schema = vol.Schema(
            {
                vol.Required(CONF_HOST, default=current_data.get(CONF_HOST, "")): str,
                vol.Required(CONF_USERNAME, default=current_data.get(CONF_USERNAME, "")): str,
                vol.Required(CONF_PASSWORD): str,  # Don't show current password
            }
        )

        return self.async_show_form(
            step_id="reconfigure_local",
            data_schema=reconfigure_schema,
            errors=errors,
        )

    async def async_step_reconfigure_remote(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle remote reconfiguration."""
        errors: dict[str, str] = {}
        reconfigure_entry = self._get_reconfigure_entry()
        current_data = reconfigure_entry.data

        if user_input is not None:
            engine_id = user_input[CONF_ENGINE_ID].strip()
            username = user_input[CONF_USERNAME].strip()

            # Validate username first
            username_error = validate_username(username)
            if username_error:
                errors["base"] = username_error

            # Validate password
            if not errors:
                password_error = validate_password(user_input[CONF_PASSWORD])
                if password_error:
                    errors["base"] = password_error

            # Validate engine ID format
            if not errors:
                engine_id_error = validate_engine_id(engine_id)
                if engine_id_error:
                    errors["base"] = engine_id_error

            if not errors:
                # Test connection with new credentials
                session = async_get_clientsession(self.hass)
                api = EvonApi(
                    engine_id=engine_id,
                    username=username,
                    password=user_input[CONF_PASSWORD],
                    session=session,
                )

                try:
                    if await api.test_connection():
                        # Update and reload the config entry
                        # Remove local-specific fields when switching to remote
                        new_data = {
                            CONF_CONNECTION_TYPE: CONNECTION_TYPE_REMOTE,
                            CONF_ENGINE_ID: engine_id,
                            CONF_USERNAME: username,
                            CONF_PASSWORD: user_input[CONF_PASSWORD],
                        }
                        return self.async_update_reload_and_abort(
                            reconfigure_entry,
                            data=new_data,  # Replace all data
                        )
                    else:
                        errors["base"] = "cannot_connect"
                except EvonAuthError:
                    errors["base"] = "invalid_auth"
                except EvonApiError:
                    errors["base"] = "cannot_connect"
                except AbortFlow:
                    raise  # Re-raise flow control exceptions
                except Exception as ex:  # pylint: disable=broad-except
                    _LOGGER.exception("Unexpected exception during reconfigure: %s", ex)
                    errors["base"] = "unknown"

        reconfigure_schema = vol.Schema(
            {
                vol.Required(CONF_ENGINE_ID, default=current_data.get(CONF_ENGINE_ID, "")): str,
                vol.Required(CONF_USERNAME, default=current_data.get(CONF_USERNAME, "")): str,
                vol.Required(CONF_PASSWORD): str,  # Don't show current password
            }
        )

        return self.async_show_form(
            step_id="reconfigure_remote",
            data_schema=reconfigure_schema,
            errors=errors,
        )


class EvonOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for Evon Smart Home."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current_interval = self.config_entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        current_sync_areas = self.config_entry.options.get(CONF_SYNC_AREAS, DEFAULT_SYNC_AREAS)
        current_http_only = self.config_entry.options.get(CONF_HTTP_ONLY, DEFAULT_HTTP_ONLY)
        current_non_dimmable = self.config_entry.options.get(CONF_NON_DIMMABLE_LIGHTS, [])

        # Get available lights from coordinator
        light_options: dict[str, str] = {}
        if self.config_entry.entry_id in self.hass.data.get(DOMAIN, {}):
            coordinator = self.hass.data[DOMAIN][self.config_entry.entry_id].get("coordinator")
            if coordinator and coordinator.data and ENTITY_TYPE_LIGHTS in coordinator.data:
                for light in coordinator.data[ENTITY_TYPE_LIGHTS]:
                    light_id = light["id"]
                    light_name = light["name"]
                    light_options[light_id] = light_name

        # Build schema - order: sync_areas, non_dimmable_lights, http_only, scan_interval
        schema_dict: dict[Any, Any] = {
            vol.Required(CONF_SYNC_AREAS, default=current_sync_areas): bool,
        }

        if light_options:
            from homeassistant.helpers.selector import (
                SelectSelector,
                SelectSelectorConfig,
                SelectSelectorMode,
            )

            schema_dict[vol.Optional(CONF_NON_DIMMABLE_LIGHTS, default=current_non_dimmable)] = SelectSelector(
                SelectSelectorConfig(
                    options=[{"value": k, "label": v} for k, v in light_options.items()],
                    multiple=True,
                    mode=SelectSelectorMode.DROPDOWN,
                )
            )

        # Advanced options last
        schema_dict[vol.Required(CONF_HTTP_ONLY, default=current_http_only)] = bool
        schema_dict[vol.Required(CONF_SCAN_INTERVAL, default=current_interval)] = vol.All(
            vol.Coerce(int), vol.Range(min=MIN_POLL_INTERVAL, max=MAX_POLL_INTERVAL)
        )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(schema_dict),
        )


class EvonStaleEntitiesRepairFlow(RepairsFlow):
    """Handler for stale entities repair flow."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle the initial step."""
        return await self.async_step_confirm()

    async def async_step_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle the confirm step."""
        if user_input is not None:
            return self.async_create_entry(data={})

        return self.async_show_form(step_id="confirm")


async def async_create_fix_flow(hass: HomeAssistant, issue_id: str, data: dict[str, Any] | None) -> RepairsFlow:
    """Create a repair flow for the given issue."""
    if issue_id.startswith("stale_entities_cleaned"):
        return EvonStaleEntitiesRepairFlow()
    raise ValueError(f"Unknown issue: {issue_id}")
