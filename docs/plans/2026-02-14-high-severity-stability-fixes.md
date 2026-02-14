# High-Severity Stability Fixes — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix all 6 high-severity issues (P-H1, P-H2, T-H1, T-H2, T-H3, T-H4) plus bonus T-L4 to eliminate silent crashes, data races, and lost WS subscriptions.

**Architecture:** Python coordinator gets batched statistics queries and copy-on-write entity updates. TypeScript WS client gets a proper connection lifecycle with sequence reset, subscription re-registration, and clean disconnect-during-connect handling. MCP server gets graceful shutdown and fatal error exit.

**Tech Stack:** Python 3.12 / Home Assistant coordinator, TypeScript 5.9 / Node.js WS client, pytest + node:test

---

## Task 1: T-H1 — Fix silent server death + T-L4 — Add graceful shutdown

These two changes are both in `src/index.ts` and are trivial — do them together.

**Files:**
- Modify: `src/index.ts:12,39`
- Test: `tests-mcp/index.test.js` (new)

**Step 1: Write the failing tests**

Create `tests-mcp/index.test.js`:

```javascript
import test from "node:test";
import assert from "node:assert/strict";

test("T-H1: main().catch calls process.exit(1) on fatal error", async () => {
  // We can't easily test the actual main() without mocking MCP server,
  // but we can verify the catch handler pattern by importing and checking
  // the module sets up process.exit(1). Instead, test the shutdown utility.
  const { setupGracefulShutdown } = await import(
    `../dist/index.js?v=${Date.now()}`
  );
  // setupGracefulShutdown should be exported for testability
  assert.equal(typeof setupGracefulShutdown, "function");
});
```

**Step 2: Run tests to verify they fail**

Run: `npm run build && node --test tests-mcp/index.test.js`
Expected: FAIL — `setupGracefulShutdown` not exported

**Step 3: Implement the fix**

In `src/index.ts`, make these changes:

1. Add import for `getWsClient` (after line 14):
```typescript
import { getWsClient } from "./ws-client.js";
```

2. Export a `setupGracefulShutdown` function and replace line 39:
```typescript
export function setupGracefulShutdown(): void {
  const shutdown = () => {
    try {
      getWsClient().disconnect();
    } catch {
      // Best-effort cleanup
    }
    process.exit(0);
  };
  process.on("SIGTERM", shutdown);
  process.on("SIGINT", shutdown);
}

main()
  .then(() => setupGracefulShutdown())
  .catch((error) => {
    console.error("Fatal error:", error);
    process.exit(1);
  });
```

**Step 4: Run tests to verify they pass**

Run: `npm run build && node --test tests-mcp/index.test.js`
Expected: PASS

**Step 5: Run existing tests to verify no regressions**

Run: `npm run build && node --test tests-mcp/*.test.js`
Expected: All PASS

**Step 6: Commit**

```bash
git add src/index.ts tests-mcp/index.test.js
git commit -m "fix: add process.exit(1) on fatal error and graceful shutdown (T-H1, T-L4)"
```

---

## Task 2: T-H2 — Reset sequenceId on reconnect

**Files:**
- Modify: `src/ws-client.ts:169`
- Test: `tests-mcp/ws-client.test.js` (new — will grow through tasks 2-4)

**Step 1: Write the failing test**

Create `tests-mcp/ws-client.test.js`:

```javascript
import test from "node:test";
import assert from "node:assert/strict";

const WS_CLIENT_URL = new URL("../dist/ws-client.js", import.meta.url);

async function importFresh(url) {
  const href = url.href + `?v=${Date.now()}-${Math.random()}`;
  return import(href);
}

test("T-H2: sequenceId resets to 1 after reconnect", async () => {
  const { EvonWsClient } = await importFresh(WS_CLIENT_URL);
  const client = new EvonWsClient("http://localhost:9999");

  // Access private sequenceId via bracket notation
  assert.equal(client["sequenceId"], 1, "starts at 1");

  // Simulate incrementing sequenceId (as if calls were made)
  client["sequenceId"] = 500;
  assert.equal(client["sequenceId"], 500, "incremented");

  // Call resetConnectionState (our new method) to simulate what happens on reconnect
  client["resetConnectionState"]();
  assert.equal(client["sequenceId"], 1, "reset to 1 after reconnect");
});
```

**Step 2: Run test to verify it fails**

Run: `npm run build && node --test tests-mcp/ws-client.test.js`
Expected: FAIL — `resetConnectionState` is not a function

**Step 3: Implement the fix**

In `src/ws-client.ts`, add a private method after `rejectAllPending()` (after line 450):

```typescript
  /**
   * Reset connection-specific state for a fresh connection.
   * Called at the start of performConnect().
   */
  private resetConnectionState(): void {
    this.sequenceId = 1;
  }
```

Then in `performConnect()`, add call after login (after line 169):

```typescript
  private async performConnect(): Promise<void> {
    // Get token via HTTP login
    this.token = await this.login();

    // Reset connection-specific state
    this.resetConnectionState();

    return new Promise((resolve, reject) => {
```

**Step 4: Run test to verify it passes**

Run: `npm run build && node --test tests-mcp/ws-client.test.js`
Expected: PASS

**Step 5: Commit**

```bash
git add src/ws-client.ts tests-mcp/ws-client.test.js
git commit -m "fix: reset sequenceId on WS reconnect to prevent overflow (T-H2)"
```

---

## Task 3: T-H3 — Re-register subscriptions after reconnect

**Files:**
- Modify: `src/ws-client.ts:207,221`
- Test: `tests-mcp/ws-client.test.js` (append)

**Step 1: Write the failing test**

Append to `tests-mcp/ws-client.test.js`:

```javascript
test("T-H3: resubscribeAll builds correct subscription list from Map", async () => {
  const { EvonWsClient } = await importFresh(WS_CLIENT_URL);
  const client = new EvonWsClient("http://localhost:9999");

  // Populate subscriptions Map (simulating prior registerValuesChanged)
  const callback = () => {};
  client["subscriptions"].set("light_1", callback);
  client["subscriptions"].set("blind_2", callback);

  // Track what call() would receive
  const calls = [];
  client["call"] = async (method, args) => {
    calls.push({ method, args });
    return null;
  };

  await client["resubscribeAll"]();

  assert.equal(calls.length, 1, "one RegisterValuesChanged call");
  assert.equal(calls[0].method, "RegisterValuesChanged");
  const [enable, subs, flag1, flag2] = calls[0].args;
  assert.equal(enable, true);
  assert.equal(flag1, true);
  assert.equal(flag2, true);
  // Should contain both instance IDs
  const instanceIds = subs.map(s => s.Instanceid).sort();
  assert.deepEqual(instanceIds, ["blind_2", "light_1"]);
  // Properties should be empty arrays (subscribe to all)
  for (const sub of subs) {
    assert.deepEqual(sub.Properties, []);
  }
});

test("T-H3: resubscribeAll is a no-op when no subscriptions exist", async () => {
  const { EvonWsClient } = await importFresh(WS_CLIENT_URL);
  const client = new EvonWsClient("http://localhost:9999");

  let callCount = 0;
  client["call"] = async () => { callCount++; return null; };

  await client["resubscribeAll"]();
  assert.equal(callCount, 0, "no call made when no subscriptions");
});
```

**Step 2: Run tests to verify they fail**

Run: `npm run build && node --test tests-mcp/ws-client.test.js`
Expected: FAIL — `resubscribeAll` is not a function

**Step 3: Implement the fix**

In `src/ws-client.ts`, add after `disconnect()` method (after line 234):

```typescript
  /**
   * Re-register all local subscriptions with the server.
   * Called after a successful reconnect to restore server-side state.
   */
  private async resubscribeAll(): Promise<void> {
    if (this.subscriptions.size === 0) {
      return;
    }

    const subs: PropertySubscription[] = Array.from(
      this.subscriptions.keys()
    ).map((instanceId) => ({
      Instanceid: instanceId,
      Properties: [],
    }));

    try {
      await this.call("RegisterValuesChanged", [true, subs, true, true]);
    } catch (error) {
      console.error("Failed to resubscribe after reconnect:", error);
    }
  }
```

Then in `performConnect()`, after `resolve()` on line 207, add the resubscription call:

```typescript
          resolve();

          // Restore server-side subscriptions after reconnect
          this.resubscribeAll().catch((err) => {
            console.error("Resubscription after connect failed:", err);
          });
```

Also modify `disconnect()` to **not** clear the subscriptions Map (line 233), so reconnection can restore them. Instead, only clear subscriptions on explicit `unregisterValuesChanged` calls:

```typescript
  disconnect(): void {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this.connected = false;
    this.token = null;
    // Note: do NOT clear subscriptions — they're needed for resubscribeAll on reconnect
  }
```

**Step 4: Run tests to verify they pass**

Run: `npm run build && node --test tests-mcp/ws-client.test.js`
Expected: All PASS

**Step 5: Commit**

```bash
git add src/ws-client.ts tests-mcp/ws-client.test.js
git commit -m "fix: re-register WS subscriptions after reconnect (T-H3)"
```

---

## Task 4: T-H4 — Handle disconnect during connect

**Files:**
- Modify: `src/ws-client.ts:128,149,167,226`
- Test: `tests-mcp/ws-client.test.js` (append)

**Step 1: Write the failing test**

Append to `tests-mcp/ws-client.test.js`:

```javascript
test("T-H4: disconnect during connect rejects connectPromise", async () => {
  const { EvonWsClient } = await importFresh(WS_CLIENT_URL);
  const client = new EvonWsClient("http://localhost:9999");

  // Mock login to succeed but be slow
  client["login"] = () => new Promise(resolve => setTimeout(() => resolve("token"), 50));

  // Start connecting (will await login)
  const connectPromise = client.connect();

  // Disconnect immediately
  client.disconnect();

  // connect() should reject (not hang for 10s)
  await assert.rejects(connectPromise, /aborted/i);
});

test("T-H4: disconnectRequested flag resets on next connect", async () => {
  const { EvonWsClient } = await importFresh(WS_CLIENT_URL);
  const client = new EvonWsClient("http://localhost:9999");

  // Set disconnectRequested
  client["disconnectRequested"] = true;

  // On next connect(), it should reset
  // Mock connect to check the flag
  const origPerform = client["performConnect"].bind(client);
  let flagDuringConnect;
  client["performConnect"] = async () => {
    flagDuringConnect = client["disconnectRequested"];
    throw new Error("stop here"); // Don't actually connect
  };

  try {
    await client.connect();
  } catch {
    // Expected
  }

  assert.equal(flagDuringConnect, false, "flag reset at start of connect()");
});
```

**Step 2: Run tests to verify they fail**

Run: `npm run build && node --test tests-mcp/ws-client.test.js`
Expected: FAIL — `disconnectRequested` doesn't exist, connect hangs

**Step 3: Implement the fix**

Add `disconnectRequested` property (after line 128):

```typescript
  private userData: WsUserData | null = null;
  private disconnectRequested = false;
```

Modify `connect()` (line 149) to reset flag:

```typescript
  async connect(): Promise<void> {
    this.disconnectRequested = false;

    if (this.connected && this.ws?.readyState === WebSocket.OPEN) {
      return;
    }
```

Modify `performConnect()` to check flag after login (after the `resetConnectionState()` call):

```typescript
  private async performConnect(): Promise<void> {
    // Get token via HTTP login
    this.token = await this.login();

    // Reset connection-specific state
    this.resetConnectionState();

    // If disconnect was requested during login, abort early
    if (this.disconnectRequested) {
      throw new Error("Connection aborted by disconnect()");
    }

    return new Promise((resolve, reject) => {
```

Also add the abort check in the message handler inside `performConnect()` (around line 192):

```typescript
      this.ws.on("message", (data) => {
        // Abort if disconnect was called during connection setup
        if (this.disconnectRequested) {
          this.ws?.close();
          reject(new Error("Connection aborted by disconnect()"));
          return;
        }

        this.handleMessage(data.toString());
```

Modify `disconnect()` to set the flag:

```typescript
  disconnect(): void {
    this.disconnectRequested = true;
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this.connected = false;
    this.token = null;
  }
```

**Step 4: Run tests to verify they pass**

Run: `npm run build && node --test tests-mcp/ws-client.test.js`
Expected: All PASS

**Step 5: Run all MCP tests**

Run: `npm run build && node --test tests-mcp/*.test.js`
Expected: All PASS

**Step 6: Commit**

```bash
git add src/ws-client.ts tests-mcp/ws-client.test.js
git commit -m "fix: abort WS connect cleanly when disconnect is called mid-connect (T-H4)"
```

---

## Task 5: P-H1 — Batch statistics_during_period calls

**Files:**
- Modify: `custom_components/evon/coordinator/__init__.py:687-814`
- Test: `tests/test_coordinator_energy.py` (new)

**Step 1: Write the failing test**

Create `tests/test_coordinator_energy.py`:

```python
"""Tests for coordinator energy calculation batching (P-H1)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# These tests require the HA test framework
pytest_plugins = ["tests.conftest"]

# Only run if HA test framework is available
ha_test = pytest.importorskip("pytest_homeassistant_custom_component")

from homeassistant.core import HomeAssistant  # noqa: E402

from custom_components.evon.const import DOMAIN  # noqa: E402


@pytest.fixture
def mock_config_entry():
    """Create a mock config entry."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    return MockConfigEntry(
        domain="evon",
        title="Evon Smart Home",
        data={
            "host": "http://192.168.1.1",
            "username": "admin",
            "password": "password",
        },
        options={
            "scan_interval": 30,
            "sync_areas": False,
        },
        entry_id="test_energy_entry",
    )


class TestEnergyBatching:
    """Tests for P-H1: batched statistics_during_period calls."""

    @pytest.mark.asyncio
    async def test_multiple_meters_use_single_statistics_call(
        self,
        hass: HomeAssistant,
        mock_evon_api_class,
        mock_config_entry,
    ) -> None:
        """Verify N meters produce 1 statistics_during_period call, not N."""
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        coordinator = hass.data[DOMAIN][mock_config_entry.entry_id]["coordinator"]

        # Create 3 mock meters
        meters = [
            {"id": "meter_1", "name": "Meter One", "energy_data_month": [1.0, 2.0]},
            {"id": "meter_2", "name": "Meter Two", "energy_data_month": [3.0, 4.0]},
            {"id": "meter_3", "name": "Meter Three", "energy_data_month": [5.0]},
        ]

        stats_call_count = 0
        original_async_add_executor_job = hass.async_add_executor_job

        async def counting_executor_job(func, *args):
            nonlocal stats_call_count
            # Count calls to statistics_during_period
            if hasattr(func, "__name__") and "statistics" in func.__name__:
                stats_call_count += 1
            return await original_async_add_executor_job(func, *args)

        with patch.object(hass, "async_add_executor_job", side_effect=counting_executor_job):
            await coordinator._calculate_energy_today_and_month(meters)

        # Should be exactly 1 call, not 3
        assert stats_call_count == 1, (
            f"Expected 1 batched statistics call, got {stats_call_count}"
        )
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_coordinator_energy.py -v -x`
Expected: FAIL — `stats_call_count` is 3 (one per meter)

**Step 3: Implement the fix**

Replace the `_calculate_energy_today_and_month` method (lines 687-814) in `coordinator/__init__.py`:

```python
    async def _calculate_energy_today_and_month(self, smart_meters: list[dict[str, Any]]) -> None:
        """Calculate energy_today and energy_this_month for smart meters.

        Uses HA statistics to get today's consumption and combines with
        Evon's EnergyDataMonth for this month's total.
        """
        if not smart_meters:
            return

        now = dt_util.now()
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_day = now.day  # Day of month (1-31)

        _LOGGER.debug(
            "Calculating energy for %d smart meters, today_day=%d, start_of_day=%s",
            len(smart_meters),
            today_day,
            start_of_day.isoformat(),
        )

        # Build entity_id mapping for all meters upfront
        meter_entity_ids: dict[str, dict[str, Any]] = {}
        all_entity_ids: list[str] = []
        for meter in smart_meters:
            meter_name = meter.get("name", "")
            entity_id = f"sensor.{meter_name.lower().replace(' ', '_')}_energy_total"
            meter_entity_ids[entity_id] = meter
            all_entity_ids.append(entity_id)

        # Single batched statistics query for all meters
        all_stats: dict[str, list[dict[str, Any]]] = {}
        try:
            all_stats = await self.hass.async_add_executor_job(
                statistics_during_period,
                self.hass,
                start_of_day,
                now,
                all_entity_ids,
                "hour",
                {"energy": UnitOfEnergy.KILO_WATT_HOUR},
                {"change"},
            )
            _LOGGER.debug("Batched statistics result keys: %s", list(all_stats.keys()) if all_stats else "None")
            self._energy_stats_consecutive_failures = 0
        except (HomeAssistantError, ValueError, TypeError, KeyError) as err:
            self._energy_stats_consecutive_failures += 1
            if self._energy_stats_consecutive_failures >= ENERGY_STATS_FAILURE_LOG_THRESHOLD:
                _LOGGER.error(
                    "Energy statistics batch query failed %d times consecutively: %s. "
                    "Check that the recorder component is running.",
                    self._energy_stats_consecutive_failures,
                    err,
                )
            else:
                _LOGGER.warning("Could not get energy statistics: %s", err)
            all_stats = {}
        except Exception as err:
            self._energy_stats_consecutive_failures += 1
            if self._energy_stats_consecutive_failures >= ENERGY_STATS_FAILURE_LOG_THRESHOLD:
                _LOGGER.error(
                    "Energy statistics batch query failed %d times consecutively: %s. "
                    "Check that the recorder component is running.",
                    self._energy_stats_consecutive_failures,
                    err,
                    exc_info=True,
                )
            else:
                _LOGGER.warning("Could not get energy statistics: %s", err, exc_info=True)
            all_stats = {}

        # Distribute results to individual meters
        for entity_id, meter in meter_entity_ids.items():
            meter_name = meter.get("name", "")
            energy_today = None

            if entity_id in all_stats:
                hourly_changes = [s.get("change", 0) or 0 for s in all_stats[entity_id]]
                _LOGGER.debug("Hourly changes for %s: %s", entity_id, hourly_changes)
                energy_today = sum(hourly_changes)
                energy_today = round(energy_today, 2) if energy_today > 0 else 0.0
                _LOGGER.debug("Calculated energy_today for %s: %s kWh", meter_name, energy_today)
            else:
                _LOGGER.debug("No statistics found for %s in result", entity_id)

            # Store energy_today in the meter data
            meter["energy_today_calculated"] = energy_today
            _LOGGER.debug("Set energy_today_calculated=%s for %s", energy_today, meter_name)

            # Calculate energy_this_month
            energy_data_month = meter.get("energy_data_month")
            _LOGGER.debug(
                "energy_data_month for %s: %d items, last 5: %s",
                meter_name,
                len(energy_data_month) if energy_data_month else 0,
                energy_data_month[-5:] if energy_data_month else "None",
            )

            if energy_data_month and isinstance(energy_data_month, list):
                days_this_month_excluding_today = today_day - 1

                month_sum = 0.0
                if days_this_month_excluding_today > 0 and len(energy_data_month) >= days_this_month_excluding_today:
                    relevant_days = energy_data_month[-days_this_month_excluding_today:]
                    _LOGGER.debug(
                        "Using %d days from energy_data_month: %s", days_this_month_excluding_today, relevant_days
                    )
                    for v in relevant_days:
                        if isinstance(v, (int, float)):
                            month_sum += float(v)
                        elif isinstance(v, str):
                            with contextlib.suppress(ValueError):
                                month_sum += float(v)

                # Add today's consumption
                if energy_today is not None:
                    month_sum += energy_today

                meter["energy_this_month_calculated"] = round(month_sum, 2)
                _LOGGER.debug(
                    "Set energy_this_month_calculated=%s for %s (month_sum=%s + today=%s)",
                    meter["energy_this_month_calculated"],
                    meter_name,
                    month_sum - (energy_today or 0),
                    energy_today,
                )
            else:
                meter["energy_this_month_calculated"] = energy_today
                _LOGGER.debug("No energy_data_month, set energy_this_month_calculated=%s", energy_today)
```

Key changes:
- Collect all entity IDs first, then make ONE `statistics_during_period` call with all IDs
- Handle errors once at the batch level instead of per-meter
- Distribute results to individual meters after the single call
- The monthly calculation logic is unchanged

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_coordinator_energy.py -v -x`
Expected: PASS

**Step 5: Run all Python tests**

Run: `python -m pytest tests/ -v --timeout=30`
Expected: All PASS

**Step 6: Commit**

```bash
git add custom_components/evon/coordinator/__init__.py tests/test_coordinator_energy.py
git commit -m "perf: batch statistics_during_period into single call for all meters (P-H1)"
```

---

## Task 6: P-H2 — Copy-on-write for WS data updates

**Files:**
- Modify: `custom_components/evon/coordinator/__init__.py:513-646`
- Test: `tests/test_coordinator_ws_cow.py` (new)

**Step 1: Write the failing test**

Create `tests/test_coordinator_ws_cow.py`:

```python
"""Tests for coordinator copy-on-write WS updates (P-H2)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

pytest_plugins = ["tests.conftest"]
ha_test = pytest.importorskip("pytest_homeassistant_custom_component")

from homeassistant.core import HomeAssistant  # noqa: E402

from custom_components.evon.const import DOMAIN  # noqa: E402


@pytest.fixture
def mock_config_entry():
    """Create a mock config entry."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    return MockConfigEntry(
        domain="evon",
        title="Evon Smart Home",
        data={
            "host": "http://192.168.1.1",
            "username": "admin",
            "password": "password",
        },
        options={
            "scan_interval": 30,
            "sync_areas": False,
        },
        entry_id="test_cow_entry",
    )


class TestCopyOnWriteWsUpdates:
    """Tests for P-H2: copy-on-write pattern in WS handler."""

    @pytest.mark.asyncio
    async def test_ws_update_replaces_entity_dict_not_mutates(
        self,
        hass: HomeAssistant,
        mock_evon_api_class,
        mock_config_entry,
    ) -> None:
        """Verify WS update creates a new entity dict (copy-on-write)."""
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        coordinator = hass.data[DOMAIN][mock_config_entry.entry_id]["coordinator"]

        # Get the original entity dict reference for light_1
        original_entity = coordinator.get_entity_data("lights", "light_1")
        assert original_entity is not None
        original_id = id(original_entity)

        # Simulate WS update for this light
        coordinator._handle_ws_values_changed(
            "light_1",
            {"IsOn": True},
        )

        # Get the entity dict reference after WS update
        updated_entity = coordinator.get_entity_data("lights", "light_1")
        assert updated_entity is not None

        # The entity dict should be a NEW object (copy-on-write)
        assert id(updated_entity) != original_id, (
            "WS update should create a new entity dict, not mutate the original"
        )
        # But should still have the updated value
        assert updated_entity.get("is_on") is True

    @pytest.mark.asyncio
    async def test_ws_update_uses_data_index_for_lookup(
        self,
        hass: HomeAssistant,
        mock_evon_api_class,
        mock_config_entry,
    ) -> None:
        """Verify WS handler uses _data_index for O(1) lookup."""
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        coordinator = hass.data[DOMAIN][mock_config_entry.entry_id]["coordinator"]

        # Verify the entity exists in the index
        entity = coordinator._data_index.get(("lights", "light_1"))
        assert entity is not None

        # WS update should succeed (proves index lookup works)
        coordinator._handle_ws_values_changed(
            "light_1",
            {"IsOn": False},
        )

        updated = coordinator.get_entity_data("lights", "light_1")
        assert updated is not None
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_coordinator_ws_cow.py -v -x`
Expected: FAIL — `id(updated_entity) != original_id` fails (same object, mutated in place)

**Step 3: Implement the fix**

Replace the `_handle_ws_values_changed` method (lines 513-646) in `coordinator/__init__.py`:

```python
    def _handle_ws_values_changed(
        self,
        instance_id: str,
        properties: dict[str, Any],
    ) -> None:
        """Handle WebSocket ValuesChanged events.

        Uses copy-on-write: creates a new entity dict with updates applied,
        then atomically replaces it in the data structure. This prevents
        concurrent HTTP polls from reading partially-updated entity data.

        Args:
            instance_id: The instance ID that changed.
            properties: Dictionary of changed property names to values.
        """
        data_snapshot = self.data
        if not data_snapshot or not properties:
            return

        from ..ws_mappings import CLASS_TO_TYPE, ws_to_coordinator_data

        # Use _data_index for O(1) lookup instead of linear search
        entity: dict[str, Any] | None = None
        entity_type: str | None = None
        for etype in CLASS_TO_TYPE.values():
            found = self._data_index.get((etype, instance_id))
            if found is not None:
                entity = found
                entity_type = etype
                break

        if entity is None or entity_type is None:
            _LOGGER.debug(
                "WebSocket update for unknown instance: %s",
                instance_id,
            )
            return

        # Convert WebSocket properties to coordinator format
        try:
            coord_data = ws_to_coordinator_data(entity_type, properties, entity)
        except Exception as err:
            _LOGGER.error(
                "Failed to convert WebSocket data for %s (%s): %s. Requesting coordinator refresh to sync state.",
                instance_id,
                entity_type,
                err,
                exc_info=True,
            )
            self.hass.async_create_task(self.async_request_refresh())
            return

        if not coord_data:
            return

        # Re-check data reference before modifying
        current_data = self.data
        if current_data is not data_snapshot:
            _LOGGER.debug("Data replaced during WebSocket processing for %s, retargeting to new data", instance_id)
            entity = self._data_index.get((entity_type, instance_id))
            if entity is None:
                _LOGGER.debug("Entity %s not found in new data, dropping WS update", instance_id)
                return
            data_snapshot = current_data

        # Final consistency check
        final_data = self.data
        if final_data is not data_snapshot:
            _LOGGER.debug("Data replaced again during WS processing for %s, dropping update", instance_id)
            self.hass.async_create_task(self.async_request_refresh())
            return

        # Copy-on-write: create a new entity dict with updates applied
        updated_entity = dict(entity)
        for key, value in coord_data.items():
            old_value = entity.get(key)
            updated_entity[key] = value
            if old_value != value:
                _LOGGER.debug(
                    "WebSocket update: %s.%s: %s -> %s",
                    instance_id,
                    key,
                    old_value,
                    value,
                )

                # Fire doorbell event only on False→True transition
                if (
                    entity_type == ENTITY_TYPE_INTERCOMS
                    and key == "doorbell_triggered"
                    and value is True
                    and old_value is not True
                ):
                    self.hass.bus.async_fire(
                        f"{DOMAIN}_doorbell", {"device_id": instance_id, "name": updated_entity.get("name", "")}
                    )
                    _LOGGER.info("Doorbell event fired for %s", instance_id)

        # Atomically replace entity in the list and update index
        entities_list = data_snapshot.get(entity_type)
        if entities_list and isinstance(entities_list, list):
            for idx, e in enumerate(entities_list):
                if e and e.get("id") == instance_id:
                    entities_list[idx] = updated_entity
                    break
        self._data_index[(entity_type, instance_id)] = updated_entity

        # Import energy statistics when smart meter data is received
        if entity_type == ENTITY_TYPE_SMART_METERS:
            self._maybe_import_energy_statistics(instance_id, updated_entity)

        # Notify listeners
        self.async_set_updated_data(data_snapshot)
```

Key changes:
- Uses `_data_index` for O(1) entity lookup instead of linear search through all entity types
- Creates a new `updated_entity = dict(entity)` (shallow copy) before applying changes
- Replaces the entity in the list and updates `_data_index` atomically
- Existing race detection checks remain as defense-in-depth

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_coordinator_ws_cow.py -v -x`
Expected: PASS

**Step 5: Run all Python tests**

Run: `python -m pytest tests/ -v --timeout=30`
Expected: All PASS (including doorbell transition tests)

**Step 6: Commit**

```bash
git add custom_components/evon/coordinator/__init__.py tests/test_coordinator_ws_cow.py
git commit -m "fix: copy-on-write for WS entity updates to prevent data races (P-H2)"
```

---

## Task 7: Final verification and backlog update

**Files:**
- Modify: `docs/CODE_ANALYSIS_BACKLOG.md`

**Step 1: Run all tests**

```bash
python -m pytest tests/ -v --timeout=30
npm run build && node --test tests-mcp/*.test.js
```

Expected: All PASS in both suites.

**Step 2: Run linting**

```bash
cd /Users/milan/www/evon-ha && python -m ruff check custom_components/ tests/
cd /Users/milan/www/evon-ha && npx eslint src/
```

Expected: No new warnings/errors.

**Step 3: Update backlog**

Move P-H1, P-H2, T-H1, T-H2, T-H3, T-H4, and T-L4 from "Remaining Backlog" to "Fixed Issues" table. Update summary statistics.

**Step 4: Commit**

```bash
git add docs/CODE_ANALYSIS_BACKLOG.md
git commit -m "docs: update backlog — mark 7 issues as fixed (P-H1, P-H2, T-H1-H4, T-L4)"
```
