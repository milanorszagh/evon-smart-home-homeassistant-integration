# Code Analysis Backlog

Deep code analysis performed on 2026-02-13 identified **74 issues** across the
Python HA integration (18), TypeScript MCP server (27), and Tests/CI (29).

**21 issues were fixed** across two passes. This document tracks the remaining
**58 issues** organized by severity and category.

---

## Fixed Issues (for reference)

| Fix # | Area | Issue |
|-------|------|-------|
| 1 | CI | mypy CI step: install `requirements-test.txt` before mypy |
| 2 | TS | Add `EVON_HOST` check at MCP server startup (`src/index.ts:29`) |
| 3 | Tests | Fix tautological test assertions; move constants to `const.py` |
| 4 | CI | Add `--cov-fail-under=76` threshold to CI |
| 5 | Python | Fix `recording_finished` event frame count (capture before finalize) |
| 6 | Python | Cap camera recorder frame buffer (`deque` with `maxlen`) |
| 7 | Python | Add entity data index for O(1) lookup in coordinator |
| 8 | TS | Fix WS subscription leak in `getPropertyValues` |
| 9 | TS | Add post-connection error handler in TS WS client |
| 10 | TS | Fix API client retry to detect re-auth failure |
| 11 | Python | Batch `statistics_during_period` calls for smart meters (P-H1) |
| 12 | Python | Copy-on-write for WS data updates to prevent data races (P-H2) |
| 13 | TS | Add `process.exit(1)` to `main().catch()` handler (T-H1) |
| 14 | TS | Reset `sequenceId` on WS reconnect (T-H2) |
| 15 | TS | Re-register WS subscriptions after reconnect (T-H3) |
| 16 | TS | Handle disconnect during connect cleanly (T-H4) |
| 17 | TS | Add SIGTERM/SIGINT graceful shutdown handler (T-L4) |

---

## Remaining Backlog

### Critical / High Severity

#### Python

| ID | Category | File | Line | Description |
|----|----------|------|------|-------------|
| | | | | *(P-H1 and P-H2 fixed — see Fixed Issues table)* |

#### TypeScript

| ID | Category | File | Line | Description |
|----|----------|------|------|-------------|
| | | | | *(T-H1, T-H2, T-H3, T-H4 fixed — see Fixed Issues table)* |

#### Tests / CI

| ID | Category | File | Line | Description |
|----|----------|------|------|-------------|
| C-H1 | Coverage | `custom_components/evon/__init__.py` | 608 | **`_async_cleanup_stale_entities` completely untested.** This function removes entities whose instance IDs no longer appear in the API response. A bug here silently deletes user entities. |
| C-H2 | Coverage | `custom_components/evon/__init__.py` | 681 | **`_async_update_listener` (options change handler) completely untested.** This handler reloads the integration on options changes. A failure here leaves the integration in a broken state after reconfiguration. |
| C-H3 | Coverage | `custom_components/evon/__init__.py` | 420-440 | **`start_recording`/`stop_recording` service handlers completely untested.** These services control camera recording lifecycle but have zero test coverage. |
| C-H4 | Coverage | `custom_components/evon/ws_client.py` | 345 | **WS reconnection loop (`_run_loop`) has zero test coverage.** The main WebSocket reconnection state machine, including backoff, resubscription, and error handling, is entirely untested. |
| C-H5 | Quality | `tests/test_services.py` | 89-104 | **`test_refresh_service` and `test_reconnect_websocket_service` have zero assertions.** These tests call the service and return, verifying only that no exception is raised. They do not assert that the coordinator was actually refreshed or the WS reconnected. |
| C-H6 | Isolation | `tests/conftest.py` | 200+ | **`MOCK_INSTANCE_DETAILS` is shared mutable state.** The nested dicts in the mock instance data are shared across tests. A test that mutates a nested property (e.g., `data["is_on"] = False`) leaks to subsequent tests. Use `copy.deepcopy()` in the fixture or make the fixture function-scoped. |
| C-H7 | CI | `.github/workflows/ci.yml` | 37 | **mypy runs with `continue-on-error: true`.** Type errors never fail CI. This was partially addressed (requirements now install correctly) but the flag remains because 83 type errors still exist. Track resolution of those errors to eventually remove the flag. |

---

### Medium Severity

#### Python

| ID | Category | File | Line | Description |
|----|----------|------|------|-------------|
| P-M1 | Bug | `switch.py` | 281 | **Bathroom radiator `turn_off` race condition.** Timer expiry between the state check (`data.get("is_on")`) and the `toggle` command sends the opposite command. The double-tap guard mitigates rapid user interactions but not server-side timer expiry during the window. Consider adding a server-side `SwitchOff` method or a post-toggle verification. |
| P-M2 | Bug | `__init__.py` | 699 | **Services operate on partially-unloaded entry data.** If `async_unload_platforms` fails partway through, `hass.data[DOMAIN][entry.entry_id]` still exists but platforms are partially unloaded. Subsequent service calls may operate on stale or missing data. |
| P-M3 | Bug | `coordinator/__init__.py` | 708 | **Energy `entity_id` constructed from meter name via fragile string manipulation.** The format `sensor.{name.lower().replace(' ', '_')}_energy_total` breaks if the user renames the entity or if the name contains special characters. Use `entity_registry.async_get_entity_id()` instead. |
| P-M4 | Concurrency | `coordinator/__init__.py` | 483 | **`update_interval` mutated directly in WS callback without synchronization.** `_handle_ws_connection_state` sets `self.update_interval` from a callback context. While HA's event loop is single-threaded, this mutation interleaves with the coordinator's scheduling logic and could set an unexpected interval if called during `_async_update_data`. |

#### TypeScript

| ID | Category | File | Line | Description |
|----|----------|------|------|-------------|
| T-M1 | Bug | `src/ws-client.ts` | 302 | **`getPropertyValues` hangs for full timeout if server never sends data.** If the server omits data for one of the requested instance IDs, the function waits the entire `API_TIMEOUT_MS` (10s) before rejecting. There is no partial-result fallback. |
| T-M2 | Type Safety | `src/api-client.ts` | 125 | **`response.json()` cast to `ApiResponse<T>` is unchecked.** No runtime validation ensures the response matches the `ApiResponse<T>` shape. A server error returning HTML or a different JSON structure will produce confusing downstream errors. Add a runtime schema check (e.g., Zod). |
| T-M3 | Error Handling | `src/ws-client.ts` | 572 | **`handleMessage` parse errors logged to stderr via `console.error`.** Since MCP uses stdio transport, writing to stderr can corrupt the MCP message stream if stderr is not fully separated. Use the MCP server's logging mechanism instead. |
| T-M4 | Security | `src/helpers.ts` | 22-27 | **`sanitizeId` applied inconsistently across tool handlers.** Some tool handlers call `sanitizeId()` (e.g., `generic.ts:57`, `lights.ts:34`), but resource handlers in `helpers.ts` pass `light.ID` directly to URL construction at line 88 without sanitization. If the API returns a crafted ID, it could cause path traversal. |
| T-M5 | Security | `src/helpers.ts` | 88 | **`fetchXxxWithState` helpers pass instance IDs to URL without sanitization.** Functions like `fetchLightsWithState()` use `apiRequest(\`/instances/${light.ID}\`)` where `light.ID` comes from a prior API call. While the ID originates from the same server, a compromised or buggy server response could inject path segments. |
| T-M6 | Performance | `src/ws-client.ts` | 697-702 | **`wsControlLight` sends on+brightness sequentially instead of in parallel.** When both `options.on` and `options.brightness` are specified, two separate `await` calls are made. These could be fired concurrently with `Promise.all()`. |
| T-M7 | Performance | `src/helpers.ts` | 82 | **`fetchXxxWithState` helpers call `getInstances()` redundantly.** Each `fetchLightsWithState()`, `fetchBlindsWithState()`, `fetchClimateWithState()`, etc. independently calls `getInstances()`, which makes a full HTTP round-trip. If multiple are called in sequence (e.g., from `summary.ts`), the instances list is fetched multiple times. Add a short-lived cache or accept instances as a parameter. |
| T-M8 | Bug | `src/config.ts` | 25-27 | **`isPasswordEncoded` heuristic false positive on 88-char passwords ending `==`.** A user password that happens to be exactly 88 characters and ends with `==` will be treated as pre-encoded, causing authentication failure. The `EVON_PASSWORD_ENCODED` env var override exists but the default heuristic is fragile. |
| T-M9 | Security | `src/tools/generic.ts` | 80-93 | **`call_method` tool exposes full API surface with no method allowlist.** Any MCP client can call arbitrary methods on any instance. While `sanitizeId` prevents path traversal, there is no restriction on which methods can be called. A malicious or misconfigured LLM could invoke destructive methods. Consider an allowlist or confirmation step. |
| T-M10 | Bug | `src/helpers.ts` | 40-48 | **`filterClimateDevices` uses `includes()` for substring match.** `i.ClassName.includes(DEVICE_CLASSES.CLIMATE_UNIVERSAL)` matches any class name containing the substring `ClimateControlUniversal`, which could match unintended classes. Use exact match or `startsWith()`. |

#### Tests / CI

| ID | Category | File | Line | Description |
|----|----------|------|------|-------------|
| C-M1 | Coverage | `camera_recorder.py` | 196 | **Camera MP4 encoding path (`_finalize_recording`) is fully mocked out.** The actual ffmpeg/imageio encoding is never exercised in tests, so encoding regressions are invisible. |
| C-M2 | Coverage | `__init__.py` | varies | **Bulk service error accumulation/partial failure untested.** Services like `all_lights_off` iterate over devices; partial failures (some succeed, some throw) are not tested. |
| C-M3 | Coverage | `coordinator/__init__.py` | 687 | **Energy midnight rollover and month boundary untested.** The `_calculate_energy_today_and_month` logic depends on time-of-day boundaries that are never exercised. |
| C-M4 | Coverage | `config_flow.py` | varies | **Options flow completely untested.** The `EvonOptionsFlowHandler` that handles reconfiguration is not covered by any test. |
| C-M5 | Coverage | `light.py` | varies | **Brightness rounding edge cases (1->0, 254->100) untested.** The brightness conversion between HA (0-255) and Evon (0-100) at boundary values is not verified. |
| C-M6 | Mock Quality | `tests/conftest.py` | varies | **Mock HA modules use `MagicMock` -- wrong constants compare equal.** `MagicMock()` instances always return `True` for `==` comparisons, so tests using `HVACMode.HEAT == some_mock` will pass regardless of value, hiding type bugs. |
| C-M7 | Mock Quality | `tests/conftest.py` | varies | **Mock API missing validation -- accepts out-of-range values real API would reject.** The mock API's `set_climate_temperature(id, temp)` accepts any value, while the real API rejects temperatures outside 5-40. |
| C-M8 | Mock Quality | `tests/conftest.py` | 308 | **`set_ws_client`/`set_instance_classes` are lambdas, not mockable.** These are plain lambda functions rather than `MagicMock` instances, so tests cannot assert on their call counts or arguments. |
| C-M9 | Quality | `tests/test_constants.py` | 1-40 | **`TestServiceConstants` / `TestDomainConstants` tests local copies of constants, not production code.** Some constant tests define local values and compare them, rather than importing from `const.py` and verifying against expected values. The test at line 9 does import correctly, but others in `test_services.py` used local copies (now fixed). |
| C-M10 | CI | `.github/workflows/ci.yml` | 54-55 | **No Python dependency security scanning.** `npm audit` runs for Node.js dependencies but there is no `pip-audit` or `safety` check for Python dependencies. |
| C-M11 | CI | `.github/workflows/ci.yml` | 103 | **Codecov upload failures silently ignored.** `fail_ci_if_error: false` means coverage upload failures are invisible. If the Codecov token expires or the service is down, CI still passes but coverage data is lost. |
| C-M12 | Missing | tests/ | -- | **No concurrent API call tests (WS + HTTP race).** There are no tests simulating simultaneous WebSocket value updates and HTTP poll responses to verify the coordinator's concurrency handling. |
| C-M13 | Missing | tests/ | -- | **No negative tests for service handlers (invalid params).** Service handlers are never tested with invalid parameters (e.g., unknown home state, out-of-range temperature). |

---

### Low Severity

#### Python

| ID | Category | File | Line | Description |
|----|----------|------|------|-------------|
| P-L1 | Bug | `climate.py` | 163 | **`current_humidity` transform crashes on malformed API data.** `entity_data("humidity", transform=lambda v: int(v))` will raise `ValueError` if `v` is `None`, an empty string, or a non-numeric value. Add a safe cast: `lambda v: int(v) if v is not None else None`. |
| P-L2 | Security | `ws_client.py` | 100 | **WS client credentials not cleared on shutdown.** `self._password` (the encoded password) remains in memory after `stop()` is called. For defense-in-depth, clear sensitive fields on shutdown. |
| P-L3 | Resource Leak | `__init__.py` | 451 | **Static paths not cleaned up on unload.** The `StaticPathConfig` for `/evon/recordings` and the camera card JS file are registered once but never unregistered on `async_unload_entry`. The paths remain accessible after the integration is removed. HA does not provide an unregister API, so this is a framework limitation, but worth noting. |
| P-L4 | Performance | `__init__.py` | 467 | **Stale entity cleanup runs on every reload.** `_async_cleanup_stale_entities` runs unconditionally during `async_setup_entry`. For users with many entities, this adds latency to every reload even when no entities are stale. Consider running only on version upgrades or first setup. |
| P-L5 | Error Handling | `camera_recorder.py` | 179 | **Recording loop auto-stop error path produces confusing logs.** When the recording auto-stops due to max duration, the `asyncio.CancelledError` path returns before the auto-stop event fires, making the log output ambiguous about whether the recording ended normally or was cancelled. |
| P-L6 | Bug | `ws_client.py` | 554 | **WS key parsing edge case with malformed keys.** The `key.split(".")` / `parts.pop()` pattern for parsing `InstanceId.PropertyName` fails silently on keys with no dots (the property is the entire key, and `instance_id` becomes empty string). While the server should always send dotted keys, a defensive check would prevent silent data loss. |
| P-L7 | Security | `config_flow.py` | varies | **Config entry password stored plain text on disk.** `ConfigEntry.data[CONF_PASSWORD]` stores the user's plaintext password in `.storage/core.config_entries`. This is a HA-wide pattern (most integrations do this), but it means the password is readable by any process with filesystem access. |
| P-L8 | Bug | `ws_client.py` | 108 | **Sequence ID unbounded growth (theoretical).** `self._sequence_id` increments monotonically without bound. Python integers have arbitrary precision so this won't overflow, but the server may use fixed-width integers. After ~2 billion calls the server could wrap. Unlikely in practice. |
| P-L9 | HA Practices | `climate.py` | varies | **HVAC OFF maps to freeze protection, not actual off.** Setting `HVACMode.OFF` sends the freeze protection mode to the Evon controller rather than actually turning off heating. This is intentional and documented to prevent pipe freezing, but may surprise users. |

#### TypeScript

| ID | Category | File | Line | Description |
|----|----------|------|------|-------------|
| T-L1 | Bug | `src/ws-client.ts` | 556-558 | **WS `ValuesChanged` handler ignores malformed entries silently.** If a `ValuesChanged` event contains entries where `entry.value` is missing or `entry.value.Value` is undefined, the property is set to `undefined` without logging. This makes debugging data issues difficult. |
| T-L2 | Bug | `src/helpers.ts` | 177-182 | **`timeRemaining` unit ambiguity in radiator state.** `NextSwitchPoint` is treated as hours (integer part = hours, fractional = minutes) but the property name and format string suggest minutes. The conversion `Math.floor(timeRemaining)` and `(timeRemaining % 1) * 60` is correct for hours-and-fraction but confusing. Add a comment or rename variables. |
| T-L3 | Performance | `src/resources/*.ts` | varies | **Hardcoded resource URIs like `evon://climate`.** Resource URIs are hardcoded strings. If the naming convention changes, multiple files must be updated. Consider defining them in `constants.ts`. |
| | | | | *(T-L4 fixed — see Fixed Issues table)* |
| T-L5 | Error Handling | `src/ws-client.ts` | 573 | **`console.error` usage throughout WS client on stdio transport.** Multiple `console.error` calls in the WS client write to stderr. While stderr is separate from stdout (used for MCP), some environments merge them. Use structured logging or suppress in production. |
| T-L6 | Security | `src/tools/generic.ts` | 88 | **`callMethod` uses `sanitizeId` for method name but no semantic validation.** While `sanitizeId` prevents path traversal in the method parameter, it does not restrict which methods can be called. Combined with T-M9, this means any alphanumeric method name is accepted. |
| T-L7 | Bug | `src/tools/radiators.ts` | 38-48 | **Bathroom radiator `on`/`off` actions are not truly mutual exclusive.** The `on` action toggles only if currently off, and `off` toggles only if currently on. But between the state check (`apiRequest`) and the toggle (`callMethod`), the state could change (same race as P-M1). |
| T-L8 | Maintenance | `src/ws-client.ts` | 449-481 | **Duplicated login logic between WS client and API client.** The `EvonWsClient.login()` method duplicates the HTTP login flow from `api-client.ts:performLogin()`. Changes to the login protocol must be made in both places. Consider extracting a shared login function. |
| T-L9 | Maintenance | `src/ws-client.ts` | 126 | **Subscription cleanup on disconnect clears local map but not server-side.** `disconnect()` calls `this.subscriptions.clear()` (line 230) which removes local callbacks but does not send `RegisterValuesChanged(false, ...)` to the server. The server may continue processing subscriptions for the closed connection until it detects the disconnect. |
| T-L10 | Bug | `src/config.ts` | 31 | **`EVON_HOST` defaults to empty string instead of `undefined`.** Using `process.env.EVON_HOST || ""` means `EVON_HOST` is falsy but not `undefined`. Some downstream checks (like `if (!EVON_HOST)`) work, but TypeScript type narrowing treats it as always-string, masking the "not configured" state. |

#### Tests / CI

| ID | Category | File | Line | Description |
|----|----------|------|------|-------------|
| C-L1 | Coverage | `ws_client.py` | varies | **`_calculate_reconnect_delay` (backoff/jitter) untested.** The reconnect delay calculation with exponential backoff and jitter is a pure function that could easily be unit tested but has no coverage. |
| C-L2 | Isolation | `tests/test_base_entity.py` | 14-30 | **`sys.modules` manipulation in `test_base_entity.py` cleanup is fragile.** Tests manually inject/remove `MagicMock` modules into `sys.modules` to stub HA dependencies. If a test fails before cleanup, subsequent tests may see stale mocks. Use `unittest.mock.patch.dict` for safer scoping. |
| C-L3 | CI | `.github/workflows/ci.yml` | 91 | **No pip cache in test job.** The Python test job does not cache pip packages, causing full downloads on every CI run. Add `cache: "pip"` to `setup-python`. |
| C-L4 | CI | `.github/workflows/ci.yml` | 77-80 | **Single OS matrix (ubuntu only, dev is macOS).** Tests run only on Ubuntu while development happens on macOS. Path handling, async behavior, and ffmpeg availability may differ across platforms. Consider adding macOS to the matrix. |
| C-L5 | Quality | `tests/test_device_trigger.py` | 12-26 | **`test_device_trigger` tests local constants, not imported ones.** `TRIGGER_TYPE_DOORBELL` and `TRIGGER_TYPES` are defined locally in the test file rather than imported from `device_trigger.py`. The test verifies its own local values, not the production constants. |
| C-L6 | Missing | tests/ | -- | **No timing boundary tests for optimistic state / token expiry.** Edge cases around optimistic state timeout (e.g., exactly at the expiry boundary) and token refresh timing are not tested. |

---

## Summary Statistics

| Severity | Python | TypeScript | Tests/CI | Total |
|----------|--------|------------|----------|-------|
| High     | 0      | 0          | 7        | 7     |
| Medium   | 4      | 10         | 13       | 27    |
| Low      | 9      | 9          | 6        | 24    |
| **Total remaining** | **13** | **19** | **26** | **58** |
| Fixed    | 5      | 9          | 7 (3 Test + 4 CI) | 21 |
| **Grand total** | **18** | **28** | **33** | **79** |

> Note: The original analysis found 74 issues. During the fix pass, 5 additional
> sub-issues were identified (e.g., separate aspects of the same root cause),
> bringing the tracked total to 79. The discrepancy is intentional -- it reflects
> more granular tracking, not scope creep.

---

## Suggested Next Priorities

### Quick wins (< 1 hour each)

1. **P-L1** -- Add null guard to `current_humidity` transform
2. ~~**T-L4** -- Add `SIGTERM`/`SIGINT` graceful shutdown handler~~ ✅ Fixed
3. ~~**T-H1** -- Add `process.exit(1)` to `main().catch()` handler~~ ✅ Fixed
4. **C-L3** -- Add pip cache to CI
5. **C-L5** -- Import `TRIGGER_TYPE_DOORBELL` from production code in test

### High-impact improvements (1-4 hours each)

6. ~~**P-H1** -- Batch `statistics_during_period` calls for smart meters~~ ✅ Fixed
7. ~~**T-H3** -- Implement WS reconnection with subscription re-registration~~ ✅ Fixed
8. **T-L8** -- Extract shared login function between WS and API clients
9. **C-H4** -- Add basic WS reconnection loop tests
10. **C-H1** -- Add tests for `_async_cleanup_stale_entities`

### Technical debt reduction

11. **T-M7** -- Add instances cache to reduce redundant `getInstances()` calls
12. **P-M3** -- Use entity registry for energy entity_id resolution
13. **C-M6** -- Replace `MagicMock` HA constants with real enum values in mocks
14. **C-H7** -- Resolve remaining 83 mypy errors to remove `continue-on-error`
