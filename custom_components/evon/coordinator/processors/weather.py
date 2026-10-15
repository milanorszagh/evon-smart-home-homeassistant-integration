"""Weather-station processor for Evon Smart Home coordinator.

The weather station is a ``Weather.ProxyStation`` that lives on a shared
controller, not on the apartment controller. It is read through the apartment's
Home Connect proxy (class ``Rest.evonHomeConnect.evonHomeConnect``) with a
``Get`` method call, so it is poll-only (no WebSocket subscription) and does not
appear in the apartment's own instance list. See docs/INTERCOM_AUDIO.md's sibling
note and AGENTS.md "Weather station (proxy)".
"""

from __future__ import annotations

from datetime import datetime
import logging
from typing import Any

from homeassistant.util import dt as dt_util

from ...const import EVON_CLASS_HOME_CONNECT, EVON_CLASS_WEATHER_PROXY

_LOGGER = logging.getLogger(__name__)

# LastRainDateTime is formatted "dd.mm.YYYY, HH:MM:SS" in the controller's local time.
_LAST_RAIN_FORMAT = "%d.%m.%Y, %H:%M:%S"


def _named(instances: list[dict[str, Any]], class_name: str) -> list[dict[str, Any]]:
    """Return instances of ``class_name`` that have a non-empty Name.

    Class-template objects share the class name but carry an empty Name; they are
    skipped (same convention as the other processors).
    """
    out = []
    for i in instances:
        if i.get("ClassName") != class_name:
            continue
        if not i.get("Name"):
            continue
        if not i.get("ID"):
            continue
        out.append({"id": i["ID"], "name": i["Name"]})
    return out


def find_home_connect_instances(instances: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Find the named Home Connect proxy instances in the apartment instance list."""
    return _named(instances, EVON_CLASS_HOME_CONNECT)


def find_weather_stations_in(proxy_instances: Any) -> list[dict[str, Any]]:
    """Find named Weather.ProxyStation entries in a proxy ``Get('/instances')`` list."""
    if not isinstance(proxy_instances, list):
        return []
    return _named(proxy_instances, EVON_CLASS_WEATHER_PROXY)


def parse_last_rain(value: Any) -> datetime | None:
    """Parse LastRainDateTime into a timezone-aware datetime (controller local tz).

    The controller returns local wall-clock time without an offset; we attach HA's
    configured timezone (the installation's zone, same as the controller's). A zone,
    not today's fixed offset, so a timestamp from before a DST change keeps the
    offset valid on its own date. Returns None for anything unparseable.
    """
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        naive = datetime.strptime(value.strip(), _LAST_RAIN_FORMAT)
    except ValueError:
        return None
    return naive.replace(tzinfo=dt_util.get_default_time_zone())


def _f(value: Any) -> float | None:
    """Coerce to float, or None."""
    if value is None:
        return None
    try:
        return float(value)
    except TypeError, ValueError:
        return None


def _b(value: Any) -> bool | None:
    """Coerce to bool, or None if missing."""
    if value is None:
        return None
    return bool(value)


def process_weather_stations(
    stations_raw: list[dict[str, Any]],
    get_room_name: Any = None,
) -> list[dict[str, Any]]:
    """Shape polled weather-station data into entity dicts.

    Args:
        stations_raw: list of {"id", "name", "data"} where data is the weather
            dict read via the Home Connect proxy (``.data.Data.data``).
        get_room_name: unused (proxy stations have no apartment room); accepted
            to match the processor call signature.

    Returns:
        One dict per station with "id", "name", "room_name" and the fields.
    """
    stations = []
    for entry in stations_raw:
        data = entry.get("data")
        if not isinstance(data, dict):
            _LOGGER.debug("Skipping weather station %s: no data", entry.get("id"))
            continue
        ws_id = entry.get("id") or data.get("ID", "")
        if not ws_id:
            continue
        stations.append(
            {
                "id": ws_id,
                "name": entry.get("name") or data.get("Name") or "Weather Station",
                "room_name": "",
                "temperature": _f(data.get("Temperature")),
                "temperature_valid": _b(data.get("TemperatureValid")),
                "wind_speed": _f(data.get("WindSpeed")),
                "brightness": _f(data.get("Brightness")),
                "sun_north": _f(data.get("SunNorth")),
                "sun_east": _f(data.get("SunEast")),
                "sun_south": _f(data.get("SunSouth")),
                "sun_west": _f(data.get("SunWest")),
                "rain": _b(data.get("Rain")),
                "twilight": _b(data.get("Twilight")),
                "wind_alarm": _b(data.get("WindAlarm")),
                "wind_alarm_1": _b(data.get("WindAlarm1")),
                "wind_alarm_2": _b(data.get("WindAlarm2")),
                "connected": _b(data.get("Connected")),
                "polling_activated": _b(data.get("PollingActivated")),
                "temp_min_today": _f(data.get("MinTempToday")),
                "temp_max_today": _f(data.get("MaxTempToday")),
                "wind_max_today": _f(data.get("MaxWindToday")),
                "temp_min": _f(data.get("MinTemp")),
                "temp_max": _f(data.get("MaxTemp")),
                "wind_max": _f(data.get("MaxWind")),
                "last_rain": parse_last_rain(data.get("LastRainDateTime")),
                "last_rain_in_days": _f(data.get("LastRainInDays")),
            }
        )
    return stations
