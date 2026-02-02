"""Blind processor for Evon Smart Home coordinator."""

from __future__ import annotations

from collections.abc import Callable
import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ...api import EvonApi

from ...api import EvonApiError
from ...const import EVON_CLASS_BLIND, EVON_CLASS_BLIND_GROUP

_LOGGER = logging.getLogger(__name__)

# Blind classes to process
BLIND_CLASSES = {EVON_CLASS_BLIND, EVON_CLASS_BLIND_GROUP, "Base.bBlind", "Base.ehBlind"}


async def process_blinds(
    api: EvonApi,
    instances: list[dict[str, Any]],
    get_room_name: Callable[[str], str],
) -> list[dict[str, Any]]:
    """Process blind instances.

    Args:
        api: The Evon API client
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
        try:
            details = await api.get_instance(instance_id)
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
        except EvonApiError:
            _LOGGER.warning("Failed to get details for blind %s", instance_id)
    return blinds
