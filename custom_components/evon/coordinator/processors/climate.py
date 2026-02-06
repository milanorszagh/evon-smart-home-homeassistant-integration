"""Climate processor for Evon Smart Home coordinator."""

from __future__ import annotations

from collections.abc import Callable
import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ...api import EvonApi

from ...api import EvonApiError
from ...const import EVON_CLASS_CLIMATE, EVON_CLASS_CLIMATE_UNIVERSAL

_LOGGER = logging.getLogger(__name__)


async def process_climates(
    api: EvonApi,
    instances: list[dict[str, Any]],
    get_room_name: Callable[[str], str],
    season_mode: bool,
) -> list[dict[str, Any]]:
    """Process climate instances.

    Args:
        api: The Evon API client
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
        try:
            details = await api.get_instance(instance_id)

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
        except EvonApiError:
            _LOGGER.warning("Failed to get details for climate %s", instance_id)
    return climates
