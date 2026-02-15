# Features & Bugfix Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix the v1.17.1 auth retry storm regression (Issue #2), add WebSocket connection quality diagnostic sensors, add doorbell event entity for 2N intercoms, and add 8 language translations.

**Architecture:** Four independent features implemented in TDD style. The Issue #2 fix patches `api.py` and `ws_client.py` to prevent cascading auth failures. The WS sensor adds metrics tracking to `EvonWsClient` and exposes two diagnostic sensor entities. The doorbell event creates a new `event.py` platform using existing coordinator data flow. Translations copy the `en.json` structure into 8 new language files.

**Tech Stack:** Python 3.12+, Home Assistant 2024.1+ APIs, pytest, aiohttp

---

### Task 1: Fix auth retry storm — backoff on network errors during login

**Files:**
- Modify: `custom_components/evon/api.py:380-381`
- Test: `tests/test_api.py`

**Step 1: Write the failing test**

Add to `tests/test_api.py`:

```python
class TestLoginBackoff:
    """Tests for login backoff on network errors."""

    @pytest.mark.asyncio
    async def test_login_network_error_increments_backoff(self):
        """Network error during login should increment backoff counter."""
        api = EvonApi(host="http://192.168.1.100", username="user", password="pass")
        mock_session = MagicMock()
        mock_session.closed = False
        mock_session.post = AsyncMock(side_effect=aiohttp.ClientError("Connection refused"))
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
        mock_session.post = AsyncMock(side_effect=aiohttp.ClientError("Connection refused"))
        api._session = mock_session

        with pytest.raises(EvonConnectionError):
            await api.login()

        # Second attempt should hit backoff
        with pytest.raises(EvonAuthError, match="Login rate limited"):
            await api.login()
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_api.py::TestLoginBackoff -v`
Expected: FAIL — `_login_failure_count` stays 0 because `_increment_login_backoff()` is not called on `aiohttp.ClientError`

**Step 3: Write minimal implementation**

In `custom_components/evon/api.py`, change line 380-381 from:

```python
        except aiohttp.ClientError as err:
            raise EvonConnectionError(f"Connection error: {err}") from err
```

to:

```python
        except aiohttp.ClientError as err:
            self._increment_login_backoff()
            raise EvonConnectionError(f"Connection error: {err}") from err
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_api.py::TestLoginBackoff -v`
Expected: PASS

**Step 5: Commit**

```bash
git add custom_components/evon/api.py tests/test_api.py
git commit -m "fix: increment login backoff on network errors during login"
```

---

### Task 2: Fix auth retry storm — safe re-auth in _request()

**Files:**
- Modify: `custom_components/evon/api.py:449-455`
- Test: `tests/test_api.py`

**Step 1: Write the failing test**

Add to `tests/test_api.py`:

```python
class TestRequestAuthRetry:
    """Tests for safe auth retry in _request()."""

    @pytest.mark.asyncio
    async def test_request_401_login_failure_raises_auth_error(self):
        """When 401 triggers re-login that fails, should raise EvonAuthError cleanly."""
        api = EvonApi(host="http://192.168.1.100", username="user", password="pass")
        api._token = "old_token"
        api._token_timestamp = 1.0

        mock_session = MagicMock()
        mock_session.closed = False

        # First request returns 401, then login fails with connection error
        mock_response = AsyncMock()
        mock_response.status = 401
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        mock_session.request = MagicMock(return_value=mock_response)
        # login() will fail
        mock_session.post = AsyncMock(side_effect=aiohttp.ClientError("Connection refused"))
        api._session = mock_session

        with pytest.raises(EvonAuthError, match="Re-authentication failed"):
            await api._request("GET", "/test")

    @pytest.mark.asyncio
    async def test_request_401_login_failure_does_not_leave_none_token(self):
        """After failed re-auth, token should not be left as None for next caller."""
        api = EvonApi(host="http://192.168.1.100", username="user", password="pass")
        api._token = "old_token"
        api._token_timestamp = 1.0

        mock_session = MagicMock()
        mock_session.closed = False

        mock_response = AsyncMock()
        mock_response.status = 401
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        mock_session.request = MagicMock(return_value=mock_response)
        mock_session.post = AsyncMock(side_effect=aiohttp.ClientError("Connection refused"))
        api._session = mock_session

        with pytest.raises(EvonAuthError):
            await api._request("GET", "/test")

        # Backoff should be set, preventing immediate retry storm
        assert api._login_failure_count >= 1
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_api.py::TestRequestAuthRetry -v`
Expected: FAIL — currently the `EvonConnectionError` from `login()` propagates uncaught instead of being wrapped as `EvonAuthError`

**Step 3: Write minimal implementation**

In `custom_components/evon/api.py`, change lines 449-455 from:

```python
                # Handle auth errors with retry
                if response.status in (302, 401) and retry:
                    async with self._token_lock:
                        self._token = None
                        self._token_timestamp = 0.0
                        await self.login()
                    return await self._request(method, endpoint, data, retry=False)
```

to:

```python
                # Handle auth errors with retry
                if response.status in (302, 401) and retry:
                    try:
                        async with self._token_lock:
                            self._token = None
                            self._token_timestamp = 0.0
                            await self.login()
                        return await self._request(method, endpoint, data, retry=False)
                    except (EvonAuthError, EvonConnectionError) as err:
                        raise EvonAuthError(
                            f"Re-authentication failed: {err}"
                        ) from err
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_api.py::TestRequestAuthRetry -v`
Expected: PASS

**Step 5: Run full API test suite**

Run: `pytest tests/test_api.py -v`
Expected: All tests PASS (no regressions)

**Step 6: Commit**

```bash
git add custom_components/evon/api.py tests/test_api.py
git commit -m "fix: wrap re-auth in _request() to prevent token=None cascades"
```

---

### Task 3: Fix WS receive timeout — increase from 90s to 180s

**Files:**
- Modify: `custom_components/evon/const.py:162`
- Test: `tests/test_constants.py`

**Step 1: Write the failing test**

Add to `tests/test_constants.py`:

```python
def test_ws_receive_timeout_is_180s():
    """WS receive timeout should be 180s (6x heartbeat) to avoid false disconnects."""
    from custom_components.evon.const import WS_HEARTBEAT_INTERVAL, WS_RECEIVE_TIMEOUT
    assert WS_RECEIVE_TIMEOUT == WS_HEARTBEAT_INTERVAL * 6
    assert WS_RECEIVE_TIMEOUT == 180
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_constants.py::test_ws_receive_timeout_is_180s -v`
Expected: FAIL — currently `WS_RECEIVE_TIMEOUT == 90`

**Step 3: Write minimal implementation**

In `custom_components/evon/const.py`, change line 162 from:

```python
WS_RECEIVE_TIMEOUT = WS_HEARTBEAT_INTERVAL * 3  # 90s — detect silent connection death
```

to:

```python
WS_RECEIVE_TIMEOUT = WS_HEARTBEAT_INTERVAL * 6  # 180s — detect silent connection death (relaxed to avoid false disconnects on low-traffic systems)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_constants.py::test_ws_receive_timeout_is_180s -v`
Expected: PASS

**Step 5: Run full test suite to check for regressions**

Run: `pytest tests/ -v --tb=short`
Expected: All tests PASS

**Step 6: Commit**

```bash
git add custom_components/evon/const.py tests/test_constants.py
git commit -m "fix: increase WS receive timeout from 90s to 180s to prevent false disconnects

Fixes #2 - the 90s timeout triggered false disconnects on low-traffic systems,
causing reconnection storms that cascaded into auth retry storms."
```

---

### Task 4: Add WS metrics tracking to EvonWsClient

**Files:**
- Modify: `custom_components/evon/ws_client.py`
- Test: `tests/test_ws_client.py`

**Step 1: Write the failing tests**

Add to `tests/test_ws_client.py`:

```python
class TestWsClientMetrics:
    """Tests for WebSocket client metrics tracking."""

    def test_initial_metrics(self):
        """New client should have zero metrics."""
        client = EvonWsClient(
            host="http://192.168.1.100",
            username="user",
            password="pass",
        )
        assert client.reconnect_count == 0
        assert client.messages_received == 0
        assert client.requests_sent == 0
        assert client.last_error is None
        assert client.avg_response_time_ms is None
        assert client.connection_uptime == 0.0

    def test_connected_at_set_on_connect(self):
        """connected_at should be set when connection established."""
        client = EvonWsClient(
            host="http://192.168.1.100",
            username="user",
            password="pass",
        )
        assert client._connected_at == 0.0
        # Simulate connection
        client._connected = True
        client._connected_at = 100.0
        assert client._connected_at == 100.0

    def test_reconnect_count_increments(self):
        """reconnect_count should increment on each reconnection."""
        client = EvonWsClient(
            host="http://192.168.1.100",
            username="user",
            password="pass",
        )
        client._reconnect_count = 0
        client._reconnect_count += 1
        assert client.reconnect_count == 1

    def test_avg_response_time_none_when_empty(self):
        """avg_response_time_ms should be None when no responses tracked."""
        client = EvonWsClient(
            host="http://192.168.1.100",
            username="user",
            password="pass",
        )
        assert client.avg_response_time_ms is None

    def test_avg_response_time_calculated(self):
        """avg_response_time_ms should be mean of response times."""
        client = EvonWsClient(
            host="http://192.168.1.100",
            username="user",
            password="pass",
        )
        client._response_times.extend([10.0, 20.0, 30.0])
        assert client.avg_response_time_ms == pytest.approx(20.0)
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_ws_client.py::TestWsClientMetrics -v`
Expected: FAIL — properties don't exist yet

**Step 3: Write minimal implementation**

In `custom_components/evon/ws_client.py`, add to imports at top:

```python
from collections import deque
```

In `__init__()` (after line 117 `self._subscriptions`), add:

```python
        # Connection quality metrics
        self._connected_at: float = 0.0
        self._reconnect_count: int = 0
        self._messages_received: int = 0
        self._requests_sent: int = 0
        self._last_error: str | None = None
        self._response_times: deque[float] = deque(maxlen=100)
```

Add properties after the `is_connected` property (after line 122):

```python
    @property
    def reconnect_count(self) -> int:
        """Return total number of reconnections."""
        return self._reconnect_count

    @property
    def messages_received(self) -> int:
        """Return total WebSocket messages received."""
        return self._messages_received

    @property
    def requests_sent(self) -> int:
        """Return total WebSocket requests sent."""
        return self._requests_sent

    @property
    def last_error(self) -> str | None:
        """Return last error message."""
        return self._last_error

    @property
    def avg_response_time_ms(self) -> float | None:
        """Return average response time in milliseconds."""
        if not self._response_times:
            return None
        return sum(self._response_times) / len(self._response_times)

    @property
    def connection_uptime(self) -> float:
        """Return seconds since connection established."""
        if not self._connected or self._connected_at == 0.0:
            return 0.0
        return time.monotonic() - self._connected_at

    @property
    def pending_request_count(self) -> int:
        """Return number of pending WebSocket requests."""
        return len(self._pending_requests)
```

**Step 4: Wire up metrics in existing methods**

In `_wait_for_connected()`, when `self._connected = True` is set, also set:
```python
self._connected_at = time.monotonic()
```

In `_run_loop()`, when reconnecting (line 355, after `if await self.connect():`), add:
```python
self._reconnect_count += 1
```
(But NOT on the very first connect — only on reconnections. Track with `_has_connected_once` bool.)

In `_handle_messages()`, after successfully receiving a message (line 467, after `if msg.type == aiohttp.WSMsgType.TEXT:`), add:
```python
self._messages_received += 1
```

In error handlers (`_run_loop` except blocks and `_handle_messages` except blocks), set:
```python
self._last_error = str(err)
```

In the method that sends requests (wherever `_sequence_id` is incremented for outgoing requests), add:
```python
self._requests_sent += 1
```

In the callback handler where responses are matched to pending requests, record response time:
```python
if seq_id in self._pending_request_times:
    elapsed_ms = (time.monotonic() - self._pending_request_times[seq_id]) * 1000
    self._response_times.append(elapsed_ms)
```

**Step 5: Run test to verify it passes**

Run: `pytest tests/test_ws_client.py::TestWsClientMetrics -v`
Expected: PASS

**Step 6: Run full WS client test suite**

Run: `pytest tests/test_ws_client.py -v --tb=short`
Expected: All tests PASS

**Step 7: Commit**

```bash
git add custom_components/evon/ws_client.py tests/test_ws_client.py
git commit -m "feat: add connection quality metrics tracking to WS client"
```

---

### Task 5: Add WebSocket diagnostic sensor entities

**Files:**
- Modify: `custom_components/evon/sensor.py`
- Modify: `custom_components/evon/strings.json`
- Test: `tests/test_sensor.py` or `tests/test_sensor_unit.py`

**Step 1: Write the failing tests**

Add to `tests/test_sensor_unit.py`:

```python
class TestWsStatusSensor:
    """Tests for WebSocket status diagnostic sensor."""

    def test_ws_status_sensor_connected(self):
        """WS status sensor should show 'connected' when WS is connected."""
        coordinator = MagicMock()
        coordinator.data = {}
        coordinator.last_update_success = True
        coordinator.ws_client = MagicMock()
        coordinator.ws_client.is_connected = True
        coordinator.ws_client.reconnect_count = 3
        coordinator.ws_client.messages_received = 100
        coordinator.ws_client.requests_sent = 50
        coordinator.ws_client.pending_request_count = 2
        coordinator.ws_client.avg_response_time_ms = 15.5
        coordinator.ws_client.last_error = None
        coordinator.ws_client.connection_uptime = 3600.0

        entry = MagicMock()
        entry.entry_id = "test_entry"

        sensor = EvonWsStatusSensor(coordinator, entry)
        assert sensor.native_value == "connected"
        attrs = sensor.extra_state_attributes
        assert attrs["reconnect_count"] == 3
        assert attrs["messages_received"] == 100
        assert attrs["connection_uptime_seconds"] == 3600.0

    def test_ws_status_sensor_disconnected(self):
        """WS status sensor should show 'disconnected' when WS is not connected."""
        coordinator = MagicMock()
        coordinator.data = {}
        coordinator.last_update_success = True
        coordinator.ws_client = MagicMock()
        coordinator.ws_client.is_connected = False

        entry = MagicMock()
        entry.entry_id = "test_entry"

        sensor = EvonWsStatusSensor(coordinator, entry)
        assert sensor.native_value == "disconnected"

    def test_ws_status_sensor_no_ws_client(self):
        """WS status sensor should show 'disabled' when WS client is None (HTTP-only mode)."""
        coordinator = MagicMock()
        coordinator.data = {}
        coordinator.last_update_success = True
        coordinator.ws_client = None

        entry = MagicMock()
        entry.entry_id = "test_entry"

        sensor = EvonWsStatusSensor(coordinator, entry)
        assert sensor.native_value == "disabled"


class TestWsLatencySensor:
    """Tests for WebSocket latency diagnostic sensor."""

    def test_ws_latency_sensor_value(self):
        """WS latency sensor should return avg response time."""
        coordinator = MagicMock()
        coordinator.data = {}
        coordinator.last_update_success = True
        coordinator.ws_client = MagicMock()
        coordinator.ws_client.avg_response_time_ms = 25.3

        entry = MagicMock()
        entry.entry_id = "test_entry"

        sensor = EvonWsLatencySensor(coordinator, entry)
        assert sensor.native_value == 25.3

    def test_ws_latency_sensor_none_when_no_data(self):
        """WS latency sensor should return None when no response data."""
        coordinator = MagicMock()
        coordinator.data = {}
        coordinator.last_update_success = True
        coordinator.ws_client = MagicMock()
        coordinator.ws_client.avg_response_time_ms = None

        entry = MagicMock()
        entry.entry_id = "test_entry"

        sensor = EvonWsLatencySensor(coordinator, entry)
        assert sensor.native_value is None
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_sensor_unit.py::TestWsStatusSensor tests/test_sensor_unit.py::TestWsLatencySensor -v`
Expected: FAIL — classes don't exist

**Step 3: Write minimal implementation**

In `custom_components/evon/sensor.py`, add at the end of the file:

```python
class EvonWsStatusSensor(CoordinatorEntity[EvonDataUpdateCoordinator], SensorEntity):
    """Diagnostic sensor for WebSocket connection status."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:websocket"
    _attr_translation_key = "websocket_status"

    def __init__(
        self,
        coordinator: EvonDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_websocket_status"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info — attached to integration system device."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name="Evon Smart Home",
            manufacturer="Evon",
        )

    @property
    def native_value(self) -> str:
        """Return connection state."""
        ws_client = self.coordinator.ws_client
        if ws_client is None:
            return "disabled"
        return "connected" if ws_client.is_connected else "disconnected"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return connection quality metrics."""
        ws_client = self.coordinator.ws_client
        if ws_client is None:
            return {}
        return {
            "connection_uptime_seconds": round(ws_client.connection_uptime, 1),
            "reconnect_count": ws_client.reconnect_count,
            "messages_received": ws_client.messages_received,
            "requests_sent": ws_client.requests_sent,
            "pending_requests": ws_client.pending_request_count,
            "avg_response_time_ms": round(ws_client.avg_response_time_ms, 1) if ws_client.avg_response_time_ms is not None else None,
            "last_error": ws_client.last_error,
        }


class EvonWsLatencySensor(CoordinatorEntity[EvonDataUpdateCoordinator], SensorEntity):
    """Diagnostic sensor for WebSocket response latency (long-term statistics)."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "ms"
    _attr_suggested_display_precision = 1
    _attr_icon = "mdi:timer-outline"
    _attr_translation_key = "websocket_latency"

    def __init__(
        self,
        coordinator: EvonDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_websocket_latency"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info — attached to integration system device."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name="Evon Smart Home",
            manufacturer="Evon",
        )

    @property
    def native_value(self) -> float | None:
        """Return average response time in ms."""
        ws_client = self.coordinator.ws_client
        if ws_client is None:
            return None
        return ws_client.avg_response_time_ms
```

Also expose `ws_client` on the coordinator. In `custom_components/evon/coordinator/__init__.py`, add a property:

```python
    @property
    def ws_client(self) -> EvonWsClient | None:
        """Return the WebSocket client instance."""
        return self._ws_client
```

In `custom_components/evon/sensor.py` `async_setup_entry()`, add before the final `if entities:` block:

```python
    # Create WebSocket diagnostic sensors
    ws_client = coordinator.ws_client
    entities.append(EvonWsStatusSensor(coordinator, entry))
    if ws_client is not None:
        entities.append(EvonWsLatencySensor(coordinator, entry))
```

Add translation keys to `custom_components/evon/strings.json` in the `"entity" > "sensor"` section:

```json
      "websocket_status": {
        "name": "WebSocket Status"
      },
      "websocket_latency": {
        "name": "WebSocket Latency"
      }
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_sensor_unit.py::TestWsStatusSensor tests/test_sensor_unit.py::TestWsLatencySensor -v`
Expected: PASS

**Step 5: Run full sensor test suite**

Run: `pytest tests/test_sensor.py tests/test_sensor_unit.py -v --tb=short`
Expected: All tests PASS

**Step 6: Commit**

```bash
git add custom_components/evon/sensor.py custom_components/evon/coordinator/__init__.py custom_components/evon/strings.json tests/test_sensor_unit.py
git commit -m "feat: add WebSocket connection quality diagnostic sensors"
```

---

### Task 6: Add doorbell event entity for 2N intercoms

**Files:**
- Create: `custom_components/evon/event.py`
- Modify: `custom_components/evon/__init__.py:139-150` (PLATFORMS list)
- Modify: `custom_components/evon/strings.json`
- Test: `tests/test_event.py` (new)

**Step 1: Write the failing tests**

Create `tests/test_event.py`:

```python
"""Tests for Evon doorbell event entity."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from custom_components.evon.const import DOMAIN, ENTITY_TYPE_INTERCOMS
from custom_components.evon.event import EvonDoorbellEvent


class TestDoorbellEvent:
    """Tests for doorbell event entity."""

    def _make_coordinator(self, intercoms=None):
        """Create a mock coordinator with intercom data."""
        coordinator = MagicMock()
        coordinator.data = {
            ENTITY_TYPE_INTERCOMS: intercoms or []
        }
        coordinator.last_update_success = True
        return coordinator

    def _make_entity(self, coordinator, intercom_data, entry=None):
        """Create a doorbell event entity."""
        if entry is None:
            entry = MagicMock()
            entry.entry_id = "test_entry"
        return EvonDoorbellEvent(
            coordinator,
            intercom_data["id"],
            intercom_data["name"],
            intercom_data.get("room_name", ""),
            entry,
        )

    def test_event_types(self):
        """Event entity should support 'ring' event type."""
        coordinator = self._make_coordinator()
        entity = self._make_entity(coordinator, {"id": "Intercom1", "name": "Front Door"})
        assert "ring" in entity.event_types

    def test_unique_id(self):
        """Unique ID should include instance ID."""
        coordinator = self._make_coordinator()
        entity = self._make_entity(coordinator, {"id": "Intercom1", "name": "Front Door"})
        assert entity.unique_id == "evon_doorbell_Intercom1"

    def test_doorbell_transition_fires_event(self):
        """False→True transition of doorbell_triggered should fire 'ring' event."""
        intercom = {"id": "Intercom1", "name": "Front Door", "doorbell_triggered": False}
        coordinator = self._make_coordinator([intercom])
        entity = self._make_entity(coordinator, intercom)

        # Simulate initial state
        with patch.object(entity, "_trigger_event") as mock_trigger:
            entity._last_doorbell_state = False

            # Now doorbell triggers
            intercom["doorbell_triggered"] = True
            entity._handle_coordinator_update()

            mock_trigger.assert_called_once_with("ring")

    def test_no_event_on_same_state(self):
        """No event should fire when doorbell_triggered stays True."""
        intercom = {"id": "Intercom1", "name": "Front Door", "doorbell_triggered": True}
        coordinator = self._make_coordinator([intercom])
        entity = self._make_entity(coordinator, intercom)

        with patch.object(entity, "_trigger_event") as mock_trigger:
            entity._last_doorbell_state = True
            entity._handle_coordinator_update()
            mock_trigger.assert_not_called()

    def test_no_event_on_release(self):
        """No event should fire on True→False transition."""
        intercom = {"id": "Intercom1", "name": "Front Door", "doorbell_triggered": False}
        coordinator = self._make_coordinator([intercom])
        entity = self._make_entity(coordinator, intercom)

        with patch.object(entity, "_trigger_event") as mock_trigger:
            entity._last_doorbell_state = True
            entity._handle_coordinator_update()
            mock_trigger.assert_not_called()
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_event.py -v`
Expected: FAIL — `custom_components.evon.event` module doesn't exist

**Step 3: Write minimal implementation**

Create `custom_components/evon/event.py`:

```python
"""Event platform for Evon Smart Home integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.event import EventDeviceClass, EventEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .base_entity import EvonEntity
from .const import DOMAIN, ENTITY_TYPE_INTERCOMS
from .coordinator import EvonDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Evon event entities from a config entry."""
    coordinator: EvonDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    entities: list[EventEntity] = []

    if coordinator.data and ENTITY_TYPE_INTERCOMS in coordinator.data:
        for intercom in coordinator.data[ENTITY_TYPE_INTERCOMS]:
            entities.append(
                EvonDoorbellEvent(
                    coordinator,
                    intercom["id"],
                    intercom["name"],
                    intercom.get("room_name", ""),
                    entry,
                )
            )

    if entities:
        async_add_entities(entities)


class EvonDoorbellEvent(EvonEntity, EventEntity):
    """Event entity for Evon 2N intercom doorbell press."""

    _attr_device_class = EventDeviceClass.DOORBELL
    _attr_event_types = ["ring"]
    _attr_translation_key = "doorbell"
    _entity_type = ENTITY_TYPE_INTERCOMS

    def __init__(
        self,
        coordinator: EvonDataUpdateCoordinator,
        instance_id: str,
        name: str,
        room_name: str,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the event entity."""
        super().__init__(coordinator, instance_id, name, room_name, entry)
        self._attr_unique_id = f"evon_doorbell_{instance_id}"
        self._last_doorbell_state: bool = False

    @property
    def event_types(self) -> list[str]:
        """Return supported event types."""
        return ["ring"]

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return self._build_device_info("Intercom")

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        data = self._get_data()
        if data is None:
            super()._handle_coordinator_update()
            return

        current_state = data.get("doorbell_triggered", False)

        # Fire event on False → True transition only
        if current_state and not self._last_doorbell_state:
            self._trigger_event("ring")

        self._last_doorbell_state = current_state
        super()._handle_coordinator_update()
```

Add `Platform.EVENT` to `PLATFORMS` in `custom_components/evon/__init__.py:139`:

```python
PLATFORMS: list[Platform] = [
    Platform.BUTTON,
    Platform.CAMERA,
    Platform.EVENT,  # ADD THIS
    Platform.IMAGE,
    Platform.LIGHT,
    Platform.COVER,
    Platform.CLIMATE,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.BINARY_SENSOR,
    Platform.SELECT,
]
```

Add translation key to `custom_components/evon/strings.json` in the `"entity"` section:

```json
    "event": {
      "doorbell": {
        "name": "Doorbell",
        "state_attributes": {
          "event_type": {
            "state": {
              "ring": "Ring"
            }
          }
        }
      }
    },
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_event.py -v`
Expected: PASS

**Step 5: Run full test suite**

Run: `pytest tests/ -v --tb=short`
Expected: All tests PASS

**Step 6: Commit**

```bash
git add custom_components/evon/event.py custom_components/evon/__init__.py custom_components/evon/strings.json tests/test_event.py
git commit -m "feat: add doorbell event entity for 2N intercoms"
```

---

### Task 7: Add translations for 8 languages

**Files:**
- Create: `custom_components/evon/translations/fr.json`
- Create: `custom_components/evon/translations/it.json`
- Create: `custom_components/evon/translations/sl.json`
- Create: `custom_components/evon/translations/es.json`
- Create: `custom_components/evon/translations/pt.json`
- Create: `custom_components/evon/translations/pl.json`
- Create: `custom_components/evon/translations/cs.json`
- Create: `custom_components/evon/translations/sk.json`
- Also update: `custom_components/evon/translations/en.json` and `de.json` with new entity keys from Tasks 5 and 6

**Step 1: Update en.json and de.json with new entity keys**

Add to both `en.json` and `de.json` the new sensor and event translation keys added in Tasks 5 and 6:

In `"entity" > "sensor"`, add:
```json
"websocket_status": { "name": "WebSocket Status" },
"websocket_latency": { "name": "WebSocket Latency" }
```

In `"entity"`, add:
```json
"event": {
  "doorbell": {
    "name": "Doorbell",
    "state_attributes": {
      "event_type": {
        "state": {
          "ring": "Ring"
        }
      }
    }
  }
}
```

(German translations: `"WebSocket Status"`, `"WebSocket Latenz"`, `"Türklingel"`, `"Klingeln"`)

**Step 2: Create all 8 translation files**

Each file copies the exact key structure from `en.json` with translated values. Technical terms (WebSocket, API, Home Assistant, IP, Engine ID) remain in English. All 124+ strings translated per language.

Languages: French (fr), Italian (it), Slovenian (sl), Spanish (es), Portuguese (pt), Polish (pl), Czech (cs), Slovak (sk).

**Step 3: Verify JSON validity**

Run: `python3 -c "import json, glob; [json.load(open(f)) for f in glob.glob('custom_components/evon/translations/*.json')]; print('All valid')""`

Expected: "All valid" — no JSON parse errors

**Step 4: Verify key consistency**

Run a quick check that all translation files have the same keys as en.json:

```python
python3 -c "
import json, glob
with open('custom_components/evon/translations/en.json') as f:
    en = json.load(f)
for path in sorted(glob.glob('custom_components/evon/translations/*.json')):
    if 'en.json' in path:
        continue
    with open(path) as f:
        lang = json.load(f)
    # Simple top-level key check
    if set(en.keys()) != set(lang.keys()):
        print(f'MISMATCH: {path}')
    else:
        print(f'OK: {path}')
"
```

Expected: All files show "OK"

**Step 5: Run full test suite**

Run: `pytest tests/ -v --tb=short`
Expected: All tests PASS (translations don't affect test behavior)

**Step 6: Commit**

```bash
git add custom_components/evon/translations/
git commit -m "feat: add translations for FR, IT, SL, ES, PT, PL, CS, SK"
```

---

### Task 8: Final verification and release commit

**Step 1: Run full test suite**

Run: `pytest tests/ -v --tb=short`
Expected: All 1100+ tests PASS

**Step 2: Verify no regressions in existing functionality**

Run: `pytest tests/test_api.py tests/test_ws_client.py tests/test_sensor.py tests/test_coordinator.py -v`
Expected: All PASS

**Step 3: Review all changes**

Run: `git log --oneline main..HEAD`
Expected: 7 commits — one per task

Run: `git diff main --stat`
Expected: Changes to api.py, ws_client.py, const.py, sensor.py, coordinator/__init__.py, __init__.py, strings.json, event.py (new), test files, 10 translation files
