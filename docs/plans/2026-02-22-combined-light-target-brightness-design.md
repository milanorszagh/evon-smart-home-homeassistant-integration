# Combined Light Target Brightness Design

## Problem

Combined lights (Evon relay + Govee LED strip) use template light entities where:
- Evon relay controls power (on/off)
- Govee LED handles brightness/color via MQTT

When the relay turns on, the Govee strip needs ~11 seconds to boot and connect to MQTT before it accepts brightness commands. Any brightness set during this boot window is lost.

Additionally, if a user changes brightness multiple times before the Govee is ready, only the latest value should be applied.

## Non-problem

The 0% brightness sometimes observed after turn-on is user behavior (dimmed to 0 before turning off), not a code bug. The Evon integration never sets brightness to 0 during turn_off, and `_last_brightness` only applies to dimmable Evon entities, not the Govee.

## Solution: Target Brightness with Pending Flag

### Architecture

Each combined light gets two helpers:
- `input_number.*_target_brightness` — stores the desired brightness (0-255)
- `input_boolean.*_brightness_pending` — flag indicating brightness needs applying

### Entities

| Combined Light | Govee Entity | Target Brightness Helper | Pending Flag Helper |
|---|---|---|---|
| Counter Ambient | `light.kitchen_counter_2` | `input_number.counter_ambient_target_brightness` | `input_boolean.counter_ambient_brightness_pending` |
| Bar Ambient | `light.bar_ambient` | `input_number.bar_ambient_target_brightness` | `input_boolean.bar_ambient_brightness_pending` |
| Kitchen Ambient | `light.kitchen_ambient` | `input_number.kitchen_ambient_target_brightness` | `input_boolean.kitchen_ambient_brightness_pending` |
| Living Room Wall | `light.living_room` | `input_number.living_room_wall_target_brightness` | `input_boolean.living_room_wall_brightness_pending` |

### Flow

```
User sets brightness -> set_level script fires
  -> Updates input_number (target)
  -> Sets input_boolean (pending = on)
  -> Tries to set Govee brightness immediately
     -> If Govee responds: input_boolean -> off (done)
     -> If Govee unresponsive: no-op, automation handles it

User changes brightness again (Govee still booting)
  -> input_number updated to new value
  -> pending flag stays on

Govee entity transitions from unavailable to on
  -> Automation fires
  -> Checks pending flag
  -> If on: reads input_number, sets Govee brightness, clears flag
```

### Modified set_level Scripts

Each `set_level` script changes from a simple pass-through to:

1. Store target brightness in `input_number`
2. Set pending flag via `input_boolean`
3. Attempt immediate `light.turn_on` on Govee with brightness

### Automation: Apply Pending Brightness

A single automation with one trigger per Govee entity, watching for `unavailable` -> `on` state transitions. On trigger:
1. Check if the corresponding pending flag is on
2. Read target brightness from input_number
3. Apply via `light.turn_on`
4. Clear pending flag

### Edge Cases

- **Turn off while pending**: Govee loses power, pending flag stays. Next turn-on with brightness overwrites the target. If turned on without brightness, Govee boots to its own last state and the pending flag applies the stored target.
- **Govee boots to `off` instead of `on`**: May need to also trigger on `unavailable` -> `off` transition. Needs verification on actual Govee boot behavior.
- **Color temp / RGB**: Same pattern can be extended later. Out of scope for now.

### Scope

- Brightness target/pending pattern for 4 combined lights
- Modified set_level scripts (4 scripts)
- One automation for applying pending brightness
- 8 helper entities (4 input_number + 4 input_boolean)
- No changes to the Evon custom integration code
