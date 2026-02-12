"""Evon Smart Home API client."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import logging
import re
import ssl
import time
from typing import TYPE_CHECKING, Any

import aiohttp
from homeassistant.exceptions import HomeAssistantError

if TYPE_CHECKING:
    from .ws_client import EvonWsClient

from .const import (
    DEFAULT_BATHROOM_RADIATOR_DURATION,
    DEFAULT_CONNECTION_POOL_SIZE,
    DEFAULT_LOGIN_TIMEOUT,
    DEFAULT_REQUEST_TIMEOUT,
    ENGINE_ID_MAX_LENGTH,
    ENGINE_ID_MIN_LENGTH,
    EVON_REMOTE_HOST,
    IMAGE_FETCH_TIMEOUT,
    LOGIN_BACKOFF_BASE,
    LOGIN_MAX_BACKOFF,
)

_LOGGER = logging.getLogger(__name__)

# Token TTL in seconds (refresh token after this time).
# The HA integration refreshes aggressively (1 hour) since it maintains a persistent
# connection and can re-login cheaply. The MCP server uses a longer TTL (27 days)
# because it starts fresh each session and tokens are valid for ~30 days on the Evon API.
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


class EvonWsError(EvonApiError):
    """Exception for WebSocket errors."""


class EvonWsNotConnectedError(EvonWsError):
    """Exception raised when WebSocket is not connected."""


class EvonWsTimeoutError(EvonWsError):
    """Exception raised when WebSocket request times out."""


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

        # Login rate limiting
        self._login_failure_count: int = 0
        self._login_backoff_until: float = 0.0

        # WebSocket control support
        self._ws_client: EvonWsClient | None = None
        self._instance_classes: dict[str, str] = {}  # ID → ClassName cache
        self._blind_angles: dict[str, int] = {}  # ID → current Angle cache for WS control
        self._blind_positions: dict[str, int] = {}  # ID → current Position cache for WS control

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session with proper SSL configuration."""
        # Check if session is None or closed (e.g., by HA shutdown)
        if self._session is None or self._session.closed:
            try:
                # Use explicit SSL context for secure HTTPS connections
                # Set a reasonable limit on concurrent connections
                connector = aiohttp.TCPConnector(
                    ssl=_create_ssl_context(),
                    limit=DEFAULT_CONNECTION_POOL_SIZE,
                    limit_per_host=DEFAULT_CONNECTION_POOL_SIZE // 2,
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
        # Clear all sensitive data from memory for security
        self._token = None
        self._token_timestamp = 0.0
        self._username = ""
        self._password = ""
        # Clear caches
        self._instance_classes = {}
        self._blind_angles = {}
        self._blind_positions = {}
        # Reset login rate limiting
        self._login_failure_count = 0
        self._login_backoff_until = 0.0

    def set_ws_client(self, ws_client: EvonWsClient | None) -> None:
        """Set the WebSocket client for control operations.

        Args:
            ws_client: The WebSocket client, or None to disable WS control.
        """
        self._ws_client = ws_client

    def set_instance_classes(self, instances: list[dict[str, Any]]) -> None:
        """Cache instance class names for WebSocket routing.

        Args:
            instances: List of instance dictionaries with ID and ClassName.
        """
        self._instance_classes = {i.get("ID", ""): i.get("ClassName", "") for i in instances if i.get("ID")}

    def update_blind_angle(self, instance_id: str, angle: int) -> None:
        """Update cached blind angle for WebSocket position control.

        Args:
            instance_id: The blind instance ID.
            angle: The current angle (0-100).
        """
        self._blind_angles[instance_id] = angle

    def get_blind_angle(self, instance_id: str) -> int | None:
        """Get cached blind angle.

        Args:
            instance_id: The blind instance ID.

        Returns:
            The cached angle, or None if not cached.
        """
        return self._blind_angles.get(instance_id)

    def update_blind_position(self, instance_id: str, position: int) -> None:
        """Update cached blind position for WebSocket tilt control.

        Args:
            instance_id: The blind instance ID.
            position: The current position (0-100, 0=open, 100=closed).
        """
        self._blind_positions[instance_id] = position

    def get_blind_position(self, instance_id: str) -> int | None:
        """Get cached blind position.

        Args:
            instance_id: The blind instance ID.

        Returns:
            The cached position, or None if not cached.
        """
        return self._blind_positions.get(instance_id)

    async def login(self) -> str:
        """Login to Evon and get token."""
        # Check login rate limiting backoff
        now = time.monotonic()
        if now < self._login_backoff_until:
            wait = self._login_backoff_until - now
            raise EvonAuthError(f"Login rate limited: too many failures, retry in {wait:.0f}s")

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
                        self._increment_login_backoff()
                        raise EvonAuthError("Login failed: Invalid credentials")
                    # Unexpected redirect - don't expose full URL in logs
                    _LOGGER.warning("Unexpected redirect during login")
                    self._increment_login_backoff()
                    raise EvonAuthError("Login failed: Unexpected redirect")

                if response.status != 200:
                    self._increment_login_backoff()
                    raise EvonAuthError(f"Login failed: {response.status} {response.reason}")

                token = response.headers.get("x-elocs-token")
                if not token:
                    raise EvonAuthError("No token received from login")

                self._token = token
                self._token_timestamp = time.monotonic()
                # Reset backoff on successful login
                self._login_failure_count = 0
                self._login_backoff_until = 0.0
                return token

        except aiohttp.ClientError as err:
            raise EvonConnectionError(f"Connection error: {err}") from err

    def _increment_login_backoff(self) -> None:
        """Increment login failure count and set exponential backoff."""
        self._login_failure_count += 1
        backoff = min(LOGIN_BACKOFF_BASE**self._login_failure_count, LOGIN_MAX_BACKOFF)
        self._login_backoff_until = time.monotonic() + backoff
        _LOGGER.warning(
            "Login failed (%d consecutive), backing off for %ds",
            self._login_failure_count,
            backoff,
        )

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
            "X-Requested-With": "XMLHttpRequest",
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
        """Call a method on an instance.

        Tries WebSocket first if available, falls back to HTTP.
        """
        _validate_instance_id(instance_id)
        _validate_method_name(method)

        # Try WebSocket first if available (faster, real-time)
        ws_attempted = False
        if self._ws_client and self._ws_client.is_connected:
            ws_attempted = True
            _LOGGER.debug("Attempting WS control for %s.%s", instance_id, method)
            if await self._try_ws_control(instance_id, method, params):
                _LOGGER.debug("WS control succeeded for %s.%s", instance_id, method)
                return {}
            _LOGGER.debug("WS control failed/unavailable, falling back to HTTP")

        # Fall back to HTTP - translate canonical WS-native name to HTTP name
        from .ws_control import get_http_method_name

        http_method = get_http_method_name(method)
        _LOGGER.debug("HTTP control: POST /instances/%s/%s %s", instance_id, http_method, params or [])
        result = await self._request(
            "POST",
            f"/instances/{instance_id}/{http_method}",
            params or [],
        )

        # Log warning if WS was attempted but failed (helps diagnose WS issues)
        if ws_attempted:
            _LOGGER.warning(
                "WebSocket control failed for %s.%s, HTTP fallback succeeded. "
                "Consider checking WebSocket connection or device support.",
                instance_id,
                method,
            )

        return result

    async def _try_ws_control(
        self,
        instance_id: str,
        method: str,
        params: list | None,
    ) -> bool:
        """Try to execute control via WebSocket.

        Args:
            instance_id: The instance ID.
            method: The method name.
            params: Optional parameters.

        Returns:
            True if WebSocket control succeeded, False otherwise.
        """
        from .ws_control import get_ws_control_mapping

        class_name = self._instance_classes.get(instance_id, "")
        if not class_name:
            _LOGGER.debug("WS control: No class found for instance %s, using HTTP", instance_id)
            return False

        # Special handling for blind position/tilt - use MoveToPosition with cached values
        if self._is_blind_class(class_name):
            if method == "SetPosition" and params:
                # Set position: MoveToPosition([cached_angle, new_position])
                cached_angle = self.get_blind_angle(instance_id)
                if cached_angle is None:
                    _LOGGER.debug("WS control: No cached angle for blind %s, using HTTP", instance_id)
                    return False
                new_position = params[0]
                _LOGGER.debug(
                    "WS control: CallMethod %s.MoveToPosition([%s, %s]) (class: %s)",
                    instance_id,
                    cached_angle,
                    new_position,
                    class_name,
                )
                result = await self._ws_client.call_method(  # type: ignore[union-attr]
                    instance_id, "MoveToPosition", [cached_angle, new_position], False
                )
                _LOGGER.debug("WS control: MoveToPosition result = %s", result)
                return result

            if method == "SetAngle" and params:
                # Set tilt: MoveToPosition([new_angle, cached_position])
                cached_position = self.get_blind_position(instance_id)
                if cached_position is None:
                    _LOGGER.debug("WS control: No cached position for blind %s, using HTTP", instance_id)
                    return False
                new_angle = params[0]
                _LOGGER.debug(
                    "WS control: CallMethod %s.MoveToPosition([%s, %s]) (class: %s)",
                    instance_id,
                    new_angle,
                    cached_position,
                    class_name,
                )
                result = await self._ws_client.call_method(  # type: ignore[union-attr]
                    instance_id, "MoveToPosition", [new_angle, cached_position], False
                )
                _LOGGER.debug("WS control: MoveToPosition result = %s", result)
                return result

        mapping = get_ws_control_mapping(class_name, method)
        if not mapping:
            _LOGGER.debug("WS control: No mapping for %s.%s, using HTTP", class_name, method)
            return False

        if mapping.property_name:
            # SetValue operation
            value = mapping.get_value(params)
            _LOGGER.debug(
                "WS control: SetValue %s.%s = %s (class: %s)", instance_id, mapping.property_name, value, class_name
            )
            result = await self._ws_client.set_value(  # type: ignore[union-attr]
                instance_id, mapping.property_name, value
            )
            _LOGGER.debug("WS control: SetValue result = %s", result)
            return result
        else:
            # CallMethod operation - use get_value to transform params if needed
            method_params = mapping.get_value(params)
            _LOGGER.debug(
                "WS control: CallMethod %s.%s(%s) (class: %s, fire_and_forget: %s)",
                instance_id,
                mapping.method_name,
                method_params,
                class_name,
                mapping.fire_and_forget,
            )
            result = await self._ws_client.call_method(  # type: ignore[union-attr]
                instance_id, mapping.method_name, method_params, mapping.fire_and_forget
            )
            _LOGGER.debug("WS control: CallMethod result = %s", result)
            return result

    def _is_blind_class(self, class_name: str) -> bool:
        """Check if a class name is a blind class.

        Args:
            class_name: The class name to check.

        Returns:
            True if it's a blind class, False otherwise.
        """
        from .const import EVON_CLASS_BLIND, EVON_CLASS_BLIND_GROUP

        blind_classes = {
            EVON_CLASS_BLIND,
            EVON_CLASS_BLIND_GROUP,
            "Base.bBlind",
            "Base.ehBlind",
        }
        return class_name in blind_classes

    # Light methods
    async def turn_on_light(self, instance_id: str) -> None:
        """Turn on a light."""
        await self.call_method(instance_id, "SwitchOn")

    async def turn_off_light(self, instance_id: str) -> None:
        """Turn off a light."""
        await self.call_method(instance_id, "SwitchOff")

    async def set_light_brightness(self, instance_id: str, brightness: int) -> None:
        """Set light brightness (0-100)."""
        brightness = max(0, min(100, int(brightness)))
        await self.call_method(instance_id, "BrightnessSetScaled", [brightness])

    async def set_light_color_temp(self, instance_id: str, kelvin: int) -> None:
        """Set light color temperature (in Kelvin)."""
        await self.call_method(instance_id, "SetColorTemp", [kelvin])

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

    async def open_all_blinds(self) -> None:
        """Open all blinds (for blind groups)."""
        await self.call_method("Base.bBlind", "OpenAll", [None])

    async def close_all_blinds(self) -> None:
        """Close all blinds (for blind groups)."""
        await self.call_method("Base.bBlind", "CloseAll", [None])

    async def stop_all_blinds(self) -> None:
        """Stop all blinds (for blind groups)."""
        await self.call_method("Base.bBlind", "StopAll", [None])

    async def set_blind_position(self, instance_id: str, position: int) -> None:
        """Set blind position (0=open, 100=closed)."""
        position = max(0, min(100, int(position)))
        await self.call_method(instance_id, "SetPosition", [position])

    async def set_blind_tilt(self, instance_id: str, angle: int) -> None:
        """Set blind tilt angle (0-100)."""
        angle = max(0, min(100, int(angle)))
        await self.call_method(instance_id, "SetAngle", [angle])

    # Climate methods
    async def set_climate_comfort_mode(self, instance_id: str) -> None:
        """Set climate to comfort (day) mode.

        Args:
            instance_id: The climate instance ID.
        """
        await self.call_method(instance_id, "WriteDayMode")

    async def set_climate_energy_saving_mode(self, instance_id: str) -> None:
        """Set climate to energy saving (night) mode.

        Args:
            instance_id: The climate instance ID.
        """
        await self.call_method(instance_id, "WriteNightMode")

    async def set_climate_freeze_protection_mode(self, instance_id: str) -> None:
        """Set climate to freeze/heat protection mode.

        In heating mode (winter): freeze protection prevents pipes from freezing.
        In cooling mode (summer): heat protection prevents overheating.

        Args:
            instance_id: The climate instance ID.
        """
        await self.call_method(instance_id, "WriteFreezeMode")

    async def set_climate_temperature(self, instance_id: str, temperature: float) -> None:
        """Set climate target temperature."""
        temperature = round(float(temperature), 1)
        await self.call_method(instance_id, "WriteCurrentSetTemperature", [temperature])

    # Group climate methods (all thermostats at once)
    async def all_climate_comfort(self) -> None:
        """Set all climate controls to comfort (day) mode."""
        await self.call_method("Base.ehThermostat", "AllDayMode")

    async def all_climate_eco(self) -> None:
        """Set all climate controls to eco (night/energy saving) mode."""
        await self.call_method("Base.ehThermostat", "AllNightMode")

    async def all_climate_away(self) -> None:
        """Set all climate controls to away (freeze/heat protection) mode.

        In heating mode (winter): freeze protection prevents pipes from freezing.
        In cooling mode (summer): heat protection prevents overheating.
        """
        await self.call_method("Base.ehThermostat", "AllFreezeMode")

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

    async def turn_on_bathroom_radiator(self, instance_id: str) -> None:
        """Turn on a bathroom radiator for one heating cycle.

        Uses SwitchOneTime method (verified working January 2025).
        This is idempotent - calling when already on restarts the timer.
        """
        await self.call_method(instance_id, "SwitchOneTime")

    async def turn_off_bathroom_radiator(self, instance_id: str) -> None:
        """Turn off a bathroom radiator.

        Uses Switch (toggle) because SwitchOff is acknowledged by the controller
        but has no effect on bathroom radiators.

        Caller responsibility: the caller MUST verify the radiator is currently on
        before calling this method. If called when already off, the toggle will
        turn it ON instead. See EvonBathroomRadiatorSwitch.async_turn_off() for
        the state-check and double-tap guard logic.
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
                        "duration_mins": details.get("EnableForMins", DEFAULT_BATHROOM_RADIATOR_DURATION),
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
        is_cool = details.get("IsCool")

        # Validate the response - IsCool should be a boolean
        if is_cool is None:
            _LOGGER.warning("Season mode response missing 'IsCool' field, defaulting to heating mode")
            return False

        if not isinstance(is_cool, bool):
            _LOGGER.warning(
                "Season mode 'IsCool' has unexpected type %s (value: %s), attempting to interpret as boolean",
                type(is_cool).__name__,
                is_cool,
            )
            # Try to interpret common values as boolean
            if is_cool in (0, "0", "false", "False", "no", "No"):
                return False
            if is_cool in (1, "1", "true", "True", "yes", "Yes"):
                return True
            # Unknown value, default to heating
            _LOGGER.warning("Could not interpret season mode value, defaulting to heating mode")
            return False

        return is_cool

    async def set_season_mode(self, is_cooling: bool) -> None:
        """Set the global season mode.

        Tries WebSocket first if available, falls back to HTTP PUT.

        Args:
            is_cooling: True for cooling (summer), False for heating (winter)
        """
        # Try WebSocket first if available
        ws_attempted = self._ws_client and self._ws_client.is_connected
        if ws_attempted:
            _LOGGER.debug("WS control: SetValue Base.ehThermostat.IsCool = %s", is_cooling)
            result = await self._ws_client.set_value("Base.ehThermostat", "IsCool", is_cooling)  # type: ignore[union-attr]
            _LOGGER.debug("WS control: SetValue result = %s", result)
            if result:
                return

        # Fall back to HTTP PUT
        await self._request(
            "PUT",
            "/instances/Base.ehThermostat/IsCool",
            {"value": is_cooling},
        )

        # Log warning if WS was attempted but failed
        if ws_attempted:
            _LOGGER.warning("WebSocket control failed for Base.ehThermostat.IsCool, HTTP fallback succeeded.")

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

    async def fetch_image(self, image_path: str) -> bytes | None:
        """Fetch an image from the Evon server.

        This method handles authentication and fetches images from paths
        like /temp/image.jpg that are returned by camera entities.

        Args:
            image_path: The image path (e.g., "/temp/image.jpg")

        Returns:
            The image bytes, or None if fetch failed
        """
        try:
            url = f"{self._host}{image_path}"
            token = await self._ensure_token()
            session = await self._get_session()
            cookies = {"token": token}
            timeout = aiohttp.ClientTimeout(total=IMAGE_FETCH_TIMEOUT)

            async with session.get(url, cookies=cookies, timeout=timeout) as resp:
                if resp.status == 200:
                    return await resp.read()
                _LOGGER.debug("Failed to fetch image: HTTP %d", resp.status)
        except aiohttp.ClientError as err:
            _LOGGER.debug("Failed to fetch image: %s", err)
        except EvonConnectionError:
            _LOGGER.debug("Failed to fetch image: session error")
        except Exception as err:
            _LOGGER.warning("Unexpected error fetching image: %s", err)
        return None
