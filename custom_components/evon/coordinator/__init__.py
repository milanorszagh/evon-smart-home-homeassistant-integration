"""Data update coordinator for Evon Smart Home."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from ..api import EvonApi, EvonApiError
from ..const import (
    CONNECTION_FAILURE_THRESHOLD,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    REPAIR_CONNECTION_FAILED,
)
from .processors import (
    process_air_quality,
    process_bathroom_radiators,
    process_blinds,
    process_climates,
    process_home_states,
    process_lights,
    process_scenes,
    process_smart_meters,
    process_switches,
    process_valves,
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
        self._consecutive_failures = 0
        self._repair_created = False
        self._last_successful_data: dict[str, Any] | None = None

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

            # Fetch season mode (global heating/cooling)
            season_mode = await self._fetch_season_mode()

            # Process all device types using modular processors
            lights = await process_lights(self.api, instances, self._get_room_name)
            blinds = await process_blinds(self.api, instances, self._get_room_name)
            climates = await process_climates(self.api, instances, self._get_room_name, season_mode)
            switches = await process_switches(self.api, instances, self._get_room_name)
            smart_meters = await process_smart_meters(self.api, instances, self._get_room_name)
            air_quality = await process_air_quality(self.api, instances, self._get_room_name)
            valves = await process_valves(self.api, instances, self._get_room_name)
            home_states = await process_home_states(self.api, instances)
            bathroom_radiators = await process_bathroom_radiators(self.api, instances, self._get_room_name)
            scenes = await process_scenes(instances)

            # Success - reset failure counter and clear any connection repair
            self._consecutive_failures = 0
            if self._repair_created:
                ir.async_delete_issue(self.hass, DOMAIN, REPAIR_CONNECTION_FAILED)
                self._repair_created = False
                _LOGGER.info("Connection restored, cleared connection failure repair")

            result = {
                "lights": lights,
                "blinds": blinds,
                "climates": climates,
                "switches": switches,
                "smart_meters": smart_meters,
                "air_quality": air_quality,
                "valves": valves,
                "home_states": home_states,
                "bathroom_radiators": bathroom_radiators,
                "scenes": scenes,
                "rooms": self._rooms_cache if self._sync_areas else {},
                "season_mode": season_mode,
            }

            # Cache successful data for use during transient failures
            self._last_successful_data = result
            return result

        except EvonApiError as err:
            return self._handle_api_error(err)

    def _handle_api_error(self, err: EvonApiError) -> dict[str, Any]:
        """Handle API errors with failure tracking and repair issue management."""
        self._consecutive_failures += 1
        _LOGGER.warning(
            "Evon API error (failure %d/%d): %s",
            self._consecutive_failures,
            CONNECTION_FAILURE_THRESHOLD,
            err,
        )

        # Create repair issue after threshold consecutive failures
        if self._consecutive_failures >= CONNECTION_FAILURE_THRESHOLD and not self._repair_created:
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                REPAIR_CONNECTION_FAILED,
                is_fixable=False,
                is_persistent=True,
                severity=ir.IssueSeverity.ERROR,
                translation_key="connection_failed",
                translation_placeholders={
                    "failures": str(self._consecutive_failures),
                    "error": str(err),
                },
            )
            self._repair_created = True
            _LOGGER.error(
                "Created repair issue: Evon API connection failed %d times",
                self._consecutive_failures,
            )

        # Return cached data for transient failures to keep entities available
        # Only raise UpdateFailed after threshold is reached AND no cached data
        if self._consecutive_failures < CONNECTION_FAILURE_THRESHOLD and self._last_successful_data:
            _LOGGER.info(
                "Returning cached data due to transient API failure (failure %d/%d)",
                self._consecutive_failures,
                CONNECTION_FAILURE_THRESHOLD,
            )
            return self._last_successful_data

        # Even after threshold, prefer cached data over unavailable entities
        if self._last_successful_data:
            _LOGGER.warning(
                "Returning stale cached data after %d consecutive failures",
                self._consecutive_failures,
            )
            return self._last_successful_data

        # No cached data available - entities will become unavailable
        raise UpdateFailed(f"Error communicating with Evon API: {err}") from err

    async def _fetch_rooms(self) -> None:
        """Fetch rooms for area sync."""
        try:
            self._rooms_cache = await self.api.get_rooms()
            _LOGGER.debug("Fetched %d rooms from Evon", len(self._rooms_cache))
        except EvonApiError:
            _LOGGER.warning("Failed to fetch rooms, area sync disabled for this update")
            self._rooms_cache = {}

    async def _fetch_season_mode(self) -> bool:
        """Fetch the global season mode (heating/cooling).

        Returns:
            True if cooling (summer), False if heating (winter)
        """
        try:
            return await self.api.get_season_mode()
        except EvonApiError:
            _LOGGER.warning("Failed to fetch season mode, defaulting to heating")
            return False

    def _get_room_name(self, group: str) -> str:
        """Get room name for a group ID."""
        return self._rooms_cache.get(group, "") if self._sync_areas else ""

    def get_entity_data(self, entity_type: str, instance_id: str) -> dict[str, Any] | None:
        """Get data for a specific entity.

        Args:
            entity_type: The type of entity (lights, blinds, climates, switches,
                        smart_meters, air_quality, valves, home_states, scenes)
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

    def get_season_mode(self) -> bool:
        """Get the current season mode.

        Returns:
            True if cooling (summer), False if heating (winter)
        """
        if self.data:
            return self.data.get("season_mode", False)
        return False

    def get_scene_data(self, instance_id: str) -> dict[str, Any] | None:
        """Get data for a specific scene."""
        return self.get_entity_data("scenes", instance_id)

    def get_scenes(self) -> list[dict[str, Any]]:
        """Get all scenes."""
        if self.data and "scenes" in self.data:
            return self.data["scenes"]
        return []
