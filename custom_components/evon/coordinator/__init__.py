"""Data update coordinator for Evon Smart Home."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import TYPE_CHECKING, Any

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from ..api import EvonApi, EvonApiError
from ..const import (
    CONNECTION_FAILURE_THRESHOLD,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    REPAIR_CONNECTION_FAILED,
    WS_POLL_INTERVAL,
)
from .processors import (
    process_air_quality,
    process_bathroom_radiators,
    process_blinds,
    process_cameras,
    process_climates,
    process_home_states,
    process_intercoms,
    process_lights,
    process_scenes,
    process_security_doors,
    process_smart_meters,
    process_switches,
    process_valves,
)

if TYPE_CHECKING:
    from ..ws_client import EvonWsClient

_LOGGER = logging.getLogger(__name__)


class EvonDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching Evon data."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: EvonApi,
        scan_interval: int = DEFAULT_SCAN_INTERVAL,
        sync_areas: bool = False,
        use_websocket: bool = False,
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
        self._base_scan_interval = scan_interval

        # WebSocket support
        self._use_websocket = use_websocket
        self._ws_client: EvonWsClient | None = None
        self._ws_connected = False

    def set_update_interval(self, scan_interval: int) -> None:
        """Update the polling interval."""
        self._base_scan_interval = scan_interval
        # Only apply base interval if WebSocket not connected
        if not self._ws_connected:
            self.update_interval = timedelta(seconds=scan_interval)

    def set_sync_areas(self, sync_areas: bool) -> None:
        """Update the sync areas setting."""
        self._sync_areas = sync_areas

    def set_use_websocket(self, use_websocket: bool) -> None:
        """Update the WebSocket setting."""
        self._use_websocket = use_websocket

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from Evon API."""
        try:
            # Get all instances
            instances = await self.api.get_instances()
            self._instances_cache = instances

            # Update instance class cache for WebSocket routing
            self.api.set_instance_classes(instances)

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
            security_doors = await process_security_doors(self.api, instances, self._get_room_name)
            intercoms = await process_intercoms(self.api, instances, self._get_room_name)
            cameras = await process_cameras(self.api, instances, self._get_room_name)

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
                "security_doors": security_doors,
                "intercoms": intercoms,
                "cameras": cameras,
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

    # WebSocket methods

    async def async_setup_websocket(
        self,
        session: aiohttp.ClientSession,
        host: str | None,
        username: str,
        password: str,
        is_remote: bool = False,
        engine_id: str | None = None,
    ) -> None:
        """Set up WebSocket client for real-time updates.

        Args:
            session: The aiohttp client session.
            host: The Evon system URL (None for remote connections).
            username: The username for authentication.
            password: The password (plain text).
            is_remote: Whether this is a remote connection via my.evon-smarthome.com.
            engine_id: The engine ID for remote connections.
        """
        if not self._use_websocket:
            return

        from ..ws_client import EvonWsClient
        from ..ws_mappings import build_subscription_list

        connection_type = "remote" if is_remote else "local"
        _LOGGER.info("Setting up %s WebSocket for real-time updates", connection_type)

        self._ws_client = EvonWsClient(
            host=host or "",
            username=username,
            password=password,
            session=session,
            on_values_changed=self._handle_ws_values_changed,
            on_connection_state=self._handle_ws_connection_state,
            is_remote=is_remote,
            engine_id=engine_id,
        )

        # Start the WebSocket client
        await self._ws_client.start()

        # Connect WS client to API for control operations
        self.api.set_ws_client(self._ws_client)

        # Build subscription list from cached instances
        if self._instances_cache:
            subscriptions = build_subscription_list(self._instances_cache)
            if subscriptions:
                await self._ws_client.subscribe_instances(subscriptions)
                _LOGGER.debug(
                    "Subscribed to %d instances via WebSocket",
                    len(subscriptions),
                )

    async def async_shutdown_websocket(self) -> None:
        """Shut down the WebSocket client."""
        if self._ws_client:
            _LOGGER.debug("Shutting down WebSocket client")
            # Disconnect WS from API before stopping
            self.api.set_ws_client(None)
            await self._ws_client.stop()
            self._ws_client = None
            self._ws_connected = False

    def _handle_ws_connection_state(self, connected: bool) -> None:
        """Handle WebSocket connection state changes.

        Args:
            connected: Whether the WebSocket is now connected.
        """
        from homeassistant.components.persistent_notification import (
            async_create,
            async_dismiss,
        )

        from ..const import DOMAIN

        self._ws_connected = connected
        notification_id = f"{DOMAIN}_websocket_status"

        if connected:
            # Reduce polling frequency when WebSocket is connected
            self.update_interval = timedelta(seconds=WS_POLL_INTERVAL)
            _LOGGER.info(
                "WebSocket connected, reduced poll interval to %d seconds",
                WS_POLL_INTERVAL,
            )
            # Dismiss any disconnect notification
            async_dismiss(self.hass, notification_id)
        else:
            # Resume normal polling when WebSocket disconnects
            self.update_interval = timedelta(seconds=self._base_scan_interval)
            _LOGGER.info(
                "WebSocket disconnected, resumed poll interval to %d seconds",
                self._base_scan_interval,
            )
            # Create disconnect notification
            async_create(
                self.hass,
                message=(
                    "The WebSocket connection to your Evon system has been lost. "
                    "Real-time updates are temporarily unavailable. "
                    "The integration is using HTTP polling as fallback.\n\n"
                    "The connection will automatically reconnect when available. "
                    "If this persists, try calling the `evon.reconnect_websocket` service."
                ),
                title="Evon WebSocket Disconnected",
                notification_id=notification_id,
            )
            # Trigger an immediate refresh to get latest state
            self.hass.async_create_task(self.async_request_refresh())

    def _handle_ws_values_changed(
        self,
        instance_id: str,
        properties: dict[str, Any],
    ) -> None:
        """Handle WebSocket ValuesChanged events.

        Args:
            instance_id: The instance ID that changed.
            properties: Dictionary of changed property names to values.
        """
        if not self.data:
            return

        from ..ws_mappings import CLASS_TO_TYPE, ws_to_coordinator_data

        # Find the entity in our data
        # First, find what type of entity this is
        entity_type: str | None = None
        entity_index: int | None = None

        # Search through all entity types to find this instance
        for etype in CLASS_TO_TYPE.values():
            if etype not in self.data:
                continue
            for idx, entity in enumerate(self.data[etype]):
                if entity.get("id") == instance_id:
                    entity_type = etype
                    entity_index = idx
                    break
            if entity_type:
                break

        if entity_type is None or entity_index is None:
            # Unknown instance, might be a type we don't track
            _LOGGER.debug(
                "WebSocket update for unknown instance: %s",
                instance_id,
            )
            return

        # Get existing entity data for derived value computation
        entity = self.data[entity_type][entity_index]

        # Convert WebSocket properties to coordinator format
        coord_data = ws_to_coordinator_data(entity_type, properties, entity)
        if not coord_data:
            return

        # Update the entity data in place
        for key, value in coord_data.items():
            if key in entity:
                old_value = entity[key]
                entity[key] = value
                if old_value != value:
                    _LOGGER.debug(
                        "WebSocket update: %s.%s: %s -> %s",
                        instance_id,
                        key,
                        old_value,
                        value,
                    )

                    # Fire doorbell event when doorbell_triggered transitions to True
                    if entity_type == "intercoms" and key == "doorbell_triggered" and value is True:
                        self.hass.bus.async_fire(
                            f"{DOMAIN}_doorbell", {"device_id": instance_id, "name": entity.get("name", "")}
                        )
                        _LOGGER.info("Doorbell event fired for %s", instance_id)

        # Notify listeners of the update
        self.async_set_updated_data(self.data)

    @property
    def ws_connected(self) -> bool:
        """Return whether WebSocket is connected."""
        return self._ws_connected

    @property
    def use_websocket(self) -> bool:
        """Return whether WebSocket is enabled."""
        return self._use_websocket
