"""Tests for Evon weather-station support (processor, API read, discovery, poll).

Two station shapes are covered: a local ``Apps.WeatherStation`` wired to this
controller (plain instance GET) and a ``Weather.ProxyStation`` on a shared
controller, read through the apartment's Home Connect proxy. These tests cover the
pure processor/helpers, the ``EvonApi.get_via_home_connect`` read, and the
coordinator discovery/poll orchestration (exercised via bound methods on a
lightweight stub, so no Home Assistant runtime is required).
"""

from __future__ import annotations

import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from custom_components.evon.api import EvonApi
from custom_components.evon.const import (
    CONF_WEATHER_HOME_CONNECT_ID,
    CONF_WEATHER_STATION_ID,
    EVON_CLASS_HOME_CONNECT,
    EVON_CLASS_WEATHER_PROXY,
    EVON_CLASS_WEATHER_STATION,
)
from custom_components.evon.coordinator import EvonDataUpdateCoordinator
from custom_components.evon.coordinator.processors.weather import (
    find_home_connect_instances,
    find_local_weather_stations,
    find_weather_stations_in,
    parse_last_rain,
    process_weather_stations,
)
from tests.conftest import requires_ha_test_framework

# A full weather payload as read via the proxy (.data.Data.data).
FULL_WEATHER = {
    "ID": "WeatherStation1525",
    "Name": "Wetterstation Dining",
    "ClassName": EVON_CLASS_WEATHER_PROXY,
    "Connected": True,
    "PollingActivated": True,
    "Temperature": 12.5,
    "TemperatureValid": True,
    "WindSpeed": 8.0,
    "Rain": False,
    "Brightness": 15000.0,
    "SunNorth": 1.1,
    "SunEast": 2.2,
    "SunSouth": 33.3,
    "SunWest": 4.4,
    "Twilight": False,
    "WindAlarm": False,
    "WindAlarm1": False,
    "WindAlarm2": True,
    "LastRainDateTime": "12.10.2026, 14:30:05",
    "LastRainInDays": 2.0,
    "MinTemp": -8.0,
    "MaxTemp": 35.0,
    "MinTempToday": 6.0,
    "MaxTempToday": 14.0,
    "MaxWind": 70.0,
    "MaxWindToday": 20.0,
}

# A local station as returned by GET /api/instances/<id> (.data). The controller
# stores the name with a trailing space, and Connected/PollingActivated exist on
# the proxy path only.
LOCAL_WEATHER = {
    **{k: v for k, v in FULL_WEATHER.items() if k not in ("Connected", "PollingActivated", "ClassName")},
    "ID": "WeatherStation9118",
    "Name": "Terrasse Wetterstationen ",
    "ClassName": EVON_CLASS_WEATHER_STATION,
}


def _proxy_source(station_id: str, name: str | None, hc_id: str = "evonHomeConnect4939") -> dict:
    """Discovery source for a station read through a Home Connect proxy."""
    return {"station_id": station_id, "name": name, "home_connect_id": hc_id, "proxied": True}


def _local_source(station_id: str, name: str | None) -> dict:
    """Discovery source for a station wired to this controller."""
    return {"station_id": station_id, "name": name, "home_connect_id": None, "proxied": False}


LOCAL_STATION_ENTRY = {
    "ID": "WeatherStation9118",
    "Name": "Terrasse Wetterstationen ",
    "ClassName": EVON_CLASS_WEATHER_STATION,
}
PROXY_ENTRY = {"ID": "evonHomeConnect4939", "Name": "Allgemein", "ClassName": EVON_CLASS_HOME_CONNECT}


class TestFindHomeConnectInstances:
    """find_home_connect_instances filters named proxy instances."""

    def test_finds_named_proxy(self):
        instances = [
            {"ID": "evonHomeConnect4939", "Name": "Allgemein", "ClassName": EVON_CLASS_HOME_CONNECT},
            {"ID": "evonHomeConnect0000", "Name": "", "ClassName": EVON_CLASS_HOME_CONNECT},  # template
            {"ID": "Light1", "Name": "Lamp", "ClassName": "SmartCOM.Light.LightDim"},
        ]
        assert find_home_connect_instances(instances) == [{"id": "evonHomeConnect4939", "name": "Allgemein"}]

    def test_skips_instances_without_id(self):
        instances = [{"ID": "", "Name": "x", "ClassName": EVON_CLASS_HOME_CONNECT}]
        assert find_home_connect_instances(instances) == []

    def test_empty_list(self):
        assert find_home_connect_instances([]) == []


class TestFindWeatherStationsIn:
    """find_weather_stations_in filters named Weather.ProxyStation entries."""

    def test_finds_named_station(self):
        remote = [
            {"ID": "WeatherStation1525", "Name": "Wetterstation Dining", "ClassName": EVON_CLASS_WEATHER_PROXY},
            {"ID": "WeatherStation0000", "Name": "", "ClassName": EVON_CLASS_WEATHER_PROXY},  # template
            {"ID": "Other1", "Name": "Other", "ClassName": "Some.Other.Class"},
        ]
        assert find_weather_stations_in(remote) == [{"id": "WeatherStation1525", "name": "Wetterstation Dining"}]

    def test_non_list_returns_empty(self):
        assert find_weather_stations_in(None) == []
        assert find_weather_stations_in({"not": "a list"}) == []
        assert find_weather_stations_in("string") == []


class TestFindLocalWeatherStations:
    """find_local_weather_stations filters named Apps.WeatherStation instances."""

    def test_finds_named_local_station(self):
        instances = [
            LOCAL_STATION_ENTRY,
            {"ID": "Apps.WeatherStation", "Name": "", "ClassName": EVON_CLASS_WEATHER_STATION},  # class template
            {"ID": "WeatherStation1525", "Name": "Proxy", "ClassName": EVON_CLASS_WEATHER_PROXY},
        ]
        assert find_local_weather_stations(instances) == [
            {"id": "WeatherStation9118", "name": "Terrasse Wetterstationen "}
        ]

    def test_empty_and_missing(self):
        assert find_local_weather_stations([]) == []
        assert find_local_weather_stations([{"ID": "", "Name": "x", "ClassName": EVON_CLASS_WEATHER_STATION}]) == []


class TestParseLastRain:
    """parse_last_rain turns the controller timestamp into a tz-aware datetime."""

    def test_valid_timestamp(self):
        result = parse_last_rain("12.10.2026, 14:30:05")
        assert result is not None
        assert (result.year, result.month, result.day) == (2026, 10, 12)
        assert (result.hour, result.minute, result.second) == (14, 30, 5)
        assert result.tzinfo is not None  # device-local tz attached

    def test_uses_home_assistant_zone_with_the_offset_of_that_date(self):
        """A CEST timestamp must keep +02:00 after DST ends (and vice versa), and the
        zone is HA's configured one, not the process TZ (Docker/venv hosts run UTC)."""
        from datetime import timedelta
        from zoneinfo import ZoneInfo

        from homeassistant.util import dt as dt_util

        previous = dt_util.get_default_time_zone()
        dt_util.set_default_time_zone(ZoneInfo("Europe/Vienna"))
        try:
            summer = parse_last_rain("20.10.2026, 14:00:00")  # before DST ends on 25 Oct
            winter = parse_last_rain("30.10.2026, 14:00:00")
        finally:
            dt_util.set_default_time_zone(previous)

        assert summer.utcoffset() == timedelta(hours=2)
        assert winter.utcoffset() == timedelta(hours=1)

    @pytest.mark.parametrize("value", ["", "   ", "not a date", "2026-10-12T14:30:05", None, 123, []])
    def test_unparseable_returns_none(self, value):
        assert parse_last_rain(value) is None


class TestProcessWeatherStations:
    """process_weather_stations shapes raw proxy data into entity dicts."""

    def test_full_payload(self):
        out = process_weather_stations([{"id": "WeatherStation1525", "name": "Dining", "data": FULL_WEATHER}])
        assert len(out) == 1
        s = out[0]
        assert s["id"] == "WeatherStation1525"
        assert s["name"] == "Dining"
        assert s["room_name"] == ""
        assert s["temperature"] == 12.5
        assert s["temperature_valid"] is True
        assert s["wind_speed"] == 8.0
        assert s["brightness"] == 15000.0
        assert s["sun_north"] == 1.1
        assert s["sun_east"] == 2.2
        assert s["sun_south"] == 33.3
        assert s["sun_west"] == 4.4
        assert s["rain"] is False
        assert s["twilight"] is False
        assert s["wind_alarm"] is False
        assert s["wind_alarm_1"] is False
        assert s["wind_alarm_2"] is True
        assert s["connected"] is True
        assert s["polling_activated"] is True
        assert s["temp_min_today"] == 6.0
        assert s["temp_max_today"] == 14.0
        assert s["wind_max_today"] == 20.0
        assert s["temp_min"] == -8.0
        assert s["temp_max"] == 35.0
        assert s["wind_max"] == 70.0
        assert s["last_rain"] is not None
        assert s["last_rain"].year == 2026
        assert s["last_rain_in_days"] == 2.0

    def test_missing_fields_become_none(self):
        out = process_weather_stations([{"id": "WS1", "name": "Bare", "data": {"ID": "WS1"}}])
        assert len(out) == 1
        s = out[0]
        assert s["temperature"] is None
        assert s["wind_speed"] is None
        assert s["rain"] is None
        assert s["last_rain"] is None
        assert s["connected"] is None

    def test_non_numeric_temperature_coerced_to_none(self):
        out = process_weather_stations([{"id": "WS1", "name": "X", "data": {"Temperature": "n/a"}}])
        assert out[0]["temperature"] is None

    def test_entry_without_data_is_skipped(self):
        out = process_weather_stations(
            [
                {"id": "WS1", "name": "no data", "data": None},
                {"id": "WS2", "name": "ok", "data": {"ID": "WS2", "Temperature": 10.0}},
            ]
        )
        assert [s["id"] for s in out] == ["WS2"]

    def test_id_and_name_fallback_to_payload(self):
        out = process_weather_stations([{"id": None, "name": None, "data": FULL_WEATHER}])
        assert len(out) == 1
        assert out[0]["id"] == "WeatherStation1525"
        assert out[0]["name"] == "Wetterstation Dining"

    def test_proxied_defaults_to_true(self):
        """Entries from before the local-station support are proxy reads."""
        out = process_weather_stations([{"id": "WS1", "name": "X", "data": {"ID": "WS1"}}])
        assert out[0]["proxied"] is True

    def test_local_station_is_marked_not_proxied(self):
        out = process_weather_stations(
            [{"id": "WeatherStation9118", "name": LOCAL_WEATHER["Name"], "data": LOCAL_WEATHER, "proxied": False}]
        )
        s = out[0]
        assert s["proxied"] is False
        # The controller stores the name with a trailing space; it must not leak
        # into the entity/device name.
        assert s["name"] == "Terrasse Wetterstationen"
        # The local path does not report the proxy diagnostics.
        assert s["connected"] is None
        assert s["polling_activated"] is None
        assert s["temperature"] == 12.5
        assert s["last_rain"] is not None

    def test_empty_input(self):
        assert process_weather_stations([]) == []


class TestGetViaHomeConnect:
    """EvonApi.get_via_home_connect reads through the proxy's Get method."""

    @pytest.fixture
    def api(self):
        api = EvonApi(host="http://192.168.1.100", username="user", password="pass")
        api._token = "test_token"
        api._request = AsyncMock()
        return api

    @pytest.mark.asyncio
    async def test_reads_nested_payload_and_posts_correct_body(self, api):
        api._request.return_value = {"data": {"Data": {"data": {"ID": "WeatherStation1525"}}}}
        result = await api.get_via_home_connect("evonHomeConnect4939", "/instances/WeatherStation1525")
        assert result == {"ID": "WeatherStation1525"}
        api._request.assert_awaited_once_with(
            "POST",
            "/instances/evonHomeConnect4939/Get",
            ["/instances/WeatherStation1525", {}, False],
        )

    @pytest.mark.asyncio
    async def test_reads_instance_list(self, api):
        api._request.return_value = {"data": {"Data": {"data": [{"ID": "WeatherStation1525"}]}}}
        result = await api.get_via_home_connect("evonHomeConnect4939", "/instances")
        assert result == [{"ID": "WeatherStation1525"}]

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "payload",
        [
            {},  # no data
            {"data": {}},  # no Data
            {"data": {"Data": {}}},  # no inner data
            "not a dict",
            None,
        ],
    )
    async def test_missing_payload_returns_none(self, api, payload):
        api._request.return_value = payload
        result = await api.get_via_home_connect("evonHomeConnect4939", "/instances")
        assert result is None

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "path",
        [
            "bad",
            "/foo",
            "instances",
            "",
            "/instancesFoo",
            "/instances/",
            "/instances/..",
            "/instances/../apps",
            "/instances/a?b",
            "/instances/a/b",
            "/instances/a#b",
            None,
        ],
    )
    async def test_invalid_path_raises(self, api, path):
        with pytest.raises(ValueError):
            await api.get_via_home_connect("evonHomeConnect4939", path)
        api._request.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_invalid_home_connect_id_raises(self, api):
        with pytest.raises(ValueError):
            await api.get_via_home_connect("bad id!", "/instances")
        api._request.assert_not_awaited()


class _StubCoordinator:
    """Minimal stand-in exposing the weather discovery/poll methods.

    The methods reference only ``api``, ``config_entry.options``,
    ``_instances_cache`` and ``_weather_sources`` — no HA runtime — so binding the
    real methods onto this stub exercises the orchestration directly.
    """

    _discover_weather_sources = EvonDataUpdateCoordinator._discover_weather_sources
    _discover_proxy_weather_sources = EvonDataUpdateCoordinator._discover_proxy_weather_sources
    _poll_weather_stations = EvonDataUpdateCoordinator._poll_weather_stations
    has_home_connect_proxy = EvonDataUpdateCoordinator.has_home_connect_proxy

    def __init__(self, api, options=None, instances=None):
        self.api = api
        self.config_entry = SimpleNamespace(options=options or {})
        self._instances_cache = instances or []
        self._weather_sources: list[dict] | None = None
        self._weather_discovered_at = None
        self._invalid_weather_override = None


class TestDiscoverWeatherSources:
    """Coordinator._discover_weather_sources orchestration."""

    @pytest.mark.asyncio
    async def test_options_override_skips_discovery(self):
        api = AsyncMock()
        coord = _StubCoordinator(
            api,
            options={
                CONF_WEATHER_HOME_CONNECT_ID: "evonHomeConnect4939",
                CONF_WEATHER_STATION_ID: "WeatherStation1525",
            },
        )
        sources = await coord._discover_weather_sources()
        assert sources == [_proxy_source("WeatherStation1525", None)]
        api.get_via_home_connect.assert_not_called()

    @pytest.mark.asyncio
    async def test_invalid_options_override_is_ignored(self):
        api = AsyncMock()
        coord = _StubCoordinator(
            api,
            options={
                CONF_WEATHER_HOME_CONNECT_ID: "evonHomeConnect4939",
                CONF_WEATHER_STATION_ID: "../apps",
            },
        )
        assert await coord._discover_weather_sources() == []
        api.get_via_home_connect.assert_not_called()

    @pytest.mark.asyncio
    async def test_invalid_options_override_warns_once(self, caplog):
        """Discovery re-runs on every 30 s weather tick while it finds nothing."""
        coord = _StubCoordinator(
            AsyncMock(),
            options={
                CONF_WEATHER_HOME_CONNECT_ID: "evonHomeConnect4939",
                CONF_WEATHER_STATION_ID: "../apps",
            },
        )
        with caplog.at_level(logging.WARNING):
            for _ in range(3):
                assert await coord._discover_weather_sources() == []
        assert sum("Ignoring weather station override" in r.message for r in caplog.records) == 1

    @pytest.mark.asyncio
    async def test_discovery_skips_stations_with_invalid_ids(self):
        """Station ids come from the shared controller and end up in a request path."""
        api = AsyncMock()
        api.get_via_home_connect.return_value = [
            {"ID": "../apps", "Name": "Evil", "ClassName": EVON_CLASS_WEATHER_PROXY},
            {"ID": "a?b", "Name": "Evil 2", "ClassName": EVON_CLASS_WEATHER_PROXY},
            {"ID": "WeatherStation1525", "Name": "Dining", "ClassName": EVON_CLASS_WEATHER_PROXY},
        ]
        coord = _StubCoordinator(
            api,
            instances=[{"ID": "evonHomeConnect4939", "Name": "Allgemein", "ClassName": EVON_CLASS_HOME_CONNECT}],
        )
        sources = await coord._discover_weather_sources()
        assert sources == [_proxy_source("WeatherStation1525", "Dining")]

    @pytest.mark.asyncio
    async def test_auto_discovery_finds_station(self):
        api = AsyncMock()
        api.get_via_home_connect.return_value = [
            {"ID": "WeatherStation1525", "Name": "Dining", "ClassName": EVON_CLASS_WEATHER_PROXY},
        ]
        coord = _StubCoordinator(
            api,
            instances=[{"ID": "evonHomeConnect4939", "Name": "Allgemein", "ClassName": EVON_CLASS_HOME_CONNECT}],
        )
        sources = await coord._discover_weather_sources()
        assert sources == [_proxy_source("WeatherStation1525", "Dining")]
        api.get_via_home_connect.assert_awaited_once_with("evonHomeConnect4939", "/instances")

    @pytest.mark.asyncio
    async def test_no_home_connect_returns_empty_without_api_call(self):
        api = AsyncMock()
        coord = _StubCoordinator(api, instances=[{"ID": "Light1", "Name": "L", "ClassName": "SmartCOM.Light.Light"}])
        sources = await coord._discover_weather_sources()
        assert sources == []
        api.get_via_home_connect.assert_not_called()

    @pytest.mark.asyncio
    async def test_proxy_error_is_tolerated(self):
        api = AsyncMock()
        api.get_via_home_connect.side_effect = RuntimeError("proxy down")
        coord = _StubCoordinator(
            api,
            instances=[{"ID": "evonHomeConnect4939", "Name": "Allgemein", "ClassName": EVON_CLASS_HOME_CONNECT}],
        )
        sources = await coord._discover_weather_sources()
        assert sources == []

    @pytest.mark.asyncio
    async def test_non_empty_cache_is_reused(self):
        api = AsyncMock()
        coord = _StubCoordinator(api)
        coord._weather_sources = [_proxy_source("ws", "Name", "hc")]
        sources = await coord._discover_weather_sources()
        assert sources == [_proxy_source("ws", "Name", "hc")]
        api.get_via_home_connect.assert_not_called()

    @pytest.mark.asyncio
    async def test_empty_cache_triggers_rediscovery(self):
        api = AsyncMock()
        api.get_via_home_connect.return_value = [
            {"ID": "WeatherStation1525", "Name": "Dining", "ClassName": EVON_CLASS_WEATHER_PROXY},
        ]
        coord = _StubCoordinator(
            api,
            instances=[{"ID": "evonHomeConnect4939", "Name": "Allgemein", "ClassName": EVON_CLASS_HOME_CONNECT}],
        )
        coord._weather_sources = []  # empty: re-discover
        sources = await coord._discover_weather_sources()
        assert sources == [_proxy_source("WeatherStation1525", "Dining")]
        api.get_via_home_connect.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_empty_result_is_not_rediscovered_on_every_poll(self):
        """A proxy without a station (or a failing proxy) must not cost a full remote
        instance listing per poll; empty results are retried after a back-off."""
        import time

        api = AsyncMock()
        coord = _StubCoordinator(
            api,
            instances=[{"ID": "evonHomeConnect4939", "Name": "Allgemein", "ClassName": EVON_CLASS_HOME_CONNECT}],
        )
        coord._weather_sources = []
        coord._weather_discovered_at = time.monotonic() - 10  # tried 10 s ago

        assert await coord._discover_weather_sources() == []
        api.get_via_home_connect.assert_not_called()

    @pytest.mark.asyncio
    async def test_empty_result_is_retried_after_backoff(self):
        import time

        from custom_components.evon.const import WEATHER_REDISCOVERY_INTERVAL

        api = AsyncMock()
        api.get_via_home_connect.return_value = [
            {"ID": "WeatherStation1525", "Name": "Dining", "ClassName": EVON_CLASS_WEATHER_PROXY},
        ]
        coord = _StubCoordinator(
            api,
            instances=[{"ID": "evonHomeConnect4939", "Name": "Allgemein", "ClassName": EVON_CLASS_HOME_CONNECT}],
        )
        coord._weather_sources = []
        coord._weather_discovered_at = time.monotonic() - WEATHER_REDISCOVERY_INTERVAL - 1

        assert await coord._discover_weather_sources() == [_proxy_source("WeatherStation1525", "Dining")]

    @pytest.mark.asyncio
    async def test_local_station_is_discovered_without_a_proxy(self):
        """A station wired to this controller needs no Home Connect proxy at all."""
        api = AsyncMock()
        coord = _StubCoordinator(api, instances=[LOCAL_STATION_ENTRY])
        sources = await coord._discover_weather_sources()
        assert sources == [_local_source("WeatherStation9118", "Terrasse Wetterstationen ")]
        api.get_via_home_connect.assert_not_called()

    @pytest.mark.asyncio
    async def test_local_and_proxy_stations_coexist(self):
        api = AsyncMock()
        api.get_via_home_connect.return_value = [
            {"ID": "WeatherStation1525", "Name": "Dining", "ClassName": EVON_CLASS_WEATHER_PROXY},
        ]
        coord = _StubCoordinator(api, instances=[LOCAL_STATION_ENTRY, PROXY_ENTRY])
        sources = await coord._discover_weather_sources()
        assert sources == [
            _local_source("WeatherStation9118", "Terrasse Wetterstationen "),
            _proxy_source("WeatherStation1525", "Dining"),
        ]

    @pytest.mark.asyncio
    async def test_empty_proxy_cache_does_not_hide_a_local_station(self):
        """The proxy back-off cache must not suppress the always-cheap local lookup."""
        api = AsyncMock()
        coord = _StubCoordinator(api, instances=[LOCAL_STATION_ENTRY])
        coord._weather_sources = []  # proxy discovery already ran and found nothing
        sources = await coord._discover_weather_sources()
        assert sources == [_local_source("WeatherStation9118", "Terrasse Wetterstationen ")]
        api.get_via_home_connect.assert_not_called()

    @pytest.mark.asyncio
    async def test_local_station_is_skipped_while_it_has_no_name(self):
        """An uninstalled station is the class template with an empty Name."""
        api = AsyncMock()
        coord = _StubCoordinator(
            api,
            instances=[{"ID": "Apps.WeatherStation", "Name": "", "ClassName": EVON_CLASS_WEATHER_STATION}],
        )
        assert await coord._discover_weather_sources() == []

    def test_has_home_connect_proxy_property(self):
        coord = _StubCoordinator(
            AsyncMock(),
            instances=[{"ID": "evonHomeConnect4939", "Name": "Allgemein", "ClassName": EVON_CLASS_HOME_CONNECT}],
        )
        assert coord.has_home_connect_proxy is True
        coord2 = _StubCoordinator(AsyncMock(), instances=[])
        assert coord2.has_home_connect_proxy is False


class TestPollWeatherStations:
    """Coordinator._poll_weather_stations orchestration."""

    @pytest.mark.asyncio
    async def test_no_sources_returns_empty(self):
        api = AsyncMock()
        coord = _StubCoordinator(api)
        coord._weather_sources = []
        result = await coord._poll_weather_stations()
        assert result == []

    @pytest.mark.asyncio
    async def test_polls_each_station(self):
        api = AsyncMock()
        api.get_via_home_connect.return_value = FULL_WEATHER
        coord = _StubCoordinator(api)
        coord._weather_sources = [_proxy_source("WeatherStation1525", "Dining")]
        result = await coord._poll_weather_stations()
        assert result == [{"id": "WeatherStation1525", "name": "Dining", "data": FULL_WEATHER, "proxied": True}]
        api.get_via_home_connect.assert_awaited_once_with("evonHomeConnect4939", "/instances/WeatherStation1525")

    @pytest.mark.asyncio
    async def test_per_station_failure_is_tolerated(self):
        api = AsyncMock()

        async def _get(hc, path):
            if "Broken" in path:
                raise RuntimeError("unreachable")
            return FULL_WEATHER

        api.get_via_home_connect.side_effect = _get
        coord = _StubCoordinator(api)
        coord._weather_sources = [
            _proxy_source("WeatherStationBroken", "Broken", "hc"),
            _proxy_source("WeatherStation1525", "Dining", "hc"),
        ]
        result = await coord._poll_weather_stations()
        assert [r["id"] for r in result] == ["WeatherStation1525"]

    @pytest.mark.asyncio
    async def test_local_station_is_polled_with_a_plain_instance_get(self):
        api = AsyncMock()
        api.get_instance.return_value = LOCAL_WEATHER
        coord = _StubCoordinator(api)
        coord._weather_sources = [_local_source("WeatherStation9118", "Terrasse Wetterstationen ")]
        result = await coord._poll_weather_stations()
        assert result == [
            {
                "id": "WeatherStation9118",
                "name": "Terrasse Wetterstationen ",
                "data": LOCAL_WEATHER,
                "proxied": False,
            }
        ]
        api.get_instance.assert_awaited_once_with("WeatherStation9118")
        api.get_via_home_connect.assert_not_called()

    @pytest.mark.asyncio
    async def test_non_dict_response_skipped(self):
        api = AsyncMock()
        api.get_via_home_connect.return_value = None
        coord = _StubCoordinator(api)
        coord._weather_sources = [_proxy_source("WeatherStation1525", "Dining", "hc")]
        result = await coord._poll_weather_stations()
        assert result == []


@requires_ha_test_framework
class TestWeatherEntitiesAddedLater:
    """A station found after setup (proxy slow/failing during the first refresh)
    must still get its entities without a manual reload."""

    async def test_station_discovered_after_setup_gets_entities(self, hass, mock_evon_api_class):
        from homeassistant.helpers import entity_registry as er
        from pytest_homeassistant_custom_component.common import MockConfigEntry

        from custom_components.evon.const import DOMAIN
        from tests.conftest import MOCK_INSTANCES, TEST_HOST, TEST_PASSWORD, TEST_USERNAME

        proxy = {"ID": "evonHomeConnect4939", "Name": "Allgemein", "ClassName": EVON_CLASS_HOME_CONNECT}
        mock_evon_api_class.get_instances = AsyncMock(return_value=[*MOCK_INSTANCES, proxy])
        mock_evon_api_class.get_via_home_connect = AsyncMock(side_effect=RuntimeError("proxy not ready"))

        entry = MockConfigEntry(
            domain=DOMAIN,
            data={"host": TEST_HOST, "username": TEST_USERNAME, "password": TEST_PASSWORD},
            options={"scan_interval": 30, "sync_areas": False},
            entry_id="weather_late_entry",
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        registry = er.async_get(hass)
        temp_uid = "evon_weather_WeatherStation1525_temperature"
        rain_uid = "evon_weather_WeatherStation1525_rain"
        assert registry.async_get_entity_id("sensor", DOMAIN, temp_uid) is None

        async def _proxy(hc_id, path):
            if path == "/instances":
                return [{"ID": "WeatherStation1525", "Name": "Dining", "ClassName": EVON_CLASS_WEATHER_PROXY}]
            return FULL_WEATHER

        mock_evon_api_class.get_via_home_connect = AsyncMock(side_effect=_proxy)
        coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
        coordinator._weather_discovered_at = None  # skip the back-off for the test
        await coordinator._async_weather_tick(None)  # the 30 s weather timer
        await hass.async_block_till_done()

        assert registry.async_get_entity_id("sensor", DOMAIN, temp_uid) is not None
        assert registry.async_get_entity_id("binary_sensor", DOMAIN, rain_uid) is not None

        # Further updates must not add duplicates (HA would log an error).
        await coordinator._async_weather_tick(None)
        await coordinator.async_refresh()
        await hass.async_block_till_done()
        assert (
            len([e for e in er.async_entries_for_config_entry(registry, entry.entry_id) if e.unique_id == temp_uid])
            == 1
        )


@requires_ha_test_framework
class TestLocalWeatherStation:
    """A station wired to this controller (``Apps.WeatherStation``) is set up like a
    proxy station, minus the proxy-only connectivity diagnostics."""

    async def test_local_station_gets_entities(self, hass, mock_evon_api_class, monkeypatch):
        from homeassistant.helpers import device_registry as dr
        from pytest_homeassistant_custom_component.common import MockConfigEntry

        from custom_components.evon.const import DOMAIN
        from tests import conftest
        from tests.conftest import MOCK_INSTANCES, TEST_HOST, TEST_PASSWORD, TEST_USERNAME

        monkeypatch.setitem(conftest.MOCK_INSTANCE_DETAILS, "WeatherStation9118", LOCAL_WEATHER)
        mock_evon_api_class.get_instances = AsyncMock(return_value=[*MOCK_INSTANCES, LOCAL_STATION_ENTRY])

        entry = MockConfigEntry(
            domain=DOMAIN,
            data={"host": TEST_HOST, "username": TEST_USERNAME, "password": TEST_PASSWORD},
            options={"scan_interval": 30, "sync_areas": False},
            entry_id="weather_local_entry",
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # The trailing space in the controller's station name must not leak into IDs.
        temp = hass.states.get("sensor.terrasse_wetterstationen_temperature")
        assert temp is not None
        assert temp.state == "12.5"
        assert hass.states.get("binary_sensor.terrasse_wetterstationen_rain").state == "off"
        assert hass.states.get("sensor.terrasse_wetterstationen_wind_speed").state == "8.0"

        # Proxy-only diagnostics are not created for a local station.
        assert hass.states.get("binary_sensor.terrasse_wetterstationen_connected") is None
        assert hass.states.get("binary_sensor.terrasse_wetterstationen_polling_activated") is None

        device = dr.async_get(hass).async_get_device_by_identifier((DOMAIN, "WeatherStation9118"), entry.entry_id)
        assert device is not None
        assert device.name == "Terrasse Wetterstationen"
        assert device.model == "Weather Station"


@requires_ha_test_framework
class TestWeatherPolling:
    """The weather station is read on its own WEATHER_POLL_INTERVAL timer (30 s),
    independent of the (120 s with WebSocket) device poll, which reuses the latest
    station data instead of calling the proxy again."""

    async def _setup(self, hass, mock_evon_api_class, readings):
        from pytest_homeassistant_custom_component.common import MockConfigEntry

        from custom_components.evon.const import DOMAIN
        from tests.conftest import MOCK_INSTANCES, TEST_HOST, TEST_PASSWORD, TEST_USERNAME

        proxy = {"ID": "evonHomeConnect4939", "Name": "Allgemein", "ClassName": EVON_CLASS_HOME_CONNECT}
        mock_evon_api_class.get_instances = AsyncMock(return_value=[*MOCK_INSTANCES, proxy])

        async def _proxy(hc_id, path):
            if path == "/instances":
                return [{"ID": "WeatherStation1525", "Name": "Dining", "ClassName": EVON_CLASS_WEATHER_PROXY}]
            return {**FULL_WEATHER, "Temperature": readings[0]}

        mock_evon_api_class.get_via_home_connect = AsyncMock(side_effect=_proxy)
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={"host": TEST_HOST, "username": TEST_USERNAME, "password": TEST_PASSWORD},
            options={"scan_interval": 300, "sync_areas": False},
            entry_id="weather_poll_entry",
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        return entry, hass.data[DOMAIN][entry.entry_id]["coordinator"]

    @staticmethod
    def _station_reads(mock_api) -> int:
        return sum(1 for c in mock_api.get_via_home_connect.call_args_list if c.args[1] != "/instances")

    async def test_station_is_polled_every_weather_interval(self, hass, mock_evon_api_class):
        from datetime import timedelta

        from homeassistant.util import dt as dt_util
        from pytest_homeassistant_custom_component.common import async_fire_time_changed

        from custom_components.evon.const import WEATHER_POLL_INTERVAL

        readings = [12.5]
        await self._setup(hass, mock_evon_api_class, readings)
        assert hass.states.get("sensor.dining_temperature").state == "12.5"

        readings[0] = 13.0
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=WEATHER_POLL_INTERVAL + 1))
        await hass.async_block_till_done(wait_background_tasks=True)  # interval jobs run as background tasks

        assert hass.states.get("sensor.dining_temperature").state == "13.0"

    async def test_device_poll_reuses_latest_station_data(self, hass, mock_evon_api_class):
        readings = [12.5]
        _, coordinator = await self._setup(hass, mock_evon_api_class, readings)
        reads_after_setup = self._station_reads(mock_evon_api_class)

        await coordinator.async_refresh()
        await hass.async_block_till_done()

        assert self._station_reads(mock_evon_api_class) == reads_after_setup
        assert hass.states.get("sensor.dining_temperature").state == "12.5"

    async def test_weather_timer_stops_on_shutdown(self, hass, mock_evon_api_class):
        from datetime import timedelta

        from homeassistant.util import dt as dt_util
        from pytest_homeassistant_custom_component.common import async_fire_time_changed

        from custom_components.evon.const import WEATHER_POLL_INTERVAL

        _, coordinator = await self._setup(hass, mock_evon_api_class, [12.5])
        await coordinator.async_shutdown()
        reads = self._station_reads(mock_evon_api_class)

        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=WEATHER_POLL_INTERVAL * 3))
        await hass.async_block_till_done(wait_background_tasks=True)

        assert self._station_reads(mock_evon_api_class) == reads
