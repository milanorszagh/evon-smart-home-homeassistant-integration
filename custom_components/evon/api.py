"""Evon Smart Home API client."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import logging
import re
import ssl
import time
from typing import Any

import aiohttp
from homeassistant.exceptions import HomeAssistantError

from .const import (
    DEFAULT_LOGIN_TIMEOUT,
    DEFAULT_REQUEST_TIMEOUT,
    ENGINE_ID_MAX_LENGTH,
    ENGINE_ID_MIN_LENGTH,
    EVON_REMOTE_HOST,
)

_LOGGER = logging.getLogger(__name__)

# Token TTL in seconds (refresh token after this time)
TOKEN_TTL_SECONDS = 3600  # 1 hour

# Validation patterns for API parameters
INSTANCE_ID_PATTERN = re.compile(r"^[a-zA-Z0-9._-]+$")
METHOD_NAME_PATTERN = re.compile(r"^[a-zA-Z][a-zA-Z0-9]*$")

# Headers that should never be logged (contain sensitive data)
SENSITIVE_HEADERS = frozenset(
    {
        "x-elocs-token",
        "x-elocs-password",
        "authorization",
        "cookie",
        "set-cookie",
    }
)


def _redact_headers(headers: dict[str, str]) -> dict[str, str]:
    """Redact sensitive headers for safe logging."""
    return {k: "**REDACTED**" if k.lower() in SENSITIVE_HEADERS else v for k, v in headers.items()}


def _create_ssl_context() -> ssl.SSLContext:
    """Create a secure SSL context for HTTPS connections.

    Uses the system's certificate store for verification.
    """
    return ssl.create_default_context()


def _validate_instance_id(instance_id: str) -> None:
    """Validate instance ID format to prevent path traversal.

    Args:
        instance_id: The instance ID to validate

    Raises:
        ValueError: If the instance ID contains invalid characters
    """
    if not instance_id or not INSTANCE_ID_PATTERN.match(instance_id):
        raise ValueError(f"Invalid instance ID format: {instance_id!r}")


def _validate_method_name(method: str) -> None:
    """Validate method name format.

    Args:
        method: The method name to validate

    Raises:
        ValueError: If the method name contains invalid characters
    """
    if not method or not METHOD_NAME_PATTERN.match(method):
        raise ValueError(f"Invalid method name format: {method!r}")


def encode_password(username: str, password: str) -> str:
    """Encode password for Evon API.

    The x-elocs-password is computed as: Base64(SHA512(username + password))
    """
    combined = username + password
    sha512_hash = hashlib.sha512(combined.encode("utf-8")).digest()
    return base64.b64encode(sha512_hash).decode("utf-8")


def _validate_engine_id(engine_id: str) -> None:
    """Validate Engine ID format.

    Args:
        engine_id: The engine ID to validate

    Raises:
        ValueError: If the engine ID is invalid
    """
    if not engine_id:
        raise ValueError("Engine ID cannot be empty")
    if len(engine_id) < ENGINE_ID_MIN_LENGTH or len(engine_id) > ENGINE_ID_MAX_LENGTH:
        raise ValueError(f"Engine ID must be {ENGINE_ID_MIN_LENGTH}-{ENGINE_ID_MAX_LENGTH} characters")
    if not engine_id.isalnum():
        raise ValueError("Engine ID must contain only alphanumeric characters")


def build_base_url(host: str | None = None, engine_id: str | None = None) -> str:
    """Build the base URL for the Evon API.

    Args:
        host: The local Evon system URL (for local connections)
        engine_id: The Engine ID (for remote connections)

    Returns:
        The base URL for API requests

    Raises:
        ValueError: If neither host nor engine_id is provided, or if engine_id is invalid
    """
    if host:
        return host.rstrip("/")
    elif engine_id:
        _validate_engine_id(engine_id)
        return f"{EVON_REMOTE_HOST}/{engine_id}"
    else:
        raise ValueError("Either host or engine_id must be provided")


class EvonApiError(HomeAssistantError):
    """Exception for Evon API errors."""


class EvonAuthError(EvonApiError):
    """Exception for authentication errors."""


class EvonConnectionError(EvonApiError):
    """Exception for connection errors."""


class EvonApi:
    """Evon Smart Home API client."""

    def __init__(
        self,
        username: str,
        password: str,
        host: str | None = None,
        engine_id: str | None = None,
        session: aiohttp.ClientSession | None = None,
        password_is_encoded: bool = False,
    ) -> None:
        """Initialize the API client.

        Args:
            username: The username
            password: The password (plain text or pre-encoded)
            host: The Evon system URL (for local connections)
            engine_id: The Engine ID (for remote connections via my.evon-smarthome.com)
            session: Optional aiohttp session
            password_is_encoded: If True, password is already encoded (x-elocs-password).
                                If False (default), password will be encoded automatically.

        Note:
            Either host or engine_id must be provided, but not both.
            Local connections (host) are recommended for faster response times.
        """
        self._host = build_base_url(host=host, engine_id=engine_id)
        self._username = username
        if password_is_encoded:
            self._password = password
        else:
            self._password = encode_password(username, password)
        self._session = session
        self._token: str | None = None
        self._token_timestamp: float = 0.0
        self._token_lock = asyncio.Lock()
        self._own_session = False
        self._is_remote = engine_id is not None
        self._engine_id = engine_id

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session with proper SSL configuration."""
        if self._session is None:
            try:
                # Use explicit SSL context for secure HTTPS connections
                # Set a reasonable limit on concurrent connections
                connector = aiohttp.TCPConnector(
                    ssl=_create_ssl_context(),
                    limit=10,
                    limit_per_host=5,
                )
                self._session = aiohttp.ClientSession(connector=connector)
                self._own_session = True
            except Exception as err:
                raise EvonConnectionError(f"Failed to create HTTP session: {err}") from err
        return self._session

    async def close(self) -> None:
        """Close the session if we own it and clear sensitive data."""
        if self._own_session and self._session:
            await self._session.close()
            self._session = None
        # Clear token from memory for security
        self._token = None
        self._token_timestamp = 0.0

    async def login(self) -> str:
        """Login to Evon and get token."""
        session = await self._get_session()

        # Build headers - remote connections need additional headers
        headers = {
            "x-elocs-username": self._username,
            "x-elocs-password": self._password,
        }
        if self._is_remote and self._engine_id:
            headers["x-elocs-relayid"] = self._engine_id
            headers["x-elocs-sessionlogin"] = "true"
            headers["X-Requested-With"] = "XMLHttpRequest"

        # Remote login uses /login at the remote host root, not /{engine_id}/login
        login_url = f"{EVON_REMOTE_HOST}/login" if self._is_remote else f"{self._host}/login"

        try:
            # Disable auto-redirect following - we need to check the response headers
            # Use shorter timeout for login (should be fast)
            timeout = aiohttp.ClientTimeout(total=DEFAULT_LOGIN_TIMEOUT)
            async with session.post(
                login_url,
                headers=headers,
                allow_redirects=False,
                timeout=timeout,
            ) as response:
                _LOGGER.debug(
                    "Login response: status=%s, headers=%s",
                    response.status,
                    _redact_headers(dict(response.headers)),
                )

                # 302 redirect to login.html means auth failed
                if response.status == 302:
                    location = response.headers.get("Location", "")
                    # Only log the path portion, not full URL (security)
                    location_path = location.split("?")[0] if location else "unknown"
                    _LOGGER.debug("Login redirect detected to path: %s", location_path)
                    if "login" in location.lower():
                        raise EvonAuthError("Login failed: invalid credentials")
                    # Unexpected redirect - don't expose full URL in logs
                    _LOGGER.warning("Unexpected redirect during login")
                    raise EvonAuthError("Login failed: unexpected redirect")

                if response.status != 200:
                    raise EvonAuthError(f"Login failed: {response.status} {response.reason}")

                token = response.headers.get("x-elocs-token")
                if not token:
                    raise EvonAuthError("No token received from login")

                self._token = token
                self._token_timestamp = time.monotonic()
                return token

        except aiohttp.ClientError as err:
            raise EvonConnectionError(f"Connection error: {err}") from err

    def _is_token_expired(self) -> bool:
        """Check if the current token has expired based on TTL."""
        if not self._token:
            return True
        elapsed = time.monotonic() - self._token_timestamp
        return elapsed >= TOKEN_TTL_SECONDS

    async def _ensure_token(self) -> str:
        """Ensure we have a valid token.

        Uses a lock to prevent concurrent login attempts (race condition fix).

        Returns:
            The authentication token.

        Raises:
            EvonAuthError: If login fails and no token is available.
        """
        async with self._token_lock:
            if not self._token or self._is_token_expired():
                if self._is_token_expired() and self._token:
                    _LOGGER.debug("Token expired, refreshing")
                await self.login()
            # login() always sets self._token or raises an exception
            if self._token is None:
                raise EvonAuthError("Failed to obtain authentication token")
            return self._token

    async def _request(
        self,
        method: str,
        endpoint: str,
        data: Any | None = None,
        retry: bool = True,
    ) -> Any:
        """Make an API request."""
        token = await self._ensure_token()
        session = await self._get_session()

        url = f"{self._host}/api{endpoint}"
        headers = {
            "Cookie": f"token={token}",
            "Content-Type": "application/json",
        }

        try:
            timeout = aiohttp.ClientTimeout(total=DEFAULT_REQUEST_TIMEOUT)
            async with session.request(
                method,
                url,
                headers=headers,
                json=data,
                timeout=timeout,
            ) as response:
                # Handle auth errors with retry
                if response.status in (302, 401) and retry:
                    async with self._token_lock:
                        self._token = None
                        self._token_timestamp = 0.0
                    await self.login()
                    return await self._request(method, endpoint, data, retry=False)

                # Handle specific error status codes
                reason = response.reason or "Unknown"
                if response.status == 400:
                    raise EvonApiError(f"Bad request ({reason}): invalid data sent to {endpoint}")
                if response.status == 403:
                    raise EvonAuthError(f"Access forbidden ({reason}) - check user permissions")
                if response.status == 404:
                    raise EvonApiError(f"Resource not found ({reason}): {endpoint}")
                if response.status == 429:
                    raise EvonApiError(f"Rate limited ({reason}) - too many requests")
                if response.status in (500, 502, 503, 504):
                    raise EvonConnectionError(
                        f"Server error ({response.status} {reason}) - service may be temporarily unavailable"
                    )
                # Accept 200 OK, 201 Created, 204 No Content as success
                if response.status not in (200, 201, 204):
                    raise EvonApiError(f"API request failed: {response.status} {reason}")

                # 204 No Content has no body
                if response.status == 204:
                    return {}

                # Validate Content-Type header before parsing
                content_type = response.headers.get("Content-Type", "")
                if not content_type:
                    raise EvonApiError("Response missing Content-Type header")
                if "application/json" not in content_type.lower():
                    # Don't attempt to parse non-JSON responses (could be HTML error pages)
                    raise EvonApiError(f"Unexpected response type: {content_type} (expected application/json)")

                try:
                    return await response.json()
                except (ValueError, aiohttp.ContentTypeError) as err:
                    raise EvonApiError(f"Invalid JSON response: {err}") from err

        except aiohttp.ClientError as err:
            raise EvonConnectionError(f"Connection error: {err}") from err

    async def get_instances(self) -> list[dict[str, Any]]:
        """Get all instances."""
        result = await self._request("GET", "/instances")
        return result.get("data", [])

    async def get_instance(self, instance_id: str) -> dict[str, Any]:
        """Get a specific instance."""
        _validate_instance_id(instance_id)
        result = await self._request("GET", f"/instances/{instance_id}")
        return result.get("data", {})

    async def get_rooms(self, room_class: str = "System.Location.Room") -> dict[str, str]:
        """Get all rooms as a mapping of room_id -> room_name.

        Args:
            room_class: The class name for room instances (default: System.Location.Room)

        Returns:
            Dictionary mapping room IDs to room names
        """
        instances = await self.get_instances()
        rooms = {}
        for instance in instances:
            class_name = instance.get("ClassName", "")
            if class_name == room_class:
                room_id = instance.get("ID", "")
                room_name = instance.get("Name", "")
                # Only include rooms with valid ID and name
                # Skip template rooms (IDs starting with "System.Location")
                if room_id and room_name and not room_id.startswith("System.Location."):
                    rooms[room_id] = room_name
        return rooms

    async def call_method(self, instance_id: str, method: str, params: list | None = None) -> dict[str, Any]:
        """Call a method on an instance."""
        _validate_instance_id(instance_id)
        _validate_method_name(method)
        result = await self._request(
            "POST",
            f"/instances/{instance_id}/{method}",
            params or [],
        )
        return result

    # Light methods
    async def turn_on_light(self, instance_id: str) -> None:
        """Turn on a light."""
        await self.call_method(instance_id, "AmznTurnOn")

    async def turn_off_light(self, instance_id: str) -> None:
        """Turn off a light."""
        await self.call_method(instance_id, "AmznTurnOff")

    async def set_light_brightness(self, instance_id: str, brightness: int) -> None:
        """Set light brightness (0-100)."""
        await self.call_method(instance_id, "AmznSetBrightness", [brightness])

    # Blind methods
    async def open_blind(self, instance_id: str) -> None:
        """Open a blind (move up)."""
        await self.call_method(instance_id, "Open")

    async def close_blind(self, instance_id: str) -> None:
        """Close a blind (move down)."""
        await self.call_method(instance_id, "Close")

    async def stop_blind(self, instance_id: str) -> None:
        """Stop a blind."""
        await self.call_method(instance_id, "Stop")

    async def set_blind_position(self, instance_id: str, position: int) -> None:
        """Set blind position (0=open, 100=closed)."""
        await self.call_method(instance_id, "AmznSetPercentage", [position])

    async def set_blind_tilt(self, instance_id: str, angle: int) -> None:
        """Set blind tilt angle (0-100)."""
        await self.call_method(instance_id, "SetAngle", [angle])

    # Climate methods
    async def set_climate_comfort_mode(self, instance_id: str) -> None:
        """Set climate to comfort (day) mode."""
        await self.call_method(instance_id, "WriteDayMode")

    async def set_climate_energy_saving_mode(self, instance_id: str) -> None:
        """Set climate to energy saving (night) mode."""
        await self.call_method(instance_id, "WriteNightMode")

    async def set_climate_freeze_protection_mode(self, instance_id: str) -> None:
        """Set climate to freeze protection mode."""
        await self.call_method(instance_id, "WriteFreezeMode")

    async def set_climate_temperature(self, instance_id: str, temperature: float) -> None:
        """Set climate target temperature."""
        await self.call_method(instance_id, "WriteCurrentSetTemperature", [temperature])

    # Switch methods
    async def turn_on_switch(self, instance_id: str) -> None:
        """Turn on a switch."""
        await self.call_method(instance_id, "AmznTurnOn")

    async def turn_off_switch(self, instance_id: str) -> None:
        """Turn off a switch."""
        await self.call_method(instance_id, "AmznTurnOff")

    # Home state methods
    async def get_home_states(self, home_state_class: str = "System.HomeState") -> list[dict[str, Any]]:
        """Get all home states.

        Args:
            home_state_class: The class name for home state instances

        Returns:
            List of home state dictionaries with id, name, and active status
        """
        instances = await self.get_instances()
        home_states = []
        for instance in instances:
            class_name = instance.get("ClassName", "")
            instance_id = instance.get("ID", "")
            # Skip template instances
            if class_name == home_state_class and not instance_id.startswith("System."):
                # Get detailed info to check active status
                details = await self.get_instance(instance_id)
                home_states.append(
                    {
                        "id": instance_id,
                        "name": instance.get("Name", instance_id),
                        "active": details.get("Active", False),
                    }
                )
        return home_states

    async def get_active_home_state(self) -> str | None:
        """Get the currently active home state ID."""
        home_states = await self.get_home_states()
        for state in home_states:
            if state.get("active"):
                return state.get("id")
        return None

    async def activate_home_state(self, instance_id: str) -> None:
        """Activate a home state."""
        await self.call_method(instance_id, "Activate")

    # Bathroom radiator methods
    async def toggle_bathroom_radiator(self, instance_id: str) -> None:
        """Toggle a bathroom radiator (electric heater) on/off.

        This uses the Switch method which toggles the current state.
        If off, turns on for the configured duration (default 30 min).
        If on, turns off immediately.
        """
        await self.call_method(instance_id, "Switch")

    async def get_bathroom_radiators(self, radiator_class: str = "Heating.BathroomRadiator") -> list[dict[str, Any]]:
        """Get all bathroom radiators with their current state.

        Returns:
            List of radiator dictionaries with id, name, is_on, time_remaining, etc.
        """
        instances = await self.get_instances()
        radiators = []
        for instance in instances:
            class_name = instance.get("ClassName", "")
            if class_name == radiator_class:
                instance_id = instance.get("ID", "")
                details = await self.get_instance(instance_id)
                radiators.append(
                    {
                        "id": instance_id,
                        "name": instance.get("Name", instance_id),
                        "is_on": details.get("Output", False),
                        "time_remaining": details.get("NextSwitchPoint", -1),
                        "duration_mins": details.get("EnableForMins", 30),
                    }
                )
        return radiators

    # Scene methods
    async def execute_scene(self, instance_id: str) -> None:
        """Execute an Evon scene."""
        await self.call_method(instance_id, "Execute")

    # Season mode methods (global heating/cooling)
    async def get_season_mode(self) -> bool:
        """Get the current season mode.

        Returns:
            True if cooling (summer), False if heating (winter)
        """
        details = await self.get_instance("Base.ehThermostat")
        return details.get("IsCool", False)

    async def set_season_mode(self, is_cooling: bool) -> None:
        """Set the global season mode.

        Args:
            is_cooling: True for cooling (summer), False for heating (winter)
        """
        await self._request(
            "PUT",
            "/instances/Base.ehThermostat/IsCool",
            {"value": is_cooling},
        )

    async def test_connection(self) -> bool:
        """Test the connection to the Evon system."""
        try:
            await self.login()
            await self.get_instances()
            return True
        except EvonAuthError:
            raise  # Re-raise auth errors to be handled by caller
        except EvonConnectionError:
            return False
        except EvonApiError:
            return False
        except aiohttp.ClientError as err:
            raise EvonConnectionError(f"Connection error: {err}") from err
        except TimeoutError as err:
            raise EvonConnectionError(f"Connection timeout: {err}") from err
