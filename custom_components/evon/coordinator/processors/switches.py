"""Switch processor for Evon Smart Home coordinator."""

from __future__ import annotations

from collections.abc import Callable
import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ...api import EvonApi

from ...api import EvonApiError
from ...const import EVON_CLASS_LIGHT

_LOGGER = logging.getLogger(__name__)


async def process_switches(
    api: EvonApi,
    instances: list[dict[str, Any]],
    get_room_name: Callable[[str], str],
) -> list[dict[str, Any]]:
    """Process controllable switch instances (relays).

    Args:
        api: The Evon API client
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
        try:
            details = await api.get_instance(instance_id)
            switches.append(
                {
                    "id": instance_id,
                    "name": instance.get("Name"),
                    "room_name": get_room_name(instance.get("Group", "")),
                    "is_on": details.get("IsOn", False),
                }
            )
        except EvonApiError:
            _LOGGER.warning("Failed to get details for switch %s", instance_id)
    return switches
