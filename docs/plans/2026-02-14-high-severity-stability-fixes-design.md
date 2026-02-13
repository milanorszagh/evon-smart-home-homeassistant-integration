# High-Severity Stability Fixes

Date: 2026-02-14
Scope: 6 high-severity issues from CODE_ANALYSIS_BACKLOG.md (P-H1, P-H2, T-H1, T-H2, T-H3, T-H4)
Bonus: T-L4 (graceful shutdown) since we're already modifying the WS client

---

## Python Fixes

### P-H1: Batch `statistics_during_period` calls

**Problem:** Each smart meter triggers a separate `async_add_executor_job` call to the synchronous recorder API. With N meters, that's N sequential blocking executor calls per poll cycle, starving the event loop.

**Solution:** Refactor `_calculate_energy_today_and_month` to collect all smart meter entity IDs upfront and make a single batched `statistics_during_period` call. The HA recorder API already accepts a list of entity IDs. Distribute results after the single call.

**Files:** `coordinator/__init__.py`

### P-H2: Copy-on-write for WS data updates

**Problem:** `_handle_ws_values_changed` mutates entity dicts in-place. A concurrent HTTP poll can read partially-updated entity data.

**Solution:**
1. Create a shallow copy of the entity dict before applying WS changes
2. Apply all WS property updates to the copy
3. Atomically replace the entity in the list
4. Use `_data_index` for O(1) entity lookup instead of linear search

The existing race detection (snapshot checks) stays as defense-in-depth.

**Files:** `coordinator/__init__.py`

---

## TypeScript Fixes

### T-H1: Silent server death

**Problem:** `main().catch(console.error)` allows silent process death.

**Solution:** Add `process.exit(1)` in the catch handler.

**Files:** `src/index.ts`

### T-H2, T-H3, T-H4: WS client reliability

These three issues share a root cause: the WS client lacks a proper connection lifecycle.

**T-H2 (sequenceId overflow):** Reset `sequenceId` to 1 on reconnect.

**T-H3 (lost subscriptions):** After successful reconnect, replay all entries from the `subscriptions` Map back to the server. Add a private `resubscribeAll()` method called after `performConnect()` succeeds.

**T-H4 (disconnect during connect):** Add an `AbortController` pattern so `disconnect()` can cancel an in-progress `performConnect()`. When disconnect is called during connect, abort immediately and reject the `connectPromise`.

**Design choice:** Clean manual reconnect only -- the caller manages when to reconnect. No auto-reconnect loop inside the WS client.

**Files:** `src/ws-client.ts`

### T-L4 (bonus): Graceful shutdown

**Solution:** Add `SIGTERM`/`SIGINT` handlers in `index.ts` that disconnect the WS client before exiting.

**Files:** `src/index.ts`

---

## Testing

| Fix | Test Strategy |
|-----|---------------|
| P-H1 | Mock `statistics_during_period`, verify single batched call with multiple meter entity IDs |
| P-H2 | Verify entity dict reference changes after WS update (copy-on-write), not just values |
| T-H1 | Verify process exits on main() rejection |
| T-H2 | Test that sequenceId resets to 1 after reconnect |
| T-H3 | Test that subscriptions are re-registered after reconnect |
| T-H4 | Test disconnect during connect aborts cleanly |

---

## Out of Scope

- Auto-reconnect logic (callers already handle this)
- WS client refactoring beyond what's needed for these fixes
- Other backlog items (medium/low severity)
