"""Config flow for Evon Smart Home integration."""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlparse

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import AbortFlow, FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import voluptuous as vol

from .api import EvonApi, EvonApiError, EvonAuthError
from .const import CONF_SCAN_INTERVAL, CONF_SYNC_AREAS, DEFAULT_SCAN_INTERVAL, DEFAULT_SYNC_AREAS, DOMAIN

_LOGGER = logging.getLogger(__name__)


def normalize_host(host: str) -> str:
    """Normalize host input to a proper URL.

    Handles various input formats:
    - "192.168.1.4" -> "http://192.168.1.4"
    - "192.168.1.4:8080" -> "http://192.168.1.4:8080"
    - "http://192.168.1.4" -> "http://192.168.1.4"
    - "http://192.168.1.4/" -> "http://192.168.1.4"
    """
    host = host.strip()

    # If no scheme, add http://
    if not host.startswith(("http://", "https://")):
        host = f"http://{host}"

    # Parse and reconstruct to normalize
    parsed = urlparse(host)

    # Reconstruct URL without trailing slash
    normalized = f"{parsed.scheme}://{parsed.netloc}"

    return normalized


STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class EvonConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Evon Smart Home."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize config flow."""
        self._reconfig_entry: config_entries.ConfigEntry | None = None

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> EvonOptionsFlow:
        """Get the options flow for this handler."""
        return EvonOptionsFlow(config_entry)

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Normalize the host URL
            user_input[CONF_HOST] = normalize_host(user_input[CONF_HOST])

            # Test connection
            session = async_get_clientsession(self.hass)
            api = EvonApi(
                host=user_input[CONF_HOST],
                username=user_input[CONF_USERNAME],
                password=user_input[CONF_PASSWORD],
                session=session,
            )

            try:
                if await api.test_connection():
                    # Check if already configured
                    await self.async_set_unique_id(user_input[CONF_HOST])
                    self._abort_if_unique_id_configured()

                    return self.async_create_entry(
                        title=f"Evon ({user_input[CONF_HOST]})",
                        data=user_input,
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
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle reconfiguration."""
        # Get the config entry being reconfigured
        self._reconfig_entry = self._get_reconfigure_entry()

        errors: dict[str, str] = {}

        if user_input is not None:
            # Normalize the host URL
            user_input[CONF_HOST] = normalize_host(user_input[CONF_HOST])

            # Test connection with new credentials
            session = async_get_clientsession(self.hass)
            api = EvonApi(
                host=user_input[CONF_HOST],
                username=user_input[CONF_USERNAME],
                password=user_input[CONF_PASSWORD],
                session=session,
            )

            try:
                if await api.test_connection():
                    # Update the config entry
                    self.hass.config_entries.async_update_entry(
                        self._reconfig_entry,
                        data=user_input,
                    )
                    await self.hass.config_entries.async_reload(self._reconfig_entry.entry_id)
                    return self.async_abort(reason="reconfigure_successful")
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

        # Pre-fill with current values
        current_data = self._reconfig_entry.data
        reconfigure_schema = vol.Schema(
            {
                vol.Required(CONF_HOST, default=current_data.get(CONF_HOST, "")): str,
                vol.Required(CONF_USERNAME, default=current_data.get(CONF_USERNAME, "")): str,
                vol.Required(CONF_PASSWORD): str,  # Don't show current password
            }
        )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=reconfigure_schema,
            errors=errors,
        )


class EvonOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for Evon Smart Home."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current_interval = self.config_entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        current_sync_areas = self.config_entry.options.get(CONF_SYNC_AREAS, DEFAULT_SYNC_AREAS)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SCAN_INTERVAL,
                        default=current_interval,
                    ): vol.All(vol.Coerce(int), vol.Range(min=5, max=300)),
                    vol.Required(
                        CONF_SYNC_AREAS,
                        default=current_sync_areas,
                    ): bool,
                }
            ),
        )
