"""Climate processor for Evon Smart Home coordinator."""

from __future__ import annotations

from collections.abc import Callable
import logging
from typing import Any

from ...const import EVON_CLASS_CLIMATE, EVON_CLASS_CLIMATE_UNIVERSAL

_LOGGER = logging.getLogger(__name__)


def process_climates(
    instance_details: dict[str, dict[str, Any]],
    instances: list[dict[str, Any]],
    get_room_name: Callable[[str], str],
    season_mode: bool,
) -> list[dict[str, Any]]:
    """Process climate instances.

    Args:
        instance_details: Pre-fetched instance details keyed by instance ID
        instances: List of all device instances
        get_room_name: Function to get room name from group ID
        season_mode: True if cooling (summer), False if heating (winter)

    Returns:
        List of processed climate data dictionaries
    """
    climates = []
    for instance in instances:
        class_name = instance.get("ClassName", "")
        if class_name != EVON_CLASS_CLIMATE and EVON_CLASS_CLIMATE_UNIVERSAL not in class_name:
            continue
        if not instance.get("Name"):
            continue

        instance_id = instance.get("ID", "")
        details = instance_details.get(instance_id)
        if details is None:
            _LOGGER.warning("No details available for climate %s", instance_id)
            continue

        # Get temperature values based on season mode
        if season_mode:  # Cooling (summer)
            comfort_temp = details.get("SetValueComfortCooling", 25)
            eco_temp = details.get("SetValueEnergySavingCooling", 24)
            protection_temp = details.get("SetValueHeatProtection", 29)
            evon_min = details.get("MinSetValueCool", 18)
            evon_max = details.get("MaxSetValueCool", 30)
            # Include protection temp in range (heat protection can be above normal max)
            min_temp = min(evon_min, comfort_temp, eco_temp, protection_temp)
            max_temp = max(evon_max, protection_temp)
        else:  # Heating (winter)
            comfort_temp = details.get("SetValueComfortHeating", 22)
            eco_temp = details.get("SetValueEnergySavingHeating", 20)
            protection_temp = details.get("SetValueFreezeProtection", 15)
            evon_min = details.get("MinSetValueHeat", 15)
            evon_max = details.get("MaxSetValueHeat", 25)
            # Include protection temp in range (freeze protection can be below normal min)
            min_temp = min(evon_min, protection_temp)
            max_temp = max(evon_max, comfort_temp, eco_temp)

        climates.append(
            {
                "id": instance_id,
                "name": instance.get("Name"),
                "room_name": get_room_name(instance.get("Group", "")),
                "current_temperature": details.get("ActualTemperature", 0),
                "target_temperature": details.get("SetTemperature", 0),
                "min_temp": min_temp,
                "max_temp": max_temp,
                "min_set_value_heat": details.get("MinSetValueHeat"),
                "max_set_value_heat": details.get("MaxSetValueHeat"),
                "min_set_value_cool": details.get("MinSetValueCool"),
                "max_set_value_cool": details.get("MaxSetValueCool"),
                "comfort_temp": comfort_temp,
                "energy_saving_temp": eco_temp,
                "protection_temp": protection_temp,
                # ClimateControlUniversal uses ModeSaved, ClimateControl uses MainState
                "mode_saved": details.get("ModeSaved", details.get("MainState", 4)),
                "is_cooling": details.get("CoolingMode", False),
                "cooling_enabled": not details.get("DisableCooling", True),
                "is_on": details.get("IsOn", False),
                "humidity": details.get("Humidity"),
            }
        )
    return climates
