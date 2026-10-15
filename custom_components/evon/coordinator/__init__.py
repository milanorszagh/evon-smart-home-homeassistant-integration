"""Data update coordinator for Evon Smart Home."""

from __future__ import annotations

import asyncio
import contextlib
from datetime import datetime, timedelta
import logging
import time
from typing import TYPE_CHECKING, Any

import aiohttp
from homeassistant.components.recorder import get_instance as get_recorder_instance
from homeassistant.components.recorder.statistics import statistics_during_period
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from ..api import EvonApi, EvonApiError, EvonAuthError, EvonRateLimitError
from ..const import (
    CONF_WEATHER_HOME_CONNECT_ID,
    CONF_WEATHER_STATION_ID,
    CONNECTION_FAILURE_THRESHOLD,
    DEFAULT_BUTTON_DOUBLE_CLICK_DELAY,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    ENERGY_STATS_FAILURE_LOG_THRESHOLD,
    ENTITY_TYPE_AIR_QUALITY,
    ENTITY_TYPE_BATHROOM_RADIATORS,
    ENTITY_TYPE_BLINDS,
    ENTITY_TYPE_BUTTON_EVENTS,
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
    ENTITY_TYPE_WEATHER,
    POLL_DETAIL_MAX_IN_FLIGHT,
    REPAIR_CONNECTION_FAILED,
    REPAIR_WEBSOCKET_DISCONNECTED,
    WEATHER_REDISCOVERY_INTERVAL,
    WS_POLL_INTERVAL,
)
from ..ws_mappings import get_entity_type, get_ws_mapped_keys
from .button_press import ButtonPressDetector
from .processors import (
    process_air_quality,
    process_bathroom_radiators,
    process_blinds,
    process_button_events,
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
    process_weather_stations,
)
from .processors.weather import find_home_connect_instances, find_weather_stations_in

if TYPE_CHECKING:
    from ..ws_client import EvonWsClient

_LOGGER = logging.getLogger(__name__)


SEASON_MODE_INSTANCE_ID = "Base.ehThermostat"


def select_instances_for_detail_fetch(instances: list[dict[str, Any]]) -> list[str]:
    """Return the instance IDs the poll fetches details for.

    A controller lists hundreds of objects (logic blocks, notifications, rooms,
    configuration ...) but the processors only read details of *named* instances
    of the classes that become entities — 63 of 930 on the reference system
    (every processor skips unnamed instances: templates and unused channels).
    Buttons are WS-only and scenes are fire-and-forget, so neither needs details
    either. Fetching all 930 in parallel saturated the controller for ~20 s per
    poll and starved the camera snapshot requests (see AGENTS.md → Note #7).
    ``Base.ehThermostat`` (season mode) is always included.
    """
    ids: list[str] = []
    for inst in instances:
        inst_id = inst.get("ID", "")
        if not inst_id or not inst.get("Name"):
            continue
        entity_type = get_entity_type(inst.get("ClassName", ""))
        if entity_type is None or entity_type == ENTITY_TYPE_BUTTON_EVENTS:
            continue
        ids.append(inst_id)
    if SEASON_MODE_INSTANCE_ID not in ids:
        ids.append(SEASON_MODE_INSTANCE_ID)
    return ids


class EvonDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching Evon data."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: EvonApi,
        config_entry: ConfigEntry,
        scan_interval: int = DEFAULT_SCAN_INTERVAL,
        sync_areas: bool = False,
        use_websocket: bool = False,
        button_double_click_delay: float = DEFAULT_BUTTON_DOUBLE_CLICK_DELAY,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )
        self.api = api
        # Device-registry id of the hub device; set by async_setup_entry before the
        # platforms load. Entities link their devices to it via `via_device_id`.
        self.hub_device_id: str | None = None
        self._instances_cache: list[dict[str, Any]] = []
        self._sync_areas = sync_areas
        self._rooms_cache: dict[str, str] = {}
        self._consecutive_failures = 0
        self._repair_created = False
        self._last_successful_data: dict[str, Any] | None = None
        self._base_scan_interval = scan_interval

        # Energy statistics failure tracking
        self._energy_stats_consecutive_failures = 0

        # Entity data index for O(1) lookup by (entity_type, instance_id)
        self._data_index: dict[tuple[str, str], dict[str, Any]] = {}

        # Per-entity timestamp (time.monotonic()) of the most recent WS update.
        # Used to detect entities that were updated via WS during an in-flight
        # poll, so the poll's stale snapshot doesn't overwrite confirmed state.
        self._ws_update_timestamps: dict[tuple[str, str], float] = {}
        # Smart meters only: per-key timestamps of the last WS update. Meters push
        # readings every few seconds, so an entity-level timestamp lands inside
        # nearly every poll; the merge must keep only the keys the WS actually
        # updated during the poll (see _merge_ws_updates_into_poll_result).
        self._ws_key_update_timestamps: dict[tuple[str, str], dict[str, float]] = {}
        # Guards against a re-entrant concurrent poll (HA core does not serialize
        # _async_refresh — a recheck-triggered refresh can fire while a scheduled
        # poll is mid-flight). The flag drives the fast-path skip; the lock covers
        # the case the flag can't (no data yet, so nothing cached to return): two
        # concurrent FIRST refreshes serialize instead of racing on
        # _instances_cache / _rooms_cache / _ws_update_timestamps.
        self._update_in_progress = False
        self._update_lock = asyncio.Lock()
        # True while async_shutdown_websocket is stopping the WS client, so the
        # disconnect callback fired from stop() is not mistaken for a connection
        # failure (which would pop a spurious repair issue and schedule a full
        # poll against a session that is about to close).
        self._shutting_down = False
        # True when the most recent poll dropped one or more instances due to a
        # transient per-instance fetch error (_safe_get_instance returned None).
        # Setup uses this to avoid deleting entities that are only transiently
        # missing (see _async_cleanup_stale_entities).
        self._last_poll_had_partial_failures = False
        # Discovered weather-station sources: list of (home_connect_id, station_id,
        # name). None = not yet discovered; re-discovered while empty so a station
        # that appears later is picked up (the heavy proxy listing only runs when a
        # Home Connect instance exists). Poll-only, read via the Home Connect proxy.
        self._weather_sources: list[tuple[str, str, str | None]] | None = None
        # time.monotonic() of the last auto-discovery; an empty result is retried
        # only after WEATHER_REDISCOVERY_INTERVAL (the discovery lists the shared
        # controller's whole instance tree through the proxy).
        self._weather_discovered_at: float | None = None
        # Safety-net poll statistics, exposed on the WebSocket status sensor so
        # the poll's cost and usefulness can be judged from real data (see
        # _record_poll_corrections).
        self.poll_count = 0
        self.last_poll_duration: float | None = None
        self.last_poll_instances_fetched: int | None = None
        self.poll_correction_count = 0
        self.last_poll_correction: str | None = None
        self.last_poll_correction_at: datetime | None = None

        # WebSocket support
        self._use_websocket = use_websocket
        self._ws_client: EvonWsClient | None = None
        self._ws_connected = False

        # Button press detection — uses standalone detector for testability
        self._button_detector: ButtonPressDetector | None = None
        self._button_double_click_delay = button_double_click_delay

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
        # Skip a re-entrant concurrent fetch. HA core does not serialize
        # _async_refresh, so a recheck-triggered async_request_refresh can start a
        # second ~930-instance poll while a scheduled one is mid-flight — the two
        # would race on _instances_cache / _rooms_cache / _ws_update_timestamps.
        # If a poll is already running, return current data; the in-flight poll
        # delivers fresh state when it completes.
        if self._update_in_progress and self.data is not None:
            _LOGGER.debug("Coordinator poll already in progress; skipping re-entrant refresh")
            return self.data
        # The fast path above can't help before the first successful poll (no
        # data to return), so serialize via the lock instead — duplicate work in
        # that rare startup window is fine, interleaved cache mutation is not.
        await self._update_lock.acquire()
        self._update_in_progress = True
        # Capture the poll's start time so the merge step at the end can tell
        # which WS updates arrived during the poll (and must be preserved
        # against the poll's stale snapshot).
        poll_start_time = time.monotonic()
        try:
            # Get all instances
            instances = await self.api.get_instances()
            self._instances_cache = instances

            # Update instance class cache for WebSocket routing
            self.api.set_instance_classes(instances)

            # Fetch rooms if area sync is enabled
            if self._sync_areas:
                await self._fetch_rooms()

            # Prefetch the details the processors read (only entity classes, see
            # select_instances_for_detail_fetch) with bounded concurrency: the
            # controller answers one GET in ~100 ms when idle, but an unbounded
            # burst backs it up for 20 s+ and starves the camera snapshot requests.
            instance_ids_to_fetch = select_instances_for_detail_fetch(instances)
            detail_semaphore = asyncio.Semaphore(POLL_DETAIL_MAX_IN_FLIGHT)

            async def _safe_get_instance(iid: str) -> tuple[str, dict[str, Any] | None]:
                async with detail_semaphore:
                    try:
                        return iid, await self.api.get_instance(iid)
                    except EvonApiError as err:
                        _LOGGER.warning("Failed to fetch instance %s: %s", iid, err)
                        return iid, None

            results = await asyncio.gather(*[_safe_get_instance(iid) for iid in instance_ids_to_fetch])
            self.last_poll_instances_fetched = len(instance_ids_to_fetch)
            instance_details: dict[str, dict[str, Any]] = {
                iid: details for iid, details in results if details is not None
            }
            # Record whether any instance was dropped by a transient fetch error.
            # Setup uses this to avoid removing entities that are only transiently
            # missing (see _async_cleanup_stale_entities).
            self._last_poll_had_partial_failures = any(details is None for _, details in results)

            # Weather stations live on a shared controller, read via the Home
            # Connect proxy (poll-only; not in the apartment instance list).
            weather_raw = await self._poll_weather_stations()

            # Extract season mode from prefetched data
            thermostat_details = instance_details.get(SEASON_MODE_INSTANCE_ID, {})
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
            button_events = process_button_events(instances, self._get_room_name)
            weather_stations = process_weather_stations(weather_raw)

            _LOGGER.debug(
                "Processed entities: lights=%d, climates=%d, smart_meters=%d, blinds=%d, button_events=%d",
                len(lights),
                len(climates),
                len(smart_meters),
                len(blinds),
                len(button_events),
            )

            # Success - reset failure counter and clear any connection repair
            self._consecutive_failures = 0
            if self._repair_created:
                ir.async_delete_issue(self.hass, DOMAIN, f"{REPAIR_CONNECTION_FAILED}_{self.config_entry.entry_id}")
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
                ENTITY_TYPE_BUTTON_EVENTS: button_events,
                ENTITY_TYPE_WEATHER: weather_stations,
                "rooms": self._rooms_cache if self._sync_areas else {},
                "season_mode": season_mode,
            }

            # Calculate energy_today and energy_this_month for smart meters.
            # This MUST run before the merge/index-build tail below: it is the
            # only remaining `await` in this method, and the coordinator assigns
            # self.data only after _async_update_data returns. If it ran after
            # _build_data_index, a WS event arriving during this await would find
            # _data_index already pointing at the new result dicts while self.data
            # still held the old lists — the WS handler's identity-based list
            # replacement (`e is entity`) could never match, so the update would
            # land only in the index and the poll dict (chattiest for meters)
            # would be orphaned without its calculated fields.
            await self._calculate_energy_today_and_month(smart_meters)

            # Preserve any WS updates that arrived during this poll.
            # The poll's REST snapshot was taken at poll_start_time; entities
            # that received a WS update after that have fresher state than the
            # poll's result and must not be overwritten by it (see
            # _merge_ws_updates_into_poll_result for the rationale).
            # INVARIANT: no `await` between here and `return result` — see above.
            self._record_poll_corrections(result, poll_start_time)
            self._merge_ws_updates_into_poll_result(result, poll_start_time)

            # Build O(1) lookup index
            self._build_data_index(result)

            # Prune timestamps for entities that no longer exist (entity removed,
            # renamed, or otherwise absent from this poll's result).
            self._ws_update_timestamps = {k: v for k, v in self._ws_update_timestamps.items() if k in self._data_index}
            self._ws_key_update_timestamps = {
                k: v for k, v in self._ws_key_update_timestamps.items() if k in self._data_index
            }

            # Cache successful data for use during transient failures
            self._last_successful_data = result

            # Import energy statistics for smart meters (backfill historical data).
            # force=False so the MIN_IMPORT_INTERVAL (1h) rate limit applies: the
            # first poll after startup still backfills (no prior import recorded),
            # then imports at most hourly. Forcing here reran a full ~44-row
            # rewrite per meter on every poll (30-60s), which the WS path already
            # avoids by using force=False.
            for meter in smart_meters:
                self._maybe_import_energy_statistics(meter["id"], meter)

            self.poll_count += 1
            self.last_poll_duration = round(time.monotonic() - poll_start_time, 2)
            return result

        except EvonRateLimitError as err:
            # Transient login throttle — treat as a normal transient failure
            # (keep cached data), not an auth failure that would pop a spurious
            # reauth dialog. Must be caught before EvonAuthError (it subclasses it).
            return self._handle_api_error(err)
        except EvonAuthError as err:
            raise ConfigEntryAuthFailed(f"Authentication failed: {err}") from err
        except EvonApiError as err:
            return self._handle_api_error(err)
        finally:
            self._update_in_progress = False
            self._update_lock.release()

    @property
    def last_poll_had_partial_failures(self) -> bool:
        """True when the most recent poll dropped instances via transient fetch errors.

        Setup uses this to skip stale-entity cleanup after a partial poll
        (RV-D6): a transiently missing instance must not get its entity — and
        registry customizations — deleted.
        """
        return self._last_poll_had_partial_failures

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
                f"{REPAIR_CONNECTION_FAILED}_{self.config_entry.entry_id}",
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

    async def _discover_weather_sources(self) -> list[tuple[str, str, str | None]]:
        """Discover weather stations reachable via a Home Connect proxy.

        Weather stations live on a shared controller and are read through the
        apartment's Home Connect proxy. Result is cached in ``_weather_sources``.
        A cached non-empty list is reused; an empty result (no station yet, or the
        proxy failed) is re-discovered after ``WEATHER_REDISCOVERY_INTERVAL`` so a
        station that appears later is picked up without listing the shared
        controller on every poll (the platforms add entities for new stations).
        The two options
        (``CONF_WEATHER_HOME_CONNECT_ID`` / ``CONF_WEATHER_STATION_ID``), when both
        set, bypass auto-discovery entirely.

        Returns:
            List of (home_connect_id, station_id, name) tuples (name may be None
            for an options override; the processor falls back to the polled Name).
        """
        if self._weather_sources:
            return self._weather_sources

        options = self.config_entry.options if self.config_entry else {}
        hc_override = (options.get(CONF_WEATHER_HOME_CONNECT_ID) or "").strip()
        station_override = (options.get(CONF_WEATHER_STATION_ID) or "").strip()
        if hc_override and station_override:
            self._weather_sources = [(hc_override, station_override, None)]
            _LOGGER.debug(
                "Weather station source from options: proxy=%s station=%s",
                hc_override,
                station_override,
            )
            return self._weather_sources

        proxies = find_home_connect_instances(self._instances_cache)
        if not proxies:
            self._weather_sources = []
            return self._weather_sources

        if (
            self._weather_sources is not None
            and self._weather_discovered_at is not None
            and time.monotonic() - self._weather_discovered_at < WEATHER_REDISCOVERY_INTERVAL
        ):
            return self._weather_sources  # empty, retried after the back-off
        self._weather_discovered_at = time.monotonic()

        sources: list[tuple[str, str, str | None]] = []
        for proxy in proxies:
            hc_id = proxy["id"]
            try:
                remote = await self.api.get_via_home_connect(hc_id, "/instances")
            except Exception as err:  # tolerate proxy/remote failures
                _LOGGER.debug("Weather discovery via proxy %s failed: %s", hc_id, err)
                continue
            for station in find_weather_stations_in(remote):
                sources.append((hc_id, station["id"], station.get("name")))

        self._weather_sources = sources
        if sources:
            _LOGGER.debug("Discovered %d weather station(s) via Home Connect", len(sources))
        return sources

    async def _poll_weather_stations(self) -> list[dict[str, Any]]:
        """Poll each discovered weather station through its Home Connect proxy.

        Returns:
            Raw ``[{"id", "name", "data"}]`` list for ``process_weather_stations``;
            empty when there are no weather stations. Per-station failures are
            tolerated so one unreachable station never fails the whole poll.
        """
        sources = await self._discover_weather_sources()
        if not sources:
            return []

        async def _fetch(source: tuple[str, str, str | None]) -> dict[str, Any] | None:
            hc_id, station_id, name = source
            try:
                data = await self.api.get_via_home_connect(hc_id, f"/instances/{station_id}")
            except Exception as err:  # tolerate per-station failures
                _LOGGER.debug("Weather station %s poll failed: %s", station_id, err)
                return None
            if not isinstance(data, dict):
                return None
            return {"id": station_id, "name": name, "data": data}

        results = await asyncio.gather(*[_fetch(src) for src in sources])
        return [r for r in results if r is not None]

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
            str_val = str(is_cool).lower()
            if str_val in ("0", "false", "no"):
                return False
            if str_val in ("1", "true", "yes"):
                return True
            _LOGGER.warning("Could not interpret season mode value, defaulting to heating mode")
            return False

        return is_cool

    def _get_room_name(self, group: str) -> str:
        """Get room name for a group ID."""
        return self._rooms_cache.get(group, "") if self._sync_areas else ""

    def _build_data_index(self, data: dict[str, Any]) -> None:
        """Build O(1) lookup index from entity data."""
        index: dict[tuple[str, str], dict[str, Any]] = {}
        for entity_type, entities in data.items():
            if isinstance(entities, list):
                for entity in entities:
                    if entity and "id" in entity:
                        index[(entity_type, entity["id"])] = entity
        self._data_index = index

    def _merge_ws_updates_into_poll_result(self, result: dict[str, Any], poll_start_time: float) -> None:
        """Preserve WS updates that arrived during the in-flight poll.

        The HTTP poll's REST snapshot was taken near ``poll_start_time`` and
        completes ~10-25s later. Any entity updated via WebSocket since the
        poll started has fresher state than the poll's snapshot. Without this
        merge, the poll's stale result would overwrite confirmed state changes
        (e.g. a light turned on via HA service: WS confirms is_on=True at
        T+1s, then the poll completes at T+22s and reverts the cached state to
        is_on=False because its REST snapshot predates the WS event).

        Smart meters get a field-level merge instead of a plain replacement: the
        keys a WS event updated *during this poll* come from the WS entity (a poll
        snapshot taken 20 s earlier regressed the ``total_increasing`` ``energy``
        counter once and made the recorder flag the sensor); every other key
        comes from the poll, which just computed ``energy_today_calculated`` /
        ``energy_this_month_calculated`` and read the poll-only inputs. Meters
        push readings every few seconds, so merging all WS keys whenever any
        event landed would stop the poll from refreshing values the WS did not
        push (e.g. the daily array the controller shifts at midnight).
        """
        if not self._ws_update_timestamps:
            return

        for index_key, ws_ts in self._ws_update_timestamps.items():
            if ws_ts < poll_start_time:
                continue
            entity_type, instance_id = index_key
            ws_entity = self._data_index.get(index_key)
            if ws_entity is None:
                continue
            entities_list = result.get(entity_type)
            if not isinstance(entities_list, list):
                continue
            for idx, e in enumerate(entities_list):
                if e.get("id") == instance_id:
                    if entity_type == ENTITY_TYPE_SMART_METERS:
                        # New dict: readers may still hold either input. Only keys
                        # the WS updated during this poll override the poll's value.
                        key_ts = self._ws_key_update_timestamps.get(index_key, {})
                        merged = dict(e)
                        merged.update(
                            {k: ws_entity[k] for k, ts in key_ts.items() if ts >= poll_start_time and k in ws_entity}
                        )
                        entities_list[idx] = merged
                    else:
                        entities_list[idx] = ws_entity
                    _LOGGER.debug(
                        "Poll-WS merge: preserved WS update for %s/%s (WS at %.3fs, poll started %.3fs ago)",
                        entity_type,
                        instance_id,
                        ws_ts - poll_start_time,
                        time.monotonic() - poll_start_time,
                    )
                    break

    def _record_poll_corrections(self, result: dict[str, Any], poll_start_time: float) -> int:
        """Count values this poll changed that the WebSocket should have delivered.

        For every WS-covered entity that received *no* WS event during the poll,
        compare the poll's snapshot with the current, WS-maintained state on the
        keys mapped 1:1 from a WS property (derived values such as the meter's
        summed ``power`` differ by float rounding alone and are skipped). A
        difference means the device changed without a WS event — the safety-net
        poll was actually needed. The
        counters feed the WebSocket status sensor's attributes so the poll's
        usefulness (and interval) can be judged from real data. Only counted
        while the WebSocket is connected; without it the poll is the primary
        source and every change is expected.

        Returns:
            The number of corrected values in this poll.
        """
        if not self._ws_connected:
            return 0
        corrections: list[str] = []
        for entity_type, entities in result.items():
            if not isinstance(entities, list):
                continue
            ws_keys = get_ws_mapped_keys(entity_type)
            if not ws_keys:
                continue
            for poll_entity in entities:
                instance_id = poll_entity.get("id")
                if not instance_id:
                    continue
                index_key = (entity_type, instance_id)
                current = self._data_index.get(index_key)
                if current is None:
                    continue
                ws_ts = self._ws_update_timestamps.get(index_key)
                if ws_ts is not None and ws_ts >= poll_start_time:
                    continue  # WS is fresher; the merge keeps it
                for key in sorted(ws_keys):
                    if key in poll_entity and key in current and poll_entity[key] != current[key]:
                        corrections.append(
                            f"{entity_type}/{instance_id} {key}: {current[key]!r} -> {poll_entity[key]!r}"
                        )
        if corrections:
            self.poll_correction_count += len(corrections)
            self.last_poll_correction = corrections[-1]
            self.last_poll_correction_at = dt_util.utcnow()
            shown = "; ".join(corrections[:5])
            if len(corrections) > 5:
                shown += f"; ... ({len(corrections) - 5} more)"
            _LOGGER.info("Poll corrected %d value(s) the WebSocket did not deliver: %s", len(corrections), shown)
        return len(corrections)

    def get_entity_data(self, entity_type: str, instance_id: str) -> dict[str, Any] | None:
        """Get data for a specific entity via O(1) index lookup.

        Args:
            entity_type: The type of entity (lights, blinds, climates, switches,
                        smart_meters, air_quality, valves, home_states, scenes)
            instance_id: The instance ID to look up

        Returns:
            The entity data dictionary or None if not found
        """
        return self._data_index.get((entity_type, instance_id))

    def get_ws_update_timestamp(self, entity_type: str, instance_id: str) -> float | None:
        """Return the monotonic time of the most recent WS update for an entity.

        Used by the post-command recheck to tell a genuine WS confirmation (this
        timestamp advances) apart from an HTTP poll rebuild (it does not), so a
        stale in-flight poll completing during the quiesce window can't cancel
        the recheck safety net. Returns None if the entity has had no WS update.
        """
        return self._ws_update_timestamps.get((entity_type, instance_id))

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
            # stop() fires the disconnect callback when the socket was connected;
            # flag the shutdown so _handle_ws_connection_state doesn't treat our
            # own teardown as a connection failure.
            self._shutting_down = True
            try:
                await self._ws_client.stop()
            finally:
                self._shutting_down = False
            self._ws_client = None
            self._ws_connected = False
            # Cancel pending button press timers
            if self._button_detector is not None:
                self._button_detector.cancel_all_timers()
                self._button_detector = None
            # Clear caches (rebuilt on next _async_update_data call)
            self._instances_cache = []
            self._rooms_cache = {}
            self._last_successful_data = None

    def _handle_ws_connection_state(self, connected: bool) -> None:
        """Handle WebSocket connection state changes.

        Direct mutation of ``self.update_interval`` here is safe because HA's
        event loop is single-threaded and this callback runs on the same event
        loop as ``_async_update_data``, so there is no concurrent-access risk.

        Args:
            connected: Whether the WebSocket is now connected.
        """
        self._ws_connected = connected

        if not connected and (self._shutting_down or self.hass.is_stopping):
            # Intentional teardown (unload/reload/options save) or HA shutting
            # down, not a failure: no repair issue, no refresh against a session
            # that is closing.
            _LOGGER.debug("WebSocket stopped as part of shutdown; skipping disconnect repair and refresh")
            return

        if connected:
            # Reduce polling frequency when WebSocket is connected
            self.update_interval = timedelta(seconds=WS_POLL_INTERVAL)
            _LOGGER.info(
                "WebSocket connected, reduced poll interval to %d seconds",
                WS_POLL_INTERVAL,
            )
            # Clear any disconnect repair issue
            ir.async_delete_issue(self.hass, DOMAIN, f"{REPAIR_WEBSOCKET_DISCONNECTED}_{self.config_entry.entry_id}")
        else:
            # Resume normal polling when WebSocket disconnects
            self.update_interval = timedelta(seconds=self._base_scan_interval)
            _LOGGER.info(
                "WebSocket disconnected, resumed poll interval to %d seconds",
                self._base_scan_interval,
            )
            # Create disconnect repair issue
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                f"{REPAIR_WEBSOCKET_DISCONNECTED}_{self.config_entry.entry_id}",
                is_fixable=False,
                is_persistent=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key=REPAIR_WEBSOCKET_DISCONNECTED,
            )
            # Trigger an immediate refresh to get latest state
            self.hass.async_create_task(
                self.async_request_refresh(),
                name="evon_ws_disconnect_refresh",
            )

    def _handle_ws_values_changed(
        self,
        instance_id: str,
        properties: dict[str, Any],
    ) -> None:
        """Handle WebSocket ValuesChanged events with copy-on-write semantics.

        Creates a shallow copy of the entity dict before applying changes, then
        atomically replaces it in the entities list and _data_index. This prevents
        concurrent HTTP polls from reading partially-updated data.

        Args:
            instance_id: The instance ID that changed.
            properties: Dictionary of changed property names to values.
        """
        # Capture data reference at start to detect concurrent replacement by HTTP poll
        data_snapshot = self.data
        if not data_snapshot or not properties:
            return

        from ..ws_mappings import CLASS_TO_TYPE, ws_to_coordinator_data

        # Use _data_index for O(1) entity lookup instead of linear search
        entity_type: str | None = None
        entity: dict[str, Any] | None = None
        index_key: tuple[str, str] | None = None

        for etype in set(CLASS_TO_TYPE.values()):
            key = (etype, instance_id)
            found = self._data_index.get(key)
            if found is not None:
                entity_type = etype
                entity = found
                index_key = key
                break

        if entity_type is None or entity is None or index_key is None:
            # Unknown instance, might be a type we don't track
            _LOGGER.debug(
                "WebSocket update for unknown instance: %s",
                instance_id,
            )
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
            self.hass.async_create_task(
                self.async_request_refresh(),
                name="evon_ws_button_refresh",
            )
            return

        if not coord_data:
            return

        # Re-check data reference — if HTTP poll replaced self.data, re-find entity
        current_data = self.data
        if current_data is not data_snapshot:
            _LOGGER.debug("Data replaced during WebSocket processing for %s, retargeting to new data", instance_id)
            entity = self._data_index.get(index_key)
            if entity is None:
                _LOGGER.debug("Entity %s not found in new data, dropping WS update", instance_id)
                return
            data_snapshot = current_data

        # Final consistency check: if data was replaced again, drop update
        final_data = self.data
        if final_data is not data_snapshot:
            _LOGGER.debug("Data replaced again during WS processing for %s, dropping update", instance_id)
            self.hass.async_create_task(
                self.async_request_refresh(),
                name="evon_ws_values_refresh",
            )
            return

        # Copy-on-write: create a shallow copy of the entity before applying changes
        updated_entity: dict[str, Any] = dict(entity)

        # Apply all coord_data to the copy
        for key, value in coord_data.items():
            old_value = updated_entity.get(key)
            updated_entity[key] = value
            if old_value != value:
                _LOGGER.debug(
                    "WebSocket update: %s.%s: %s -> %s",
                    instance_id,
                    key,
                    old_value,
                    value,
                )

                # Fire doorbell event only on False->True transition (not every WS update)
                if (
                    entity_type == ENTITY_TYPE_INTERCOMS
                    and key == "doorbell_triggered"
                    and value is True
                    and old_value is not True
                ):
                    self.hass.bus.async_fire(
                        f"{DOMAIN}_doorbell", {"device_id": instance_id, "name": updated_entity.get("name", "")}
                    )
                    _LOGGER.info("Doorbell event fired for %s", instance_id)

            # Button press detection: process EVERY WS event (not just changes).
            # Evon controller may coalesce rapid True→False into just False,
            # so we can't rely on old_value != value for double-press detection.
            if entity_type == ENTITY_TYPE_BUTTON_EVENTS and key == "is_on":
                self._handle_button_press(instance_id, updated_entity, value)

        # Atomically replace in the entities list AND _data_index
        # INVARIANT: No `await` must be added between the data_snapshot fetch (line ~598)
        # and this list mutation. The single-threaded event loop ensures no interleaving,
        # but adding an `await` would open a TOCTOU race with HTTP poll replacing self.data.
        entities_list = data_snapshot.get(entity_type)
        if entities_list and isinstance(entities_list, list):
            for idx, e in enumerate(entities_list):
                if e is entity:
                    entities_list[idx] = updated_entity
                    break

        self._data_index[index_key] = updated_entity
        # Mark this entity as WS-updated so a concurrent poll's stale snapshot
        # doesn't overwrite our confirmed change when it completes.
        self._ws_update_timestamps[index_key] = time.monotonic()
        if entity_type == ENTITY_TYPE_SMART_METERS:
            key_ts = self._ws_key_update_timestamps.setdefault(index_key, {})
            now = time.monotonic()
            for key in coord_data:
                key_ts[key] = now

        # Import energy statistics when smart meter data is received
        if entity_type == ENTITY_TYPE_SMART_METERS:
            self._maybe_import_energy_statistics(instance_id, updated_entity)

        # Notify listeners without resetting the REST poll timer.
        # async_set_updated_data() cancels and reschedules the timer, so frequent
        # WS events for other devices would continuously push the 60-second poll
        # forward and it would never fire, leaving stale state indefinitely.
        self.async_update_listeners()

    def _get_button_detector(self) -> ButtonPressDetector:
        """Get or create the ButtonPressDetector instance (lazy init)."""
        if self._button_detector is None:
            self._button_detector = ButtonPressDetector(
                on_press=self._fire_button_event,
                schedule_timer=self.hass.loop.call_later,
                on_timeout=self._button_press_timeout,
                double_click_delay=self._button_double_click_delay,
            )
        return self._button_detector

    def _handle_button_press(
        self,
        instance_id: str,
        entity_data: dict[str, Any],
        is_on: bool,
    ) -> None:
        """Detect button press type from IsOn WS events.

        Delegates to ButtonPressDetector for the state machine logic.
        """
        self._get_button_detector().handle_event(instance_id, entity_data, is_on)

    def _button_press_timeout(
        self,
        instance_id: str,
    ) -> None:
        """Handle button press timeout with CoW re-lookup.

        Called after double_click_delay expires with no further presses.
        Re-looks up entity_data from _data_index to avoid stale references from
        copy-on-write updates that may have occurred during the timeout window.
        """
        # Re-lookup current entity data (may have been replaced by CoW)
        entity_data = self._data_index.get((ENTITY_TYPE_BUTTON_EVENTS, instance_id))
        if entity_data is None:
            return

        detector = self._get_button_detector()
        detector.timeout(instance_id, entity_data)

        # Notify coordinator listeners — needed here because the timeout fires
        # outside the WS handler (which has its own async_update_listeners call).
        if self.data:
            self.async_update_listeners()

    def _fire_button_event(
        self,
        instance_id: str,
        entity_data: dict[str, Any],
        press_type: str,
    ) -> None:
        """Fire a button press event on the HA bus and update entity data.

        Args:
            instance_id: The button instance ID.
            entity_data: The entity data dict (will set last_event_type).
            press_type: The press type (single_press, double_press, long_press).
        """
        button_name = entity_data.get("name", "")
        self.hass.bus.async_fire(
            f"{DOMAIN}_button_press",
            {
                "device_id": instance_id,
                "name": button_name,
                "press_type": press_type,
            },
        )
        _LOGGER.debug(
            "Button event fired: %s (%s) — %s",
            button_name,
            instance_id,
            press_type,
        )

        # Update entity data so the event entity can pick it up.
        # Use a monotonic counter so repeated same-type presses are detected.
        entity_data["last_event_type"] = press_type
        entity_data["last_event_id"] = entity_data.get("last_event_id", 0) + 1

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
        from ..statistics import import_energy_statistics, is_import_rate_limited

        # Rate-limit BEFORE creating the task: smart meters push WS updates
        # every few seconds, and spawning a task per event just for its body to
        # return on the 1h limit is pointless churn. import_energy_statistics
        # keeps its own check as a safety net for other callers.
        if not force and is_import_rate_limited(self.hass, instance_id):
            return

        self.hass.async_create_task(
            import_energy_statistics(
                hass=self.hass,
                meter_id=instance_id,
                meter_name=entity_data.get("name") or instance_id,
                energy_data_month=energy_data_month,
                feed_in_data_month=entity_data.get("feed_in_data_month"),
                energy_data_year=entity_data.get("energy_data_year"),
                force=force,
            ),
            name=f"evon_import_energy_{instance_id}",
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

        Makes a single batched statistics_during_period call for all meters
        instead of one call per meter.
        """
        if not smart_meters:
            return

        if self.hass.is_stopping:
            # The recorder's executor is already gone during shutdown; a poll
            # that was in flight when HA started stopping must not schedule
            # work on it ("cannot schedule new futures after shutdown").
            _LOGGER.debug("Home Assistant is stopping; skipping energy statistics")
            return

        now = dt_util.now()
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_day = now.day  # Day of month (1-31)

        _LOGGER.debug(
            "Calculating energy for %d smart meters, today_day=%d, start_of_day=%s",
            len(smart_meters),
            today_day,
            start_of_day.isoformat(),
        )

        # Build mapping of entity_id -> meter dict for all meters upfront
        ent_reg = er.async_get(self.hass)
        meter_entity_ids: dict[str, dict[str, Any]] = {}
        for meter in smart_meters:
            meter_id = meter.get("id", "")
            unique_id = f"evon_meter_energy_{meter_id}"
            entity_id = ent_reg.async_get_entity_id("sensor", DOMAIN, unique_id)
            if entity_id is None:
                _LOGGER.debug(
                    "Energy entity not found in registry for meter %s (unique_id=%s), skipping",
                    meter.get("name", ""),
                    unique_id,
                )
                continue
            meter_entity_ids[entity_id] = meter

        all_entity_ids = list(meter_entity_ids.keys())
        _LOGGER.debug("Querying statistics for %d entity_ids: %s", len(all_entity_ids), all_entity_ids)

        # Make ONE batched statistics_during_period call for all meters
        stats: dict[str, Any] = {}
        try:
            stats = await get_recorder_instance(self.hass).async_add_executor_job(
                statistics_during_period,
                self.hass,
                start_of_day,
                now,
                all_entity_ids,
                "hour",
                {"energy": UnitOfEnergy.KILO_WATT_HOUR},
                {"change"},
            )
            _LOGGER.debug("Statistics result keys: %s", list(stats.keys()) if stats else "None")
            # Success — reset failure counter
            self._energy_stats_consecutive_failures = 0
        except (HomeAssistantError, ValueError, TypeError, KeyError) as err:
            self._energy_stats_consecutive_failures += 1
            if self._energy_stats_consecutive_failures >= ENERGY_STATS_FAILURE_LOG_THRESHOLD:
                _LOGGER.error(
                    "Energy statistics batch call failed %d times consecutively: %s. "
                    "Check that the recorder component is running and the entities exist.",
                    self._energy_stats_consecutive_failures,
                    err,
                )
            else:
                _LOGGER.warning("Could not get energy statistics: %s", err)
        except Exception as err:
            self._energy_stats_consecutive_failures += 1
            if self._energy_stats_consecutive_failures >= ENERGY_STATS_FAILURE_LOG_THRESHOLD:
                _LOGGER.error(
                    "Energy statistics batch call failed %d times consecutively: %s. "
                    "Check that the recorder component is running and the entities exist.",
                    self._energy_stats_consecutive_failures,
                    err,
                    exc_info=True,
                )
            else:
                _LOGGER.warning("Could not get energy statistics: %s", err, exc_info=True)

        # Distribute results to each meter and compute monthly totals
        for entity_id, meter in meter_entity_ids.items():
            meter_name = meter.get("name", "")
            energy_today = None

            if entity_id in stats:
                # Sum all hourly changes for today
                hourly_changes = [s.get("change", 0) or 0 for s in stats[entity_id]]
                _LOGGER.debug("Hourly changes for %s: %s", entity_id, hourly_changes)
                energy_today = sum(hourly_changes)
                energy_today = round(energy_today, 2) if energy_today > 0 else 0.0
                _LOGGER.debug("Calculated energy_today for %s: %s kWh", meter_name, energy_today)
            else:
                _LOGGER.debug("No statistics found for %s in result", entity_id)

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
                        elif isinstance(v, str):
                            with contextlib.suppress(ValueError):
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

    @property
    def has_home_connect_proxy(self) -> bool:
        """Return whether a Home Connect proxy instance is present.

        Used by the options flow to decide whether to offer the weather-station
        override fields (a weather station is read through this proxy).
        """
        return bool(find_home_connect_instances(self._instances_cache))
