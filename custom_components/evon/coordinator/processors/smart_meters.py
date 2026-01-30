"""Smart meter processor for Evon Smart Home coordinator."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from ...api import EvonApi

from ...api import EvonApiError
from ...const import EVON_CLASS_SMART_METER

_LOGGER = logging.getLogger(__name__)


async def process_smart_meters(
    api: EvonApi,
    instances: list[dict[str, Any]],
    get_room_name: Callable[[str], str],
) -> list[dict[str, Any]]:
    """Process smart meter instances.

    Args:
        api: The Evon API client
        instances: List of all device instances
        get_room_name: Function to get room name from group ID

    Returns:
        List of processed smart meter data dictionaries
    """
    smart_meters = []
    for instance in instances:
        if EVON_CLASS_SMART_METER not in instance.get("ClassName", ""):
            continue
        if not instance.get("Name"):
            continue

        instance_id = instance.get("ID", "")
        try:
            details = await api.get_instance(instance_id)
            smart_meters.append(
                {
                    "id": instance_id,
                    "name": instance.get("Name"),
                    "room_name": get_room_name(instance.get("Group", "")),
                    "power": details.get("PowerActual", 0),
                    "power_unit": details.get("PowerActualUnit", "W"),
                    "energy": details.get("Energy", 0),
                    "energy_24h": details.get("Energy24h", 0),
                    "feed_in": details.get("FeedIn", 0),
                    "feed_in_energy": details.get("FeedInEnergy", 0),
                    "frequency": details.get("Frequency", 0),
                    "voltage_l1": details.get("UL1N", 0),
                    "voltage_l2": details.get("UL2N", 0),
                    "voltage_l3": details.get("UL3N", 0),
                    "current_l1": details.get("IL1", 0),
                    "current_l2": details.get("IL2", 0),
                    "current_l3": details.get("IL3", 0),
                }
            )
        except EvonApiError:
            _LOGGER.warning("Failed to get details for smart meter %s", instance_id)
    return smart_meters
