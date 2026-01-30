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
        api = EvonApi(
            host="http://192.168.1.100",
            username="user",
            password="pass",
        )
        api._token = "existing_token"

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
        mock_api._request.assert_called_with(
            "POST", "/instances/light_1/AmznTurnOn", []
        )

    @pytest.mark.asyncio
    async def test_turn_off_light(self, mock_api):
        """Test turning off a light."""
        await mock_api.turn_off_light("light_1")
        mock_api._request.assert_called_with(
            "POST", "/instances/light_1/AmznTurnOff", []
        )

    @pytest.mark.asyncio
    async def test_set_light_brightness(self, mock_api):
        """Test setting light brightness."""
        await mock_api.set_light_brightness("light_1", 75)
        mock_api._request.assert_called_with(
            "POST", "/instances/light_1/AmznSetBrightness", [75]
        )

    @pytest.mark.asyncio
    async def test_open_blind(self, mock_api):
        """Test opening a blind."""
        await mock_api.open_blind("blind_1")
        mock_api._request.assert_called_with(
            "POST", "/instances/blind_1/Open", []
        )

    @pytest.mark.asyncio
    async def test_close_blind(self, mock_api):
        """Test closing a blind."""
        await mock_api.close_blind("blind_1")
        mock_api._request.assert_called_with(
            "POST", "/instances/blind_1/Close", []
        )

    @pytest.mark.asyncio
    async def test_stop_blind(self, mock_api):
        """Test stopping a blind."""
        await mock_api.stop_blind("blind_1")
        mock_api._request.assert_called_with(
            "POST", "/instances/blind_1/Stop", []
        )

    @pytest.mark.asyncio
    async def test_set_blind_position(self, mock_api):
        """Test setting blind position."""
        await mock_api.set_blind_position("blind_1", 50)
        mock_api._request.assert_called_with(
            "POST", "/instances/blind_1/AmznSetPercentage", [50]
        )

    @pytest.mark.asyncio
    async def test_set_blind_tilt(self, mock_api):
        """Test setting blind tilt."""
        await mock_api.set_blind_tilt("blind_1", 45)
        mock_api._request.assert_called_with(
            "POST", "/instances/blind_1/SetAngle", [45]
        )

    @pytest.mark.asyncio
    async def test_set_climate_comfort_mode(self, mock_api):
        """Test setting climate to comfort mode."""
        await mock_api.set_climate_comfort_mode("climate_1")
        mock_api._request.assert_called_with(
            "POST", "/instances/climate_1/WriteDayMode", []
        )

    @pytest.mark.asyncio
    async def test_set_climate_energy_saving_mode(self, mock_api):
        """Test setting climate to energy saving mode."""
        await mock_api.set_climate_energy_saving_mode("climate_1")
        mock_api._request.assert_called_with(
            "POST", "/instances/climate_1/WriteNightMode", []
        )

    @pytest.mark.asyncio
    async def test_set_climate_freeze_protection_mode(self, mock_api):
        """Test setting climate to freeze protection mode."""
        await mock_api.set_climate_freeze_protection_mode("climate_1")
        mock_api._request.assert_called_with(
            "POST", "/instances/climate_1/WriteFreezeMode", []
        )

    @pytest.mark.asyncio
    async def test_set_climate_temperature(self, mock_api):
        """Test setting climate temperature."""
        await mock_api.set_climate_temperature("climate_1", 22.5)
        mock_api._request.assert_called_with(
            "POST", "/instances/climate_1/WriteCurrentSetTemperature", [22.5]
        )

    @pytest.mark.asyncio
    async def test_execute_scene(self, mock_api):
        """Test executing a scene."""
        await mock_api.execute_scene("scene_1")
        mock_api._request.assert_called_with(
            "POST", "/instances/scene_1/Execute", []
        )

    @pytest.mark.asyncio
    async def test_activate_home_state(self, mock_api):
        """Test activating a home state."""
        await mock_api.activate_home_state("HomeStateAtHome")
        mock_api._request.assert_called_with(
            "POST", "/instances/HomeStateAtHome/Activate", []
        )

    @pytest.mark.asyncio
    async def test_toggle_bathroom_radiator(self, mock_api):
        """Test toggling bathroom radiator."""
        await mock_api.toggle_bathroom_radiator("radiator_1")
        mock_api._request.assert_called_with(
            "POST", "/instances/radiator_1/Switch", []
        )


class TestEvonApiExceptions:
    """Tests for API exception handling."""

    def test_evon_api_error_inheritance(self):
        """Test that EvonApiError inherits from HomeAssistantError."""
        from homeassistant.exceptions import HomeAssistantError

        assert issubclass(EvonApiError, HomeAssistantError)

    def test_evon_auth_error_inheritance(self):
        """Test that EvonAuthError inherits from EvonApiError."""
        assert issubclass(EvonAuthError, EvonApiError)

    def test_evon_connection_error_inheritance(self):
        """Test that EvonConnectionError inherits from EvonApiError."""
        assert issubclass(EvonConnectionError, EvonApiError)
