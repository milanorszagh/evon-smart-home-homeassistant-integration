"""Tests for Evon API client.

These tests use importlib to load api.py directly, avoiding the __init__.py
import chain that requires homeassistant. We mock the homeassistant module
to allow importing api.py without the full HA installation.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from types import ModuleType
from unittest.mock import MagicMock

from tests.conftest import TEST_HOST, TEST_PASSWORD, TEST_USERNAME

# Create a mock homeassistant module before importing api.py
mock_ha = ModuleType("homeassistant")
mock_ha_exceptions = ModuleType("homeassistant.exceptions")


class MockHomeAssistantError(Exception):
    """Mock HomeAssistantError for testing."""

    pass


mock_ha_exceptions.HomeAssistantError = MockHomeAssistantError
mock_ha.exceptions = mock_ha_exceptions
sys.modules["homeassistant"] = mock_ha
sys.modules["homeassistant.exceptions"] = mock_ha_exceptions

# Load api.py directly without triggering __init__.py
api_path = os.path.join(
    os.path.dirname(__file__), "..", "custom_components", "evon", "api.py"
)
spec = importlib.util.spec_from_file_location("evon_api", api_path)
evon_api = importlib.util.module_from_spec(spec)
sys.modules["evon_api"] = evon_api
spec.loader.exec_module(evon_api)

# Import the classes we need
EvonApi = evon_api.EvonApi
EvonApiError = evon_api.EvonApiError
EvonAuthError = evon_api.EvonAuthError
encode_password = evon_api.encode_password


class TestPasswordEncoding:
    """Test password encoding."""

    def test_encode_password(self):
        """Test that password encoding works correctly."""
        # Test with known values
        username = "TestUser"
        password = "test_password_123"
        encoded = encode_password(username, password)

        # The encoded password should be a base64 string
        assert encoded is not None
        assert len(encoded) == 88  # SHA512 produces 64 bytes, base64 encoded = 88 chars
        assert encoded.endswith("==")

    def test_encode_password_consistency(self):
        """Test that encoding is consistent."""
        encoded1 = encode_password("user", "pass")
        encoded2 = encode_password("user", "pass")
        assert encoded1 == encoded2

    def test_encode_password_different_inputs(self):
        """Test that different inputs produce different outputs."""
        encoded1 = encode_password("user1", "pass")
        encoded2 = encode_password("user2", "pass")
        assert encoded1 != encoded2


class TestEvonApi:
    """Test EvonApi class."""

    def test_init_with_plain_password(self):
        """Test API initialization with plain password."""
        api = EvonApi(
            host=TEST_HOST,
            username=TEST_USERNAME,
            password=TEST_PASSWORD,
        )
        # Password should be encoded
        assert api._password != TEST_PASSWORD
        assert len(api._password) == 88

    def test_init_with_encoded_password(self):
        """Test API initialization with pre-encoded password."""
        encoded = encode_password(TEST_USERNAME, TEST_PASSWORD)
        api = EvonApi(
            host=TEST_HOST,
            username=TEST_USERNAME,
            password=encoded,
            password_is_encoded=True,
        )
        # Password should remain as-is
        assert api._password == encoded

    def test_host_trailing_slash_removed(self):
        """Test that trailing slash is removed from host."""
        api = EvonApi(
            host=f"{TEST_HOST}/",
            username=TEST_USERNAME,
            password=TEST_PASSWORD,
        )
        assert api._host == TEST_HOST


class TestEvonApiErrors:
    """Test API error classes."""

    def test_evon_api_error(self):
        """Test EvonApiError."""
        error = EvonApiError("Test error")
        assert str(error) == "Test error"

    def test_evon_auth_error_inherits(self):
        """Test that EvonAuthError inherits from EvonApiError."""
        error = EvonAuthError("Auth failed")
        assert isinstance(error, EvonApiError)
        assert str(error) == "Auth failed"


class TestEvonApiHomeStateMethods:
    """Test home state related API methods."""

    def test_api_has_home_state_methods(self):
        """Test that API has home state methods."""
        api = EvonApi(
            host=TEST_HOST,
            username=TEST_USERNAME,
            password=TEST_PASSWORD,
        )
        # Check methods exist
        assert hasattr(api, "get_home_states")
        assert hasattr(api, "get_active_home_state")
        assert hasattr(api, "activate_home_state")
        # Check they are callable
        assert callable(api.get_home_states)
        assert callable(api.get_active_home_state)
        assert callable(api.activate_home_state)


class TestEvonApiSeasonModeMethods:
    """Test season mode related API methods."""

    def test_api_has_season_mode_methods(self):
        """Test that API has season mode methods."""
        api = EvonApi(
            host=TEST_HOST,
            username=TEST_USERNAME,
            password=TEST_PASSWORD,
        )
        # Check methods exist
        assert hasattr(api, "get_season_mode")
        assert hasattr(api, "set_season_mode")
        # Check they are callable
        assert callable(api.get_season_mode)
        assert callable(api.set_season_mode)
