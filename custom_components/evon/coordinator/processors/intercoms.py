"""Intercom processor for Evon Smart Home coordinator."""

from __future__ import annotations

from collections.abc import Callable
import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ...api import EvonApi

from ...api import EvonApiError
from ...const import EVON_CLASS_INTERCOM_2N

_LOGGER = logging.getLogger(__name__)


async def process_intercoms(
    api: EvonApi,
    instances: list[dict[str, Any]],
    get_room_name: Callable[[str], str],
) -> list[dict[str, Any]]:
    """Process intercom instances.

    Args:
        api: The Evon API client
        instances: List of all device instances
        get_room_name: Function to get room name from group ID

    Returns:
        List of processed intercom data dictionaries
    """
    intercoms = []
    for instance in instances:
        if instance.get("ClassName") != EVON_CLASS_INTERCOM_2N:
            continue
        if not instance.get("Name"):
            continue

        instance_id = instance.get("ID", "")
        try:
            details = await api.get_instance(instance_id)
            intercoms.append(
                {
                    "id": instance_id,
                    "name": instance.get("Name"),
                    "room_name": get_room_name(instance.get("Group", "")),
                    "doorbell_triggered": details.get("DoorBellTriggered", False),
                    "door_open_triggered": details.get("DoorOpenTriggered", False),
                    "is_door_open": details.get("IsDoorOpen", False),
                    "connection_lost": details.get("ConnectionToIntercomHasBeenLost", False),
                }
            )
        except EvonApiError:
            _LOGGER.warning("Failed to get details for intercom %s", instance_id)
    return intercoms
