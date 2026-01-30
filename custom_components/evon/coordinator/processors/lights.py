"""Light processor for Evon Smart Home coordinator."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from ...api import EvonApi

from ...api import EvonApiError
from ...const import EVON_CLASS_LIGHT_DIM

_LOGGER = logging.getLogger(__name__)


async def process_lights(
    api: EvonApi,
    instances: list[dict[str, Any]],
    get_room_name: Callable[[str], str],
) -> list[dict[str, Any]]:
    """Process light instances.

    Args:
        api: The Evon API client
        instances: List of all device instances
        get_room_name: Function to get room name from group ID

    Returns:
        List of processed light data dictionaries
    """
    lights = []
    for instance in instances:
        if instance.get("ClassName") != EVON_CLASS_LIGHT_DIM:
            continue
        if not instance.get("Name"):
            continue

        instance_id = instance.get("ID", "")
        try:
            details = await api.get_instance(instance_id)
            lights.append(
                {
                    "id": instance_id,
                    "name": instance.get("Name"),
                    "room_name": get_room_name(instance.get("Group", "")),
                    "is_on": details.get("IsOn", False),
                    "brightness": details.get("ScaledBrightness", 0),
                }
            )
        except EvonApiError:
            _LOGGER.warning("Failed to get details for light %s", instance_id)
    return lights
