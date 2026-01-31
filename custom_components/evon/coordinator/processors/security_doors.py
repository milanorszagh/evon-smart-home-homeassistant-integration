"""Security door processor for Evon Smart Home coordinator."""

from __future__ import annotations

from collections.abc import Callable
import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ...api import EvonApi

from ...api import EvonApiError
from ...const import EVON_CLASS_SECURITY_DOOR

_LOGGER = logging.getLogger(__name__)


async def process_security_doors(
    api: EvonApi,
    instances: list[dict[str, Any]],
    get_room_name: Callable[[str], str],
) -> list[dict[str, Any]]:
    """Process security door instances.

    Args:
        api: The Evon API client
        instances: List of all device instances
        get_room_name: Function to get room name from group ID

    Returns:
        List of processed security door data dictionaries
    """
    security_doors = []
    for instance in instances:
        if instance.get("ClassName") != EVON_CLASS_SECURITY_DOOR:
            continue
        if not instance.get("Name"):
            continue

        instance_id = instance.get("ID", "")
        try:
            details = await api.get_instance(instance_id)
            security_doors.append(
                {
                    "id": instance_id,
                    "name": instance.get("Name"),
                    "room_name": get_room_name(instance.get("Group", "")),
                    "is_open": details.get("IsOpen", False) or details.get("DoorIsOpen", False),
                    "call_in_progress": details.get("CallInProgress", False),
                }
            )
        except EvonApiError:
            _LOGGER.warning("Failed to get details for security door %s", instance_id)
    return security_doors
