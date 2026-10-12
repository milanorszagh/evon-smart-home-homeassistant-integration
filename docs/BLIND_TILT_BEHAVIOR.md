# Evon Blind Tilt Behavior

## Summary

Evon blinds have a hardware characteristic where the slat/tilt orientation depends on the **last movement direction** of the blind. This document explains the behavior, our findings, and the implementation decisions made for the Home Assistant integration.

## The Problem

When controlling blind tilt (slat angle) via the Evon API:

| Last Movement | Tilt 0 | Tilt 100 |
|---------------|--------|----------|
| **DOWN** | Slats OPEN (horizontal) | Slats CLOSED (blocking light) |
| **UP** | Slats CLOSED | Slats OPEN |

This means the same tilt value produces **opposite physical results** depending on whether the blind last moved up or down.

## Technical Details

### API Method

The Evon API provides two methods for blind/tilt control:

**HTTP (SetAngle)**:
- **Method**: `SetAngle`
- **Parameter**: Integer value 0-100
- **Endpoint**: `POST /api/instances/{blind_id}/SetAngle` with body `[angle]`

**WebSocket (preferred)**:
- **Method**: `CallMethod MoveToPosition([angle, position])`
- This is the preferred method as it allows setting tilt angle and position in a single call
- Note: `SetValue Position` does **NOT** work — the hardware does not move

There are no dedicated "open tilt" or "close tilt" commands that would handle direction automatically.

### Tested Ranges

We tested the valid range for the `SetAngle` method:

| Input Value | Actual Result |
|-------------|---------------|
| -50 | Clamped to 0 |
| 0 | 0 |
| 50 | 50 |
| 100 | 100 |
| 150 | Clamped to 100 |

**Conclusion**: Valid tilt range is **0-100**. Values outside this range are silently clamped.

### Direction Detection

We investigated whether the Evon API exposes any property to detect the last movement direction:

- `IsLeftOpening`: Does not change based on movement direction
- `LastState`: Does not reliably indicate direction
- `IsClosing` / `IsOpening`: Only indicates current movement, not last direction

**Conclusion**: There is no reliable way to detect the last movement direction from the API.

## Solutions Considered

### Option 1: Normalization Approach (Rejected)

**Concept**: Before setting tilt, automatically move the blind down by 1-2% to ensure consistent orientation, then set the tilt value.

**Implementation**:
```python
async def _normalize_tilt_direction(self):
    current_position = get_current_position()
    if current_position < 98:
        await set_blind_position(current_position + 2)
        await asyncio.sleep(1.5)  # Wait for movement
```

**Why Rejected**:
1. Large blinds (e.g., 3 meters) take significant time to move
2. The 1.5+ second delay negatively impacts user experience
3. Causes unexpected position changes when user only wants to adjust tilt
4. Position drift over multiple tilt adjustments

### Option 2: Track Direction in HA (Rejected)

**Concept**: Store the last movement direction in Home Assistant and invert tilt values when needed.

**Why Rejected**:
1. The API exposes no last-direction property, and the WebSocket `ValuesChanged` events the integration receives for blinds (since v1.13.0; `ws_mappings.py` subscribes to `Position` and `Angle`, `cover.py` consumes them) carry position and angle only — direction would have to be inferred from position deltas
2. Users can control blinds via hardware switches or Evon app
3. An inferred direction would drift after hardware-switch moves, causing incorrect tilt behavior
4. No reliable way to detect the *direction* of external changes

### Option 3: Dedicated Tilt Commands (Not Available)

**Concept**: Use Evon API methods that handle direction automatically.

**Investigation**: We tested various potential method names:
- `OpenTilt`, `CloseTilt` - 404 Not Found
- `TiltOpen`, `TiltClose` - 404 Not Found
- `OpenSlat`, `CloseSlat` - 404 Not Found
- Various other combinations - 404 Not Found

**Conclusion**: No such methods exist in the Evon API.

### Option 4: Match Evon App Behavior (Implemented)

**Concept**: Use the same convention as the Evon app without any workarounds.

**Implementation**:
- HA Tilt 0 = slats CLOSED (blocking light), Tilt 100 = slats OPEN (horizontal)
- Evon angle 0 = open, 100 = closed (inverted from HA convention)
- Values are inverted when sending to the API: `evon_angle = 100 - ha_tilt`
- Optimistic state updates provide instant UI feedback

**Rationale**:
1. Matches user expectations from the Evon app
2. No delays or unexpected side effects
3. Same limitations as official Evon app - users are already familiar with this
4. Simple and maintainable implementation

## Current Implementation

The Home Assistant integration uses **Option 4** (match Evon app behavior). The only tilt-specific logic is the inversion between the HA and Evon conventions, in `custom_components/evon/cover.py` (`async_open_cover_tilt`, `async_close_cover_tilt`, `async_set_cover_tilt_position`):

```python
# async_open_cover_tilt:  HA tilt 100 = open (horizontal), Evon angle 0 = open
await self._api.set_blind_tilt(self._instance_id, 0)

# async_close_cover_tilt: HA tilt 0 = closed (blocking), Evon angle 100 = closed
await self._api.set_blind_tilt(self._instance_id, 100)

# async_set_cover_tilt_position: convert HA (0=closed, 100=open) → Evon (0=open, 100=closed)
ha_tilt = max(0, min(100, int(kwargs[ATTR_TILT_POSITION])))
evon_angle = 100 - ha_tilt
await self._api.set_blind_tilt(self._instance_id, evon_angle)
```

Everything around those calls — the optimistic tilt value, the WS-liveness snapshot captured *before* the command await (`recheck_snapshot = self._recheck_snapshot()`) and the 5 s post-command recheck it is passed to (`_schedule_post_command_recheck(recheck_snapshot)`) — is the shared entity plumbing described under "Optimistic Updates Pattern" in `DEVELOPMENT.md`; read `cover.py` for the current code rather than a copy here.

## User Impact

Users should be aware that:

1. Tilt values (0=closed/blocking light, 100=open/horizontal) are correct when the blind **last moved down**
2. If the blind last moved up (via any method), tilt will appear **inverted**
3. To "reset" tilt orientation, move the blind down slightly before adjusting tilt
4. This is the same behavior as the official Evon app

## Future Considerations

If Evon releases a firmware update or API change that addresses this issue:

1. Check for new API methods: `OpenTilt`, `CloseTilt`, or similar
2. Check for a direction indicator property in the blind state
3. Check for an option to set tilt with explicit orientation

## Test Procedure

To verify this behavior on any Evon blind:

1. Move blind DOWN to any position
2. Set tilt to 0 - observe slats are OPEN
3. Set tilt to 100 - observe slats are CLOSED
4. Move blind UP slightly
5. Set tilt to 0 - observe slats are now CLOSED (inverted!)
6. Set tilt to 100 - observe slats are now OPEN (inverted!)

## Date of Investigation

- **Date**: January 2026
- **Evon System**: Tested on production Evon Smart Home system
- **Blind Type**: 3-meter blinds with tilt capability
- **API Version**: Current as of testing date
