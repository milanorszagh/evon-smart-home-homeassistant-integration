"""Data update coordinator for Evon Smart Home."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import EvonApi, EvonApiError
from .const import (
    DOMAIN,
    DEFAULT_SCAN_INTERVAL,
    EVON_CLASS_LIGHT_DIM,
    EVON_CLASS_BLIND,
    EVON_CLASS_CLIMATE,
    EVON_CLASS_CLIMATE_UNIVERSAL,
)

_LOGGER = logging.getLogger(__name__)


class EvonDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching Evon data."""

    def __init__(self, hass: HomeAssistant, api: EvonApi) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self.api = api
        self._instances_cache: list[dict[str, Any]] = []

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from Evon API."""
        try:
            # Get all instances
            instances = await self.api.get_instances()
            self._instances_cache = instances

            # Filter and organize by type
            lights = []
            blinds = []
            climates = []

            for instance in instances:
                class_name = instance.get("ClassName", "")
                name = instance.get("Name", "")
                instance_id = instance.get("ID", "")

                # Skip instances without names (templates/base classes)
                if not name:
                    continue

                if class_name == EVON_CLASS_LIGHT_DIM:
                    # Get detailed state for light
                    try:
                        details = await self.api.get_instance(instance_id)
                        lights.append({
                            "id": instance_id,
                            "name": name,
                            "is_on": details.get("IsOn", False),
                            "brightness": details.get("ScaledBrightness", 0),
                        })
                    except EvonApiError:
                        _LOGGER.warning("Failed to get details for light %s", instance_id)

                elif class_name == EVON_CLASS_BLIND:
                    # Get detailed state for blind
                    try:
                        details = await self.api.get_instance(instance_id)
                        blinds.append({
                            "id": instance_id,
                            "name": name,
                            "position": details.get("Position", 0),
                            "angle": details.get("Angle", 0),
                            "is_moving": details.get("IsMoving", False),
                        })
                    except EvonApiError:
                        _LOGGER.warning("Failed to get details for blind %s", instance_id)

                elif class_name == EVON_CLASS_CLIMATE or EVON_CLASS_CLIMATE_UNIVERSAL in class_name:
                    # Get detailed state for climate
                    try:
                        details = await self.api.get_instance(instance_id)
                        climates.append({
                            "id": instance_id,
                            "name": name,
                            "current_temperature": details.get("ActualTemperature", 0),
                            "target_temperature": details.get("SetTemperature", 0),
                            "min_temp": details.get("MinSetValueHeat", 15),
                            "max_temp": details.get("MaxSetValueHeat", 25),
                            "comfort_temp": details.get("SetValueComfortHeating", 22),
                            "energy_saving_temp": details.get("SetValueEnergySavingHeating", 20),
                            "freeze_protection_temp": details.get("SetValueFreezeProtection", 15),
                        })
                    except EvonApiError:
                        _LOGGER.warning("Failed to get details for climate %s", instance_id)

            return {
                "lights": lights,
                "blinds": blinds,
                "climates": climates,
            }

        except EvonApiError as err:
            raise UpdateFailed(f"Error communicating with Evon API: {err}") from err

    def get_light_data(self, instance_id: str) -> dict[str, Any] | None:
        """Get data for a specific light."""
        if self.data and "lights" in self.data:
            for light in self.data["lights"]:
                if light["id"] == instance_id:
                    return light
        return None

    def get_blind_data(self, instance_id: str) -> dict[str, Any] | None:
        """Get data for a specific blind."""
        if self.data and "blinds" in self.data:
            for blind in self.data["blinds"]:
                if blind["id"] == instance_id:
                    return blind
        return None

    def get_climate_data(self, instance_id: str) -> dict[str, Any] | None:
        """Get data for a specific climate."""
        if self.data and "climates" in self.data:
            for climate in self.data["climates"]:
                if climate["id"] == instance_id:
                    return climate
        return None
