# Feature Batch: Issue #2 Fix, WS Sensor, Doorbell Event, Translations

Date: 2026-02-15

## Overview

Four features to implement in one batch:

1. Fix v1.17.1 regression (Issue #2) — auth retry storm and WS timeout
2. WebSocket connection quality diagnostic sensor
3. Doorbell event entity for 2N intercoms
4. Translations for 8 additional languages

## Feature 1: Issue #2 Fix — Auth Retry Storm & WS Timeout

### Problem

Three bugs in v1.17.1 create a cascading failure that generates >700 API requests/min:

1. **Auth retry clears token before login** (`api.py:450-455`): On 401/302, the token is set to `None` and `login()` is called. If `login()` raises (network error), the token stays `None`. Every subsequent `_ensure_token()` call retries login immediately with no backoff.

2. **No backoff on network errors during login** (`api.py:380`): The `aiohttp.ClientError` catch in `login()` doesn't call `_increment_login_backoff()`, so network failures have no rate limiting.

3. **Aggressive WS receive timeout** (`ws_client.py:463`): The 90s `asyncio.timeout` on `_ws.receive()` triggers false disconnects on low-traffic systems, causing reconnection storms that compound the auth issue.

Switch control was previously forced to HTTP fallback (empty WS mappings), making relay switches (`Base.bSwitch`) uniquely vulnerable to auth storms. This has been fixed — relay switches now use `SwitchOn`/`SwitchOff` via WebSocket, same as lights.

### Fix A: Safe auth retry in `_request()` (`api.py:450-455`)

Wrap the `login()` call in the retry path with try/except. On failure, raise `EvonAuthError` instead of leaving the token as `None`:

```python
if response.status in (302, 401) and retry:
    try:
        async with self._token_lock:
            self._token = None
            self._token_timestamp = 0.0
            await self.login()
        return await self._request(method, endpoint, data, retry=False)
    except (EvonAuthError, EvonConnectionError) as err:
        raise EvonAuthError(f"Re-authentication failed: {err}") from err
```

### Fix B: Backoff on network errors during login (`api.py:380`)

Add `_increment_login_backoff()` before raising:

```python
except aiohttp.ClientError as err:
    self._increment_login_backoff()
    raise EvonConnectionError(f"Connection error: {err}") from err
```

### Fix C: Relax WS receive timeout (`ws_client.py:463`)

Increase `WS_RECEIVE_TIMEOUT` from `WS_HEARTBEAT_INTERVAL * 3` (90s) to `WS_HEARTBEAT_INTERVAL * 6` (180s).

### Files changed

- `custom_components/evon/api.py` (fixes A and B)
- `custom_components/evon/ws_client.py` or `const.py` (fix C)

---

## Feature 2: WebSocket Connection Quality Sensor

### New metrics in `EvonWsClient`

Add these instance variables:

- `_connected_at: float` — `time.monotonic()` when connected
- `_reconnect_count: int` — lifetime reconnect counter
- `_messages_received: int` — total WS messages received
- `_requests_sent: int` — total WS requests sent
- `_last_error: str | None` — last error message
- `_response_times: deque[float]` — rolling window (last 100) of response times in ms

Add read-only properties to expose each metric.

### Sensor entities

**`sensor.evon_websocket`** (diagnostic):
- State: `"connected"` / `"disconnected"`
- Attributes: `connection_uptime_seconds`, `reconnect_count`, `messages_received`, `requests_sent`, `pending_requests`, `avg_response_time_ms`, `last_error`
- `EntityCategory.DIAGNOSTIC`
- Unique ID: `{entry_id}_websocket_status`
- Device: Evon system device

**`sensor.evon_websocket_latency`** (diagnostic measurement):
- State: average response time in ms (float)
- `state_class=SensorStateClass.MEASUREMENT`
- `unit_of_measurement="ms"`
- `EntityCategory.DIAGNOSTIC`
- Unique ID: `{entry_id}_websocket_latency`
- Device: Evon system device
- Enables HA long-term statistics (hourly mean/min/max)

Both sensors update on coordinator refresh (every 60s with WS, every 30s HTTP-only). No extra API calls.

### Files changed

- `custom_components/evon/ws_client.py` (add metrics tracking and properties)
- `custom_components/evon/sensor.py` (add two diagnostic sensor entities)
- `custom_components/evon/strings.json` (entity names)
- `custom_components/evon/translations/*.json` (entity names)

---

## Feature 3: Doorbell Event Entity

### Architecture

New `event.py` platform with `EvonDoorbellEvent` entity:

- Extends `EvonEntity` + `EventEntity`
- `event_types = ["ring"]`
- `device_class = EventDeviceClass.DOORBELL`
- Created for every 2N intercom in `coordinator.data[ENTITY_TYPE_INTERCOMS]`
- Unique ID: `evon_doorbell_{instance_id}`

### State transition detection

Each entity tracks `_last_doorbell_state: bool`. On coordinator update:
1. Read `doorbell_triggered` from coordinator data
2. If `False → True`: call `self._trigger_event("ring")`
3. Update `_last_doorbell_state`

This gives proper event history with timestamps in HA's event timeline UI.

### Data flow (already exists)

```
WS: DoorBellTriggered → ws_mappings: doorbell_triggered → coordinator → event entity
```

No changes to coordinator, processors, or ws_mappings needed.

### Files changed

- `custom_components/evon/event.py` (new, ~80 lines)
- `custom_components/evon/__init__.py` (add `Platform.EVENT` to `PLATFORMS`)
- `custom_components/evon/strings.json` (entity name)
- `custom_components/evon/translations/*.json` (entity name)

---

## Feature 4: Translations (8 languages)

### Scope

Generate translation files for: French (fr), Italian (it), Slovenian (sl), Spanish (es), Portuguese (pt), Polish (pl), Czech (cs), Slovak (sk).

- 124 translatable strings per language
- Standard HA translation format (copy `en.json` structure)
- Technical terms (WebSocket, API, Home Assistant) kept in English
- Device terms translated to local equivalents

### Files created

- `custom_components/evon/translations/fr.json`
- `custom_components/evon/translations/it.json`
- `custom_components/evon/translations/sl.json`
- `custom_components/evon/translations/es.json`
- `custom_components/evon/translations/pt.json`
- `custom_components/evon/translations/pl.json`
- `custom_components/evon/translations/cs.json`
- `custom_components/evon/translations/sk.json`

---

## Deferred

- **RGBW full color**: Needs API property name discovery on actual hardware
- **Blind sun-tracking**: Better as HA blueprint, not integration feature
- **Backup/restore**: Evon API doesn't expose config import/export
- **Physical buttons (Taster)**: Infrastructure already prepared; waiting for Evon WS event support
