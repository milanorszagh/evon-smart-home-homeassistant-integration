"""Switch processor for Evon Smart Home coordinator."""

from __future__ import annotations

from collections.abc import Callable
import logging
from typing import Any

from ...const import EVON_CLASS_LIGHT

_LOGGER = logging.getLogger(__name__)


def process_switches(
    instance_details: dict[str, dict[str, Any]],
    instances: list[dict[str, Any]],
    get_room_name: Callable[[str], str],
) -> list[dict[str, Any]]:
    """Process controllable switch instances (relays).

    Args:
        instance_details: Pre-fetched instance details keyed by instance ID
        instances: List of all device instances
        get_room_name: Function to get room name from group ID

    Returns:
        List of processed switch data dictionaries
    """
    switches = []
    for instance in instances:
        # Only process SmartCOM.Light.Light (controllable relays)
        if instance.get("ClassName") != EVON_CLASS_LIGHT:
            continue
        if not instance.get("Name"):
            continue

        instance_id = instance.get("ID", "")
        details = instance_details.get(instance_id)
        if details is None:
            _LOGGER.warning("No details available for switch %s", instance_id)
            continue

        switches.append(
            {
                "id": instance_id,
                "name": instance.get("Name"),
                "room_name": get_room_name(instance.get("Group", "")),
                "is_on": details.get("IsOn", False),
            }
        )
    return switches
