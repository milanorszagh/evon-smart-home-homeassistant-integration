"""Data update coordinator for Evon Smart Home."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import EvonApi, EvonApiError
from .const import (
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    EVON_CLASS_AIR_QUALITY,
    EVON_CLASS_BATHROOM_RADIATOR,
    EVON_CLASS_BLIND,
    EVON_CLASS_CLIMATE,
    EVON_CLASS_CLIMATE_UNIVERSAL,
    EVON_CLASS_HOME_STATE,
    EVON_CLASS_LIGHT,
    EVON_CLASS_LIGHT_DIM,
    EVON_CLASS_SMART_METER,
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
                await self._fetch_rooms()

            # Process all device types
            lights = await self._process_lights(instances)
            blinds = await self._process_blinds(instances)
            climates = await self._process_climates(instances)
            switches = await self._process_switches(instances)
            smart_meters = await self._process_smart_meters(instances)
            air_quality = await self._process_air_quality(instances)
            valves = await self._process_valves(instances)
            home_states = await self._process_home_states(instances)
            bathroom_radiators = await self._process_bathroom_radiators(instances)

            return {
                "lights": lights,
                "blinds": blinds,
                "climates": climates,
                "switches": switches,
                "smart_meters": smart_meters,
                "air_quality": air_quality,
                "valves": valves,
                "home_states": home_states,
                "bathroom_radiators": bathroom_radiators,
                "rooms": self._rooms_cache if self._sync_areas else {},
            }

        except EvonApiError as err:
            raise UpdateFailed(f"Error communicating with Evon API: {err}") from err

    async def _fetch_rooms(self) -> None:
        """Fetch rooms for area sync."""
        try:
            self._rooms_cache = await self.api.get_rooms()
            _LOGGER.debug("Fetched %d rooms from Evon", len(self._rooms_cache))
        except EvonApiError:
            _LOGGER.warning("Failed to fetch rooms, area sync disabled for this update")
            self._rooms_cache = {}

    def _get_room_name(self, group: str) -> str:
        """Get room name for a group ID."""
        return self._rooms_cache.get(group, "") if self._sync_areas else ""

    async def _process_lights(self, instances: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Process light instances."""
        lights = []
        for instance in instances:
            if instance.get("ClassName") != EVON_CLASS_LIGHT_DIM:
                continue
            if not instance.get("Name"):
                continue

            instance_id = instance.get("ID", "")
            try:
                details = await self.api.get_instance(instance_id)
                lights.append(
                    {
                        "id": instance_id,
                        "name": instance.get("Name"),
                        "room_name": self._get_room_name(instance.get("Group", "")),
                        "is_on": details.get("IsOn", False),
                        "brightness": details.get("ScaledBrightness", 0),
                    }
                )
            except EvonApiError:
                _LOGGER.warning("Failed to get details for light %s", instance_id)
        return lights

    async def _process_blinds(self, instances: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Process blind instances."""
        blinds = []
        for instance in instances:
            if instance.get("ClassName") != EVON_CLASS_BLIND:
                continue
            if not instance.get("Name"):
                continue

            instance_id = instance.get("ID", "")
            try:
                details = await self.api.get_instance(instance_id)
                blinds.append(
                    {
                        "id": instance_id,
                        "name": instance.get("Name"),
                        "room_name": self._get_room_name(instance.get("Group", "")),
                        "position": details.get("Position", 0),
                        "angle": details.get("Angle", 0),
                        "is_moving": details.get("IsMoving", False),
                    }
                )
            except EvonApiError:
                _LOGGER.warning("Failed to get details for blind %s", instance_id)
        return blinds

    async def _process_climates(self, instances: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Process climate instances."""
        climates = []
        for instance in instances:
            class_name = instance.get("ClassName", "")
            if class_name != EVON_CLASS_CLIMATE and EVON_CLASS_CLIMATE_UNIVERSAL not in class_name:
                continue
            if not instance.get("Name"):
                continue

            instance_id = instance.get("ID", "")
            try:
                details = await self.api.get_instance(instance_id)
                climates.append(
                    {
                        "id": instance_id,
                        "name": instance.get("Name"),
                        "room_name": self._get_room_name(instance.get("Group", "")),
                        "current_temperature": details.get("ActualTemperature", 0),
                        "target_temperature": details.get("SetTemperature", 0),
                        "min_temp": details.get("MinSetValueHeat", 15),
                        "max_temp": details.get("MaxSetValueHeat", 25),
                        "comfort_temp": details.get("SetValueComfortHeating", 22),
                        "energy_saving_temp": details.get("SetValueEnergySavingHeating", 20),
                        "freeze_protection_temp": details.get("SetValueFreezeProtection", 15),
                        "mode_saved": details.get("ModeSaved", 4),
                        "is_cooling": details.get("CoolingMode", False),
                        "cooling_enabled": not details.get("DisableCooling", True),
                        "is_on": details.get("IsOn", False),
                    }
                )
            except EvonApiError:
                _LOGGER.warning("Failed to get details for climate %s", instance_id)
        return climates

    async def _process_switches(self, instances: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Process controllable switch instances (relays)."""
        switches = []
        for instance in instances:
            # Only process SmartCOM.Light.Light (controllable relays)
            if instance.get("ClassName") != EVON_CLASS_LIGHT:
                continue
            if not instance.get("Name"):
                continue

            instance_id = instance.get("ID", "")
            try:
                details = await self.api.get_instance(instance_id)
                switches.append(
                    {
                        "id": instance_id,
                        "name": instance.get("Name"),
                        "room_name": self._get_room_name(instance.get("Group", "")),
                        "is_on": details.get("IsOn", False),
                    }
                )
            except EvonApiError:
                _LOGGER.warning("Failed to get details for switch %s", instance_id)
        return switches

    async def _process_smart_meters(self, instances: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Process smart meter instances."""
        smart_meters = []
        for instance in instances:
            if EVON_CLASS_SMART_METER not in instance.get("ClassName", ""):
                continue
            if not instance.get("Name"):
                continue

            instance_id = instance.get("ID", "")
            try:
                details = await self.api.get_instance(instance_id)
                smart_meters.append(
                    {
                        "id": instance_id,
                        "name": instance.get("Name"),
                        "room_name": self._get_room_name(instance.get("Group", "")),
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

    async def _process_air_quality(self, instances: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Process air quality instances."""
        air_quality_sensors = []
        for instance in instances:
            if instance.get("ClassName") != EVON_CLASS_AIR_QUALITY:
                continue
            if not instance.get("Name"):
                continue

            instance_id = instance.get("ID", "")
            try:
                details = await self.api.get_instance(instance_id)
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
                            "room_name": self._get_room_name(instance.get("Group", "")),
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

    async def _process_valves(self, instances: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Process valve instances."""
        valves = []
        for instance in instances:
            if instance.get("ClassName") != EVON_CLASS_VALVE:
                continue
            if not instance.get("Name"):
                continue

            instance_id = instance.get("ID", "")
            try:
                details = await self.api.get_instance(instance_id)
                valves.append(
                    {
                        "id": instance_id,
                        "name": instance.get("Name"),
                        "room_name": self._get_room_name(instance.get("Group", "")),
                        "is_open": details.get("ActValue", False),
                        "valve_type": details.get("Type", 0),
                    }
                )
            except EvonApiError:
                _LOGGER.warning("Failed to get details for valve %s", instance_id)
        return valves

    async def _process_home_states(self, instances: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Process home state instances."""
        home_states = []
        for instance in instances:
            if instance.get("ClassName") != EVON_CLASS_HOME_STATE:
                continue
            # Skip template instances (ID starting with "System.")
            instance_id = instance.get("ID", "")
            if instance_id.startswith("System."):
                continue
            if not instance.get("Name"):
                continue

            try:
                details = await self.api.get_instance(instance_id)
                home_states.append(
                    {
                        "id": instance_id,
                        "name": instance.get("Name"),
                        "active": details.get("Active", False),
                    }
                )
            except EvonApiError:
                _LOGGER.warning("Failed to get details for home state %s", instance_id)
        return home_states

    async def _process_bathroom_radiators(self, instances: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Process bathroom radiator (electric heater) instances."""
        radiators = []
        for instance in instances:
            if instance.get("ClassName") != EVON_CLASS_BATHROOM_RADIATOR:
                continue
            if not instance.get("Name"):
                continue

            instance_id = instance.get("ID", "")
            try:
                details = await self.api.get_instance(instance_id)
                radiators.append(
                    {
                        "id": instance_id,
                        "name": instance.get("Name"),
                        "room_name": self._get_room_name(instance.get("Group", "")),
                        "is_on": details.get("Output", False),
                        "time_remaining": details.get("NextSwitchPoint", -1),
                        "duration_mins": details.get("EnableForMins", 30),
                        "permanently_on": details.get("PermanentlyOn", False),
                        "permanently_off": details.get("PermanentlyOff", False),
                        "deactivated": details.get("Deactivated", False),
                    }
                )
            except EvonApiError:
                _LOGGER.warning("Failed to get details for bathroom radiator %s", instance_id)
        return radiators

    def get_entity_data(self, entity_type: str, instance_id: str) -> dict[str, Any] | None:
        """Get data for a specific entity.

        Args:
            entity_type: The type of entity (lights, blinds, climates, switches,
                        smart_meters, air_quality, valves, home_states)
            instance_id: The instance ID to look up

        Returns:
            The entity data dictionary or None if not found
        """
        if self.data and entity_type in self.data:
            for entity in self.data[entity_type]:
                if entity["id"] == instance_id:
                    return entity
        return None

    # Legacy getter methods for backwards compatibility
    def get_light_data(self, instance_id: str) -> dict[str, Any] | None:
        """Get data for a specific light."""
        return self.get_entity_data("lights", instance_id)

    def get_blind_data(self, instance_id: str) -> dict[str, Any] | None:
        """Get data for a specific blind."""
        return self.get_entity_data("blinds", instance_id)

    def get_climate_data(self, instance_id: str) -> dict[str, Any] | None:
        """Get data for a specific climate."""
        return self.get_entity_data("climates", instance_id)

    def get_switch_data(self, instance_id: str) -> dict[str, Any] | None:
        """Get data for a specific switch."""
        return self.get_entity_data("switches", instance_id)

    def get_smart_meter_data(self, instance_id: str) -> dict[str, Any] | None:
        """Get data for a specific smart meter."""
        return self.get_entity_data("smart_meters", instance_id)

    def get_air_quality_data(self, instance_id: str) -> dict[str, Any] | None:
        """Get data for a specific air quality sensor."""
        return self.get_entity_data("air_quality", instance_id)

    def get_valve_data(self, instance_id: str) -> dict[str, Any] | None:
        """Get data for a specific valve."""
        return self.get_entity_data("valves", instance_id)

    def get_home_state_data(self, instance_id: str) -> dict[str, Any] | None:
        """Get data for a specific home state."""
        return self.get_entity_data("home_states", instance_id)

    def get_bathroom_radiator_data(self, instance_id: str) -> dict[str, Any] | None:
        """Get data for a specific bathroom radiator."""
        return self.get_entity_data("bathroom_radiators", instance_id)

    def get_active_home_state(self) -> str | None:
        """Get the currently active home state ID."""
        if self.data and "home_states" in self.data:
            for state in self.data["home_states"]:
                if state.get("active"):
                    return state.get("id")
        return None

    def get_home_states(self) -> list[dict[str, Any]]:
        """Get all home states."""
        if self.data and "home_states" in self.data:
            return self.data["home_states"]
        return []
