"""Unit tests for Evon API client."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

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
    async def test_set_climate_comfort_mode_heating(self, mock_api):
        """Test setting climate to comfort mode in heating season."""
        # In heating mode (is_cooling=False), comfort uses ModeSaved=4
        await mock_api.set_climate_comfort_mode("climate_1", is_cooling=False)
        mock_api._request.assert_called_with("POST", "/instances/climate_1/SetPreset", [4])

    @pytest.mark.asyncio
    async def test_set_climate_comfort_mode_cooling(self, mock_api):
        """Test setting climate to comfort mode in cooling season."""
        # In cooling mode (is_cooling=True), comfort uses ModeSaved=7
        await mock_api.set_climate_comfort_mode("climate_1", is_cooling=True)
        mock_api._request.assert_called_with("POST", "/instances/climate_1/SetPreset", [7])

    @pytest.mark.asyncio
    async def test_set_climate_energy_saving_mode_heating(self, mock_api):
        """Test setting climate to energy saving mode in heating season."""
        # In heating mode (is_cooling=False), eco uses ModeSaved=3
        await mock_api.set_climate_energy_saving_mode("climate_1", is_cooling=False)
        mock_api._request.assert_called_with("POST", "/instances/climate_1/SetPreset", [3])

    @pytest.mark.asyncio
    async def test_set_climate_energy_saving_mode_cooling(self, mock_api):
        """Test setting climate to energy saving mode in cooling season."""
        # In cooling mode (is_cooling=True), eco uses ModeSaved=6
        await mock_api.set_climate_energy_saving_mode("climate_1", is_cooling=True)
        mock_api._request.assert_called_with("POST", "/instances/climate_1/SetPreset", [6])

    @pytest.mark.asyncio
    async def test_set_climate_freeze_protection_mode_heating(self, mock_api):
        """Test setting climate to freeze protection mode in heating season."""
        # In heating mode (is_cooling=False), away uses ModeSaved=2
        await mock_api.set_climate_freeze_protection_mode("climate_1", is_cooling=False)
        mock_api._request.assert_called_with("POST", "/instances/climate_1/SetPreset", [2])

    @pytest.mark.asyncio
    async def test_set_climate_freeze_protection_mode_cooling(self, mock_api):
        """Test setting climate to freeze protection mode in cooling season."""
        # In cooling mode (is_cooling=True), away uses ModeSaved=5
        await mock_api.set_climate_freeze_protection_mode("climate_1", is_cooling=True)
        mock_api._request.assert_called_with("POST", "/instances/climate_1/SetPreset", [5])

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

        # WebSocket call_method should be called with SwitchOn (no params)
        mock_ws.call_method.assert_called_once_with("Light1", "SwitchOn", None)
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

        # WebSocket call_method should be called with SwitchOff (no params)
        mock_ws.call_method.assert_called_once_with("Light1", "SwitchOff", None)
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

        # WebSocket call_method should be called with BrightnessSetScaled([brightness, transition])
        mock_ws.call_method.assert_called_once_with("Light1", "BrightnessSetScaled", [75, 0])
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

        # WebSocket call_method should be used for Open
        mock_ws.call_method.assert_called_once_with("Blind1", "Open", None)
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

        # WebSocket call_method should be called with MoveToPosition([angle, position])
        mock_ws.call_method.assert_called_once_with("Blind1", "MoveToPosition", [45, 50])
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

        # WebSocket call_method should be called with MoveToPosition([angle, position])
        mock_ws.call_method.assert_called_once_with("Blind1", "MoveToPosition", [75, 30])
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
