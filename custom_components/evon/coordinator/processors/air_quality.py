"""Air quality processor for Evon Smart Home coordinator."""

from __future__ import annotations

from collections.abc import Callable
import logging
from typing import Any

from ...const import EVON_CLASS_AIR_QUALITY

_LOGGER = logging.getLogger(__name__)

# Evon uses -999 to indicate "no data available" for sensor readings
EVON_NO_DATA_VALUE = -999


def process_air_quality(
    instance_details: dict[str, dict[str, Any]],
    instances: list[dict[str, Any]],
    get_room_name: Callable[[str], str],
) -> list[dict[str, Any]]:
    """Process air quality instances.

    Args:
        instance_details: Pre-fetched instance details keyed by instance ID
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
        details = instance_details.get(instance_id)
        if details is None:
            _LOGGER.warning("No details available for air quality %s", instance_id)
            continue

        # Only add if sensor has actual data (not EVON_NO_DATA_VALUE)
        co2 = details.get("CO2Value", EVON_NO_DATA_VALUE)
        humidity = details.get("Humidity", EVON_NO_DATA_VALUE)
        temperature = details.get("ActualTemperature", EVON_NO_DATA_VALUE)
        has_data = co2 != EVON_NO_DATA_VALUE or humidity != EVON_NO_DATA_VALUE or temperature != EVON_NO_DATA_VALUE
        if has_data:
            air_quality_sensors.append(
                {
                    "id": instance_id,
                    "name": instance.get("Name"),
                    "room_name": get_room_name(instance.get("Group", "")),
                    "co2": co2 if co2 != EVON_NO_DATA_VALUE else None,
                    "humidity": humidity if humidity != EVON_NO_DATA_VALUE else None,
                    "temperature": temperature if temperature != EVON_NO_DATA_VALUE else None,
                    "health_index": details.get("HealthIndex", 0),
                    "co2_index": details.get("CO2Index", 0),
                    "humidity_index": details.get("HumidityIndex", 0),
                }
            )
    return air_quality_sensors
