"""Data update coordinator for Evon Smart Home."""
from __future__ import annotations

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
    EVON_CLASS_LIGHT,
    EVON_CLASS_BLIND,
    EVON_CLASS_CLIMATE,
    EVON_CLASS_CLIMATE_UNIVERSAL,
    EVON_CLASS_SWITCH,
    EVON_CLASS_SMART_METER,
    EVON_CLASS_AIR_QUALITY,
    EVON_CLASS_VALVE,
)

_LOGGER = logging.getLogger(__name__)


class EvonDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching Evon data."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: EvonApi,
        scan_interval: int = DEFAULT_SCAN_INTERVAL,
        sync_areas: bool = False,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )
        self.api = api
        self._instances_cache: list[dict[str, Any]] = []
        self._sync_areas = sync_areas
        self._rooms_cache: dict[str, str] = {}

    def set_update_interval(self, scan_interval: int) -> None:
        """Update the polling interval."""
        self.update_interval = timedelta(seconds=scan_interval)

    def set_sync_areas(self, sync_areas: bool) -> None:
        """Update the sync areas setting."""
        self._sync_areas = sync_areas

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from Evon API."""
        try:
            # Get all instances
            instances = await self.api.get_instances()
            self._instances_cache = instances

            # Fetch rooms if area sync is enabled
            if self._sync_areas:
                try:
                    self._rooms_cache = await self.api.get_rooms()
                    _LOGGER.debug("Fetched %d rooms from Evon", len(self._rooms_cache))
                except EvonApiError:
                    _LOGGER.warning("Failed to fetch rooms, area sync disabled for this update")
                    self._rooms_cache = {}

            # Filter and organize by type
            lights = []
            blinds = []
            climates = []
            switches = []
            smart_meters = []
            air_quality_sensors = []
            valves = []

            for instance in instances:
                class_name = instance.get("ClassName", "")
                name = instance.get("Name", "")
                instance_id = instance.get("ID", "")
                group = instance.get("Group", "")

                # Skip instances without names (templates/base classes)
                if not name:
                    continue

                # Look up room name if area sync is enabled
                room_name = self._rooms_cache.get(group, "") if self._sync_areas else ""

                if class_name == EVON_CLASS_LIGHT_DIM:
                    # Get detailed state for light
                    try:
                        details = await self.api.get_instance(instance_id)
                        lights.append({
                            "id": instance_id,
                            "name": name,
                            "room_name": room_name,
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
                            "room_name": room_name,
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
                            "room_name": room_name,
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

                elif class_name == EVON_CLASS_LIGHT or class_name == EVON_CLASS_SWITCH:
                    # Get detailed state for non-dimmable light / switch
                    try:
                        details = await self.api.get_instance(instance_id)
                        switches.append({
                            "id": instance_id,
                            "name": name,
                            "room_name": room_name,
                            "is_on": details.get("IsOn", False),
                            "last_click": details.get("LastClickType", None),
                        })
                    except EvonApiError:
                        _LOGGER.warning("Failed to get details for switch %s", instance_id)

                elif EVON_CLASS_SMART_METER in class_name:
                    # Get detailed state for smart meter
                    try:
                        details = await self.api.get_instance(instance_id)
                        smart_meters.append({
                            "id": instance_id,
                            "name": name,
                            "room_name": room_name,
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
                        })
                    except EvonApiError:
                        _LOGGER.warning("Failed to get details for smart meter %s", instance_id)

                elif class_name == EVON_CLASS_AIR_QUALITY:
                    # Get detailed state for air quality sensor
                    try:
                        details = await self.api.get_instance(instance_id)
                        # Only add if sensor has actual data (not -999)
                        co2 = details.get("CO2Value", -999)
                        humidity = details.get("Humidity", -999)
                        temperature = details.get("ActualTemperature", -999)
                        has_data = co2 != -999 or humidity != -999 or temperature != -999
                        if has_data:
                            air_quality_sensors.append({
                                "id": instance_id,
                                "name": name,
                                "room_name": room_name,
                                "co2": co2 if co2 != -999 else None,
                                "humidity": humidity if humidity != -999 else None,
                                "temperature": temperature if temperature != -999 else None,
                                "health_index": details.get("HealthIndex", 0),
                                "co2_index": details.get("CO2Index", 0),
                                "humidity_index": details.get("HumidityIndex", 0),
                            })
                    except EvonApiError:
                        _LOGGER.warning("Failed to get details for air quality %s", instance_id)

                elif class_name == EVON_CLASS_VALVE:
                    # Get detailed state for valve
                    try:
                        details = await self.api.get_instance(instance_id)
                        valves.append({
                            "id": instance_id,
                            "name": name,
                            "room_name": room_name,
                            "is_open": details.get("ActValue", False),
                            "valve_type": details.get("Type", 0),
                        })
                    except EvonApiError:
                        _LOGGER.warning("Failed to get details for valve %s", instance_id)

            return {
                "lights": lights,
                "blinds": blinds,
                "climates": climates,
                "switches": switches,
                "smart_meters": smart_meters,
                "air_quality": air_quality_sensors,
                "valves": valves,
                "rooms": self._rooms_cache if self._sync_areas else {},
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

    def get_switch_data(self, instance_id: str) -> dict[str, Any] | None:
        """Get data for a specific switch."""
        if self.data and "switches" in self.data:
            for switch in self.data["switches"]:
                if switch["id"] == instance_id:
                    return switch
        return None

    def get_smart_meter_data(self, instance_id: str) -> dict[str, Any] | None:
        """Get data for a specific smart meter."""
        if self.data and "smart_meters" in self.data:
            for meter in self.data["smart_meters"]:
                if meter["id"] == instance_id:
                    return meter
        return None

    def get_air_quality_data(self, instance_id: str) -> dict[str, Any] | None:
        """Get data for a specific air quality sensor."""
        if self.data and "air_quality" in self.data:
            for sensor in self.data["air_quality"]:
                if sensor["id"] == instance_id:
                    return sensor
        return None

    def get_valve_data(self, instance_id: str) -> dict[str, Any] | None:
        """Get data for a specific valve."""
        if self.data and "valves" in self.data:
            for valve in self.data["valves"]:
                if valve["id"] == instance_id:
                    return valve
        return None
