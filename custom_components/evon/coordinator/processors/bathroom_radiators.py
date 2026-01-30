"""Bathroom radiator processor for Evon Smart Home coordinator."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from ...api import EvonApi

from ...api import EvonApiError
from ...const import EVON_CLASS_BATHROOM_RADIATOR

_LOGGER = logging.getLogger(__name__)


async def process_bathroom_radiators(
    api: EvonApi,
    instances: list[dict[str, Any]],
    get_room_name: Callable[[str], str],
) -> list[dict[str, Any]]:
    """Process bathroom radiator (electric heater) instances.

    Args:
        api: The Evon API client
        instances: List of all device instances
        get_room_name: Function to get room name from group ID

    Returns:
        List of processed bathroom radiator data dictionaries
    """
    radiators = []
    for instance in instances:
        if instance.get("ClassName") != EVON_CLASS_BATHROOM_RADIATOR:
            continue
        if not instance.get("Name"):
            continue

        instance_id = instance.get("ID", "")
        try:
            details = await api.get_instance(instance_id)
            radiators.append(
                {
                    "id": instance_id,
                    "name": instance.get("Name"),
                    "room_name": get_room_name(instance.get("Group", "")),
                    "is_on": details.get("Output", False),
                    "time_remaining": details.get("NextSwitchPoint", -1),
                    "duration_mins": details.get("EnableForMins", 30),
                    "permanently_on": details.get("PermanentlyOn", False),
                    "permanently_off": details.get("PermanentlyOff", False),
                    "deactivated": details.get("Deactivated", False),
                }
            )
        except EvonApiError:
            _LOGGER.warning("Failed to get details for bathroom radiator %s", instance_id)
    return radiators
