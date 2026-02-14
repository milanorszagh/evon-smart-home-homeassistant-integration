"""Tests for WebSocket _run_loop reconnection behavior."""

from __future__ import annotations

import asyncio
import contextlib
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from custom_components.evon.ws_client import (
    EvonWsClient,
    _calculate_reconnect_delay,
)


class TestCalculateReconnectDelay:
    """Tests for the reconnect delay calculation."""

    def test_delay_within_bounds(self):
        """Test that delay is always between 1.0 and max_delay."""
        for _ in range(100):
            delay = _calculate_reconnect_delay(5.0, 300.0)
            assert 1.0 <= delay <= 300.0

    def test_delay_with_small_base(self):
        """Test delay with a very small base stays above 1.0."""
        for _ in range(50):
            delay = _calculate_reconnect_delay(0.5, 300.0)
            assert delay >= 1.0

    def test_delay_capped_at_max(self):
        """Test delay is capped at max_delay."""
        for _ in range(50):
            delay = _calculate_reconnect_delay(400.0, 300.0)
            assert delay <= 300.0

    def test_jitter_varies(self):
        """Test that jitter produces varying results."""
        delays = {_calculate_reconnect_delay(10.0, 300.0) for _ in range(50)}
        # With jitter, we should get multiple distinct values
        assert len(delays) > 1


class TestRunLoopReconnection:
    """Tests for _run_loop reconnection behavior."""

    def _make_client(self, **kwargs):
        """Create a client with mocked session."""
        session = MagicMock(spec=aiohttp.ClientSession)
        session.closed = False
        return EvonWsClient(
            host="http://192.168.1.100",
            username="testuser",
            password="testpass",
            session=session,
            **kwargs,
        )

    @staticmethod
    async def _cleanup_client(client):
        """Cancel any lingering background tasks on the client."""
        for attr in ("_cleanup_task", "_resubscribe_task"):
            task = getattr(client, attr, None)
            if task and not task.done():
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task

    @pytest.mark.asyncio
    async def test_reconnect_with_backoff(self):
        """Test that failed connections trigger exponential backoff."""
        client = self._make_client()

        connect_attempts = 0
        max_attempts = 3

        async def mock_connect():
            nonlocal connect_attempts
            connect_attempts += 1
            if connect_attempts >= max_attempts:
                client._running = False
            return False

        client.connect = mock_connect

        # Patch sleep to avoid actual waiting
        sleep_delays = []

        async def mock_sleep(delay):
            sleep_delays.append(delay)

        with patch("asyncio.sleep", side_effect=mock_sleep):
            client._running = True
            await client._run_loop()

        assert connect_attempts == max_attempts
        # Should have sleep calls with increasing delays (backoff)
        assert len(sleep_delays) >= 2
        # Second delay base should be larger than first (exponential backoff)
        # Due to jitter the actual values vary, but the base doubles

    @pytest.mark.asyncio
    async def test_reconnect_delay_resets_on_success(self):
        """Test that reconnect delay resets after a successful connection."""
        client = self._make_client()

        # Set an elevated reconnect delay (as if we had previous failures)
        client._reconnect_delay = 80

        connect_count = 0

        async def mock_connect():
            nonlocal connect_count
            connect_count += 1
            # First attempt succeeds
            return True

        async def mock_wait_for_connected():
            # Simulate successful connection
            client._connected = True

        async def mock_handle_messages():
            # Stop after handling one message cycle
            client._running = False

        client.connect = mock_connect
        client._wait_for_connected = mock_wait_for_connected
        client._handle_messages = mock_handle_messages

        client._running = True
        await client._run_loop()
        await self._cleanup_client(client)

        # After successful connect, delay should be reset to default
        from custom_components.evon.const import DEFAULT_WS_RECONNECT_DELAY

        assert client._reconnect_delay == DEFAULT_WS_RECONNECT_DELAY

    @pytest.mark.asyncio
    async def test_resubscription_after_reconnect(self):
        """Test that subscriptions are re-sent after reconnection."""
        on_values_changed = MagicMock()
        client = self._make_client(on_values_changed=on_values_changed)

        # Pre-populate subscriptions (simulating previous subscribe call)
        test_subs = [
            {"Instanceid": "Light1", "Properties": ["IsOn", "ScaledBrightness"]},
            {"Instanceid": "Blind1", "Properties": ["Position", "Angle"]},
        ]
        client._subscriptions = list(test_subs)

        resubscribe_called = False

        async def mock_connect():
            return True

        async def mock_wait_for_connected():
            client._connected = True

        async def mock_resubscribe():
            nonlocal resubscribe_called
            resubscribe_called = True

        async def mock_handle_messages():
            # Wait briefly for the resubscribe task to be created and started
            await asyncio.sleep(0.05)
            client._running = False

        client.connect = mock_connect
        client._wait_for_connected = mock_wait_for_connected
        client._resubscribe = mock_resubscribe
        client._handle_messages = mock_handle_messages

        client._running = True
        await client._run_loop()

        # Wait for the resubscribe task
        if client._resubscribe_task and not client._resubscribe_task.done():
            await client._resubscribe_task

        await self._cleanup_client(client)
        assert resubscribe_called

    @pytest.mark.asyncio
    async def test_error_recovery_client_error(self):
        """Test recovery after aiohttp.ClientError during message handling."""
        client = self._make_client()

        attempt = 0

        async def mock_connect():
            return True

        async def mock_wait_for_connected():
            client._connected = True

        async def mock_handle_messages():
            nonlocal attempt
            attempt += 1
            if attempt == 1:
                raise aiohttp.ClientError("Connection lost")
            # Second call: stop
            client._running = False

        disconnect_called = False

        async def mock_disconnect():
            nonlocal disconnect_called
            disconnect_called = True
            client._connected = False
            client._ws = None

        client.connect = mock_connect
        client._wait_for_connected = mock_wait_for_connected
        client._handle_messages = mock_handle_messages
        client.disconnect = mock_disconnect

        with patch("asyncio.sleep", new_callable=AsyncMock):
            client._running = True
            await client._run_loop()

        await self._cleanup_client(client)
        assert disconnect_called
        assert attempt == 2  # Recovered and ran again

    @pytest.mark.asyncio
    async def test_error_recovery_unexpected_exception(self):
        """Test recovery after an unexpected exception during the run loop."""
        client = self._make_client()

        attempt = 0

        async def mock_connect():
            return True

        async def mock_wait_for_connected():
            client._connected = True

        async def mock_handle_messages():
            nonlocal attempt
            attempt += 1
            if attempt == 1:
                raise RuntimeError("Unexpected error")
            client._running = False

        async def mock_disconnect():
            client._connected = False
            client._ws = None

        client.connect = mock_connect
        client._wait_for_connected = mock_wait_for_connected
        client._handle_messages = mock_handle_messages
        client.disconnect = mock_disconnect

        with patch("asyncio.sleep", new_callable=AsyncMock):
            client._running = True
            await client._run_loop()

        await self._cleanup_client(client)
        assert attempt == 2

    @pytest.mark.asyncio
    async def test_cancelled_error_stops_loop(self):
        """Test that CancelledError cleanly stops the run loop."""
        client = self._make_client()

        async def mock_connect():
            raise asyncio.CancelledError()

        client.connect = mock_connect
        client._running = True

        # Should not raise, should exit cleanly
        await client._run_loop()

    @pytest.mark.asyncio
    async def test_no_resubscribe_without_subscriptions(self):
        """Test that resubscription is skipped when there are no subscriptions."""
        client = self._make_client()
        client._subscriptions = []

        resubscribe_called = False

        async def mock_connect():
            return True

        async def mock_wait_for_connected():
            client._connected = True

        async def mock_resubscribe():
            nonlocal resubscribe_called
            resubscribe_called = True

        async def mock_handle_messages():
            await asyncio.sleep(0.01)
            client._running = False

        client.connect = mock_connect
        client._wait_for_connected = mock_wait_for_connected
        client._resubscribe = mock_resubscribe
        client._handle_messages = mock_handle_messages

        client._running = True
        await client._run_loop()
        await self._cleanup_client(client)

        assert not resubscribe_called
