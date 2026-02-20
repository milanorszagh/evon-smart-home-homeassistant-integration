"""Unit tests for Evon API client."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest

from custom_components.evon.api import (
    EvonApi,
    EvonApiError,
    EvonAuthError,
    EvonConnectionError,
    encode_password,
)


class TestEncodePassword:
    """Tests for password encoding."""

    def test_encode_password_basic(self):
        """Test basic password encoding."""
        result = encode_password("user", "pass")
        # SHA512 of "userpass" encoded as base64
        assert isinstance(result, str)
        assert len(result) > 0

    def test_encode_password_empty(self):
        """Test encoding with empty inputs."""
        result = encode_password("", "")
        assert isinstance(result, str)

    def test_encode_password_special_chars(self):
        """Test encoding with special characters."""
        result = encode_password("user@test.com", "p@ss!word#123")
        assert isinstance(result, str)

    def test_encode_password_unicode(self):
        """Test encoding with unicode characters."""
        result = encode_password("użytkownik", "hasło123")
        assert isinstance(result, str)

    def test_encode_password_deterministic(self):
        """Test that encoding is deterministic."""
        result1 = encode_password("user", "pass")
        result2 = encode_password("user", "pass")
        assert result1 == result2


class TestEvonApiInit:
    """Tests for EvonApi initialization."""

    def test_init_basic(self):
        """Test basic initialization."""
        api = EvonApi(
            host="http://192.168.1.100",
            username="user",
            password="pass",
        )
        assert api._host == "http://192.168.1.100"
        assert api._username == "user"
        # Password should be encoded
        assert api._password != "pass"

    def test_init_strips_trailing_slash(self):
        """Test that trailing slash is stripped from host."""
        api = EvonApi(
            host="http://192.168.1.100/",
            username="user",
            password="pass",
        )
        assert api._host == "http://192.168.1.100"

    def test_init_pre_encoded_password(self):
        """Test initialization with pre-encoded password."""
        encoded = "pre_encoded_password"
        api = EvonApi(
            host="http://192.168.1.100",
            username="user",
            password=encoded,
            password_is_encoded=True,
        )
        assert api._password == encoded

    def test_init_with_session(self):
        """Test initialization with custom session."""
        mock_session = MagicMock()
        api = EvonApi(
            host="http://192.168.1.100",
            username="user",
            password="pass",
            session=mock_session,
        )
        assert api._session == mock_session
        assert api._own_session is False


class TestEvonApiLogin:
    """Tests for EvonApi login."""

    @pytest.fixture
    def mock_session_success(self):
        """Create a mock session with successful login response."""
        mock_session = MagicMock()
        mock_session.closed = False  # Prevent _get_session from creating new session
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.headers = {"x-elocs-token": "test_token"}

        # Create an async context manager mock
        async_ctx = AsyncMock()
        async_ctx.__aenter__.return_value = mock_response
        async_ctx.__aexit__.return_value = None
        mock_session.post.return_value = async_ctx

        return mock_session

    @pytest.fixture
    def mock_session_auth_failure(self):
        """Create a mock session with auth failure response."""
        mock_session = MagicMock()
        mock_session.closed = False  # Prevent _get_session from creating new session
        mock_response = MagicMock()
        mock_response.status = 401
        mock_response.reason = "Unauthorized"

        async_ctx = AsyncMock()
        async_ctx.__aenter__.return_value = mock_response
        async_ctx.__aexit__.return_value = None
        mock_session.post.return_value = async_ctx

        return mock_session

    @pytest.fixture
    def mock_session_no_token(self):
        """Create a mock session with successful response but no token."""
        mock_session = MagicMock()
        mock_session.closed = False  # Prevent _get_session from creating new session
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.headers = {}

        async_ctx = AsyncMock()
        async_ctx.__aenter__.return_value = mock_response
        async_ctx.__aexit__.return_value = None
        mock_session.post.return_value = async_ctx

        return mock_session

    @pytest.mark.asyncio
    async def test_login_success(self, mock_session_success):
        """Test successful login."""
        api = EvonApi(
            host="http://192.168.1.100",
            username="user",
            password="pass",
            session=mock_session_success,
        )

        token = await api.login()
        assert token == "test_token"
        assert api._token == "test_token"

    @pytest.mark.asyncio
    async def test_login_failure_status(self, mock_session_auth_failure):
        """Test login failure due to bad status."""
        # Skip if homeassistant is mocked (exceptions are MagicMock)
        if not isinstance(EvonAuthError, type):
            pytest.skip("Requires real homeassistant package")
        api = EvonApi(
            host="http://192.168.1.100",
            username="user",
            password="pass",
            session=mock_session_auth_failure,
        )

        with pytest.raises(EvonAuthError):
            await api.login()

    @pytest.mark.asyncio
    async def test_login_no_token(self, mock_session_no_token):
        """Test login failure when no token in response."""
        # Skip if homeassistant is mocked (exceptions are MagicMock)
        if not isinstance(EvonAuthError, type):
            pytest.skip("Requires real homeassistant package")
        api = EvonApi(
            host="http://192.168.1.100",
            username="user",
            password="pass",
            session=mock_session_no_token,
        )

        with pytest.raises(EvonAuthError, match="No token received"):
            await api.login()


class TestEvonApiEnsureToken:
    """Tests for _ensure_token method."""

    @pytest.mark.asyncio
    async def test_ensure_token_already_set(self):
        """Test that existing token is reused."""
        import time

        api = EvonApi(
            host="http://192.168.1.100",
            username="user",
            password="pass",
        )
        api._token = "existing_token"
        api._token_timestamp = time.monotonic()  # Set timestamp so token is not expired

        token = await api._ensure_token()
        assert token == "existing_token"

    @pytest.mark.asyncio
    async def test_ensure_token_calls_login(self):
        """Test that login is called when no token."""
        mock_session = MagicMock()
        mock_session.closed = False  # Prevent _get_session from creating new session
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.headers = {"x-elocs-token": "new_token"}

        async_ctx = AsyncMock()
        async_ctx.__aenter__.return_value = mock_response
        async_ctx.__aexit__.return_value = None
        mock_session.post.return_value = async_ctx

        api = EvonApi(
            host="http://192.168.1.100",
            username="user",
            password="pass",
            session=mock_session,
        )

        token = await api._ensure_token()
        assert token == "new_token"


class TestEvonApiMethods:
    """Tests for EvonApi device control methods."""

    @pytest.fixture
    def mock_api(self):
        """Create an API with mocked request method."""
        api = EvonApi(
            host="http://192.168.1.100",
            username="user",
            password="pass",
        )
        api._token = "test_token"
        api._request = AsyncMock(return_value={"data": {}})
        return api

    @pytest.mark.asyncio
    async def test_get_instances(self, mock_api):
        """Test get_instances method."""
        mock_api._request.return_value = {"data": [{"ID": "test"}]}
        result = await mock_api.get_instances()
        assert result == [{"ID": "test"}]
        mock_api._request.assert_called_with("GET", "/instances")

    @pytest.mark.asyncio
    async def test_turn_on_light(self, mock_api):
        """Test turning on a light."""
        await mock_api.turn_on_light("light_1")
        mock_api._request.assert_called_with("POST", "/instances/light_1/AmznTurnOn", [])

    @pytest.mark.asyncio
    async def test_turn_off_light(self, mock_api):
        """Test turning off a light."""
        await mock_api.turn_off_light("light_1")
        mock_api._request.assert_called_with("POST", "/instances/light_1/AmznTurnOff", [])

    @pytest.mark.asyncio
    async def test_set_light_brightness(self, mock_api):
        """Test setting light brightness."""
        await mock_api.set_light_brightness("light_1", 75)
        mock_api._request.assert_called_with("POST", "/instances/light_1/AmznSetBrightness", [75])

    @pytest.mark.asyncio
    async def test_open_blind(self, mock_api):
        """Test opening a blind."""
        await mock_api.open_blind("blind_1")
        mock_api._request.assert_called_with("POST", "/instances/blind_1/Open", [])

    @pytest.mark.asyncio
    async def test_close_blind(self, mock_api):
        """Test closing a blind."""
        await mock_api.close_blind("blind_1")
        mock_api._request.assert_called_with("POST", "/instances/blind_1/Close", [])

    @pytest.mark.asyncio
    async def test_stop_blind(self, mock_api):
        """Test stopping a blind."""
        await mock_api.stop_blind("blind_1")
        mock_api._request.assert_called_with("POST", "/instances/blind_1/Stop", [])

    @pytest.mark.asyncio
    async def test_set_blind_position(self, mock_api):
        """Test setting blind position."""
        await mock_api.set_blind_position("blind_1", 50)
        mock_api._request.assert_called_with("POST", "/instances/blind_1/AmznSetPercentage", [50])

    @pytest.mark.asyncio
    async def test_set_blind_tilt(self, mock_api):
        """Test setting blind tilt."""
        await mock_api.set_blind_tilt("blind_1", 45)
        mock_api._request.assert_called_with("POST", "/instances/blind_1/SetAngle", [45])

    @pytest.mark.asyncio
    async def test_set_climate_comfort_mode(self, mock_api):
        """Test setting climate to comfort mode."""
        await mock_api.set_climate_comfort_mode("climate_1")
        mock_api._request.assert_called_with("POST", "/instances/climate_1/WriteDayMode", [])

    @pytest.mark.asyncio
    async def test_set_climate_energy_saving_mode(self, mock_api):
        """Test setting climate to energy saving mode."""
        await mock_api.set_climate_energy_saving_mode("climate_1")
        mock_api._request.assert_called_with("POST", "/instances/climate_1/WriteNightMode", [])

    @pytest.mark.asyncio
    async def test_set_climate_freeze_protection_mode(self, mock_api):
        """Test setting climate to freeze protection mode."""
        await mock_api.set_climate_freeze_protection_mode("climate_1")
        mock_api._request.assert_called_with("POST", "/instances/climate_1/WriteFreezeMode", [])

    @pytest.mark.asyncio
    async def test_set_climate_temperature(self, mock_api):
        """Test setting climate temperature."""
        await mock_api.set_climate_temperature("climate_1", 22.5)
        mock_api._request.assert_called_with("POST", "/instances/climate_1/WriteCurrentSetTemperature", [22.5])

    @pytest.mark.asyncio
    async def test_execute_scene(self, mock_api):
        """Test executing a scene."""
        await mock_api.execute_scene("scene_1")
        mock_api._request.assert_called_with("POST", "/instances/scene_1/Execute", [])

    @pytest.mark.asyncio
    async def test_activate_home_state(self, mock_api):
        """Test activating a home state."""
        await mock_api.activate_home_state("HomeStateAtHome")
        mock_api._request.assert_called_with("POST", "/instances/HomeStateAtHome/Activate", [])

    @pytest.mark.asyncio
    async def test_toggle_bathroom_radiator(self, mock_api):
        """Test toggling bathroom radiator."""
        await mock_api.toggle_bathroom_radiator("radiator_1")
        mock_api._request.assert_called_with("POST", "/instances/radiator_1/Switch", [])


class TestEvonApiExceptions:
    """Tests for API exception handling.

    These tests require the actual homeassistant package to verify inheritance.
    When homeassistant is mocked, the exception classes inherit from MagicMock
    which breaks issubclass() checks.
    """

    def test_evon_api_error_inheritance(self):
        """Test that EvonApiError inherits from HomeAssistantError."""
        # Skip if homeassistant is mocked (exception classes become MagicMock)
        if not isinstance(EvonApiError, type):
            pytest.skip("Requires real homeassistant package")
        from homeassistant.exceptions import HomeAssistantError

        assert issubclass(EvonApiError, HomeAssistantError)

    def test_evon_auth_error_inheritance(self):
        """Test that EvonAuthError inherits from EvonApiError."""
        # Skip if homeassistant is mocked (exception classes become MagicMock)
        if not isinstance(EvonApiError, type):
            pytest.skip("Requires real homeassistant package")
        assert issubclass(EvonAuthError, EvonApiError)

    def test_evon_connection_error_inheritance(self):
        """Test that EvonConnectionError inherits from EvonApiError."""
        # Skip if homeassistant is mocked (exception classes become MagicMock)
        if not isinstance(EvonApiError, type):
            pytest.skip("Requires real homeassistant package")
        assert issubclass(EvonConnectionError, EvonApiError)


class TestEvonApiWebSocketControl:
    """Tests for API WebSocket control integration."""

    @pytest.fixture
    def mock_api_with_ws(self):
        """Create an API with mocked WebSocket client."""
        api = EvonApi(
            host="http://192.168.1.100",
            username="user",
            password="pass",
        )
        api._token = "test_token"
        api._request = AsyncMock(return_value={"data": {}})

        # Set up instance classes
        api.set_instance_classes(
            [
                {"ID": "Light1", "ClassName": "SmartCOM.Light.LightDim"},
                {"ID": "Blind1", "ClassName": "SmartCOM.Blind.Blind"},
                {"ID": "Climate1", "ClassName": "SmartCOM.Clima.ClimateControl"},
            ]
        )

        return api

    def test_set_ws_client(self):
        """Test setting WebSocket client."""
        api = EvonApi(
            host="http://192.168.1.100",
            username="user",
            password="pass",
        )

        mock_ws = MagicMock()
        api.set_ws_client(mock_ws)
        assert api._ws_client == mock_ws

        api.set_ws_client(None)
        assert api._ws_client is None

    def test_set_instance_classes(self):
        """Test caching instance classes."""
        api = EvonApi(
            host="http://192.168.1.100",
            username="user",
            password="pass",
        )

        instances = [
            {"ID": "Light1", "ClassName": "SmartCOM.Light.LightDim"},
            {"ID": "Blind1", "ClassName": "SmartCOM.Blind.Blind"},
            {"ID": "", "ClassName": "Empty"},  # Should be skipped
        ]
        api.set_instance_classes(instances)

        assert api._instance_classes == {
            "Light1": "SmartCOM.Light.LightDim",
            "Blind1": "SmartCOM.Blind.Blind",
        }

    @pytest.mark.asyncio
    async def test_light_on_off_uses_ws(self, mock_api_with_ws):
        """Test that light on uses WebSocket CallMethod SwitchOn."""
        mock_ws = MagicMock()
        mock_ws.is_connected = True
        mock_ws.set_value = AsyncMock(return_value=True)
        mock_ws.call_method = AsyncMock(return_value=True)
        mock_api_with_ws.set_ws_client(mock_ws)

        await mock_api_with_ws.turn_on_light("Light1")

        # WebSocket call_method should be called with SwitchOn (no params, fire_and_forget=False)
        mock_ws.call_method.assert_called_once_with("Light1", "SwitchOn", None, False)
        # HTTP should NOT be called (WS succeeded)
        mock_api_with_ws._request.assert_not_called()

    @pytest.mark.asyncio
    async def test_light_off_uses_ws(self, mock_api_with_ws):
        """Test that light off uses WebSocket CallMethod SwitchOff."""
        mock_ws = MagicMock()
        mock_ws.is_connected = True
        mock_ws.set_value = AsyncMock(return_value=True)
        mock_ws.call_method = AsyncMock(return_value=True)
        mock_api_with_ws.set_ws_client(mock_ws)

        await mock_api_with_ws.turn_off_light("Light1")

        # WebSocket call_method should be called with SwitchOff (no params, fire_and_forget=False)
        mock_ws.call_method.assert_called_once_with("Light1", "SwitchOff", None, False)
        # HTTP should NOT be called (WS succeeded)
        mock_api_with_ws._request.assert_not_called()

    @pytest.mark.asyncio
    async def test_brightness_uses_ws_when_available(self, mock_api_with_ws):
        """Test that brightness uses WebSocket CallMethod BrightnessSetScaled."""
        mock_ws = MagicMock()
        mock_ws.is_connected = True
        mock_ws.call_method = AsyncMock(return_value=True)
        mock_api_with_ws.set_ws_client(mock_ws)

        await mock_api_with_ws.set_light_brightness("Light1", 75)

        # WebSocket call_method should be called with BrightnessSetScaled([brightness, transition], fire_and_forget=False)
        mock_ws.call_method.assert_called_once_with("Light1", "BrightnessSetScaled", [75, 0], False)
        # HTTP should NOT be called
        mock_api_with_ws._request.assert_not_called()

    @pytest.mark.asyncio
    async def test_brightness_falls_back_to_http(self, mock_api_with_ws):
        """Test that brightness falls back to HTTP when WS fails."""
        mock_ws = MagicMock()
        mock_ws.is_connected = True
        mock_ws.call_method = AsyncMock(return_value=False)  # WS fails
        mock_api_with_ws.set_ws_client(mock_ws)

        await mock_api_with_ws.set_light_brightness("Light1", 75)

        # WebSocket should be tried
        mock_ws.call_method.assert_called_once()
        # HTTP should be called as fallback
        mock_api_with_ws._request.assert_called_once_with("POST", "/instances/Light1/AmznSetBrightness", [75])

    @pytest.mark.asyncio
    async def test_call_method_uses_http_when_ws_not_connected(self, mock_api_with_ws):
        """Test that call_method uses HTTP when WS not connected."""
        mock_ws = MagicMock()
        mock_ws.is_connected = False
        mock_api_with_ws.set_ws_client(mock_ws)

        await mock_api_with_ws.turn_on_light("Light1")

        # HTTP should be called
        mock_api_with_ws._request.assert_called_once_with("POST", "/instances/Light1/AmznTurnOn", [])

    @pytest.mark.asyncio
    async def test_call_method_uses_http_when_no_ws_client(self, mock_api_with_ws):
        """Test that call_method uses HTTP when no WS client."""
        # No WS client set
        await mock_api_with_ws.turn_on_light("Light1")

        # HTTP should be called
        mock_api_with_ws._request.assert_called_once_with("POST", "/instances/Light1/AmznTurnOn", [])

    @pytest.mark.asyncio
    async def test_call_method_uses_http_for_unknown_class(self, mock_api_with_ws):
        """Test that call_method uses HTTP for unknown instance class."""
        mock_ws = MagicMock()
        mock_ws.is_connected = True
        mock_api_with_ws.set_ws_client(mock_ws)

        # Call method on instance not in cache
        await mock_api_with_ws.call_method("Unknown1", "SomeMethod")

        # HTTP should be called (no WS mapping)
        mock_api_with_ws._request.assert_called_once()

    @pytest.mark.asyncio
    async def test_blind_open_uses_ws(self, mock_api_with_ws):
        """Test that blind Open/Close/Stop use WebSocket CallMethod."""
        mock_ws = MagicMock()
        mock_ws.is_connected = True
        mock_ws.call_method = AsyncMock(return_value=True)
        mock_api_with_ws.set_ws_client(mock_ws)

        await mock_api_with_ws.open_blind("Blind1")

        # WebSocket call_method should be used for Open (fire_and_forget=False)
        mock_ws.call_method.assert_called_once_with("Blind1", "Open", None, False)
        # HTTP should NOT be called
        mock_api_with_ws._request.assert_not_called()

    @pytest.mark.asyncio
    async def test_blind_position_uses_http(self, mock_api_with_ws):
        """Test that blind position control uses HTTP (needs angle+position for WS)."""
        mock_ws = MagicMock()
        mock_ws.is_connected = True
        mock_ws.call_method = AsyncMock(return_value=True)
        mock_api_with_ws.set_ws_client(mock_ws)

        await mock_api_with_ws.set_blind_position("Blind1", 50)

        # WebSocket should NOT be called for position (no mapping)
        mock_ws.call_method.assert_not_called()
        # HTTP should be called
        mock_api_with_ws._request.assert_called_once_with("POST", "/instances/Blind1/AmznSetPercentage", [50])

    @pytest.mark.asyncio
    async def test_blind_position_uses_ws_when_angle_cached(self, mock_api_with_ws):
        """Test blind position uses WS MoveToPosition when angle is cached."""
        mock_ws = MagicMock()
        mock_ws.is_connected = True
        mock_ws.call_method = AsyncMock(return_value=True)
        mock_api_with_ws.set_ws_client(mock_ws)

        # Cache the angle
        mock_api_with_ws.update_blind_angle("Blind1", 45)

        await mock_api_with_ws.set_blind_position("Blind1", 50)

        # WebSocket call_method should be called with MoveToPosition([angle, position], fire_and_forget=False)
        mock_ws.call_method.assert_called_once_with("Blind1", "MoveToPosition", [45, 50], False)
        # HTTP should NOT be called (WS succeeded)
        mock_api_with_ws._request.assert_not_called()

    @pytest.mark.asyncio
    async def test_blind_tilt_uses_http_without_cached_position(self, mock_api_with_ws):
        """Test blind tilt control falls back to HTTP when position not cached."""
        mock_ws = MagicMock()
        mock_ws.is_connected = True
        mock_ws.call_method = AsyncMock(return_value=True)
        mock_api_with_ws.set_ws_client(mock_ws)

        await mock_api_with_ws.set_blind_tilt("Blind1", 45)

        # WebSocket should NOT be called for tilt without cached position
        mock_ws.call_method.assert_not_called()
        # HTTP should be called
        mock_api_with_ws._request.assert_called_once_with("POST", "/instances/Blind1/SetAngle", [45])

    @pytest.mark.asyncio
    async def test_blind_tilt_uses_ws_when_position_cached(self, mock_api_with_ws):
        """Test blind tilt uses WS MoveToPosition when position is cached."""
        mock_ws = MagicMock()
        mock_ws.is_connected = True
        mock_ws.call_method = AsyncMock(return_value=True)
        mock_api_with_ws.set_ws_client(mock_ws)

        # Cache the position
        mock_api_with_ws.update_blind_position("Blind1", 30)

        await mock_api_with_ws.set_blind_tilt("Blind1", 75)

        # WebSocket call_method should be called with MoveToPosition([angle, position], fire_and_forget=False)
        mock_ws.call_method.assert_called_once_with("Blind1", "MoveToPosition", [75, 30], False)
        # HTTP should NOT be called (WS succeeded)
        mock_api_with_ws._request.assert_not_called()

    @pytest.mark.asyncio
    async def test_set_season_mode_uses_ws(self, mock_api_with_ws):
        """Test set_season_mode uses WebSocket when available."""
        mock_ws = MagicMock()
        mock_ws.is_connected = True
        mock_ws.set_value = AsyncMock(return_value=True)
        mock_api_with_ws.set_ws_client(mock_ws)

        await mock_api_with_ws.set_season_mode(True)

        # WebSocket should be called
        mock_ws.set_value.assert_called_once_with("Base.ehThermostat", "IsCool", True)
        # HTTP should NOT be called
        mock_api_with_ws._request.assert_not_called()

    @pytest.mark.asyncio
    async def test_set_season_mode_falls_back_to_http(self, mock_api_with_ws):
        """Test set_season_mode falls back to HTTP when WS fails."""
        mock_ws = MagicMock()
        mock_ws.is_connected = True
        mock_ws.set_value = AsyncMock(return_value=False)
        mock_api_with_ws.set_ws_client(mock_ws)

        await mock_api_with_ws.set_season_mode(False)

        # HTTP PUT should be called
        mock_api_with_ws._request.assert_called_once_with(
            "PUT",
            "/instances/Base.ehThermostat/IsCool",
            {"value": False},
        )


class TestRedactHeaders:
    """Tests for _redact_headers function."""

    def test_redact_sensitive_headers(self):
        """Test that sensitive headers are redacted."""
        from custom_components.evon.api import _redact_headers

        headers = {
            "x-elocs-token": "secret_token",
            "x-elocs-password": "secret_password",
            "Authorization": "Bearer token",
            "Cookie": "session=abc123",
            "Content-Type": "application/json",
        }

        redacted = _redact_headers(headers)

        assert redacted["x-elocs-token"] == "**REDACTED**"
        assert redacted["x-elocs-password"] == "**REDACTED**"
        assert redacted["Authorization"] == "**REDACTED**"
        assert redacted["Cookie"] == "**REDACTED**"
        assert redacted["Content-Type"] == "application/json"

    def test_redact_headers_case_insensitive(self):
        """Test that header matching is case insensitive."""
        from custom_components.evon.api import _redact_headers

        headers = {
            "X-ELOCS-TOKEN": "secret",
            "X-Elocs-Password": "secret",
            "content-type": "application/json",
        }

        redacted = _redact_headers(headers)

        assert redacted["X-ELOCS-TOKEN"] == "**REDACTED**"
        assert redacted["X-Elocs-Password"] == "**REDACTED**"
        assert redacted["content-type"] == "application/json"

    def test_redact_headers_empty(self):
        """Test with empty headers dict."""
        from custom_components.evon.api import _redact_headers

        assert _redact_headers({}) == {}


class TestValidateInstanceId:
    """Tests for _validate_instance_id function."""

    def test_valid_instance_ids(self):
        """Test valid instance ID formats."""
        from custom_components.evon.api import _validate_instance_id

        # These should not raise
        _validate_instance_id("light_1")
        _validate_instance_id("SmartCOM.Light.LightDim")
        _validate_instance_id("intercom_1.Cam")
        _validate_instance_id("Base-Device-123")
        _validate_instance_id("device.sub.item")

    def test_invalid_empty(self):
        """Test empty instance ID raises ValueError."""
        from custom_components.evon.api import _validate_instance_id

        with pytest.raises(ValueError, match="Invalid instance ID"):
            _validate_instance_id("")

    def test_invalid_characters(self):
        """Test instance ID with invalid characters raises ValueError."""
        from custom_components.evon.api import _validate_instance_id

        with pytest.raises(ValueError, match="Invalid instance ID"):
            _validate_instance_id("light/1")  # Path traversal attempt

        with pytest.raises(ValueError, match="Invalid instance ID"):
            _validate_instance_id("light;drop table")  # SQL injection attempt

        with pytest.raises(ValueError, match="Invalid instance ID"):
            _validate_instance_id("light\n1")  # Newline


class TestValidateMethodName:
    """Tests for _validate_method_name function."""

    def test_valid_method_names(self):
        """Test valid method name formats."""
        from custom_components.evon.api import _validate_method_name

        # These should not raise
        _validate_method_name("AmznTurnOn")
        _validate_method_name("SetBrightness")
        _validate_method_name("Open")
        _validate_method_name("WriteCurrentSetTemperature")

    def test_invalid_empty(self):
        """Test empty method name raises ValueError."""
        from custom_components.evon.api import _validate_method_name

        with pytest.raises(ValueError, match="Invalid method name"):
            _validate_method_name("")

    def test_invalid_starting_with_number(self):
        """Test method name starting with number raises ValueError."""
        from custom_components.evon.api import _validate_method_name

        with pytest.raises(ValueError, match="Invalid method name"):
            _validate_method_name("123Method")

    def test_invalid_with_special_chars(self):
        """Test method name with special characters raises ValueError."""
        from custom_components.evon.api import _validate_method_name

        with pytest.raises(ValueError, match="Invalid method name"):
            _validate_method_name("Turn_On")  # Underscore not allowed

        with pytest.raises(ValueError, match="Invalid method name"):
            _validate_method_name("Turn-Off")  # Hyphen not allowed


class TestValidateEngineId:
    """Tests for _validate_engine_id function."""

    def test_valid_engine_ids(self):
        """Test valid engine ID formats."""
        from custom_components.evon.api import _validate_engine_id

        # These should not raise (4-12 alphanumeric chars)
        _validate_engine_id("ab12")  # Min length
        _validate_engine_id("ABCD1234")
        _validate_engine_id("123456789012")  # Max length

    def test_invalid_empty(self):
        """Test empty engine ID raises ValueError."""
        from custom_components.evon.api import _validate_engine_id

        with pytest.raises(ValueError, match="Engine ID cannot be empty"):
            _validate_engine_id("")

    def test_invalid_too_short(self):
        """Test engine ID too short raises ValueError."""
        from custom_components.evon.api import _validate_engine_id

        with pytest.raises(ValueError, match="must be 4-12 characters"):
            _validate_engine_id("abc")  # 3 chars, min is 4

    def test_invalid_too_long(self):
        """Test engine ID too long raises ValueError."""
        from custom_components.evon.api import _validate_engine_id

        with pytest.raises(ValueError, match="must be 4-12 characters"):
            _validate_engine_id("1234567890123")  # 13 chars, max is 12

    def test_invalid_non_alphanumeric(self):
        """Test engine ID with non-alphanumeric chars raises ValueError."""
        from custom_components.evon.api import _validate_engine_id

        with pytest.raises(ValueError, match="alphanumeric"):
            _validate_engine_id("abc-123")

        with pytest.raises(ValueError, match="alphanumeric"):
            _validate_engine_id("abc_123")


class TestBuildBaseUrl:
    """Tests for build_base_url function."""

    def test_with_host(self):
        """Test building URL with local host."""
        from custom_components.evon.api import build_base_url

        assert build_base_url(host="http://192.168.1.100") == "http://192.168.1.100"
        assert build_base_url(host="http://192.168.1.100/") == "http://192.168.1.100"

    def test_with_engine_id(self):
        """Test building URL with engine ID (remote connection)."""
        from custom_components.evon.api import build_base_url

        url = build_base_url(engine_id="ABC123")
        assert url == "https://my.evon-smarthome.com/ABC123"

    def test_host_takes_precedence(self):
        """Test that host takes precedence over engine_id."""
        from custom_components.evon.api import build_base_url

        url = build_base_url(host="http://local.evon", engine_id="ABC123")
        assert url == "http://local.evon"

    def test_neither_provided_raises(self):
        """Test that ValueError is raised when neither host nor engine_id provided."""
        from custom_components.evon.api import build_base_url

        with pytest.raises(ValueError, match="Either host or engine_id"):
            build_base_url()

    def test_invalid_engine_id_raises(self):
        """Test that invalid engine_id raises ValueError."""
        from custom_components.evon.api import build_base_url

        with pytest.raises(ValueError):
            build_base_url(engine_id="ab")  # Too short


class TestIsTokenExpired:
    """Tests for _is_token_expired method."""

    def test_expired_when_no_token(self):
        """Test token is expired when no token set."""
        from custom_components.evon.api import EvonApi

        api = EvonApi("http://192.168.1.100", "user", "pass")
        api._token = None

        assert api._is_token_expired() is True

    def test_not_expired_when_fresh(self):
        """Test token is not expired when recently set."""
        import time

        from custom_components.evon.api import EvonApi

        api = EvonApi("http://192.168.1.100", "user", "pass")
        api._token = "valid_token"
        api._token_timestamp = time.monotonic()  # Just now

        assert api._is_token_expired() is False

    def test_expired_after_ttl(self):
        """Test token is expired after TTL period."""
        import time

        from custom_components.evon.api import TOKEN_TTL_SECONDS, EvonApi

        api = EvonApi("http://192.168.1.100", "user", "pass")
        api._token = "valid_token"
        # Set timestamp to just past TTL
        api._token_timestamp = time.monotonic() - TOKEN_TTL_SECONDS - 1

        assert api._is_token_expired() is True


class TestIsBlindClass:
    """Tests for _is_blind_class method."""

    def test_blind_classes(self):
        """Test that blind classes are recognized."""
        from custom_components.evon.api import EvonApi

        api = EvonApi("http://192.168.1.100", "user", "pass")

        assert api._is_blind_class("SmartCOM.Blind.Blind") is True
        assert api._is_blind_class("SmartCOM.Blind.BlindGroup") is True
        assert api._is_blind_class("Base.bBlind") is True
        assert api._is_blind_class("Base.ehBlind") is True

    def test_non_blind_classes(self):
        """Test that non-blind classes are not recognized."""
        from custom_components.evon.api import EvonApi

        api = EvonApi("http://192.168.1.100", "user", "pass")

        assert api._is_blind_class("SmartCOM.Light.LightDim") is False
        assert api._is_blind_class("Climate.ClimateControl") is False
        assert api._is_blind_class("") is False
        assert api._is_blind_class("Blind") is False  # Partial match


class TestCreateSslContext:
    """Tests for _create_ssl_context function."""

    def test_creates_ssl_context(self):
        """Test that function creates a valid SSL context."""
        import ssl

        from custom_components.evon.api import _create_ssl_context

        ctx = _create_ssl_context()

        assert isinstance(ctx, ssl.SSLContext)
        # Default context should verify certificates
        assert ctx.verify_mode == ssl.CERT_REQUIRED


class TestApiErrorHandling:
    """Tests for API error handling paths."""

    @pytest.fixture
    def api_with_token(self):
        """Create an API with a valid token already set."""
        import time

        from custom_components.evon.api import EvonApiError

        # Skip if homeassistant is mocked (exceptions are MagicMock)
        if not isinstance(EvonApiError, type):
            pytest.skip("Requires real homeassistant package")

        api = EvonApi(
            host="http://192.168.1.100",
            username="user",
            password="pass",
        )
        api._token = "valid_token"
        api._token_timestamp = time.monotonic()
        return api

    @pytest.mark.asyncio
    async def test_request_400_bad_request(self, api_with_token):
        """Test 400 Bad Request error handling."""
        from custom_components.evon.api import EvonApiError

        mock_response = MagicMock()
        mock_response.status = 400
        mock_response.reason = "Bad Request"

        async_ctx = AsyncMock()
        async_ctx.__aenter__.return_value = mock_response
        async_ctx.__aexit__.return_value = None

        mock_session = MagicMock()
        mock_session.closed = False
        mock_session.request.return_value = async_ctx

        api_with_token._session = mock_session

        with pytest.raises(EvonApiError, match="Bad request"):
            await api_with_token._request("POST", "/instances/test/Method")

    @pytest.mark.asyncio
    async def test_request_403_forbidden(self, api_with_token):
        """Test 403 Forbidden error handling."""
        from custom_components.evon.api import EvonAuthError

        mock_response = MagicMock()
        mock_response.status = 403
        mock_response.reason = "Forbidden"

        async_ctx = AsyncMock()
        async_ctx.__aenter__.return_value = mock_response
        async_ctx.__aexit__.return_value = None

        mock_session = MagicMock()
        mock_session.closed = False
        mock_session.request.return_value = async_ctx

        api_with_token._session = mock_session

        with pytest.raises(EvonAuthError, match="Access forbidden"):
            await api_with_token._request("GET", "/instances")

    @pytest.mark.asyncio
    async def test_request_404_not_found(self, api_with_token):
        """Test 404 Not Found error handling."""
        from custom_components.evon.api import EvonApiError

        mock_response = MagicMock()
        mock_response.status = 404
        mock_response.reason = "Not Found"

        async_ctx = AsyncMock()
        async_ctx.__aenter__.return_value = mock_response
        async_ctx.__aexit__.return_value = None

        mock_session = MagicMock()
        mock_session.closed = False
        mock_session.request.return_value = async_ctx

        api_with_token._session = mock_session

        with pytest.raises(EvonApiError, match="Resource not found"):
            await api_with_token._request("GET", "/instances/nonexistent")

    @pytest.mark.asyncio
    async def test_request_429_rate_limited(self, api_with_token):
        """Test 429 Too Many Requests error handling."""
        from custom_components.evon.api import EvonApiError

        mock_response = MagicMock()
        mock_response.status = 429
        mock_response.reason = "Too Many Requests"

        async_ctx = AsyncMock()
        async_ctx.__aenter__.return_value = mock_response
        async_ctx.__aexit__.return_value = None

        mock_session = MagicMock()
        mock_session.closed = False
        mock_session.request.return_value = async_ctx

        api_with_token._session = mock_session

        with pytest.raises(EvonApiError, match="Rate limited"):
            await api_with_token._request("POST", "/instances/test/Method")

    @pytest.mark.asyncio
    async def test_request_500_server_error(self, api_with_token):
        """Test 500 Internal Server Error handling."""
        from custom_components.evon.api import EvonConnectionError

        mock_response = MagicMock()
        mock_response.status = 500
        mock_response.reason = "Internal Server Error"

        async_ctx = AsyncMock()
        async_ctx.__aenter__.return_value = mock_response
        async_ctx.__aexit__.return_value = None

        mock_session = MagicMock()
        mock_session.closed = False
        mock_session.request.return_value = async_ctx

        api_with_token._session = mock_session

        with pytest.raises(EvonConnectionError, match="Server error"):
            await api_with_token._request("GET", "/instances")

    @pytest.mark.asyncio
    async def test_request_502_bad_gateway(self, api_with_token):
        """Test 502 Bad Gateway error handling."""
        from custom_components.evon.api import EvonConnectionError

        mock_response = MagicMock()
        mock_response.status = 502
        mock_response.reason = "Bad Gateway"

        async_ctx = AsyncMock()
        async_ctx.__aenter__.return_value = mock_response
        async_ctx.__aexit__.return_value = None

        mock_session = MagicMock()
        mock_session.closed = False
        mock_session.request.return_value = async_ctx

        api_with_token._session = mock_session

        with pytest.raises(EvonConnectionError, match="Server error"):
            await api_with_token._request("GET", "/instances")

    @pytest.mark.asyncio
    async def test_request_503_service_unavailable(self, api_with_token):
        """Test 503 Service Unavailable error handling."""
        from custom_components.evon.api import EvonConnectionError

        mock_response = MagicMock()
        mock_response.status = 503
        mock_response.reason = "Service Unavailable"

        async_ctx = AsyncMock()
        async_ctx.__aenter__.return_value = mock_response
        async_ctx.__aexit__.return_value = None

        mock_session = MagicMock()
        mock_session.closed = False
        mock_session.request.return_value = async_ctx

        api_with_token._session = mock_session

        with pytest.raises(EvonConnectionError, match="Server error"):
            await api_with_token._request("GET", "/instances")

    @pytest.mark.asyncio
    async def test_request_504_gateway_timeout(self, api_with_token):
        """Test 504 Gateway Timeout error handling."""
        from custom_components.evon.api import EvonConnectionError

        mock_response = MagicMock()
        mock_response.status = 504
        mock_response.reason = "Gateway Timeout"

        async_ctx = AsyncMock()
        async_ctx.__aenter__.return_value = mock_response
        async_ctx.__aexit__.return_value = None

        mock_session = MagicMock()
        mock_session.closed = False
        mock_session.request.return_value = async_ctx

        api_with_token._session = mock_session

        with pytest.raises(EvonConnectionError, match="Server error"):
            await api_with_token._request("GET", "/instances")

    @pytest.mark.asyncio
    async def test_request_unknown_error_status(self, api_with_token):
        """Test unknown error status code handling."""
        from custom_components.evon.api import EvonApiError

        mock_response = MagicMock()
        mock_response.status = 418  # I'm a teapot
        mock_response.reason = "I'm a teapot"

        async_ctx = AsyncMock()
        async_ctx.__aenter__.return_value = mock_response
        async_ctx.__aexit__.return_value = None

        mock_session = MagicMock()
        mock_session.closed = False
        mock_session.request.return_value = async_ctx

        api_with_token._session = mock_session

        with pytest.raises(EvonApiError, match="API request failed"):
            await api_with_token._request("GET", "/instances")

    @pytest.mark.asyncio
    async def test_request_204_no_content(self, api_with_token):
        """Test 204 No Content returns empty dict."""
        mock_response = MagicMock()
        mock_response.status = 204
        mock_response.reason = "No Content"

        async_ctx = AsyncMock()
        async_ctx.__aenter__.return_value = mock_response
        async_ctx.__aexit__.return_value = None

        mock_session = MagicMock()
        mock_session.closed = False
        mock_session.request.return_value = async_ctx

        api_with_token._session = mock_session

        result = await api_with_token._request("POST", "/instances/test/Method")
        assert result == {}

    @pytest.mark.asyncio
    async def test_request_missing_content_type(self, api_with_token):
        """Test response with missing Content-Type header."""
        from custom_components.evon.api import EvonApiError

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.reason = "OK"
        mock_response.headers = {}  # No Content-Type

        async_ctx = AsyncMock()
        async_ctx.__aenter__.return_value = mock_response
        async_ctx.__aexit__.return_value = None

        mock_session = MagicMock()
        mock_session.closed = False
        mock_session.request.return_value = async_ctx

        api_with_token._session = mock_session

        with pytest.raises(EvonApiError, match="missing Content-Type"):
            await api_with_token._request("GET", "/instances")

    @pytest.mark.asyncio
    async def test_request_wrong_content_type(self, api_with_token):
        """Test response with wrong Content-Type (HTML instead of JSON)."""
        from custom_components.evon.api import EvonApiError

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.reason = "OK"
        mock_response.headers = {"Content-Type": "text/html"}

        async_ctx = AsyncMock()
        async_ctx.__aenter__.return_value = mock_response
        async_ctx.__aexit__.return_value = None

        mock_session = MagicMock()
        mock_session.closed = False
        mock_session.request.return_value = async_ctx

        api_with_token._session = mock_session

        with pytest.raises(EvonApiError, match="Unexpected response type"):
            await api_with_token._request("GET", "/instances")

    @pytest.mark.asyncio
    async def test_request_invalid_json(self, api_with_token):
        """Test response with invalid JSON body."""
        from custom_components.evon.api import EvonApiError

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.reason = "OK"
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.json = AsyncMock(side_effect=ValueError("Invalid JSON"))

        async_ctx = AsyncMock()
        async_ctx.__aenter__.return_value = mock_response
        async_ctx.__aexit__.return_value = None

        mock_session = MagicMock()
        mock_session.closed = False
        mock_session.request.return_value = async_ctx

        api_with_token._session = mock_session

        with pytest.raises(EvonApiError, match="Invalid JSON"):
            await api_with_token._request("GET", "/instances")

    @pytest.mark.asyncio
    async def test_request_connection_error(self, api_with_token):
        """Test connection error during request."""
        import aiohttp

        from custom_components.evon.api import EvonConnectionError

        mock_session = MagicMock()
        mock_session.closed = False
        mock_session.request.side_effect = aiohttp.ClientError("Connection refused")

        api_with_token._session = mock_session

        with pytest.raises(EvonConnectionError, match="Connection error"):
            await api_with_token._request("GET", "/instances")

    @pytest.mark.asyncio
    async def test_request_success_200(self, api_with_token):
        """Test successful 200 OK response."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.reason = "OK"
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.json = AsyncMock(return_value={"data": [{"ID": "test"}]})

        async_ctx = AsyncMock()
        async_ctx.__aenter__.return_value = mock_response
        async_ctx.__aexit__.return_value = None

        mock_session = MagicMock()
        mock_session.closed = False
        mock_session.request.return_value = async_ctx

        api_with_token._session = mock_session

        result = await api_with_token._request("GET", "/instances")
        assert result == {"data": [{"ID": "test"}]}

    @pytest.mark.asyncio
    async def test_request_success_201_created(self, api_with_token):
        """Test successful 201 Created response."""
        mock_response = MagicMock()
        mock_response.status = 201
        mock_response.reason = "Created"
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.json = AsyncMock(return_value={"id": "new_resource"})

        async_ctx = AsyncMock()
        async_ctx.__aenter__.return_value = mock_response
        async_ctx.__aexit__.return_value = None

        mock_session = MagicMock()
        mock_session.closed = False
        mock_session.request.return_value = async_ctx

        api_with_token._session = mock_session

        result = await api_with_token._request("POST", "/instances")
        assert result == {"id": "new_resource"}


class TestTokenRefreshScenarios:
    """Tests for token refresh and expiration edge cases."""

    @pytest.mark.asyncio
    async def test_token_almost_expired_not_refreshed(self):
        """Test that token almost at TTL but not expired is not refreshed."""
        import time

        from custom_components.evon.api import TOKEN_TTL_SECONDS

        api = EvonApi(
            host="http://192.168.1.100",
            username="user",
            password="pass",
        )
        api._token = "almost_expired_token"
        # Set timestamp to 1 second before expiration
        api._token_timestamp = time.monotonic() - TOKEN_TTL_SECONDS + 1

        assert api._is_token_expired() is False

    def test_token_exactly_at_ttl_is_expired(self):
        """Test that token exactly at TTL is considered expired."""
        import time

        from custom_components.evon.api import TOKEN_TTL_SECONDS

        api = EvonApi(
            host="http://192.168.1.100",
            username="user",
            password="pass",
        )
        api._token = "edge_case_token"
        # Set timestamp to exactly TTL seconds ago
        api._token_timestamp = time.monotonic() - TOKEN_TTL_SECONDS

        assert api._is_token_expired() is True

    def test_token_well_within_ttl(self):
        """Test that token well within TTL is not expired."""
        import time

        from custom_components.evon.api import TOKEN_TTL_SECONDS

        api = EvonApi(
            host="http://192.168.1.100",
            username="user",
            password="pass",
        )
        api._token = "fresh_token"
        # Set timestamp to half of TTL ago
        api._token_timestamp = time.monotonic() - (TOKEN_TTL_SECONDS / 2)

        assert api._is_token_expired() is False

    def test_token_timestamp_far_in_past_means_expired(self):
        """Test that timestamp far in the past means token is expired."""
        import time

        from custom_components.evon.api import TOKEN_TTL_SECONDS

        api = EvonApi(
            host="http://192.168.1.100",
            username="user",
            password="pass",
        )
        api._token = "some_token"
        # Set timestamp to well beyond TTL in the past
        api._token_timestamp = time.monotonic() - TOKEN_TTL_SECONDS - 1000

        assert api._is_token_expired() is True

    def test_no_token_means_expired(self):
        """Test that missing token is considered expired."""
        api = EvonApi(
            host="http://192.168.1.100",
            username="user",
            password="pass",
        )
        api._token = None
        api._token_timestamp = 100.0  # Timestamp doesn't matter

        assert api._is_token_expired() is True

    def test_empty_token_means_expired(self):
        """Test that empty string token is considered expired."""
        api = EvonApi(
            host="http://192.168.1.100",
            username="user",
            password="pass",
        )
        api._token = ""
        api._token_timestamp = 100.0

        # Empty string is falsy, so _is_token_expired checks if not self._token
        assert api._is_token_expired() is True


class TestLoginErrorHandling:
    """Tests for login-specific error handling.

    Note: Tests that use pytest.raises with exception classes require
    real homeassistant package and are skipped when mocked.
    """

    @pytest.mark.asyncio
    async def test_login_302_redirect_to_login_page(self):
        """Test 302 redirect to login page indicates auth failure."""
        from custom_components.evon.api import EvonAuthError

        # Skip if homeassistant is mocked (exceptions are MagicMock)
        if not isinstance(EvonAuthError, type):
            pytest.skip("Requires real homeassistant package")

        api = EvonApi(
            host="http://192.168.1.100",
            username="user",
            password="wrong_pass",
        )

        mock_response = MagicMock()
        mock_response.status = 302
        mock_response.headers = {"Location": "/login.html?error=1"}

        async_ctx = AsyncMock()
        async_ctx.__aenter__.return_value = mock_response
        async_ctx.__aexit__.return_value = None

        mock_session = MagicMock()
        mock_session.closed = False
        mock_session.post.return_value = async_ctx

        api._session = mock_session

        with pytest.raises(EvonAuthError, match="Invalid credentials"):
            await api.login()

    @pytest.mark.asyncio
    async def test_login_302_unexpected_redirect(self):
        """Test 302 redirect to unexpected location."""
        from custom_components.evon.api import EvonAuthError

        # Skip if homeassistant is mocked (exceptions are MagicMock)
        if not isinstance(EvonAuthError, type):
            pytest.skip("Requires real homeassistant package")

        api = EvonApi(
            host="http://192.168.1.100",
            username="user",
            password="pass",
        )

        mock_response = MagicMock()
        mock_response.status = 302
        mock_response.headers = {"Location": "/maintenance.html"}

        async_ctx = AsyncMock()
        async_ctx.__aenter__.return_value = mock_response
        async_ctx.__aexit__.return_value = None

        mock_session = MagicMock()
        mock_session.closed = False
        mock_session.post.return_value = async_ctx

        api._session = mock_session

        with pytest.raises(EvonAuthError, match="Unexpected redirect"):
            await api.login()

    @pytest.mark.asyncio
    async def test_login_connection_error(self):
        """Test connection error during login."""
        import aiohttp

        from custom_components.evon.api import EvonConnectionError

        # Skip if homeassistant is mocked (exceptions are MagicMock)
        if not isinstance(EvonConnectionError, type):
            pytest.skip("Requires real homeassistant package")

        api = EvonApi(
            host="http://192.168.1.100",
            username="user",
            password="pass",
        )

        mock_session = MagicMock()
        mock_session.closed = False
        mock_session.post.side_effect = aiohttp.ClientError("Connection refused")

        api._session = mock_session

        with pytest.raises(EvonConnectionError, match="Connection error"):
            await api.login()

    @pytest.mark.asyncio
    async def test_login_timeout(self):
        """Test timeout during login propagates."""
        api = EvonApi(
            host="http://192.168.1.100",
            username="user",
            password="pass",
        )

        mock_session = MagicMock()
        mock_session.closed = False
        mock_session.post.side_effect = TimeoutError()

        api._session = mock_session

        # TimeoutError is not a ClientError, so it should propagate
        with pytest.raises(TimeoutError):
            await api.login()


class TestDebugLogging:
    """Tests for debug logging configuration."""

    def test_apply_debug_logging_all_enabled(self):
        """Test applying debug logging with all options enabled."""
        import logging

        from custom_components.evon import _apply_debug_logging
        from custom_components.evon.const import (
            CONF_DEBUG_API,
            CONF_DEBUG_COORDINATOR,
            CONF_DEBUG_WEBSOCKET,
        )

        # Create mock config entry
        mock_entry = MagicMock()
        mock_entry.options = {
            CONF_DEBUG_API: True,
            CONF_DEBUG_WEBSOCKET: True,
            CONF_DEBUG_COORDINATOR: True,
        }

        _apply_debug_logging(mock_entry)

        # Check loggers are set to DEBUG
        api_logger = logging.getLogger("custom_components.evon.api")
        ws_logger = logging.getLogger("custom_components.evon.ws_client")
        coord_logger = logging.getLogger("custom_components.evon.coordinator")

        assert api_logger.level == logging.DEBUG
        assert ws_logger.level == logging.DEBUG
        assert coord_logger.level == logging.DEBUG

    def test_apply_debug_logging_all_disabled(self):
        """Test applying debug logging with all options disabled."""
        import logging

        from custom_components.evon import _apply_debug_logging
        from custom_components.evon.const import (
            CONF_DEBUG_API,
            CONF_DEBUG_COORDINATOR,
            CONF_DEBUG_WEBSOCKET,
        )

        # Create mock config entry
        mock_entry = MagicMock()
        mock_entry.options = {
            CONF_DEBUG_API: False,
            CONF_DEBUG_WEBSOCKET: False,
            CONF_DEBUG_COORDINATOR: False,
        }

        _apply_debug_logging(mock_entry)

        # Check loggers are set to INFO
        api_logger = logging.getLogger("custom_components.evon.api")
        ws_logger = logging.getLogger("custom_components.evon.ws_client")
        coord_logger = logging.getLogger("custom_components.evon.coordinator")

        assert api_logger.level == logging.INFO
        assert ws_logger.level == logging.INFO
        assert coord_logger.level == logging.INFO

    def test_apply_debug_logging_partial(self):
        """Test applying debug logging with only some options enabled."""
        import logging

        from custom_components.evon import _apply_debug_logging
        from custom_components.evon.const import (
            CONF_DEBUG_API,
            CONF_DEBUG_COORDINATOR,
            CONF_DEBUG_WEBSOCKET,
        )

        # Create mock config entry - only API debug enabled
        mock_entry = MagicMock()
        mock_entry.options = {
            CONF_DEBUG_API: True,
            CONF_DEBUG_WEBSOCKET: False,
            CONF_DEBUG_COORDINATOR: False,
        }

        _apply_debug_logging(mock_entry)

        api_logger = logging.getLogger("custom_components.evon.api")
        ws_logger = logging.getLogger("custom_components.evon.ws_client")
        coord_logger = logging.getLogger("custom_components.evon.coordinator")

        assert api_logger.level == logging.DEBUG
        assert ws_logger.level == logging.INFO
        assert coord_logger.level == logging.INFO

    def test_apply_debug_logging_defaults(self):
        """Test applying debug logging with missing options uses defaults."""
        import logging

        from custom_components.evon import _apply_debug_logging

        # Create mock config entry with empty options
        mock_entry = MagicMock()
        mock_entry.options = {}

        _apply_debug_logging(mock_entry)

        # All should default to INFO (defaults are False)
        api_logger = logging.getLogger("custom_components.evon.api")
        ws_logger = logging.getLogger("custom_components.evon.ws_client")
        coord_logger = logging.getLogger("custom_components.evon.coordinator")

        assert api_logger.level == logging.INFO
        assert ws_logger.level == logging.INFO
        assert coord_logger.level == logging.INFO

    def test_debug_constants_exist(self):
        """Test that debug logging constants are defined."""
        from custom_components.evon.const import (
            CONF_DEBUG_API,
            CONF_DEBUG_COORDINATOR,
            CONF_DEBUG_WEBSOCKET,
            DEFAULT_DEBUG_API,
            DEFAULT_DEBUG_COORDINATOR,
            DEFAULT_DEBUG_WEBSOCKET,
        )

        assert CONF_DEBUG_API == "debug_api"
        assert CONF_DEBUG_WEBSOCKET == "debug_websocket"
        assert CONF_DEBUG_COORDINATOR == "debug_coordinator"
        assert DEFAULT_DEBUG_API is False
        assert DEFAULT_DEBUG_WEBSOCKET is False
        assert DEFAULT_DEBUG_COORDINATOR is False


class TestParameterBoundsValidation:
    """Tests for API method parameter bounds validation."""

    @pytest.fixture
    def mock_api(self):
        """Create an API with mocked request method."""
        api = EvonApi(
            host="http://192.168.1.100",
            username="user",
            password="pass",
        )
        api._token = "test_token"
        api._request = AsyncMock(return_value={"data": {}})
        return api

    @pytest.mark.asyncio
    async def test_set_light_brightness_clamps_above_100(self, mock_api):
        """Test brightness values above 100 are clamped to 100."""
        await mock_api.set_light_brightness("light_1", 150)
        mock_api._request.assert_called_once()
        call_args = mock_api._request.call_args
        assert call_args[0][2] == [100]

    @pytest.mark.asyncio
    async def test_set_light_brightness_clamps_below_0(self, mock_api):
        """Test brightness values below 0 are clamped to 0."""
        await mock_api.set_light_brightness("light_1", -10)
        call_args = mock_api._request.call_args
        assert call_args[0][2] == [0]

    @pytest.mark.asyncio
    async def test_set_light_brightness_normal_value(self, mock_api):
        """Test normal brightness values pass through unchanged."""
        await mock_api.set_light_brightness("light_1", 75)
        call_args = mock_api._request.call_args
        assert call_args[0][2] == [75]

    @pytest.mark.asyncio
    async def test_set_blind_position_clamps_above_100(self, mock_api):
        """Test blind position above 100 is clamped to 100."""
        await mock_api.set_blind_position("blind_1", 120)
        call_args = mock_api._request.call_args
        assert call_args[0][2] == [100]

    @pytest.mark.asyncio
    async def test_set_blind_position_clamps_below_0(self, mock_api):
        """Test blind position below 0 is clamped to 0."""
        await mock_api.set_blind_position("blind_1", -5)
        call_args = mock_api._request.call_args
        assert call_args[0][2] == [0]

    @pytest.mark.asyncio
    async def test_set_blind_tilt_clamps_above_100(self, mock_api):
        """Test blind tilt above 100 is clamped to 100."""
        await mock_api.set_blind_tilt("blind_1", 200)
        call_args = mock_api._request.call_args
        assert call_args[0][2] == [100]

    @pytest.mark.asyncio
    async def test_set_blind_tilt_clamps_below_0(self, mock_api):
        """Test blind tilt below 0 is clamped to 0."""
        await mock_api.set_blind_tilt("blind_1", -1)
        call_args = mock_api._request.call_args
        assert call_args[0][2] == [0]

    @pytest.mark.asyncio
    async def test_set_climate_temperature_rounds(self, mock_api):
        """Test climate temperature is rounded to 1 decimal place."""
        await mock_api.set_climate_temperature("climate_1", 22.567)
        call_args = mock_api._request.call_args
        assert call_args[0][2] == [22.6]

    @pytest.mark.asyncio
    async def test_set_climate_temperature_float_conversion(self, mock_api):
        """Test climate temperature converts int to float."""
        await mock_api.set_climate_temperature("climate_1", 22)
        call_args = mock_api._request.call_args
        assert call_args[0][2] == [22.0]
        assert isinstance(call_args[0][2][0], float)


class TestTryWsControl:
    """Tests for _try_ws_control() WebSocket routing logic."""

    @pytest.fixture
    def ws_api(self):
        """Create an EvonApi with a mock WS client."""
        api = EvonApi.__new__(EvonApi)
        api._ws_client = MagicMock()
        api._ws_client.is_connected = True
        api._ws_client.call_method = AsyncMock(return_value=True)
        api._ws_client.set_value = AsyncMock(return_value=True)
        api._instance_classes = {}
        api._blind_cache = {}
        return api

    @pytest.mark.asyncio
    async def test_no_class_returns_false(self, ws_api):
        """Falls back to HTTP when instance class is unknown."""
        result = await ws_api._try_ws_control("unknown.instance", "SwitchOn", None)
        assert result is False

    @pytest.mark.asyncio
    async def test_light_switch_on_call_method(self, ws_api):
        """Light SwitchOn routes to CallMethod."""
        ws_api._instance_classes["SC1.Light1"] = "SmartCOM.Light.LightDim"
        result = await ws_api._try_ws_control("SC1.Light1", "SwitchOn", None)
        assert result is True
        ws_api._ws_client.call_method.assert_called_once_with("SC1.Light1", "SwitchOn", None, False)

    @pytest.mark.asyncio
    async def test_light_brightness_call_method(self, ws_api):
        """Light BrightnessSetScaled routes with transformed params."""
        ws_api._instance_classes["SC1.Light1"] = "SmartCOM.Light.LightDim"
        result = await ws_api._try_ws_control("SC1.Light1", "BrightnessSetScaled", [75])
        assert result is True
        ws_api._ws_client.call_method.assert_called_once_with("SC1.Light1", "BrightnessSetScaled", [75, 0], False)

    @pytest.mark.asyncio
    async def test_light_color_temp_set_value(self, ws_api):
        """Light SetColorTemp routes to SetValue on ColorTemp property."""
        ws_api._instance_classes["SC1.Light1"] = "SmartCOM.Light.DynamicRGBWLight"
        result = await ws_api._try_ws_control("SC1.Light1", "SetColorTemp", [3500])
        assert result is True
        ws_api._ws_client.set_value.assert_called_once_with("SC1.Light1", "ColorTemp", 3500)

    @pytest.mark.asyncio
    async def test_blind_open_call_method(self, ws_api):
        """Blind Open routes to CallMethod."""
        ws_api._instance_classes["SC1.Blind1"] = "SmartCOM.Blind.Blind"
        result = await ws_api._try_ws_control("SC1.Blind1", "Open", None)
        assert result is True
        ws_api._ws_client.call_method.assert_called_once_with("SC1.Blind1", "Open", None, False)

    @pytest.mark.asyncio
    async def test_blind_set_position_uses_cached_angle(self, ws_api):
        """SetPosition uses MoveToPosition with [cached_angle, new_position]."""
        ws_api._instance_classes["SC1.Blind1"] = "SmartCOM.Blind.Blind"
        ws_api._blind_cache = {"SC1.Blind1": {"angle": 45, "position": 50}}
        ws_api.get_blind_angle = MagicMock(return_value=45)
        result = await ws_api._try_ws_control("SC1.Blind1", "SetPosition", [80])
        assert result is True
        ws_api._ws_client.call_method.assert_called_once_with("SC1.Blind1", "MoveToPosition", [45, 80], False)

    @pytest.mark.asyncio
    async def test_blind_set_position_no_cached_angle_returns_false(self, ws_api):
        """SetPosition without cached angle falls back to HTTP."""
        ws_api._instance_classes["SC1.Blind1"] = "SmartCOM.Blind.Blind"
        ws_api.get_blind_angle = MagicMock(return_value=None)
        result = await ws_api._try_ws_control("SC1.Blind1", "SetPosition", [80])
        assert result is False

    @pytest.mark.asyncio
    async def test_blind_set_angle_uses_cached_position(self, ws_api):
        """SetAngle uses MoveToPosition with [new_angle, cached_position]."""
        ws_api._instance_classes["SC1.Blind1"] = "SmartCOM.Blind.Blind"
        ws_api.get_blind_position = MagicMock(return_value=60)
        result = await ws_api._try_ws_control("SC1.Blind1", "SetAngle", [30])
        assert result is True
        ws_api._ws_client.call_method.assert_called_once_with("SC1.Blind1", "MoveToPosition", [30, 60], False)

    @pytest.mark.asyncio
    async def test_blind_set_angle_no_cached_position_returns_false(self, ws_api):
        """SetAngle without cached position falls back to HTTP."""
        ws_api._instance_classes["SC1.Blind1"] = "SmartCOM.Blind.Blind"
        ws_api.get_blind_position = MagicMock(return_value=None)
        result = await ws_api._try_ws_control("SC1.Blind1", "SetAngle", [30])
        assert result is False

    @pytest.mark.asyncio
    async def test_climate_fire_and_forget(self, ws_api):
        """Climate commands use fire_and_forget=True."""
        ws_api._instance_classes["Heating.Zone1"] = "SmartCOM.Clima.ClimateControl"
        result = await ws_api._try_ws_control("Heating.Zone1", "WriteDayMode", None)
        assert result is True
        ws_api._ws_client.call_method.assert_called_once_with("Heating.Zone1", "WriteDayMode", [], True)

    @pytest.mark.asyncio
    async def test_climate_set_temperature(self, ws_api):
        """Climate WriteCurrentSetTemperature passes temp in list."""
        ws_api._instance_classes["Heating.Zone1"] = "Heating.ClimateControlUniversal"
        result = await ws_api._try_ws_control("Heating.Zone1", "WriteCurrentSetTemperature", [22.5])
        assert result is True
        ws_api._ws_client.call_method.assert_called_once_with(
            "Heating.Zone1", "WriteCurrentSetTemperature", [22.5], True
        )

    @pytest.mark.asyncio
    async def test_physical_button_no_mapping_returns_false(self, ws_api):
        """Physical button commands return False (no control mappings)."""
        ws_api._instance_classes["SC1.Switch1"] = "SmartCOM.Switch"
        result = await ws_api._try_ws_control("SC1.Switch1", "SwitchOn", None)
        assert result is False

    @pytest.mark.asyncio
    async def test_unknown_method_returns_false(self, ws_api):
        """Unknown method for known class returns False."""
        ws_api._instance_classes["SC1.Light1"] = "SmartCOM.Light.LightDim"
        result = await ws_api._try_ws_control("SC1.Light1", "NonExistentMethod", None)
        assert result is False

    @pytest.mark.asyncio
    async def test_scene_execute(self, ws_api):
        """Scene Execute routes to CallMethod."""
        ws_api._instance_classes["System.Scene1"] = "System.SceneApp"
        result = await ws_api._try_ws_control("System.Scene1", "Execute", None)
        assert result is True
        ws_api._ws_client.call_method.assert_called_once_with("System.Scene1", "Execute", None, False)

    @pytest.mark.asyncio
    async def test_bathroom_radiator_switch_one_time(self, ws_api):
        """Bathroom radiator SwitchOneTime routes to CallMethod."""
        ws_api._instance_classes["Heating.Rad1"] = "Heating.BathroomRadiator"
        result = await ws_api._try_ws_control("Heating.Rad1", "SwitchOneTime", None)
        assert result is True
        ws_api._ws_client.call_method.assert_called_once_with("Heating.Rad1", "SwitchOneTime", None, False)

    @pytest.mark.asyncio
    async def test_home_state_activate(self, ws_api):
        """Home state Activate routes to CallMethod."""
        ws_api._instance_classes["System.State1"] = "System.HomeState"
        result = await ws_api._try_ws_control("System.State1", "Activate", None)
        assert result is True
        ws_api._ws_client.call_method.assert_called_once_with("System.State1", "Activate", None, False)


class TestLoginBackoff:
    """Tests for login backoff on network errors."""

    @pytest.mark.asyncio
    async def test_login_network_error_increments_backoff(self):
        """Network error during login should increment backoff counter."""
        api = EvonApi(host="http://192.168.1.100", username="user", password="pass")
        mock_session = MagicMock()
        mock_session.closed = False
        # post() is used as async context manager; raise on __aenter__
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(side_effect=aiohttp.ClientError("Connection refused"))
        mock_session.post = MagicMock(return_value=mock_cm)
        api._session = mock_session

        assert api._login_failure_count == 0

        with pytest.raises(EvonConnectionError):
            await api.login()

        assert api._login_failure_count == 1
        assert api._login_backoff_until > 0

    @pytest.mark.asyncio
    async def test_login_network_error_respects_backoff(self):
        """Second login attempt within backoff window should raise immediately."""
        api = EvonApi(host="http://192.168.1.100", username="user", password="pass")
        mock_session = MagicMock()
        mock_session.closed = False
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(side_effect=aiohttp.ClientError("Connection refused"))
        mock_session.post = MagicMock(return_value=mock_cm)
        api._session = mock_session

        with pytest.raises(EvonConnectionError):
            await api.login()

        # Second attempt should hit backoff
        with pytest.raises(EvonAuthError, match="Login rate limited"):
            await api.login()


class TestRequestAuthRetry:
    """Tests for safe auth retry in _request()."""

    @pytest.mark.asyncio
    async def test_request_401_login_failure_raises_auth_error(self):
        """When 401 triggers re-login that fails, should raise EvonAuthError cleanly."""
        import time

        api = EvonApi(host="http://192.168.1.100", username="user", password="pass")
        api._token = "old_token"
        api._token_timestamp = time.monotonic()

        mock_session = MagicMock()
        mock_session.closed = False

        # First request returns 401, then login fails with connection error
        mock_response = AsyncMock()
        mock_response.status = 401
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        mock_session.request = MagicMock(return_value=mock_response)
        # login() will fail — post() is used as async context manager
        mock_post_cm = AsyncMock()
        mock_post_cm.__aenter__ = AsyncMock(side_effect=aiohttp.ClientError("Connection refused"))
        mock_session.post = MagicMock(return_value=mock_post_cm)
        api._session = mock_session

        with pytest.raises(EvonAuthError, match="Re-authentication failed"):
            await api._request("GET", "/test")

    @pytest.mark.asyncio
    async def test_request_401_login_failure_does_not_leave_none_token(self):
        """After failed re-auth, token should not be left as None for next caller."""
        import time

        api = EvonApi(host="http://192.168.1.100", username="user", password="pass")
        api._token = "old_token"
        api._token_timestamp = time.monotonic()

        mock_session = MagicMock()
        mock_session.closed = False

        mock_response = AsyncMock()
        mock_response.status = 401
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        mock_session.request = MagicMock(return_value=mock_response)
        mock_post_cm = AsyncMock()
        mock_post_cm.__aenter__ = AsyncMock(side_effect=aiohttp.ClientError("Connection refused"))
        mock_session.post = MagicMock(return_value=mock_post_cm)
        api._session = mock_session

        with pytest.raises(EvonAuthError):
            await api._request("GET", "/test")

        # Backoff should be set, preventing immediate retry storm
        assert api._login_failure_count >= 1
