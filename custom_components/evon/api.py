"""Evon Smart Home API client."""
from __future__ import annotations

import base64
import hashlib
import logging
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)


def encode_password(username: str, password: str) -> str:
    """Encode password for Evon API.

    The x-elocs-password is computed as: Base64(SHA512(username + password))
    """
    combined = username + password
    sha512_hash = hashlib.sha512(combined.encode("utf-8")).digest()
    return base64.b64encode(sha512_hash).decode("utf-8")


class EvonApiError(Exception):
    """Exception for Evon API errors."""


class EvonAuthError(EvonApiError):
    """Exception for authentication errors."""


class EvonApi:
    """Evon Smart Home API client."""

    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        session: aiohttp.ClientSession | None = None,
        password_is_encoded: bool = False,
    ) -> None:
        """Initialize the API client.

        Args:
            host: The Evon system URL
            username: The username
            password: The password (plain text or pre-encoded)
            session: Optional aiohttp session
            password_is_encoded: If True, password is already encoded (x-elocs-password).
                                If False (default), password will be encoded automatically.
        """
        self._host = host.rstrip("/")
        self._username = username
        if password_is_encoded:
            self._password = password
        else:
            self._password = encode_password(username, password)
        self._session = session
        self._token: str | None = None
        self._own_session = False

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None:
            self._session = aiohttp.ClientSession()
            self._own_session = True
        return self._session

    async def close(self) -> None:
        """Close the session if we own it."""
        if self._own_session and self._session:
            await self._session.close()
            self._session = None

    async def login(self) -> str:
        """Login to Evon and get token."""
        session = await self._get_session()

        try:
            async with session.post(
                f"{self._host}/login",
                headers={
                    "x-elocs-username": self._username,
                    "x-elocs-password": self._password,
                },
            ) as response:
                if response.status != 200:
                    raise EvonAuthError(
                        f"Login failed: {response.status} {response.reason}"
                    )

                token = response.headers.get("x-elocs-token")
                if not token:
                    raise EvonAuthError("No token received from login")

                self._token = token
                return token

        except aiohttp.ClientError as err:
            raise EvonApiError(f"Connection error: {err}") from err

    async def _ensure_token(self) -> str:
        """Ensure we have a valid token."""
        if not self._token:
            await self.login()
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
            async with session.request(
                method,
                url,
                headers=headers,
                json=data,
            ) as response:
                # Handle auth errors with retry
                if response.status in (302, 401) and retry:
                    self._token = None
                    await self.login()
                    return await self._request(method, endpoint, data, retry=False)

                if response.status != 200:
                    raise EvonApiError(f"API request failed: {response.status}")

                try:
                    return await response.json()
                except (ValueError, aiohttp.ContentTypeError) as err:
                    raise EvonApiError(f"Invalid JSON response: {err}") from err

        except aiohttp.ClientError as err:
            raise EvonApiError(f"Connection error: {err}") from err

    async def get_instances(self) -> list[dict[str, Any]]:
        """Get all instances."""
        result = await self._request("GET", "/instances")
        return result.get("data", [])

    async def get_instance(self, instance_id: str) -> dict[str, Any]:
        """Get a specific instance."""
        result = await self._request("GET", f"/instances/{instance_id}")
        return result.get("data", {})

    async def call_method(
        self, instance_id: str, method: str, params: list | None = None
    ) -> dict[str, Any]:
        """Call a method on an instance."""
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
        await self.call_method(instance_id, "MoveUp")

    async def close_blind(self, instance_id: str) -> None:
        """Close a blind (move down)."""
        await self.call_method(instance_id, "MoveDown")

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

    async def set_climate_temperature(
        self, instance_id: str, temperature: float
    ) -> None:
        """Set climate target temperature."""
        await self.call_method(instance_id, "WriteCurrentSetTemperature", [temperature])

    # Switch methods
    async def turn_on_switch(self, instance_id: str) -> None:
        """Turn on a switch."""
        await self.call_method(instance_id, "AmznTurnOn")

    async def turn_off_switch(self, instance_id: str) -> None:
        """Turn off a switch."""
        await self.call_method(instance_id, "AmznTurnOff")

    async def test_connection(self) -> bool:
        """Test the connection to the Evon system."""
        try:
            await self.login()
            await self.get_instances()
            return True
        except EvonAuthError:
            raise  # Re-raise auth errors to be handled by caller
        except EvonApiError:
            return False
        except Exception as err:
            # Wrap any unexpected errors
            raise EvonApiError(f"Unexpected error: {err}") from err
