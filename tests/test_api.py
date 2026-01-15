"""Tests for Evon API client."""
from __future__ import annotations

import pytest

from custom_components.evon.api import encode_password, EvonApi, EvonApiError, EvonAuthError
from tests.conftest import TEST_HOST, TEST_USERNAME, TEST_PASSWORD


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
