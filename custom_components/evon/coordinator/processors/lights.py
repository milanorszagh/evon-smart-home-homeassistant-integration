"""Light processor for Evon Smart Home coordinator."""

from __future__ import annotations

from collections.abc import Callable
import logging
from typing import Any

from ...const import EVON_CLASS_LIGHT_DIM, EVON_CLASS_LIGHT_GROUP, EVON_CLASS_LIGHT_RGBW

_LOGGER = logging.getLogger(__name__)

# Light classes to process
LIGHT_CLASSES = {EVON_CLASS_LIGHT_DIM, EVON_CLASS_LIGHT_GROUP, EVON_CLASS_LIGHT_RGBW}


def process_lights(
    instance_details: dict[str, dict[str, Any]],
    instances: list[dict[str, Any]],
    get_room_name: Callable[[str], str],
) -> list[dict[str, Any]]:
    """Process light instances.

    Args:
        instance_details: Pre-fetched instance details keyed by instance ID
        instances: List of all device instances
        get_room_name: Function to get room name from group ID

    Returns:
        List of processed light data dictionaries
    """
    lights = []
    for instance in instances:
        if instance.get("ClassName") not in LIGHT_CLASSES:
            continue
        if not instance.get("Name"):
            continue

        instance_id = instance.get("ID", "")
        class_name = instance.get("ClassName", "")
        details = instance_details.get(instance_id)
        if details is None:
            _LOGGER.warning("No details available for light %s", instance_id)
            continue

        # Check if this light supports color temperature (RGBW lights)
        supports_color_temp = class_name == EVON_CLASS_LIGHT_RGBW

        light_data: dict[str, Any] = {
            "id": instance_id,
            "name": instance.get("Name"),
            "room_name": get_room_name(instance.get("Group", "")),
            "is_on": details.get("IsOn", False),
            "brightness": details.get("ScaledBrightness", 0),
            "supports_color_temp": supports_color_temp,
        }

        # Add color temp properties for RGBW lights
        if supports_color_temp:
            light_data["color_temp"] = details.get("ColorTemp")
            light_data["min_color_temp"] = details.get("MinColorTemperature")
            light_data["max_color_temp"] = details.get("MaxColorTemperature")

        lights.append(light_data)
    return lights
