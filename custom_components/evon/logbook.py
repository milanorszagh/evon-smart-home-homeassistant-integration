"""Logbook support for Evon Smart Home integration."""

from __future__ import annotations

from collections.abc import Callable

from homeassistant.components.logbook import LOGBOOK_ENTRY_MESSAGE, LOGBOOK_ENTRY_NAME
from homeassistant.core import Event, HomeAssistant, callback

from .const import DOMAIN, EVENT_DOUBLE_CLICK, EVENT_LONG_PRESS, EVENT_SINGLE_CLICK

EVENT_EVON = f"{DOMAIN}_event"

EVENT_TYPE_TO_MESSAGE = {
    EVENT_SINGLE_CLICK: "was clicked",
    EVENT_DOUBLE_CLICK: "was double-clicked",
    EVENT_LONG_PRESS: "was long-pressed",
}


@callback
def async_describe_events(
    hass: HomeAssistant,
    async_describe_event: Callable[[str, str, Callable[[Event], dict[str, str]]], None],
) -> None:
    """Describe logbook events."""

    @callback
    def async_describe_evon_event(event: Event) -> dict[str, str]:
        """Describe an Evon event in the logbook."""
        data = event.data
        device_name = data.get("device_name", "Unknown device")
        event_type = data.get("event_type", "unknown")

        message = EVENT_TYPE_TO_MESSAGE.get(event_type, f"triggered {event_type}")

        return {
            LOGBOOK_ENTRY_NAME: device_name,
            LOGBOOK_ENTRY_MESSAGE: message,
        }

    async_describe_event(DOMAIN, EVENT_EVON, async_describe_evon_event)
