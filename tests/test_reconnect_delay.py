"""Tests for _calculate_reconnect_delay (C-L1)."""

from __future__ import annotations

from unittest.mock import patch

from custom_components.evon.const import (
    DEFAULT_WS_RECONNECT_DELAY,
    WS_RECONNECT_JITTER,
    WS_RECONNECT_MAX_DELAY,
)
from custom_components.evon.ws_client import _calculate_reconnect_delay


class TestCalculateReconnectDelay:
    """Test the pure function _calculate_reconnect_delay."""

    def test_result_within_jitter_range(self):
        """Test that delay is within +-25% of base_delay."""
        base = 10.0
        max_delay = 300.0

        for _ in range(100):
            delay = _calculate_reconnect_delay(base, max_delay)
            min_expected = base * (1 - WS_RECONNECT_JITTER)
            max_expected = base * (1 + WS_RECONNECT_JITTER)
            assert min_expected <= delay <= max_expected, f"delay={delay} outside [{min_expected}, {max_expected}]"

    def test_never_below_one(self):
        """Test that delay is always >= 1.0 seconds."""
        for _ in range(100):
            delay = _calculate_reconnect_delay(0.5, 300.0)
            assert delay >= 1.0

    def test_never_above_max_delay(self):
        """Test that delay is clamped to max_delay."""
        for _ in range(100):
            delay = _calculate_reconnect_delay(400.0, 300.0)
            assert delay <= 300.0

    def test_zero_base_returns_one(self):
        """Test that base_delay=0 still returns at least 1.0."""
        delay = _calculate_reconnect_delay(0.0, 300.0)
        assert delay >= 1.0

    def test_exact_max_delay_as_base(self):
        """Test with base_delay equal to max_delay."""
        for _ in range(50):
            delay = _calculate_reconnect_delay(300.0, 300.0)
            assert delay >= 1.0
            assert delay <= 300.0

    def test_deterministic_with_fixed_random(self):
        """Test delay calculation with a fixed random value."""
        with patch("custom_components.evon.ws_client.random.random", return_value=0.5):
            # random() = 0.5, so 2*0.5 - 1 = 0.0, jitter = 0
            delay = _calculate_reconnect_delay(10.0, 300.0)
            assert delay == 10.0

    def test_max_jitter_upward(self):
        """Test maximum upward jitter (random=1.0)."""
        with patch("custom_components.evon.ws_client.random.random", return_value=1.0):
            # 2*1.0 - 1 = 1.0, jitter = 10 * 0.25 * 1.0 = 2.5
            delay = _calculate_reconnect_delay(10.0, 300.0)
            assert delay == 12.5

    def test_max_jitter_downward(self):
        """Test maximum downward jitter (random=0.0)."""
        with patch("custom_components.evon.ws_client.random.random", return_value=0.0):
            # 2*0.0 - 1 = -1.0, jitter = 10 * 0.25 * -1.0 = -2.5
            delay = _calculate_reconnect_delay(10.0, 300.0)
            assert delay == 7.5

    def test_exponential_backoff_sequence(self):
        """Test exponential backoff behavior mimicking _run_loop."""
        reconnect_delay = DEFAULT_WS_RECONNECT_DELAY

        delays = []
        for _ in range(6):
            with patch("custom_components.evon.ws_client.random.random", return_value=0.5):
                delay = _calculate_reconnect_delay(reconnect_delay, WS_RECONNECT_MAX_DELAY)
            delays.append(delay)
            # Exponential backoff (matching _run_loop logic)
            reconnect_delay = min(reconnect_delay * 2, WS_RECONNECT_MAX_DELAY)

        # With jitter=0 (random=0.5), delays should be: 5, 10, 20, 40, 80, 160
        assert delays == [5.0, 10.0, 20.0, 40.0, 80.0, 160.0]

    def test_backoff_caps_at_max(self):
        """Test that backoff sequence caps at WS_RECONNECT_MAX_DELAY."""
        reconnect_delay = DEFAULT_WS_RECONNECT_DELAY

        for _ in range(20):
            reconnect_delay = min(reconnect_delay * 2, WS_RECONNECT_MAX_DELAY)

        assert reconnect_delay == WS_RECONNECT_MAX_DELAY

        with patch("custom_components.evon.ws_client.random.random", return_value=0.5):
            delay = _calculate_reconnect_delay(reconnect_delay, WS_RECONNECT_MAX_DELAY)
        assert delay == WS_RECONNECT_MAX_DELAY

    def test_default_constants_reasonable(self):
        """Test that the default constants are reasonable values."""
        assert DEFAULT_WS_RECONNECT_DELAY == 5
        assert WS_RECONNECT_MAX_DELAY == 300
        assert 0 < WS_RECONNECT_JITTER < 1
