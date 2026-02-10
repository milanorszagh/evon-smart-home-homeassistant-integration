"""Blind processor for Evon Smart Home coordinator."""

from __future__ import annotations

from collections.abc import Callable
import logging
from typing import Any

from ...const import EVON_CLASS_BLIND, EVON_CLASS_BLIND_GROUP

_LOGGER = logging.getLogger(__name__)

# Blind classes to process
BLIND_CLASSES = {EVON_CLASS_BLIND, EVON_CLASS_BLIND_GROUP, "Base.bBlind", "Base.ehBlind"}


def process_blinds(
    instance_details: dict[str, dict[str, Any]],
    instances: list[dict[str, Any]],
    get_room_name: Callable[[str], str],
) -> list[dict[str, Any]]:
    """Process blind instances.

    Args:
        instance_details: Pre-fetched instance details keyed by instance ID
        instances: List of all device instances
        get_room_name: Function to get room name from group ID

    Returns:
        List of processed blind data dictionaries
    """
    blinds = []
    for instance in instances:
        if instance.get("ClassName") not in BLIND_CLASSES:
            continue
        if not instance.get("Name"):
            continue

        instance_id = instance.get("ID", "")
        class_name = instance.get("ClassName", "")
        details = instance_details.get(instance_id)
        if details is None:
            _LOGGER.warning("No details available for blind %s", instance_id)
            continue

        blinds.append(
            {
                "id": instance_id,
                "name": instance.get("Name"),
                "room_name": get_room_name(instance.get("Group", "")),
                "position": details.get("Position", 0),
                "angle": details.get("Angle", 0),
                "is_moving": details.get("IsMoving", False),
                "is_group": class_name == EVON_CLASS_BLIND_GROUP,
            }
        )
    return blinds
