"""Button event processor for Evon Smart Home coordinator."""

from __future__ import annotations

from collections.abc import Callable
import logging
from typing import Any

from ...const import EVON_CLASS_PHYSICAL_BUTTON

_LOGGER = logging.getLogger(__name__)


def process_button_events(
    instances: list[dict[str, Any]],
    get_room_name: Callable[[str], str],
) -> list[dict[str, Any]]:
    """Process physical button (Taster) instances for event entities.

    Unlike other processors, this does NOT use instance_details because
    buttons are WebSocket-only — their state comes exclusively from WS
    ValuesChanged events, not HTTP polling.

    Args:
        instances: List of all device instances from /instances API
        get_room_name: Function to get room name from group ID

    Returns:
        List of button event data dictionaries
    """
    buttons = []
    for instance in instances:
        if instance.get("ClassName") != EVON_CLASS_PHYSICAL_BUTTON:
            continue
        if not instance.get("ID") or not instance.get("Name"):
            continue

        buttons.append(
            {
                "id": instance.get("ID", ""),
                "name": instance.get("Name"),
                "room_name": get_room_name(instance.get("Group", "")),
                "is_on": False,
                "last_event_type": None,
                "last_event_id": 0,
            }
        )
    return buttons
