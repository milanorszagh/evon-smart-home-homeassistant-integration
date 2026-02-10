"""Data update coordinator for Evon Smart Home."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
from typing import TYPE_CHECKING, Any

import aiohttp
from homeassistant.components.recorder.statistics import statistics_during_period
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from ..api import EvonApi, EvonApiError
from ..const import (
    CONNECTION_FAILURE_THRESHOLD,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    ENERGY_STATS_FAILURE_LOG_THRESHOLD,
    ENTITY_TYPE_AIR_QUALITY,
    ENTITY_TYPE_BATHROOM_RADIATORS,
    ENTITY_TYPE_BLINDS,
    ENTITY_TYPE_CAMERAS,
    ENTITY_TYPE_CLIMATES,
    ENTITY_TYPE_HOME_STATES,
    ENTITY_TYPE_INTERCOMS,
    ENTITY_TYPE_LIGHTS,
    ENTITY_TYPE_SCENES,
    ENTITY_TYPE_SECURITY_DOORS,
    ENTITY_TYPE_SMART_METERS,
    ENTITY_TYPE_SWITCHES,
    ENTITY_TYPE_VALVES,
    EVON_CLASS_SCENE,
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

        # Energy statistics failure tracking
        self._energy_stats_consecutive_failures = 0

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

            # Prefetch all instance details in parallel (eliminates N+1 API calls)
            # Scenes don't need detail fetch; everything else does
            instance_ids_to_fetch = []
            for inst in instances:
                class_name = inst.get("ClassName", "")
                inst_id = inst.get("ID", "")
                if not inst_id:
                    continue
                if class_name != EVON_CLASS_SCENE:
                    instance_ids_to_fetch.append(inst_id)

            # Also fetch Base.ehThermostat for season mode
            if "Base.ehThermostat" not in instance_ids_to_fetch:
                instance_ids_to_fetch.append("Base.ehThermostat")

            async def _safe_get_instance(iid: str) -> tuple[str, dict[str, Any] | None]:
                try:
                    return iid, await self.api.get_instance(iid)
                except EvonApiError as err:
                    _LOGGER.warning("Failed to fetch instance %s: %s", iid, err)
                    return iid, None

            results = await asyncio.gather(*[_safe_get_instance(iid) for iid in instance_ids_to_fetch])
            instance_details: dict[str, dict[str, Any]] = {
                iid: details for iid, details in results if details is not None
            }

            # Extract season mode from prefetched data
            thermostat_details = instance_details.get("Base.ehThermostat", {})
            season_mode = self._extract_season_mode(thermostat_details)

            # Process all device types (synchronous - just dict lookups now)
            lights = process_lights(instance_details, instances, self._get_room_name)
            blinds = process_blinds(instance_details, instances, self._get_room_name)
            climates = process_climates(instance_details, instances, self._get_room_name, season_mode)
            switches = process_switches(instance_details, instances, self._get_room_name)
            smart_meters = process_smart_meters(instance_details, instances, self._get_room_name)
            air_quality = process_air_quality(instance_details, instances, self._get_room_name)
            valves = process_valves(instance_details, instances, self._get_room_name)
            home_states = process_home_states(instance_details, instances)
            bathroom_radiators = process_bathroom_radiators(instance_details, instances, self._get_room_name)
            scenes = process_scenes(instances)
            security_doors = process_security_doors(instance_details, instances, self._get_room_name)
            intercoms = process_intercoms(instance_details, instances, self._get_room_name)
            cameras = process_cameras(instance_details, instances, self._get_room_name)

            _LOGGER.debug(
                "Processed entities: lights=%d, climates=%d, smart_meters=%d, blinds=%d",
                len(lights),
                len(climates),
                len(smart_meters),
                len(blinds),
            )

            # Success - reset failure counter and clear any connection repair
            self._consecutive_failures = 0
            if self._repair_created:
                ir.async_delete_issue(self.hass, DOMAIN, REPAIR_CONNECTION_FAILED)
                self._repair_created = False
                _LOGGER.info("Connection restored, cleared connection failure repair")

            result = {
                ENTITY_TYPE_LIGHTS: lights,
                ENTITY_TYPE_BLINDS: blinds,
                ENTITY_TYPE_CLIMATES: climates,
                ENTITY_TYPE_SWITCHES: switches,
                ENTITY_TYPE_SMART_METERS: smart_meters,
                ENTITY_TYPE_AIR_QUALITY: air_quality,
                ENTITY_TYPE_VALVES: valves,
                ENTITY_TYPE_HOME_STATES: home_states,
                ENTITY_TYPE_BATHROOM_RADIATORS: bathroom_radiators,
                ENTITY_TYPE_SCENES: scenes,
                ENTITY_TYPE_SECURITY_DOORS: security_doors,
                ENTITY_TYPE_INTERCOMS: intercoms,
                ENTITY_TYPE_CAMERAS: cameras,
                "rooms": self._rooms_cache if self._sync_areas else {},
                "season_mode": season_mode,
            }

            # Calculate energy_today and energy_this_month for smart meters
            await self._calculate_energy_today_and_month(smart_meters)

            # Cache successful data for use during transient failures
            self._last_successful_data = result

            # Import energy statistics for smart meters (backfill historical data)
            for meter in smart_meters:
                self._maybe_import_energy_statistics(meter["id"], meter, force=True)

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

    def _extract_season_mode(self, thermostat_details: dict[str, Any]) -> bool:
        """Extract the global season mode from prefetched thermostat data.

        Args:
            thermostat_details: Prefetched Base.ehThermostat instance details.

        Returns:
            True if cooling (summer), False if heating (winter)
        """
        if not thermostat_details:
            _LOGGER.warning("No thermostat data available, defaulting to heating mode")
            return False

        is_cool = thermostat_details.get("IsCool")

        if is_cool is None:
            _LOGGER.warning("Season mode response missing 'IsCool' field, defaulting to heating mode")
            return False

        if not isinstance(is_cool, bool):
            _LOGGER.warning(
                "Season mode 'IsCool' has unexpected type %s (value: %s), attempting to interpret as boolean",
                type(is_cool).__name__,
                is_cool,
            )
            if is_cool in (0, "0", "false", "False", "no", "No"):
                return False
            if is_cool in (1, "1", "true", "True", "yes", "Yes"):
                return True
            _LOGGER.warning("Could not interpret season mode value, defaulting to heating mode")
            return False

        return is_cool

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
        if not self.data:
            return None
        entities = self.data.get(entity_type)
        if not entities or not isinstance(entities, list):
            return None
        for entity in entities:
            if entity and entity.get("id") == instance_id:
                return entity
        return None

    # Legacy getter methods for backwards compatibility
    def get_light_data(self, instance_id: str) -> dict[str, Any] | None:
        """Get data for a specific light."""
        return self.get_entity_data(ENTITY_TYPE_LIGHTS, instance_id)

    def get_blind_data(self, instance_id: str) -> dict[str, Any] | None:
        """Get data for a specific blind."""
        return self.get_entity_data(ENTITY_TYPE_BLINDS, instance_id)

    def get_climate_data(self, instance_id: str) -> dict[str, Any] | None:
        """Get data for a specific climate."""
        return self.get_entity_data(ENTITY_TYPE_CLIMATES, instance_id)

    def get_switch_data(self, instance_id: str) -> dict[str, Any] | None:
        """Get data for a specific switch."""
        return self.get_entity_data(ENTITY_TYPE_SWITCHES, instance_id)

    def get_smart_meter_data(self, instance_id: str) -> dict[str, Any] | None:
        """Get data for a specific smart meter."""
        return self.get_entity_data(ENTITY_TYPE_SMART_METERS, instance_id)

    def get_air_quality_data(self, instance_id: str) -> dict[str, Any] | None:
        """Get data for a specific air quality sensor."""
        return self.get_entity_data(ENTITY_TYPE_AIR_QUALITY, instance_id)

    def get_valve_data(self, instance_id: str) -> dict[str, Any] | None:
        """Get data for a specific valve."""
        return self.get_entity_data(ENTITY_TYPE_VALVES, instance_id)

    def get_home_state_data(self, instance_id: str) -> dict[str, Any] | None:
        """Get data for a specific home state."""
        return self.get_entity_data(ENTITY_TYPE_HOME_STATES, instance_id)

    def get_bathroom_radiator_data(self, instance_id: str) -> dict[str, Any] | None:
        """Get data for a specific bathroom radiator."""
        return self.get_entity_data(ENTITY_TYPE_BATHROOM_RADIATORS, instance_id)

    def get_active_home_state(self) -> str | None:
        """Get the currently active home state ID."""
        if not self.data:
            return None
        home_states = self.data.get(ENTITY_TYPE_HOME_STATES)
        if not home_states or not isinstance(home_states, list):
            return None
        for state in home_states:
            if state and state.get("active"):
                return state.get("id")
        return None

    def get_home_states(self) -> list[dict[str, Any]]:
        """Get all home states."""
        if not self.data:
            return []
        home_states = self.data.get(ENTITY_TYPE_HOME_STATES)
        if not home_states or not isinstance(home_states, list):
            return []
        return home_states

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
        return self.get_entity_data(ENTITY_TYPE_SCENES, instance_id)

    def get_scenes(self) -> list[dict[str, Any]]:
        """Get all scenes."""
        if not self.data:
            return []
        scenes = self.data.get(ENTITY_TYPE_SCENES)
        if not scenes or not isinstance(scenes, list):
            return []
        return scenes

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
            get_session=lambda: async_get_clientsession(self.hass),
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
        # Capture data reference at start to detect concurrent replacement by HTTP poll
        data_snapshot = self.data
        if not data_snapshot or not properties:
            return

        from ..ws_mappings import CLASS_TO_TYPE, ws_to_coordinator_data

        # Find the entity in our data
        # First, find what type of entity this is
        entity_type: str | None = None
        entity_index: int | None = None
        entities_ref: list[dict[str, Any]] | None = None

        # Search through all entity types to find this instance
        for etype in CLASS_TO_TYPE.values():
            entities = data_snapshot.get(etype)
            if not entities or not isinstance(entities, list):
                continue
            for idx, entity in enumerate(entities):
                if entity and entity.get("id") == instance_id:
                    entity_type = etype
                    entity_index = idx
                    entities_ref = entities
                    break
            if entity_type:
                break

        if entity_type is None or entity_index is None or entities_ref is None:
            # Unknown instance, might be a type we don't track
            _LOGGER.debug(
                "WebSocket update for unknown instance: %s",
                instance_id,
            )
            return

        # Get existing entity data for derived value computation
        # Double-check entity exists (defensive check for race conditions)
        if data_snapshot.get(entity_type) is not entities_ref:
            _LOGGER.debug("Entity list replaced during WebSocket update for %s", instance_id)
            return
        if entity_index >= len(entities_ref):
            _LOGGER.debug("Entity list changed during WebSocket update for %s", instance_id)
            return
        entity = entities_ref[entity_index]
        if not entity:
            return

        # Convert WebSocket properties to coordinator format
        try:
            coord_data = ws_to_coordinator_data(entity_type, properties, entity)
        except Exception as err:
            _LOGGER.error(
                "Failed to convert WebSocket data for %s (%s): %s. Requesting coordinator refresh to sync state.",
                instance_id,
                entity_type,
                err,
                exc_info=True,
            )
            # Schedule HTTP refresh to recover from the conversion failure
            self.hass.async_create_task(self.async_request_refresh())
            return

        if not coord_data:
            return

        # Re-check data reference before mutating — if HTTP poll replaced self.data
        # between our snapshot and now, apply updates to the NEW data instead of the old one
        current_data = self.data
        if current_data is not data_snapshot:
            _LOGGER.debug("Data replaced during WebSocket processing for %s, retargeting to new data", instance_id)
            # Re-find the entity in the new data
            new_entities = current_data.get(entity_type) if current_data else None
            if new_entities and isinstance(new_entities, list):
                entity = None
                for e in new_entities:
                    if e and e.get("id") == instance_id:
                        entity = e
                        break
            if entity is None:
                _LOGGER.debug("Entity %s not found in new data, dropping WS update", instance_id)
                return
            data_snapshot = current_data

        # Final consistency check: if data was replaced again between retarget and now, drop update
        final_data = self.data
        if final_data is not data_snapshot:
            _LOGGER.debug("Data replaced again during WS processing for %s, dropping update", instance_id)
            self.hass.async_create_task(self.async_request_refresh())
            return

        # Update the entity data in place
        # Note: ws_to_coordinator_data already validates which keys to return,
        # so we apply all keys including ones not in the initial HTTP poll
        for key, value in coord_data.items():
            old_value = entity.get(key)
            entity[key] = value
            if old_value != value:
                _LOGGER.debug(
                    "WebSocket update: %s.%s: %s -> %s",
                    instance_id,
                    key,
                    old_value,
                    value,
                )

                # Fire doorbell event only on False→True transition (not every WS update)
                if (
                    entity_type == ENTITY_TYPE_INTERCOMS
                    and key == "doorbell_triggered"
                    and value is True
                    and old_value is not True
                ):
                    self.hass.bus.async_fire(
                        f"{DOMAIN}_doorbell", {"device_id": instance_id, "name": entity.get("name", "")}
                    )
                    _LOGGER.info("Doorbell event fired for %s", instance_id)

        # Import energy statistics when smart meter data is received
        if entity_type == ENTITY_TYPE_SMART_METERS:
            self._maybe_import_energy_statistics(instance_id, entity)

        # Notify listeners
        self.async_set_updated_data(data_snapshot)

    def _maybe_import_energy_statistics(
        self,
        instance_id: str,
        entity_data: dict[str, Any],
        force: bool = False,
    ) -> None:
        """Import energy statistics for a smart meter if data is available.

        Args:
            instance_id: The smart meter instance ID.
            entity_data: The entity data dictionary.
            force: If True, bypass rate limiting (for initial backfill).
        """
        # Check if we have the required energy data for statistics import
        energy_data_month = entity_data.get("energy_data_month")

        if not energy_data_month:
            return

        # Import the statistics module and trigger import
        from ..statistics import import_energy_statistics

        self.hass.async_create_task(
            import_energy_statistics(
                hass=self.hass,
                meter_id=instance_id,
                meter_name=entity_data.get("name") or instance_id,
                energy_data_month=energy_data_month,
                feed_in_data_month=entity_data.get("feed_in_data_month"),
                energy_data_year=entity_data.get("energy_data_year"),
                force=force,
            )
        )
        _LOGGER.debug(
            "Triggered energy statistics import for %s (force=%s)",
            instance_id,
            force,
        )

    async def _calculate_energy_today_and_month(self, smart_meters: list[dict[str, Any]]) -> None:
        """Calculate energy_today and energy_this_month for smart meters.

        Uses HA statistics to get today's consumption and combines with
        Evon's EnergyDataMonth for this month's total.
        """
        now = dt_util.now()
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_day = now.day  # Day of month (1-31)

        _LOGGER.debug(
            "Calculating energy for %d smart meters, today_day=%d, start_of_day=%s",
            len(smart_meters),
            today_day,
            start_of_day.isoformat(),
        )

        for meter in smart_meters:
            meter_name = meter.get("name", "")
            # Build the entity_id for the Energy Total sensor
            # Format: sensor.{name}_energy_total (lowercase, spaces to underscores)
            entity_id = f"sensor.{meter_name.lower().replace(' ', '_')}_energy_total"

            _LOGGER.debug("Querying statistics for entity_id: %s", entity_id)

            energy_today = None
            try:
                # Query HA statistics for today's energy consumption
                stats = await self.hass.async_add_executor_job(
                    statistics_during_period,
                    self.hass,
                    start_of_day,
                    now,
                    [entity_id],
                    "hour",
                    {"energy": UnitOfEnergy.KILO_WATT_HOUR},
                    {"change"},
                )

                _LOGGER.debug("Statistics result keys: %s", list(stats.keys()) if stats else "None")

                if entity_id in stats:
                    # Sum all hourly changes for today
                    hourly_changes = [s.get("change", 0) or 0 for s in stats[entity_id]]
                    _LOGGER.debug("Hourly changes for %s: %s", entity_id, hourly_changes)
                    energy_today = sum(hourly_changes)
                    energy_today = round(energy_today, 2) if energy_today > 0 else 0.0
                    _LOGGER.debug("Calculated energy_today for %s: %s kWh", meter_name, energy_today)
                else:
                    _LOGGER.debug("No statistics found for %s in result", entity_id)
                # Success — reset failure counter
                self._energy_stats_consecutive_failures = 0
            except (HomeAssistantError, ValueError, TypeError, KeyError) as err:
                self._energy_stats_consecutive_failures += 1
                if self._energy_stats_consecutive_failures >= ENERGY_STATS_FAILURE_LOG_THRESHOLD:
                    _LOGGER.error(
                        "Energy statistics for %s failed %d times consecutively: %s. "
                        "Check that the recorder component is running and the entity exists.",
                        entity_id,
                        self._energy_stats_consecutive_failures,
                        err,
                    )
                else:
                    _LOGGER.warning("Could not get energy statistics for %s: %s", entity_id, err)
            except Exception as err:
                self._energy_stats_consecutive_failures += 1
                if self._energy_stats_consecutive_failures >= ENERGY_STATS_FAILURE_LOG_THRESHOLD:
                    _LOGGER.error(
                        "Energy statistics for %s failed %d times consecutively: %s. "
                        "Check that the recorder component is running and the entity exists.",
                        entity_id,
                        self._energy_stats_consecutive_failures,
                        err,
                        exc_info=True,
                    )
                else:
                    _LOGGER.warning(
                        "Could not get energy statistics for %s: %s",
                        entity_id,
                        err,
                        exc_info=True,
                    )

            # Store energy_today in the meter data
            meter["energy_today_calculated"] = energy_today
            _LOGGER.debug("Set energy_today_calculated=%s for %s", energy_today, meter_name)

            # Calculate energy_this_month
            energy_data_month = meter.get("energy_data_month")
            _LOGGER.debug(
                "energy_data_month for %s: %d items, last 5: %s",
                meter_name,
                len(energy_data_month) if energy_data_month else 0,
                energy_data_month[-5:] if energy_data_month else "None",
            )

            if energy_data_month and isinstance(energy_data_month, list):
                # Days from this month excluding today: yesterday back to day 1
                days_this_month_excluding_today = today_day - 1

                month_sum = 0.0
                if days_this_month_excluding_today > 0 and len(energy_data_month) >= days_this_month_excluding_today:
                    relevant_days = energy_data_month[-days_this_month_excluding_today:]
                    _LOGGER.debug(
                        "Using %d days from energy_data_month: %s", days_this_month_excluding_today, relevant_days
                    )
                    for v in relevant_days:
                        if isinstance(v, (int, float)):
                            month_sum += float(v)

                # Add today's consumption
                if energy_today is not None:
                    month_sum += energy_today

                meter["energy_this_month_calculated"] = round(month_sum, 2)
                _LOGGER.debug(
                    "Set energy_this_month_calculated=%s for %s (month_sum=%s + today=%s)",
                    meter["energy_this_month_calculated"],
                    meter_name,
                    month_sum - (energy_today or 0),
                    energy_today,
                )
            else:
                meter["energy_this_month_calculated"] = energy_today
                _LOGGER.debug("No energy_data_month, set energy_this_month_calculated=%s", energy_today)

    @property
    def ws_client(self) -> EvonWsClient | None:
        """Return the WebSocket client instance."""
        return self._ws_client

    @property
    def ws_connected(self) -> bool:
        """Return whether WebSocket is connected."""
        return self._ws_connected

    @property
    def use_websocket(self) -> bool:
        """Return whether WebSocket is enabled."""
        return self._use_websocket
