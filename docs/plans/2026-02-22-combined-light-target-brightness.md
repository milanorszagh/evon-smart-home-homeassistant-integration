# Combined Light Target Brightness Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make brightness commands survive Govee LED boot delay (~11s) by storing a target brightness and applying it when the Govee becomes responsive.

**Architecture:** Each combined light gets an `input_number` (target brightness) and `input_boolean` (pending flag). The `set_level` scripts store the target and attempt immediate set. A single automation watches for Govee entities becoming available and applies any pending brightness.

**Tech Stack:** Home Assistant YAML configuration (helpers, scripts, automations). Changes are made on the HA instance at `192.168.1.2` via SSH (`ssh root@192.168.1.2`) or HA MCP tools. Config files live at `/config/` on the instance.

**Reference:** Design doc at `docs/plans/2026-02-22-combined-light-target-brightness-design.md`

---

### Task 1: Verify Govee Boot State Transition

Before implementing, we need to know what state the Govee entities transition through on boot. This determines the automation trigger.

**Step 1: Check current Govee entity states via MCP**

Use the HA MCP `lights_control` tool with action `list` to see current states of the Govee entities:
- `light.kitchen_counter_2`
- `light.bar_ambient`
- `light.kitchen_ambient`
- `light.living_room`

Document their current state for reference.

**Step 2: Check Govee entity history for boot transitions**

Use the HA MCP `get_history` tool on one Govee entity (e.g., `light.kitchen_counter_2`) to see recent state transitions. Look for patterns like `unavailable` -> `off` -> `on` vs `unavailable` -> `on`.

**Step 3: Document findings**

Note the transition pattern. If the Govee goes `unavailable` -> `off` first, the automation trigger needs to include both `unavailable` -> `on` and `off` -> `on` (or possibly just watch for `from: unavailable`).

---

### Task 2: Create Input Number Helpers (Target Brightness)

**Step 1: SSH into HA and check existing helpers config**

```bash
ssh root@192.168.1.2 "cat /config/configuration.yaml | grep -A5 input_number"
```

If `input_number:` section exists, we append. If not, we create it. Alternatively, check if helpers are UI-managed (in `.storage/`).

**Step 2: Create 4 input_number helpers**

Add to `/config/configuration.yaml` on the HA instance (or create via HA UI Settings -> Devices & Services -> Helpers):

```yaml
input_number:
  counter_ambient_target_brightness:
    name: "Counter Ambient Target Brightness"
    min: 0
    max: 255
    step: 1
    mode: box
  bar_ambient_target_brightness:
    name: "Bar Ambient Target Brightness"
    min: 0
    max: 255
    step: 1
    mode: box
  kitchen_ambient_target_brightness:
    name: "Kitchen Ambient Target Brightness"
    min: 0
    max: 255
    step: 1
    mode: box
  living_room_wall_target_brightness:
    name: "Living Room Wall Target Brightness"
    min: 0
    max: 255
    step: 1
    mode: box
```

**Step 3: Verify helpers exist**

After HA restart/reload, confirm entities exist via MCP or SSH:
```bash
ssh root@192.168.1.2 "ha core restart"
```

---

### Task 3: Create Input Boolean Helpers (Pending Flags)

**Step 1: Create 4 input_boolean helpers**

Add to `/config/configuration.yaml` on the HA instance:

```yaml
input_boolean:
  counter_ambient_brightness_pending:
    name: "Counter Ambient Brightness Pending"
  bar_ambient_brightness_pending:
    name: "Bar Ambient Brightness Pending"
  kitchen_ambient_brightness_pending:
    name: "Kitchen Ambient Brightness Pending"
  living_room_wall_brightness_pending:
    name: "Living Room Wall Brightness Pending"
```

**Step 2: Reload or restart HA**

```bash
ssh root@192.168.1.2 "ha core restart"
```

**Step 3: Verify all 8 helpers exist**

Check that all `input_number.*_target_brightness` and `input_boolean.*_brightness_pending` entities are available.

---

### Task 4: Modify set_level Scripts

**Step 1: Fetch current scripts from HA**

```bash
ssh root@192.168.1.2 "cat /config/scripts.yaml"
```

Identify the 4 existing set_level scripts:
- `counter_ambient_set_level`
- `bar_ambient_set_level`
- `kitchen_ambient_set_level`
- `living_room_wall_set_level`

**Step 2: Modify counter_ambient_set_level**

Replace the simple pass-through with:

```yaml
counter_ambient_set_level:
  alias: "Counter Ambient Set Level"
  mode: restart
  fields:
    brightness:
      description: "Brightness level (0-255)"
  sequence:
    - action: input_number.set_value
      target:
        entity_id: input_number.counter_ambient_target_brightness
      data:
        value: "{{ brightness }}"
    - action: input_boolean.turn_on
      target:
        entity_id: input_boolean.counter_ambient_brightness_pending
    - action: light.turn_on
      target:
        entity_id: light.kitchen_counter_2
      data:
        brightness: "{{ brightness }}"
```

Note: `mode: restart` ensures that if called again while running, it cancels the previous run and starts fresh — this supports the "last write wins" behavior.

**Step 3: Modify bar_ambient_set_level**

```yaml
bar_ambient_set_level:
  alias: "Bar Ambient Set Level"
  mode: restart
  fields:
    brightness:
      description: "Brightness level (0-255)"
  sequence:
    - action: input_number.set_value
      target:
        entity_id: input_number.bar_ambient_target_brightness
      data:
        value: "{{ brightness }}"
    - action: input_boolean.turn_on
      target:
        entity_id: input_boolean.bar_ambient_brightness_pending
    - action: light.turn_on
      target:
        entity_id: light.bar_ambient
      data:
        brightness: "{{ brightness }}"
```

**Step 4: Modify kitchen_ambient_set_level**

```yaml
kitchen_ambient_set_level:
  alias: "Kitchen Ambient Set Level"
  mode: restart
  fields:
    brightness:
      description: "Brightness level (0-255)"
  sequence:
    - action: input_number.set_value
      target:
        entity_id: input_number.kitchen_ambient_target_brightness
      data:
        value: "{{ brightness }}"
    - action: input_boolean.turn_on
      target:
        entity_id: input_boolean.kitchen_ambient_brightness_pending
    - action: light.turn_on
      target:
        entity_id: light.kitchen_ambient
      data:
        brightness: "{{ brightness }}"
```

**Step 5: Modify living_room_wall_set_level**

```yaml
living_room_wall_set_level:
  alias: "Living Room Wall Set Level"
  mode: restart
  fields:
    brightness:
      description: "Brightness level (0-255)"
  sequence:
    - action: input_number.set_value
      target:
        entity_id: input_number.living_room_wall_target_brightness
      data:
        value: "{{ brightness }}"
    - action: input_boolean.turn_on
      target:
        entity_id: input_boolean.living_room_wall_brightness_pending
    - action: light.turn_on
      target:
        entity_id: light.living_room
      data:
        brightness: "{{ brightness }}"
```

**Step 6: Upload modified scripts and reload**

```bash
# Upload the modified scripts.yaml
scp scripts.yaml root@192.168.1.2:/config/scripts.yaml
# Or edit directly via SSH:
ssh root@192.168.1.2 "vi /config/scripts.yaml"
# Reload scripts (no full restart needed):
ssh root@192.168.1.2 "ha core restart"
```

**Step 7: Verify scripts work**

Test by calling one script manually (e.g., via HA Developer Tools -> Services):
- Call `script.counter_ambient_set_level` with `brightness: 128`
- Verify `input_number.counter_ambient_target_brightness` is set to 128
- Verify `input_boolean.counter_ambient_brightness_pending` is on

---

### Task 5: Create Automation for Applying Pending Brightness

**Step 1: Determine trigger states from Task 1 findings**

Based on the Govee boot state transition findings from Task 1, set the appropriate `from` and `to` states. The example below assumes `unavailable` -> `on`. Adjust if Govee goes through `off` first.

**Step 2: Create the automation**

Add to `/config/automations.yaml` on the HA instance:

```yaml
- id: apply_pending_brightness_on_govee_ready
  alias: "Apply Pending Brightness When Govee Ready"
  description: "Watches for Govee LEDs becoming available and applies any pending target brightness"
  mode: parallel
  max: 4
  trigger:
    - platform: state
      entity_id: light.kitchen_counter_2
      from: "unavailable"
      id: counter_ambient
    - platform: state
      entity_id: light.bar_ambient
      from: "unavailable"
      id: bar_ambient
    - platform: state
      entity_id: light.kitchen_ambient
      from: "unavailable"
      id: kitchen_ambient
    - platform: state
      entity_id: light.living_room
      from: "unavailable"
      id: living_room_wall
  action:
    - choose:
        - conditions:
            - condition: trigger
              id: counter_ambient
            - condition: state
              entity_id: input_boolean.counter_ambient_brightness_pending
              state: "on"
          sequence:
            - action: light.turn_on
              target:
                entity_id: light.kitchen_counter_2
              data:
                brightness: "{{ states('input_number.counter_ambient_target_brightness') | int }}"
            - action: input_boolean.turn_off
              target:
                entity_id: input_boolean.counter_ambient_brightness_pending
        - conditions:
            - condition: trigger
              id: bar_ambient
            - condition: state
              entity_id: input_boolean.bar_ambient_brightness_pending
              state: "on"
          sequence:
            - action: light.turn_on
              target:
                entity_id: light.bar_ambient
              data:
                brightness: "{{ states('input_number.bar_ambient_target_brightness') | int }}"
            - action: input_boolean.turn_off
              target:
                entity_id: input_boolean.bar_ambient_brightness_pending
        - conditions:
            - condition: trigger
              id: kitchen_ambient
            - condition: state
              entity_id: input_boolean.kitchen_ambient_brightness_pending
              state: "on"
          sequence:
            - action: light.turn_on
              target:
                entity_id: light.kitchen_ambient
              data:
                brightness: "{{ states('input_number.kitchen_ambient_target_brightness') | int }}"
            - action: input_boolean.turn_off
              target:
                entity_id: input_boolean.kitchen_ambient_brightness_pending
        - conditions:
            - condition: trigger
              id: living_room_wall
            - condition: state
              entity_id: input_boolean.living_room_wall_brightness_pending
              state: "on"
          sequence:
            - action: light.turn_on
              target:
                entity_id: light.living_room
              data:
                brightness: "{{ states('input_number.living_room_wall_target_brightness') | int }}"
            - action: input_boolean.turn_off
              target:
                entity_id: input_boolean.living_room_wall_brightness_pending
```

Key design choices:
- `from: "unavailable"` (no `to` specified) — triggers regardless of whether Govee boots to `on` or `off`
- `mode: parallel`, `max: 4` — handles multiple Govee strips booting simultaneously
- Trigger `id` used in `choose` to route to correct entity pair
- Pending flag checked as condition — no action if no brightness is pending

**Step 3: Upload and reload automations**

```bash
ssh root@192.168.1.2 "ha core restart"
```

**Step 4: Verify automation exists**

Use HA MCP `automation` tool with action `list` to confirm the automation appears.

---

### Task 6: End-to-End Testing

**Step 1: Test happy path — brightness set while Govee is off**

1. Turn off a combined light (e.g., Counter Ambient) via MCP — this powers off relay and Govee
2. Wait for Govee entity to go `unavailable`
3. Turn on Counter Ambient with brightness 128 (via `light.turn_on` with brightness)
4. Verify `input_number.counter_ambient_target_brightness` = 128
5. Verify `input_boolean.counter_ambient_brightness_pending` = on
6. Wait for Govee to boot (~11s) and transition from `unavailable`
7. Verify automation fires and sets brightness to 128
8. Verify `input_boolean.counter_ambient_brightness_pending` = off

**Step 2: Test last-write-wins — brightness updated before Govee ready**

1. Turn off Counter Ambient, wait for Govee `unavailable`
2. Turn on with brightness 100
3. Immediately change brightness to 200 (before Govee boots)
4. Verify `input_number` = 200 (not 100)
5. Wait for Govee to boot
6. Verify brightness is set to 200

**Step 3: Test normal operation — brightness set while Govee already on**

1. With Counter Ambient already on and Govee responsive
2. Set brightness to 180
3. Verify brightness changes immediately (no delay)
4. Verify pending flag clears (or stays irrelevant since Govee handled it)

**Step 4: Commit plan as done**

```bash
git add docs/plans/2026-02-22-combined-light-target-brightness.md
git commit -m "docs: add combined light target brightness implementation plan"
```
