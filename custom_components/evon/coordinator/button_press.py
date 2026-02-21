"""Button press type detection for Evon physical buttons (Tasters).

Extracts the press detection state machine into a standalone class that can be
tested independently without HA framework dependencies.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any, Protocol

from ..const import BUTTON_LONG_PRESS_THRESHOLD, DEFAULT_BUTTON_DOUBLE_CLICK_DELAY

if TYPE_CHECKING:
    from asyncio import TimerHandle

_LOGGER = logging.getLogger(__name__)


class ButtonPressCallback(Protocol):
    """Protocol for the callback invoked when a press type is determined."""

    def __call__(self, instance_id: str, entity_data: dict[str, Any], press_type: str) -> None: ...


class TimerScheduler(Protocol):
    """Protocol for scheduling a delayed callback (wraps loop.call_later)."""

    def __call__(self, delay: float, callback: Any, *args: Any) -> TimerHandle: ...


class TimeoutCallback(Protocol):
    """Protocol for the timer-fired timeout callback."""

    def __call__(self, instance_id: str) -> None: ...


class ButtonPressDetector:
    """Detects single, double, and long press from raw IsOn WS events.

    The Evon controller sends 4 different patterns for double-press:
    - True, True, False (coalesced release — second True without intervening False)
    - True, False, False (coalesced press — second False without intervening True)
    - True, False, True, False (standard 4-event — rare)
    - False, True, False (swallowed first True — controller drops the first press-down,
      delivers only the first release + second press-release)

    Press types:
    - single_press: one press+release, no second press within double_click_delay
    - double_press: two presses within double_click_delay
    - long_press: held longer than BUTTON_LONG_PRESS_THRESHOLD
    """

    def __init__(
        self,
        on_press: ButtonPressCallback,
        schedule_timer: TimerScheduler,
        on_timeout: TimeoutCallback | None = None,
        double_click_delay: float = DEFAULT_BUTTON_DOUBLE_CLICK_DELAY,
    ) -> None:
        """Initialize the detector.

        Args:
            on_press: Callback fired when a press type is determined.
            schedule_timer: Function to schedule a delayed callback (e.g. loop.call_later).
            on_timeout: Callback fired when the timer expires. If provided, it is
                responsible for calling ``timeout()`` with the current entity_data
                (e.g. after a CoW re-lookup). If None, timer expiry is a no-op and
                the caller must invoke ``timeout()`` externally.
            double_click_delay: Seconds to wait after release before firing single press.
        """
        self._on_press = on_press
        self._schedule_timer = schedule_timer
        self._on_timeout = on_timeout
        self._double_click_delay = double_click_delay
        self._state: dict[str, dict[str, Any]] = {}

    @property
    def state(self) -> dict[str, dict[str, Any]]:
        """Expose internal state for shutdown cleanup."""
        return self._state

    def handle_event(
        self,
        instance_id: str,
        entity_data: dict[str, Any],
        is_on: bool,
    ) -> None:
        """Process a raw IsOn WS event for a button.

        Called for EVERY WS event on button entities (not just state changes),
        because the Evon controller may coalesce events.

        Args:
            instance_id: The button instance ID.
            entity_data: The entity data dict (passed to callback on fire).
            is_on: Current IsOn value (True=pressed, False=released).
        """
        now = time.monotonic()

        if instance_id not in self._state:
            self._state[instance_id] = {
                "press_start": None,
                "release_count": 0,
                "pending_timer": None,
            }

        state = self._state[instance_id]

        if is_on:
            # Button pressed — record start time.
            # If already pressed (press_start set), the Evon controller coalesced
            # the first release — treat the previous press as a completed short press.
            # This handles the True, True, False WS pattern for double-press.
            # Note: this assumes True, True only occurs for rapid presses (confirmed
            # by hardware testing — the controller never sends True, True for a
            # long-hold followed by another press).
            if state["press_start"] is not None:
                state["release_count"] += 1
                if state.get("pending_timer") is not None:
                    state["pending_timer"].cancel()
                    state["pending_timer"] = None
            state["press_start"] = now
        else:
            # Button released — determine press type
            press_start = state.get("press_start")
            if press_start is None:
                # No matching press — Evon controller may coalesce rapid presses.
                # Count this as an additional release for double-press detection.
                # This handles two WS patterns:
                # - True, False, False (coalesced press — pending_timer exists from
                #   the first release)
                # - False, True, False (swallowed first True — no pending_timer,
                #   controller dropped the first press-down and only sent the release)
                state["release_count"] += 1
                if state.get("pending_timer") is not None:
                    state["pending_timer"].cancel()
                state["pending_timer"] = self._schedule_timer(
                    self._double_click_delay,
                    self._handle_timeout,
                    instance_id,
                )
                return

            hold_duration = now - press_start
            state["press_start"] = None

            if hold_duration >= BUTTON_LONG_PRESS_THRESHOLD:
                # Long press — fire immediately
                if state.get("pending_timer") is not None:
                    state["pending_timer"].cancel()
                    state["pending_timer"] = None
                state["release_count"] = 0
                self._on_press(instance_id, entity_data, "long_press")
            else:
                # Short press — increment count, schedule delayed check
                state["release_count"] += 1

                # Cancel any existing pending timer
                if state.get("pending_timer") is not None:
                    state["pending_timer"].cancel()

                # Schedule delayed check for single vs double press
                state["pending_timer"] = self._schedule_timer(
                    self._double_click_delay,
                    self._handle_timeout,
                    instance_id,
                )

    def timeout(self, instance_id: str, entity_data: dict[str, Any]) -> None:
        """Handle button press timeout — fire single or double press event.

        Called after double_click_delay expires with no further presses.
        The caller must provide the current entity_data (re-looked up for CoW).

        Args:
            instance_id: The button instance ID.
            entity_data: Current entity data (re-looked up by caller for CoW safety).
        """
        state = self._state.get(instance_id)
        if state is None:
            return

        release_count = state.get("release_count", 0)
        state["release_count"] = 0
        state["pending_timer"] = None

        if release_count >= 2:  # 3+ clicks also treated as double press
            self._on_press(instance_id, entity_data, "double_press")
        elif release_count == 1:
            self._on_press(instance_id, entity_data, "single_press")

    def _handle_timeout(self, instance_id: str) -> None:
        """Internal timer callback — delegates to on_timeout if provided."""
        if self._on_timeout is not None:
            self._on_timeout(instance_id)

    def cancel_all_timers(self) -> None:
        """Cancel all pending timers and clear state."""
        for state in self._state.values():
            timer = state.get("pending_timer")
            if timer is not None:
                timer.cancel()
        self._state.clear()
