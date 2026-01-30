"""Valve processor for Evon Smart Home coordinator."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from ...api import EvonApi

from ...api import EvonApiError
from ...const import EVON_CLASS_VALVE

_LOGGER = logging.getLogger(__name__)


async def process_valves(
    api: EvonApi,
    instances: list[dict[str, Any]],
    get_room_name: Callable[[str], str],
) -> list[dict[str, Any]]:
    """Process valve instances.

    Args:
        api: The Evon API client
        instances: List of all device instances
        get_room_name: Function to get room name from group ID

    Returns:
        List of processed valve data dictionaries
    """
    valves = []
    for instance in instances:
        if instance.get("ClassName") != EVON_CLASS_VALVE:
            continue
        if not instance.get("Name"):
            continue

        instance_id = instance.get("ID", "")
        try:
            details = await api.get_instance(instance_id)
            valves.append(
                {
                    "id": instance_id,
                    "name": instance.get("Name"),
                    "room_name": get_room_name(instance.get("Group", "")),
                    "is_open": details.get("ActValue", False),
                    "valve_type": details.get("Type", 0),
                }
            )
        except EvonApiError:
            _LOGGER.warning("Failed to get details for valve %s", instance_id)
    return valves
