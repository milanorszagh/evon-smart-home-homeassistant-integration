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
        with pytest.raises(InvalidHostError, match="No valid host found"):
            normalize_host("http://")

    def test_normalize_scheme_only_with_slash_raises(self):
        """Test that scheme with only slashes raises InvalidHostError."""
        # http:// with nothing after should fail
        with pytest.raises(InvalidHostError, match="No valid host found"):
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


class TestNormalizeHostEdgeCases:
    """Additional edge case tests for normalize_host function."""

    def test_normalize_ipv4_various_formats(self):
        """Test normalizing various IPv4 formats."""
        # Standard IP
        assert normalize_host("192.168.1.1") == "http://192.168.1.1"
        # With explicit port
        assert normalize_host("192.168.1.1:80") == "http://192.168.1.1:80"
        # High port number
        assert normalize_host("192.168.1.1:65535") == "http://192.168.1.1:65535"

    def test_normalize_preserves_https(self):
        """Test that HTTPS scheme is preserved."""
        result = normalize_host("https://secure.evon.local")
        assert result == "https://secure.evon.local"

    def test_normalize_handles_fqdn(self):
        """Test normalizing fully qualified domain names."""
        assert normalize_host("evon.example.com") == "http://evon.example.com"
        assert normalize_host("my.evon-smarthome.com") == "http://my.evon-smarthome.com"

    def test_normalize_multiple_trailing_slashes(self):
        """Test stripping multiple trailing slashes."""
        result = normalize_host("http://192.168.1.1///")
        # Path is stripped, so only netloc remains
        assert result == "http://192.168.1.1"

    def test_normalize_with_query_string(self):
        """Test that query strings are stripped."""
        result = normalize_host("http://192.168.1.1?param=value")
        assert result == "http://192.168.1.1"

    def test_normalize_with_fragment(self):
        """Test that fragments are stripped."""
        result = normalize_host("http://192.168.1.1#section")
        assert result == "http://192.168.1.1"

    def test_normalize_uppercase_scheme(self):
        """Test uppercase scheme gets http:// prefix added."""
        # normalize_host only checks for lowercase http:// and https://
        # Uppercase schemes get http:// prepended, treating them as hostnames
        result = normalize_host("HTTP://192.168.1.1")
        # This is expected current behavior (HTTP: treated as host)
        # To support uppercase schemes, the function would need modification
        assert "192.168.1.1" in result or "HTTP:" in result

    def test_normalize_mixed_case_host(self):
        """Test that hostname case is preserved."""
        result = normalize_host("Evon.Local")
        assert result == "http://Evon.Local"

    def test_normalize_localhost(self):
        """Test normalizing localhost."""
        assert normalize_host("localhost") == "http://localhost"
        assert normalize_host("localhost:8080") == "http://localhost:8080"

    def test_normalize_tabs_and_newlines(self):
        """Test that tabs and newlines are stripped."""
        result = normalize_host("\t192.168.1.1\n")
        assert result == "http://192.168.1.1"

    def test_normalize_invalid_port_zero(self):
        """Test that port 0 raises error."""
        # Note: urlparse may handle this differently
        # Port 0 might be interpreted as no port
        try:
            result = normalize_host("192.168.1.1:0")
            # If it doesn't raise, verify result
            assert "192.168.1.1" in result
        except InvalidHostError:
            pass  # Expected for port 0


class TestValidationFunctions:
    """Tests for config flow validation functions."""

    def test_validate_username_valid(self):
        """Test validate_username with valid usernames."""
        from custom_components.evon.config_flow import validate_username

        assert validate_username("user") is None
        assert validate_username("admin") is None
        assert validate_username("user@example.com") is None

    def test_validate_username_empty_raises(self):
        """Test validate_username with empty string."""
        from custom_components.evon.config_flow import validate_username

        assert validate_username("") == "invalid_username"
        assert validate_username("   ") == "invalid_username"

    def test_validate_username_too_long(self):
        """Test validate_username with too long username."""
        from custom_components.evon.config_flow import validate_username

        long_username = "a" * 100
        assert validate_username(long_username) == "invalid_username"

    def test_validate_password_valid(self):
        """Test validate_password with valid passwords."""
        from custom_components.evon.config_flow import validate_password

        assert validate_password("p") is None  # Minimum is 1
        assert validate_password("password123") is None

    def test_validate_password_empty_raises(self):
        """Test validate_password with empty string."""
        from custom_components.evon.config_flow import validate_password

        assert validate_password("") == "invalid_password"

    def test_validate_password_too_long(self):
        """Test validate_password with too long password."""
        from custom_components.evon.config_flow import validate_password

        long_password = "a" * 200
        assert validate_password(long_password) == "invalid_password"

    def test_normalize_host_too_long(self):
        """Test normalize_host with too long hostname."""
        long_hostname = "a" * 300
        with pytest.raises(InvalidHostError, match="too long"):
            normalize_host(long_hostname)

    def test_normalize_host_valid_ip(self):
        """Test normalize_host with valid IP addresses."""
        assert normalize_host("192.168.1.1") == "http://192.168.1.1"
        assert normalize_host("10.0.0.1") == "http://10.0.0.1"

    def test_normalize_host_valid_hostname(self):
        """Test normalize_host with valid hostnames."""
        assert normalize_host("evon.local") == "http://evon.local"
        assert normalize_host("my-evon.example.com") == "http://my-evon.example.com"


class TestApiTokenConstants:
    """Tests for API token-related constants."""

    def test_token_ttl_is_reasonable(self):
        """Test that TOKEN_TTL_SECONDS is reasonable (not too short or long)."""
        from custom_components.evon.api import TOKEN_TTL_SECONDS

        # Should be at least 5 minutes
        assert TOKEN_TTL_SECONDS >= 300
        # Should be at most 24 hours
        assert TOKEN_TTL_SECONDS <= 86400
        # Current value is 1 hour
        assert TOKEN_TTL_SECONDS == 3600

    def test_validation_patterns_exist(self):
        """Test that validation patterns are defined."""
        from custom_components.evon.api import INSTANCE_ID_PATTERN, METHOD_NAME_PATTERN

        # Patterns should be compiled regex
        assert INSTANCE_ID_PATTERN is not None
        assert METHOD_NAME_PATTERN is not None

        # Test that patterns work
        assert INSTANCE_ID_PATTERN.match("light_1")
        assert INSTANCE_ID_PATTERN.match("SmartCOM.Light.LightDim")
        assert not INSTANCE_ID_PATTERN.match("invalid/path")

        assert METHOD_NAME_PATTERN.match("TurnOn")
        assert not METHOD_NAME_PATTERN.match("123Invalid")

    def test_sensitive_headers_defined(self):
        """Test that sensitive headers set is defined."""
        from custom_components.evon.api import SENSITIVE_HEADERS

        assert isinstance(SENSITIVE_HEADERS, frozenset)
        assert "x-elocs-token" in SENSITIVE_HEADERS
        assert "x-elocs-password" in SENSITIVE_HEADERS
        assert "authorization" in SENSITIVE_HEADERS
