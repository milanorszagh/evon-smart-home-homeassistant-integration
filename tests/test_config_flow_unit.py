"""Unit tests for config flow helpers (no HA framework required)."""

from __future__ import annotations

import pytest

from custom_components.evon.config_flow import InvalidHostError, normalize_host


class TestNormalizeHost:
    """Tests for normalize_host function."""

    def test_normalize_ip_address(self):
        """Test normalizing plain IP address."""
        result = normalize_host("192.168.1.100")
        assert result == "http://192.168.1.100"

    def test_normalize_ip_with_port(self):
        """Test normalizing IP address with port."""
        result = normalize_host("192.168.1.100:8080")
        assert result == "http://192.168.1.100:8080"

    def test_normalize_with_http_scheme(self):
        """Test normalizing URL with http scheme."""
        result = normalize_host("http://192.168.1.100")
        assert result == "http://192.168.1.100"

    def test_normalize_with_https_scheme(self):
        """Test normalizing URL with https scheme."""
        result = normalize_host("https://192.168.1.100")
        assert result == "https://192.168.1.100"

    def test_normalize_strips_trailing_slash(self):
        """Test that trailing slash is stripped."""
        result = normalize_host("http://192.168.1.100/")
        assert result == "http://192.168.1.100"

    def test_normalize_strips_path(self):
        """Test that path is stripped (only netloc kept)."""
        result = normalize_host("http://192.168.1.100/api/v1")
        assert result == "http://192.168.1.100"

    def test_normalize_strips_whitespace(self):
        """Test that whitespace is stripped."""
        result = normalize_host("  192.168.1.100  ")
        assert result == "http://192.168.1.100"

    def test_normalize_hostname(self):
        """Test normalizing hostname."""
        result = normalize_host("evon.local")
        assert result == "http://evon.local"

    def test_normalize_hostname_with_port(self):
        """Test normalizing hostname with port."""
        result = normalize_host("evon.local:8080")
        assert result == "http://evon.local:8080"

    def test_normalize_empty_raises(self):
        """Test that empty string raises InvalidHostError."""
        with pytest.raises(InvalidHostError, match="Host cannot be empty"):
            normalize_host("")

    def test_normalize_whitespace_only_raises(self):
        """Test that whitespace-only string raises InvalidHostError."""
        with pytest.raises(InvalidHostError, match="Host cannot be empty"):
            normalize_host("   ")

    def test_normalize_scheme_only_raises(self):
        """Test that scheme-only URL raises InvalidHostError."""
        with pytest.raises(InvalidHostError, match="no valid host found"):
            normalize_host("http://")

    def test_normalize_scheme_only_with_slash_raises(self):
        """Test that scheme with only slashes raises InvalidHostError."""
        # http:// with nothing after should fail
        with pytest.raises(InvalidHostError, match="no valid host found"):
            normalize_host("https://")


class TestInvalidHostError:
    """Tests for InvalidHostError exception."""

    def test_invalid_host_error_is_value_error(self):
        """Test that InvalidHostError inherits from ValueError."""
        assert issubclass(InvalidHostError, ValueError)

    def test_invalid_host_error_message(self):
        """Test InvalidHostError can carry a message."""
        error = InvalidHostError("Test message")
        assert str(error) == "Test message"
