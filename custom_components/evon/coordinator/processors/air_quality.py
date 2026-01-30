"""Air quality processor for Evon Smart Home coordinator."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from ...api import EvonApi

from ...api import EvonApiError
from ...const import EVON_CLASS_AIR_QUALITY

_LOGGER = logging.getLogger(__name__)


async def process_air_quality(
    api: EvonApi,
    instances: list[dict[str, Any]],
    get_room_name: Callable[[str], str],
) -> list[dict[str, Any]]:
    """Process air quality instances.

    Args:
        api: The Evon API client
        instances: List of all device instances
        get_room_name: Function to get room name from group ID

    Returns:
        List of processed air quality data dictionaries
    """
    air_quality_sensors = []
    for instance in instances:
        if instance.get("ClassName") != EVON_CLASS_AIR_QUALITY:
            continue
        if not instance.get("Name"):
            continue

        instance_id = instance.get("ID", "")
        try:
            details = await api.get_instance(instance_id)
            # Only add if sensor has actual data (not -999)
            co2 = details.get("CO2Value", -999)
            humidity = details.get("Humidity", -999)
            temperature = details.get("ActualTemperature", -999)
            has_data = co2 != -999 or humidity != -999 or temperature != -999
            if has_data:
                air_quality_sensors.append(
                    {
                        "id": instance_id,
                        "name": instance.get("Name"),
                        "room_name": get_room_name(instance.get("Group", "")),
                        "co2": co2 if co2 != -999 else None,
                        "humidity": humidity if humidity != -999 else None,
                        "temperature": temperature if temperature != -999 else None,
                        "health_index": details.get("HealthIndex", 0),
                        "co2_index": details.get("CO2Index", 0),
                        "humidity_index": details.get("HumidityIndex", 0),
                    }
                )
        except EvonApiError:
            _LOGGER.warning("Failed to get details for air quality %s", instance_id)
    return air_quality_sensors
