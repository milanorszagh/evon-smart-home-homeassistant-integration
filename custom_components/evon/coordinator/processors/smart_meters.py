"""Smart meter processor for Evon Smart Home coordinator."""

from __future__ import annotations

from collections.abc import Callable
import logging
from typing import Any

from ...const import EVON_CLASS_SMART_METER

_LOGGER = logging.getLogger(__name__)


def process_smart_meters(
    instance_details: dict[str, dict[str, Any]],
    instances: list[dict[str, Any]],
    get_room_name: Callable[[str], str],
) -> list[dict[str, Any]]:
    """Process smart meter instances.

    Args:
        instance_details: Pre-fetched instance details keyed by instance ID
        instances: List of all device instances
        get_room_name: Function to get room name from group ID

    Returns:
        List of processed smart meter data dictionaries
    """
    smart_meters = []
    _LOGGER.debug("Processing %d instances for smart meters", len(instances))
    for instance in instances:
        class_name = instance.get("ClassName", "")
        if EVON_CLASS_SMART_METER not in class_name:
            continue
        _LOGGER.debug("Found smart meter candidate: %s (class=%s)", instance.get("ID"), class_name)
        if not instance.get("Name"):
            _LOGGER.debug("Skipping %s - no name configured", instance.get("ID"))
            continue

        instance_id = instance.get("ID", "")
        details = instance_details.get(instance_id)
        if details is None:
            _LOGGER.warning("No details available for smart meter %s", instance_id)
            continue

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
                # Per-phase power (WebSocket provides P1, P2, P3)
                "power_l1": details.get("P1", 0),
                "power_l2": details.get("P2", 0),
                "power_l3": details.get("P3", 0),
                # Energy data for today and statistics import
                "energy_today": details.get("EnergyDataDay", 0),
                "energy_data_month": details.get("EnergyDataMonth", []),
                "feed_in_data_month": details.get("FeedInDataMonth", []),
                "energy_data_year": details.get("EnergyDataYear", []),
            }
        )
        _LOGGER.debug("Added smart meter: %s with power=%s", instance_id, details.get("PowerActual"))
    _LOGGER.debug("Processed %d smart meters total", len(smart_meters))
    return smart_meters
