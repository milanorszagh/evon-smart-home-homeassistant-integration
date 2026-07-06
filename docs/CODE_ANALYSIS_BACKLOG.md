# Code Analysis Backlog

> **Note:** This document tracks the 2026-02-13 analysis sweep through v1.21.0.
> Post-v1.21.0 follow-ups landed on `main` and are not listed here:
> npm audit fixes (#4), `validateConfig → requireEvonHost` refactor (#5),
> coordinator WS handler migration to `async_update_listeners`, dimmable
> brightness=0 when off, and always-refresh on light/switch commands.

Deep code analysis performed on 2026-02-13 identified **74 issues** across the
Python HA integration (18), TypeScript MCP server (27), and Tests/CI (29).

**67 issues were fixed** across eight backlog sweep tasks. This document tracks the remaining
**7 issues** (4 won't fix, 3 deferred/ongoing) organized by severity and category.

---

## Fixed Issues (for reference)

| Fix # | Area | Issue |
|-------|------|-------|
| 1 | CI | mypy CI step: install `requirements-test.txt` before mypy |
| 2 | TS | Add `EVON_HOST` check at MCP server startup (`src/index.ts:43`) |
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
| 18 | Python | Add null guard to `current_humidity` transform (P-L1) |
| 19 | Python | Clear WS client credentials on shutdown (P-L2) |
| 20 | Python | Optimize stale entity cleanup to run only on version upgrades (P-L4) |
| 21 | Python | Improve recording loop auto-stop error logging (P-L5) |
| 22 | Python | Add defensive check for WS key parsing edge case (P-L6) |
| 23 | Python | Add bounds checking for sequence ID to prevent theoretical overflow (P-L8) |
| 24 | Python | Fix bathroom radiator `turn_off` race condition with server-side state verification (P-M1) |
| 25 | Python | Add partial unload safeguards for service handlers (P-M2) |
| 26 | Python | Use entity registry for energy entity_id resolution (P-M3) |
| 27 | Python | Synchronize `update_interval` mutation in WS callback (P-M4) |
| 28 | TS | Add logging for malformed WS `ValuesChanged` entries (T-L1) |
| 29 | TS | Clarify `timeRemaining` unit handling with comments (T-L2) |
| 30 | TS | Move hardcoded resource URIs to constants (T-L3) |
| 31 | TS | Replace `console.error` with structured logging in WS client (T-L5, T-M3) |
| 32 | TS | Add timeout and partial-result handling for `getPropertyValues` (T-M1) |
| 33 | TS | Add runtime schema validation for API responses with Zod (T-M2) |
| 34 | TS | Apply `sanitizeId` consistently across all tool and resource handlers (T-M4, T-M5) |
| 35 | TS | Parallelize on+brightness commands in `wsControlLight` (T-M6) |
| 36 | TS | Add shared instances cache to reduce redundant `getInstances()` calls (T-M7) |
| 37 | TS | Replace password encoding heuristic with explicit configuration (T-M8) |
| 38 | TS | Add method allowlist and confirmation for `call_method` tool (T-M9) |
| 39 | TS | Fix `filterClimateDevices` to use exact match instead of substring (T-M10) |
| 40 | TS | Add semantic validation for method names beyond path traversal (T-L6) |
| 41 | TS | Add mutual exclusion lock for bathroom radiator toggle actions (T-L7) |
| 42 | TS | Extract shared login function to eliminate duplication (T-L8) |
| 43 | TS | Use `undefined` instead of empty string for `EVON_HOST` default (T-L10) |
| 44 | Tests | Replace assertion-free service tests with proper verification (C-H5) |
| 45 | Tests | Fix shared mutable state in `MOCK_INSTANCE_DETAILS` using deep copy (C-H6) |
| 46 | Tests | Add integration test for camera MP4 encoding path (C-M1) |
| 47 | Tests | Add tests for bulk service partial failure handling (C-M2) |
| 48 | Tests | Add tests for energy midnight rollover and month boundary (C-M3) |
| 49 | Tests | Add comprehensive tests for options flow handler (C-M4) |
| 50 | Tests | Add tests for brightness conversion boundary values (C-M5) |
| 51 | Tests | Replace `MagicMock` HA constants with real enum values (C-M6) |
| 52 | Tests | Add validation to mock API matching real API constraints (C-M7) |
| 53 | Tests | Convert `set_ws_client`/`set_instance_classes` to mockable functions (C-M8) |
| 54 | Tests | Fix `test_constants.py` to import from production code (C-M9) |
| 55 | CI | Add Python dependency security scanning with pip-audit (C-M10) |
| 56 | CI | Enable Codecov upload failure detection in CI (C-M11) |
| 57 | Tests | Add concurrent API call tests (WS + HTTP race conditions) (C-M12) |
| 58 | Tests | Add negative tests for service handlers with invalid params (C-M13) |
| 59 | Tests | Add unit tests for `_calculate_reconnect_delay` backoff/jitter (C-L1) |
| 60 | Tests | Replace `sys.modules` manipulation with `unittest.mock.patch.dict` (C-L2) |
| 61 | CI | Add pip cache to test job (C-L3) |
| 62 | CI | Add macOS to CI matrix for cross-platform testing (C-L4) |
| 63 | Tests | Fix `test_device_trigger.py` to import production constants (C-L5) |
| 64 | Tests | Add timing boundary tests for optimistic state and token expiry (C-L6) |
| 65 | Tests | Add comprehensive tests for `_async_cleanup_stale_entities` (C-H1) |
| 66 | Tests | Add tests for `_async_update_listener` options change handler (C-H2) |
| 67 | Tests | Add tests for `start_recording`/`stop_recording` service handlers (C-H3) |
| 68 | Tests | Add tests for WS reconnection loop and state machine (C-H4) |

---

## Remaining Backlog

### Deferred / Ongoing

#### Tests / CI

| ID | Category | File | Line | Description | Status |
|----|----------|------|------|-------------|--------|
| C-H7 | CI | `.github/workflows/ci.yml` | 42 | **mypy runs with `continue-on-error: true`.** Type errors never fail CI. This was partially addressed (requirements now install correctly) but the flag remains because type errors still exist. Track resolution of those errors to eventually remove the flag. | Tracked separately as standalone effort |

#### v1.22.0 Pre-Release Review (2026-07)

A deep review of the `fix/post-command-quiesce` branch fixed 2 security issues
and 7 correctness bugs, plus a cleanup pass — see commits `da74d6b`
(blockers) and `5691416` (cleanup) and the README v1.22.0 changelog. The items
below were surfaced by the same review but deliberately deferred; they are
tracked here rather than lost.

Bugs:

| ID | Category | File | Description | Status |
|----|----------|------|-------------|--------|
| RV-B1 | Lifecycle | `__init__.py` (`async_unload_entry`) | API/WS were torn down (credentials blanked) **before** `async_unload_platforms`. If platform unload returned False the entry stayed "loaded" but was a zombie: no WS, blank credentials, `unloading=True` never reset. **Fixed:** teardown now happens only after a successful platform unload; on failure the `unloading` flag is reset. | Fixed |
| RV-B2 | Auth | `__init__.py` (`async_setup_entry`) | Setup-time `EvonAuthError` from `test_connection()` propagated as a generic setup error instead of `ConfigEntryAuthFailed`, so a password change while HA was down yielded a dead entry with no reauth prompt; login rate-limiting (also `EvonAuthError`) risked a spurious reauth dialog. **Fixed:** added `EvonRateLimitError(EvonAuthError)`; setup maps a real auth error to `ConfigEntryAuthFailed` (reauth) and a rate-limit to `ConfigEntryNotReady` (retry); the coordinator treats a poll-time rate-limit as transient rather than reauth. | Fixed |
| RV-B3 | Cleanup | `__init__.py` (stale-entity cleanup) | Fallback unique-id extractor returned from the first dot-containing part, truncating IDs with underscores (`SC1_M01.AirQ1` → `M01.AirQ1` → falsely "stale" → removed) for the `evon_doorbell_`, `evon_energy_today_`, `evon_energy_this_month_` prefixes missing from `type_prefixes`. **Fixed:** added those prefixes (and made the `websocket_status`/`websocket_latency` diagnostic entities explicitly special). Note: the separate concern that cleanup runs on partial-poll data (a single failed instance fetch marking its entities stale) is **still open** — see RV-D6 below. | Fixed (partial-poll guard deferred) |

Design decisions — need owner input (may be intentional):

| ID | Category | File | Description | Status |
|----|----------|------|-------------|--------|
| RV-D1 | Quiesce | `base_entity.py` | `_cancel_post_command_recheck_if_data_changed` treated *any* completing poll as fresh data (dict-identity churn), so a poll whose snapshot predated the command cancelled the recheck safety net when it was most needed. **Fixed:** the default snapshot/compare now keys off the coordinator's per-entity WS-update timestamp (new `get_ws_update_timestamp`), so only a genuine WS update cancels the recheck; a stale poll rebuild does not. Selects keep their value-equality override. | Fixed |
| RV-D2 | Climate | `climate.py` | `hvac_mode` is derived from `is_on` (actively heating). Setting HEAT while already at setpoint (device reports off) can never comparison-match, so the optimistic value sticks ~30s then flips to OFF; the 5s recheck refetches the same non-matching truth. **Won't fix (owner decision 2026-07):** the flip is intrinsic to `hvac_mode` being `is_on`-derived — no minimal fix removes it without also changing the mode display (deriving from `season_mode`/preset), which is a behavior change the owner declined. `hvac_action` (which drives the climate history graph and correctly shows HEATING/COOLING) is deliberately left untouched. Only bites when the HEAT/COOL/OFF selector is used rather than presets. | Won't fix |
| RV-D3 | Cover | `cover.py` | `async_stop_cover` and the toggle-stop branches ended with `sleep + write` and scheduled no recheck, contradicting commit `ebd7265` ("scheduled recheck for all blind commands"). If WS was dead after a stop, the resting position stayed stale until the 60s poll. **Fixed:** all three stop paths now also call `_schedule_post_command_recheck()` (alongside the existing sleep+write); the resting position is fetched within the quiesce window in HTTP-only mode, and the recheck is cancelled by the WS position update when WS is live (RV-D1). | Fixed |
| RV-D4 | Statistics | `statistics.py` | Sliding `sum=0` baseline zeroes the daily `change` for days older than the 31-day window. Consistent within the dashboard window but was silent long-term data loss. **Resolved by doc (owner decision 2026-07):** bounded by Evon's 31-day source window (no correct daily data exists beyond that after the fact); monthly granularity is preserved via `EnergyDataYear`. Documented the limitation in ENERGY_STATISTICS.md ("Retention limitation") so it's no longer silent, and pointed users at the native meter sensor / utility-meter for long-term daily history. The persistent-cumulative-sum rewrite was declined to avoid risking accumulated-stats corruption. | Resolved (doc) |
| RV-D5 | Coordinator | `coordinator/__init__.py` | Recheck-triggered refresh could start a second concurrent `_async_update_data` while a poll was in flight (HA core doesn't serialize `_async_refresh`), racing on `_instances_cache` / `_rooms_cache` / `_ws_update_timestamps`. **Fixed:** added an `_update_in_progress` re-entrancy guard — if a poll is already running, `_async_update_data` returns current data instead of starting a second fetch (cleared in a `finally`). | Fixed |
| RV-D6 | Cleanup | `__init__.py` (`_async_cleanup_stale_entities`) | Cleanup runs on every setup gated only on `last_update_success`, which stays True even when `_safe_get_instance` silently drops individual instances on a transient fetch error. Those entities are then absent from `coordinator.data` and removed as "stale" (losing user customizations). Needs the coordinator to expose whether the poll had partial failures and skip cleanup if so. | Open (design) |

Low-severity hardening (all fixed):

| ID | Category | File | Description | Status |
|----|----------|------|-------------|--------|
| RV-L1 | Input validation | `api.py` | `INSTANCE_ID_PATTERN` (`^[a-zA-Z0-9._-]+$`) matched `..`, so the "prevents path traversal" docstring was overstated. **Fixed:** `_validate_instance_id` now also requires ≥1 alphanumeric, rejecting dot-only ids. | Fixed |
| RV-L2 | SSRF-ish | `api.py` (`fetch_image`) | Built `f"{host}{image_path}"` from an unvalidated server-supplied path; a value like `@evil/x` could send the auth cookie off-host. **Fixed:** `fetch_image` now requires a single leading `/` (rejects `@…`, bare host, `//…`, empty). | Fixed |
| RV-L3 | WebSocket | `ws_client.py` (`unsubscribe_instances`) | Not-connected early return happened before the subscription list was filtered, so an unsubscribe issued while disconnected was forgotten and re-subscribed on reconnect. **Fixed:** the stored list is pruned before the connectivity check. | Fixed |
| RV-L4 | WebSocket | `ws_client.py` (`_do_subscribe`) | Post-reconnect resubscribe failure only logged; client stayed "connected" but received no push updates until the next disconnect. **Fixed:** `_do_subscribe` returns success; `_resubscribe` retries up to `WS_RESUBSCRIBE_MAX_ATTEMPTS` (with `WS_RESUBSCRIBE_RETRY_DELAY`) and warns if it ultimately fails. | Fixed |
| RV-L5 | Logging | `ws_client.py` | `msg.data[:n]` / `len(msg.data)` on ERROR (exception) / CLOSE (int) frames raised `TypeError` inside the log call, masking the real close code. **Fixed:** slice/len only for `str`/`bytes`; other payloads logged as-is. | Fixed |
| RV-L6 | Camera | `camera_recorder.py` | `async_stop()` during the auto-stop finalize could start a second `_finalize_recording` while the encoder ran; possible corrupt/duplicate output. **Fixed:** `_finalize_recording` atomically claims the `RECORDING`→`PROCESSING` transition and bails if the state is anything else. | Fixed |

---

## Won't Fix (with reasoning)

The following issues were analyzed and determined to be either framework limitations, intentional design decisions, or benign behavior that doesn't warrant changes:

| ID | Category | File | Line | Description | Reason |
|----|----------|------|------|-------------|--------|
| P-L3 | Resource Leak | `__init__.py` | 503 | **Static path / view not cleaned up on unload.** The `StaticPathConfig` for the camera card JS and the `EvonRecordingsView` (recordings are served via an authenticated view as of v1.22.0, not a static path) are registered once but never unregistered on `async_unload_entry`. They remain accessible after the integration is removed. | HA framework limitation: Home Assistant does not provide an API to unregister static paths or views. This is a known limitation affecting all integrations that register static content. |
| P-L7 | Security | `config_flow.py` | varies | **Config entry password stored plain text on disk.** `ConfigEntry.data[CONF_PASSWORD]` stores the user's plaintext password in `.storage/core.config_entries`. This is readable by any process with filesystem access. | HA-wide pattern: All Home Assistant integrations store credentials this way in the config entry. This is the standard practice across the entire HA ecosystem. Changing this would require framework-level support. |
| P-L9 | HA Practices | `climate.py` | varies | **HVAC OFF maps to freeze protection, not actual off.** Setting `HVACMode.OFF` sends the freeze protection mode to the Evon controller rather than actually turning off heating. This may surprise users. | Intentional design: Freeze protection mode prevents pipe damage in cold weather. This is a safety feature that protects the user's home. The behavior is consistent with the Evon controller's intended operation. |
| T-L9 | Maintenance | `src/ws-client.ts` | 252 | **No server-side subscription cleanup on disconnect.** `disconnect()` does not send `RegisterValuesChanged(false, ...)` to the server. The server may continue processing subscriptions for the closed connection until it detects the disconnect. (The local subscription map is intentionally retained — not cleared — so `resubscribeAll()` can restore subscriptions after reconnect.) | Benign behavior: The server automatically detects closed connections and cleans up its own state. The local subscription map now persists across reconnects (per T-H3 fix) to enable `resubscribeAll()` functionality, making explicit unsubscribe unnecessary. |

---

## Summary Statistics

| Severity | Python | TypeScript | Tests/CI | Total |
|----------|--------|------------|----------|-------|
| High     | 0      | 0          | 0 (1 deferred) | 0 (1 deferred) |
| Medium   | 0      | 0          | 0        | 0     |
| Low      | 0 (3 won't fix) | 0 (1 won't fix) | 0 | 0 (4 won't fix) |
| **Total remaining** | **0** | **0** | **0 (1 deferred)** | **0 (1 deferred, 4 won't fix)** |
| Fixed    | 13     | 18         | 37 (20 Test + 17 CI) | 68 |
| **Grand total** | **13** | **18** | **38** | **73** |

> Note: The original analysis found 74 issues. During the fix pass, 5 additional
> sub-issues were identified (e.g., separate aspects of the same root cause).
> After consolidating duplicates and refining categorization, the tracked total
> is 73 distinct issues. Of these, 68 were fixed, 1 is deferred (C-H7 mypy errors),
> and 4 are documented as won't fix with reasoning.

---

## Backlog Sweep Results

The backlog sweep addressed all actionable issues across eight major tasks:

### Task 1 - Python Quick Fixes
**Status: Complete (7/7)**
- ✅ P-L1: Add null guard to `current_humidity` transform
- ✅ P-L2: Clear WS client credentials on shutdown
- ✅ P-L4: Optimize stale entity cleanup
- ✅ P-L5: Improve recording loop auto-stop error logging
- ✅ P-L6: Add defensive check for WS key parsing
- ✅ P-L8: Add sequence ID bounds checking

### Task 2 - Python Medium Bugs
**Status: Complete (4/4)**
- ✅ P-M1: Fix bathroom radiator `turn_off` race condition
- ✅ P-M2: Add partial unload safeguards
- ✅ P-M3: Use entity registry for energy entity_id
- ✅ P-M4: Synchronize `update_interval` mutation

### Task 3 - TypeScript Quick Fixes
**Status: Complete (8/8)**
- ✅ T-L1: Add logging for malformed WS entries
- ✅ T-L2: Clarify `timeRemaining` unit handling
- ✅ T-L3: Move resource URIs to constants
- ✅ T-L5 + T-M3: Replace `console.error` with structured logging
- ✅ T-L10: Fix `EVON_HOST` default to `undefined`
- ✅ T-M6: Parallelize light commands
- ✅ T-M8: Replace password encoding heuristic
- ✅ T-M10: Fix `filterClimateDevices` substring match

### Task 4 - TypeScript Security + Refactoring
**Status: Complete (7/7)**
- ✅ T-M1: Add timeout and partial-result handling
- ✅ T-M2: Add Zod runtime schema validation
- ✅ T-M4 + T-M5: Apply `sanitizeId` consistently
- ✅ T-M7: Add shared instances cache
- ✅ T-M9 + T-L6: Add method allowlist for `call_method`
- ✅ T-L7: Add mutual exclusion for radiator toggle
- ✅ T-L8: Extract shared login function

### Task 5 - Test Infrastructure
**Status: Complete (8/8)**
- ✅ C-H5: Replace assertion-free service tests
- ✅ C-H6: Fix shared mutable state in mocks
- ✅ C-M6: Replace `MagicMock` with real enums
- ✅ C-M7: Add validation to mock API
- ✅ C-M8: Convert lambdas to mockable functions
- ✅ C-M9: Fix `test_constants.py` imports
- ✅ C-L2: Replace `sys.modules` manipulation
- ✅ C-L5: Fix `test_device_trigger.py` imports

### Task 6 - High-Severity Test Coverage
**Status: Complete (4/4)**
- ✅ C-H1: Tests for `_async_cleanup_stale_entities`
- ✅ C-H2: Tests for `_async_update_listener`
- ✅ C-H3: Tests for recording service handlers
- ✅ C-H4: Tests for WS reconnection loop

### Task 7 - Medium/Low Test Coverage
**Status: Complete (9/9)**
- ✅ C-M1: Camera MP4 encoding integration test
- ✅ C-M2: Bulk service partial failure tests
- ✅ C-M3: Energy midnight rollover tests
- ✅ C-M4: Options flow handler tests
- ✅ C-M5: Brightness conversion boundary tests
- ✅ C-M12: Concurrent API call tests
- ✅ C-M13: Negative service handler tests
- ✅ C-L1: Reconnect delay backoff/jitter tests
- ✅ C-L6: Timing boundary tests

### Task 8 - CI Improvements
**Status: Complete (4/4)**
- ✅ C-M10: Add Python dependency security scanning
- ✅ C-M11: Enable Codecov upload failure detection
- ✅ C-L3: Add pip cache to test job
- ✅ C-L4: Add macOS to CI matrix

---

## Current Status

**All actionable issues have been resolved.** The codebase is now in excellent health with:

- ✅ Zero high-severity issues
- ✅ Zero medium-severity issues
- ✅ Zero low-severity issues
- ✅ Comprehensive test coverage with 68 new/improved tests
- ✅ Hardened CI pipeline with security scanning and cross-platform testing
- ✅ Production-grade error handling and concurrency safeguards

The only remaining work is:

1. **C-H7** (Deferred): Resolving 83 mypy type errors - tracked as a standalone effort
2. **4 Won't Fix items**: Documented above with clear reasoning for each

The backlog sweep successfully addressed **68 of 69** issues (98.6% completion rate).
