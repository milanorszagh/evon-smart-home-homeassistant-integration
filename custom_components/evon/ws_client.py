"""WebSocket client for Evon Smart Home real-time updates."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
import contextlib
import json
import logging
import random
from typing import Any

import aiohttp

from .api import EvonWsError, EvonWsNotConnectedError, EvonWsTimeoutError, encode_password
from .const import (
    DEFAULT_WS_RECONNECT_DELAY,
    WS_DEFAULT_REQUEST_TIMEOUT,
    WS_HEARTBEAT_INTERVAL,
    WS_LOG_MESSAGE_TRUNCATE,
    WS_MAX_PENDING_REQUESTS,
    WS_PROTOCOL,
    WS_RECONNECT_MAX_DELAY,
    WS_SUBSCRIBE_REQUEST_TIMEOUT,
)

_LOGGER = logging.getLogger(__name__)

# WebSocket message types
WS_MSG_CONNECTED = "Connected"
WS_MSG_CALLBACK = "Callback"
WS_MSG_EVENT = "Event"

# Jitter factor for reconnect delays (0.0 to 1.0)
# Adds randomness to prevent thundering herd on server recovery
WS_RECONNECT_JITTER = 0.25


def _calculate_reconnect_delay(base_delay: float, max_delay: float) -> float:
    """Calculate reconnect delay with jitter.

    Args:
        base_delay: The base delay in seconds.
        max_delay: The maximum delay in seconds.

    Returns:
        The delay with random jitter applied (±25% of base).
    """
    # Apply jitter: randomly adjust delay by ±25%
    jitter = base_delay * WS_RECONNECT_JITTER * (2 * random.random() - 1)
    delay = base_delay + jitter
    # Clamp to valid range
    return max(1.0, min(delay, max_delay))


class EvonWsClient:
    """WebSocket client for real-time updates from Evon Smart Home."""

    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        session: aiohttp.ClientSession | None = None,
        on_values_changed: Callable[[str, dict[str, Any]], None] | None = None,
        on_connection_state: Callable[[bool], None] | None = None,
        is_remote: bool = False,
        engine_id: str | None = None,
        get_session: Callable[[], aiohttp.ClientSession] | None = None,
    ) -> None:
        """Initialize the WebSocket client.

        Args:
            host: The Evon system URL (e.g., http://192.168.1.100) or remote host
            username: The username for authentication
            password: The password (plain text, will be encoded)
            session: The aiohttp client session (deprecated, use get_session)
            on_values_changed: Callback for ValuesChanged events (instance_id, properties)
            on_connection_state: Callback for connection state changes (connected: bool)
            is_remote: Whether this is a remote connection via my.evon-smarthome.com
            engine_id: The engine ID for remote connections
            get_session: Callback to get a fresh aiohttp session (preferred over session)
        """
        self._is_remote = is_remote
        self._engine_id = engine_id

        if is_remote:
            # Remote WebSocket connects to wss://my.evon-smarthome.com/
            self._host = "https://my.evon-smarthome.com"
            self._ws_host = "wss://my.evon-smarthome.com/"
        else:
            # Local WebSocket
            self._host = host.rstrip("/")
            self._ws_host = self._host.replace("http://", "ws://").replace("https://", "wss://")

        self._username = username
        self._password = encode_password(username, password)
        self._session = session
        self._get_session = get_session
        self._on_values_changed = on_values_changed
        self._on_connection_state = on_connection_state

        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self._token: str | None = None
        self._sequence_id = 1
        self._connected = False
        self._running = False
        self._reconnect_delay = DEFAULT_WS_RECONNECT_DELAY
        self._message_task: asyncio.Task | None = None
        self._resubscribe_task: asyncio.Task | None = None
        self._pending_requests: dict[int, asyncio.Future] = {}
        self._subscriptions: list[dict[str, Any]] = []

    @property
    def is_connected(self) -> bool:
        """Return whether the WebSocket is connected."""
        return self._connected and self._ws is not None and not self._ws.closed

    def _get_valid_session(self) -> aiohttp.ClientSession:
        """Get a valid (non-closed) aiohttp session.

        Returns:
            A valid aiohttp session.

        Raises:
            RuntimeError: If no valid session is available.
        """
        # If we have a session factory, use it to get a fresh session if needed
        if self._get_session is not None:
            # Always get fresh session from callback if available
            session = self._get_session()
            if session is not None and not session.closed:
                self._session = session
                return session

        # Fall back to stored session
        if self._session is not None and not self._session.closed:
            return self._session

        raise RuntimeError("Session is closed and no session factory available")

    async def connect(self) -> bool:
        """Connect to the WebSocket server.

        Returns:
            True if connection successful, False otherwise.
        """
        if self.is_connected:
            return True

        try:
            # Get authentication token via HTTP login
            self._token = await self._login()
            if not self._token:
                _LOGGER.error("Failed to obtain authentication token for WebSocket")
                return False

            # Connect to WebSocket
            _LOGGER.debug(
                "Connecting WebSocket to %s (remote=%s)",
                self._ws_host,
                self._is_remote,
            )

            # Build cookie based on connection type
            if self._is_remote:
                cookie = f"token={self._token}; x-elocs-isrelay=true; x-elocs-token_in_cookie_only=0"
                origin = "https://my.evon-smarthome.com"
            else:
                cookie = f"token={self._token}; x-elocs-isrelay=false; x-elocs-token_in_cookie_only=0"
                origin = self._host

            session = self._get_valid_session()
            self._ws = await session.ws_connect(
                self._ws_host,
                protocols=[WS_PROTOCOL],
                headers={
                    "Origin": origin,
                    "Cookie": cookie,
                },
                heartbeat=WS_HEARTBEAT_INTERVAL,
            )

            _LOGGER.debug(
                "WebSocket connection established to %s, protocol=%s",
                self._ws_host,
                self._ws.protocol if self._ws else None,
            )
            return True

        except aiohttp.ClientError as err:
            _LOGGER.error("WebSocket connection failed: %s", err)
            return False
        except Exception as err:  # pylint: disable=broad-except
            _LOGGER.error("Unexpected error during WebSocket connection: %s", err)
            return False

    async def _login(self) -> str | None:
        """Login via HTTP to get authentication token.

        Returns:
            The authentication token or None if login failed.
        """
        try:
            # Build headers based on connection type
            headers = {
                "x-elocs-username": self._username,
                "x-elocs-password": self._password,
            }

            if self._is_remote and self._engine_id:
                # Remote login requires additional headers
                headers["x-elocs-relayid"] = self._engine_id
                headers["x-elocs-sessionlogin"] = "true"
                headers["X-Requested-With"] = "XMLHttpRequest"
                login_url = "https://my.evon-smarthome.com/login"
            else:
                login_url = f"{self._host}/login"

            session = self._get_valid_session()
            async with session.post(
                login_url,
                headers=headers,
                allow_redirects=False,
            ) as response:
                _LOGGER.debug(
                    "WebSocket login response: status=%s",
                    response.status,
                )

                # Token can be in headers regardless of status code
                token = response.headers.get("x-elocs-token")

                if response.status == 302:
                    location = response.headers.get("Location", "")
                    if "login" in location.lower() and not token:
                        _LOGGER.error("WebSocket login failed: Invalid credentials")
                        return None
                    # Redirect with token is OK (common for successful login)
                    if token:
                        return token
                    _LOGGER.error("WebSocket login failed: Redirect without token")
                    return None

                if response.status != 200:
                    _LOGGER.error("WebSocket login failed: %s", response.status)
                    return None

                if not token:
                    _LOGGER.error("No token received from login")
                    return None

                return token

        except aiohttp.ClientError as err:
            _LOGGER.error("HTTP login failed: %s", err)
            return None

    async def start(self) -> None:
        """Start the WebSocket client with automatic reconnection."""
        if self._running:
            return

        self._running = True
        self._message_task = asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        """Stop the WebSocket client and disconnect."""
        self._running = False

        # Cancel the message loop task
        if self._message_task:
            self._message_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._message_task
            self._message_task = None

        # Close the WebSocket
        await self.disconnect()

        # Clear subscriptions since we're fully stopping
        self._subscriptions.clear()
        _LOGGER.debug("WebSocket client stopped and subscriptions cleared")

    async def disconnect(self) -> None:
        """Disconnect from the WebSocket server."""
        # Clear token first to prevent stale auth on any in-flight requests
        self._token = None

        # Cancel any pending resubscribe task
        if self._resubscribe_task and not self._resubscribe_task.done():
            self._resubscribe_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._resubscribe_task
            self._resubscribe_task = None

        # Reject pending requests before closing connection
        # to ensure proper error handling
        pending = list(self._pending_requests.items())
        self._pending_requests.clear()
        for seq_id, future in pending:
            if not future.done():
                future.set_exception(EvonWsNotConnectedError("WebSocket disconnected"))
            _LOGGER.debug("Rejected pending request: seq=%s", seq_id)

        # Close WebSocket connection
        if self._ws and not self._ws.closed:
            try:
                await self._ws.close()
            except Exception as err:
                _LOGGER.debug("Error closing WebSocket: %s", err)
        self._ws = None

        # Notify connection state change
        if self._connected:
            self._connected = False
            if self._on_connection_state:
                try:
                    self._on_connection_state(False)
                except Exception as err:
                    _LOGGER.warning("Error in connection state callback: %s", err)

    async def _run_loop(self) -> None:
        """Main loop for handling messages and reconnection."""
        while self._running:
            try:
                # Connect if not connected
                if not self.is_connected:
                    if await self.connect():
                        self._reconnect_delay = DEFAULT_WS_RECONNECT_DELAY
                        # Start message handler and wait for Connected message
                        _LOGGER.debug("WS connect OK, waiting for Connected message")
                        await self._wait_for_connected()
                        _LOGGER.debug("WS _wait_for_connected done, _connected=%s", self._connected)
                        # Resubscribe after connection is established and message loop can process responses
                        if self._connected and self._subscriptions:
                            _LOGGER.debug("WS scheduling resubscription for %d instances", len(self._subscriptions))
                            self._resubscribe_task = asyncio.create_task(self._resubscribe())
                    else:
                        # Connection failed, wait before retry with jitter
                        delay = _calculate_reconnect_delay(
                            self._reconnect_delay, WS_RECONNECT_MAX_DELAY
                        )
                        _LOGGER.debug(
                            "WebSocket reconnecting in %.1f seconds (base: %d)",
                            delay,
                            self._reconnect_delay,
                        )
                        await asyncio.sleep(delay)
                        # Exponential backoff (without jitter, jitter applied at sleep time)
                        self._reconnect_delay = min(
                            self._reconnect_delay * 2,
                            WS_RECONNECT_MAX_DELAY,
                        )
                        continue

                # Handle messages
                _LOGGER.debug("WS entering _handle_messages, is_connected=%s", self.is_connected)
                await self._handle_messages()

            except asyncio.CancelledError:
                break
            except Exception as err:  # pylint: disable=broad-except
                _LOGGER.error("WebSocket loop error: %s", err)
                await self.disconnect()
                if self._running:
                    delay = _calculate_reconnect_delay(
                        self._reconnect_delay, WS_RECONNECT_MAX_DELAY
                    )
                    await asyncio.sleep(delay)
                    self._reconnect_delay = min(
                        self._reconnect_delay * 2,
                        WS_RECONNECT_MAX_DELAY,
                    )

    async def _wait_for_connected(self) -> None:
        """Wait for the Connected message from the server."""
        if not self._ws:
            return

        try:
            # Only timeout on the receive, not on processing
            async with asyncio.timeout(10):
                msg = await self._ws.receive()

            _LOGGER.debug(
                "WebSocket received message: type=%s, data=%s",
                msg.type,
                msg.data[:WS_LOG_MESSAGE_TRUNCATE] if msg.data else None,
            )

            if msg.type == aiohttp.WSMsgType.TEXT:
                data = json.loads(msg.data)
                if data and data[0] == WS_MSG_CONNECTED:
                    self._connected = True
                    _LOGGER.info("WebSocket connected to Evon Smart Home")
                    if self._on_connection_state:
                        self._on_connection_state(True)
                    # Note: Don't resubscribe here - let _run_loop handle it
                    # after the message handler is active
                    return
                else:
                    _LOGGER.warning(
                        "Expected 'Connected' message but got: %s",
                        data[0] if data else None,
                    )
            elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.CLOSE):
                _LOGGER.error("WebSocket closed before Connected message")
            elif msg.type == aiohttp.WSMsgType.ERROR:
                _LOGGER.error("WebSocket error: %s", self._ws.exception() if self._ws else None)

            # If we get here, we didn't get a valid Connected message
            await self.disconnect()

        except TimeoutError:
            _LOGGER.error("Timeout waiting for WebSocket Connected message")
            await self.disconnect()
        except Exception as err:  # pylint: disable=broad-except
            _LOGGER.error("Error waiting for Connected message: %s", err)
            await self.disconnect()

    async def _handle_messages(self) -> None:
        """Handle incoming WebSocket messages."""
        if not self._ws:
            return

        try:
            msg = await self._ws.receive()
            _LOGGER.debug("WS msg received: type=%s, len=%s", msg.type, len(msg.data) if msg.data else 0)

            if msg.type == aiohttp.WSMsgType.TEXT:
                self._handle_message(msg.data)
            elif msg.type == aiohttp.WSMsgType.CLOSED:
                _LOGGER.debug("WebSocket closed by server")
                await self.disconnect()
            elif msg.type == aiohttp.WSMsgType.ERROR:
                _LOGGER.error("WebSocket error: %s", self._ws.exception())
                await self.disconnect()

        except asyncio.CancelledError:
            raise
        except Exception as err:  # pylint: disable=broad-except
            _LOGGER.error("Error handling WebSocket message: %s", err)
            await self.disconnect()

    def _handle_message(self, data: str) -> None:
        """Parse and handle a WebSocket message.

        Args:
            data: The raw JSON message string.
        """
        try:
            msg = json.loads(data)
            msg_type = msg[0]

            if msg_type == WS_MSG_CALLBACK:
                # Response to a request
                payload = msg[1]
                sequence_id = payload.get("sequenceId")
                _LOGGER.debug("Callback received: seq=%s, pending=%s", sequence_id, list(self._pending_requests.keys()))
                if sequence_id in self._pending_requests:
                    future = self._pending_requests.pop(sequence_id)
                    if not future.done():
                        args = payload.get("args", [])
                        future.set_result(args[0] if args else None)

            elif msg_type == WS_MSG_EVENT:
                # Event from the server
                payload = msg[1]
                if payload.get("methodName") == "ValuesChanged":
                    self._handle_values_changed(payload.get("args", []))

            elif msg_type == WS_MSG_CONNECTED:
                # Already handled in _wait_for_connected
                pass

        except json.JSONDecodeError as err:
            _LOGGER.error("Failed to parse WebSocket message: %s", err)
        except Exception as err:  # pylint: disable=broad-except
            _LOGGER.error("Error handling WebSocket message: %s", err)

    def _handle_values_changed(self, args: list[Any]) -> None:
        """Handle a ValuesChanged event.

        Args:
            args: The event arguments containing the table of changed values.
        """
        if not args or not self._on_values_changed:
            return

        table = args[0].get("table", {})
        if not table:
            return

        # Group values by instance ID
        grouped: dict[str, dict[str, Any]] = {}

        for key, entry in table.items():
            # Key format: "InstanceId.PropertyName"
            parts = key.split(".")
            prop = parts.pop()
            instance_id = ".".join(parts)

            if instance_id not in grouped:
                grouped[instance_id] = {}

            # Extract the actual value
            value_data = entry.get("value", {})
            grouped[instance_id][prop] = value_data.get("Value")

        # Notify callback for each instance
        for instance_id, properties in grouped.items():
            try:
                self._on_values_changed(instance_id, properties)
            except Exception as err:  # pylint: disable=broad-except
                _LOGGER.error(
                    "Error in values changed callback for %s: %s",
                    instance_id,
                    err,
                )

    async def _send_request(
        self,
        method_name: str,
        args: list[Any],
        request_timeout: float = WS_DEFAULT_REQUEST_TIMEOUT,
    ) -> Any:
        """Send a request and wait for the response.

        Args:
            method_name: The method to call.
            args: The arguments to pass.
            request_timeout: Timeout in seconds.

        Returns:
            The response value.

        Raises:
            Exception: If the request fails or times out.
        """
        if not self.is_connected:
            raise EvonWsNotConnectedError("WebSocket not connected")

        # Prevent unbounded memory growth from too many pending requests
        if len(self._pending_requests) >= WS_MAX_PENDING_REQUESTS:
            raise EvonWsError(
                f"Too many pending WebSocket requests ({len(self._pending_requests)}), "
                "server may be unresponsive"
            )

        sequence_id = self._sequence_id
        self._sequence_id += 1

        message = {
            "methodName": "CallWithReturn",
            "request": {
                "args": args,
                "methodName": method_name,
                "sequenceId": sequence_id,
            },
        }

        future: asyncio.Future = asyncio.get_running_loop().create_future()
        self._pending_requests[sequence_id] = future

        try:
            _LOGGER.debug("Sending WS request: method=%s, seq=%s", method_name, sequence_id)
            if not self._ws or self._ws.closed:
                raise EvonWsNotConnectedError("WebSocket closed before send")
            await self._ws.send_str(json.dumps(message))
            _LOGGER.debug("WS request sent, waiting for response (timeout=%s)", request_timeout)
            async with asyncio.timeout(request_timeout):
                return await future
        except TimeoutError:
            self._pending_requests.pop(sequence_id, None)
            raise EvonWsTimeoutError(f"Request timeout: {method_name}") from None
        except asyncio.CancelledError:
            self._pending_requests.pop(sequence_id, None)
            raise
        except Exception:
            self._pending_requests.pop(sequence_id, None)
            raise

    async def subscribe_instances(
        self,
        subscriptions: list[dict[str, Any]],
    ) -> None:
        """Subscribe to property changes for instances.

        Args:
            subscriptions: List of subscription dicts with Instanceid and Properties keys.
                Example: [{"Instanceid": "Light1", "Properties": ["IsOn", "ScaledBrightness"]}]
        """
        if not subscriptions:
            return

        # Store subscriptions for reconnection
        self._subscriptions = subscriptions

        if not self.is_connected:
            _LOGGER.debug("Not connected, subscriptions will be applied on connect")
            return

        await self._do_subscribe(subscriptions)

    async def _do_subscribe(self, subscriptions: list[dict[str, Any]]) -> None:
        """Actually perform the subscription request.

        Args:
            subscriptions: List of subscription dicts.
        """
        try:
            # RegisterValuesChanged(subscribe, subscriptions, getInitialValues, unknownFlag)
            # Use a longer timeout for subscriptions with many devices
            await self._send_request(
                "RegisterValuesChanged",
                [True, subscriptions, True, True],
                request_timeout=WS_SUBSCRIBE_REQUEST_TIMEOUT,
            )
            _LOGGER.info(
                "Subscribed to %d instances for real-time updates",
                len(subscriptions),
            )
        except Exception as err:  # pylint: disable=broad-except
            _LOGGER.error("Failed to subscribe to instances: %s", err)

    async def _resubscribe(self) -> None:
        """Re-subscribe to all stored subscriptions after reconnection."""
        if self._subscriptions:
            _LOGGER.debug("Re-subscribing to %d instances", len(self._subscriptions))
            await self._do_subscribe(self._subscriptions)

    async def unsubscribe_instances(self, instance_ids: list[str]) -> None:
        """Unsubscribe from property changes for instances.

        Args:
            instance_ids: List of instance IDs to unsubscribe from.
        """
        if not instance_ids or not self.is_connected:
            return

        # Remove from stored subscriptions
        self._subscriptions = [sub for sub in self._subscriptions if sub.get("Instanceid") not in instance_ids]

        subscriptions = [{"Instanceid": instance_id, "Properties": []} for instance_id in instance_ids]

        try:
            await self._send_request(
                "RegisterValuesChanged",
                [False, subscriptions, False, False],
            )
        except Exception as err:  # pylint: disable=broad-except
            _LOGGER.error("Failed to unsubscribe from instances: %s", err)

    async def set_value(self, instance_id: str, property_name: str, value: Any) -> bool:
        """Set a property value via WebSocket.

        Args:
            instance_id: The instance ID (e.g., "Light1").
            property_name: The property to set (e.g., "IsOn").
            value: The value to set.

        Returns:
            True if the request was sent successfully, False otherwise.
        """
        if not self.is_connected:
            return False

        try:
            await self._send_request(
                "SetValue",
                [f"{instance_id}.{property_name}", value],
            )
            _LOGGER.debug(
                "Control via WebSocket: SetValue %s.%s = %s",
                instance_id,
                property_name,
                value,
            )
            return True
        except Exception as err:  # pylint: disable=broad-except
            _LOGGER.warning("WebSocket SetValue failed: %s", err)
            return False

    async def call_method(
        self,
        instance_id: str,
        method: str,
        params: list[Any] | None = None,
    ) -> bool:
        """Call a method on an instance via WebSocket.

        Uses the format discovered from the Evon web app:
        CallMethod [instanceId.methodName, params]

        Args:
            instance_id: The instance ID (e.g., "SC1_M09.Blind2").
            method: The method name (e.g., "Open", "MoveToPosition").
            params: Optional list of parameters.

        Returns:
            True if the request was sent successfully, False otherwise.
        """
        if not self.is_connected:
            return False

        try:
            # Format: [instanceId.methodName, params]
            # This matches the Evon web app's WebSocket protocol
            await self._send_request(
                "CallMethod",
                [f"{instance_id}.{method}", params or []],
            )
            _LOGGER.debug(
                "Control via WebSocket: CallMethod %s.%s(%s)",
                instance_id,
                method,
                params or [],
            )
            return True
        except Exception as err:  # pylint: disable=broad-except
            _LOGGER.warning("WebSocket CallMethod failed: %s", err)
            return False
