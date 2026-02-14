"""Tests for energy midnight rollover edge cases (C-M3)."""

from __future__ import annotations

import ast
import contextlib
from datetime import datetime, timezone
from pathlib import Path
import textwrap
import types
from unittest.mock import AsyncMock, MagicMock

import pytest

_UTC = timezone.utc  # noqa: UP017


def _load_calculate_method():
    """Load _calculate_energy_today_and_month from source and compile it."""
    source_path = str(Path(__file__).resolve().parent.parent / "custom_components" / "evon" / "coordinator" / "__init__.py")
    with open(source_path) as f:
        source = f.read()

    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "_calculate_energy_today_and_month":
            lines = source.splitlines()
            func_lines = lines[node.lineno - 1 : node.end_lineno]
            func_source = "\n".join(func_lines)
            return textwrap.dedent(func_source)

    raise RuntimeError("Could not find _calculate_energy_today_and_month")


@pytest.fixture
def mock_hass():
    """Create a mock HomeAssistant instance."""
    hass = MagicMock()
    hass.async_add_executor_job = AsyncMock()
    hass.async_create_task = MagicMock()
    return hass


@pytest.fixture
def calc_method(mock_hass):
    """Create a bound _calculate_energy_today_and_month method."""
    from homeassistant.components.recorder.statistics import statistics_during_period
    from homeassistant.const import UnitOfEnergy
    from homeassistant.exceptions import HomeAssistantError
    from homeassistant.util import dt as dt_util

    from custom_components.evon.const import ENERGY_STATS_FAILURE_LOG_THRESHOLD

    ns = {}
    ns["statistics_during_period"] = statistics_during_period
    ns["UnitOfEnergy"] = UnitOfEnergy
    ns["HomeAssistantError"] = HomeAssistantError
    ns["dt_util"] = dt_util
    ns["ENERGY_STATS_FAILURE_LOG_THRESHOLD"] = ENERGY_STATS_FAILURE_LOG_THRESHOLD
    ns["contextlib"] = contextlib
    ns["_LOGGER"] = MagicMock()
    ns["DOMAIN"] = "evon"

    # Mock entity registry to return predictable entity_ids
    mock_ent_reg = MagicMock()
    mock_ent_reg.async_get_entity_id = MagicMock(
        side_effect=lambda domain, integration, unique_id: f"sensor.{unique_id}"
    )
    ns["er"] = MagicMock()
    ns["er"].async_get = MagicMock(return_value=mock_ent_reg)

    func_source = _load_calculate_method()
    exec(compile(func_source, "<test>", "exec"), ns)
    real_method = ns["_calculate_energy_today_and_month"]

    obj = MagicMock()
    obj.hass = mock_hass
    obj._energy_stats_consecutive_failures = 0

    return obj, types.MethodType(real_method, obj)


class TestMidnightBoundary:
    """Test energy calculation at midnight boundary (day = 1)."""

    @pytest.mark.asyncio
    async def test_first_day_of_month_no_historical_data(self, calc_method, mock_hass):
        """On day 1 of the month, days_this_month_excluding_today=0.

        energy_this_month should equal energy_today only.
        """
        coordinator, calc = calc_method

        smart_meters = [{"name": "Meter A", "id": "meter_a", "energy_data_month": []}]

        # Return statistics showing 2 kWh today
        mock_hass.async_add_executor_job.return_value = {
            "sensor.evon_meter_energy_meter_a": [{"change": 2.0}],
        }

        # Simulate day 1 by patching dt_util.now
        day1 = datetime(2024, 3, 1, 0, 5, 0, tzinfo=_UTC)
        with _patch_dt_now(day1):
            await calc(smart_meters)

        # On day 1, no previous days in month, so month = today only
        assert smart_meters[0]["energy_today_calculated"] == 2.0
        assert smart_meters[0]["energy_this_month_calculated"] == 2.0

    @pytest.mark.asyncio
    async def test_day_2_includes_day_1_data(self, calc_method, mock_hass):
        """On day 2, energy_data_month[-1:] should be used for previous day."""
        coordinator, calc = calc_method

        # energy_data_month has 1 entry (day 1's consumption)
        smart_meters = [{"name": "Meter A", "id": "meter_a", "energy_data_month": [10.5]}]

        mock_hass.async_add_executor_job.return_value = {
            "sensor.evon_meter_energy_meter_a": [{"change": 3.0}],
        }

        day2 = datetime(2024, 3, 2, 14, 0, 0, tzinfo=_UTC)
        with _patch_dt_now(day2):
            await calc(smart_meters)

        assert smart_meters[0]["energy_today_calculated"] == 3.0
        # Month = day1 (10.5) + today (3.0) = 13.5
        assert smart_meters[0]["energy_this_month_calculated"] == 13.5

    @pytest.mark.asyncio
    async def test_midnight_exactly_day1_zero_stats(self, calc_method, mock_hass):
        """At exactly midnight on day 1, no stats for today yet."""
        coordinator, calc = calc_method

        smart_meters = [{"name": "Meter A", "id": "meter_a", "energy_data_month": []}]

        # No statistics yet (empty dict)
        mock_hass.async_add_executor_job.return_value = {}

        midnight = datetime(2024, 3, 1, 0, 0, 0, tzinfo=_UTC)
        with _patch_dt_now(midnight):
            await calc(smart_meters)

        # No stats available for today
        assert smart_meters[0]["energy_today_calculated"] is None
        # energy_this_month = energy_today when no monthly data
        assert smart_meters[0]["energy_this_month_calculated"] is None


class TestMonthBoundary:
    """Test energy calculation at month boundary."""

    @pytest.mark.asyncio
    async def test_last_day_of_month(self, calc_method, mock_hass):
        """On day 31, sum 30 previous days plus today."""
        coordinator, calc = calc_method

        # 30 days of historical data (5 kWh each)
        energy_data = [5.0] * 30
        smart_meters = [{"name": "Meter A", "id": "meter_a", "energy_data_month": energy_data}]

        mock_hass.async_add_executor_job.return_value = {
            "sensor.evon_meter_energy_meter_a": [{"change": 4.0}],
        }

        day31 = datetime(2024, 1, 31, 18, 0, 0, tzinfo=_UTC)
        with _patch_dt_now(day31):
            await calc(smart_meters)

        assert smart_meters[0]["energy_today_calculated"] == 4.0
        # Month = 30 days * 5 kWh + 4 kWh today = 154 kWh
        assert smart_meters[0]["energy_this_month_calculated"] == 154.0

    @pytest.mark.asyncio
    async def test_month_with_string_values_in_data(self, calc_method, mock_hass):
        """Test that string values in energy_data_month are parsed correctly."""
        coordinator, calc = calc_method

        # Mix of float and string values
        energy_data = [1.5, "2.5", 3.0, "invalid", 4.0]
        smart_meters = [{"name": "Meter A", "id": "meter_a", "energy_data_month": energy_data}]

        mock_hass.async_add_executor_job.return_value = {
            "sensor.evon_meter_energy_meter_a": [{"change": 1.0}],
        }

        # Day 6 means we look at last 5 entries
        day6 = datetime(2024, 3, 6, 12, 0, 0, tzinfo=_UTC)
        with _patch_dt_now(day6):
            await calc(smart_meters)

        assert smart_meters[0]["energy_today_calculated"] == 1.0
        # Sum of valid values: 1.5 + 2.5 + 3.0 + 0 (invalid skipped) + 4.0 = 11.0 + today 1.0 = 12.0
        assert smart_meters[0]["energy_this_month_calculated"] == 12.0


class TestStatsFailure:
    """Test behavior when statistics_during_period fails."""

    @pytest.mark.asyncio
    async def test_stats_failure_increments_counter(self, calc_method, mock_hass):
        """Test that statistics failures increment the failure counter."""
        coordinator, calc = calc_method
        coordinator._energy_stats_consecutive_failures = 0

        smart_meters = [{"name": "Meter A", "id": "meter_a", "energy_data_month": [5.0]}]

        mock_hass.async_add_executor_job.side_effect = ValueError("recorder not ready")

        day2 = datetime(2024, 3, 2, 12, 0, 0, tzinfo=_UTC)
        with _patch_dt_now(day2):
            await calc(smart_meters)

        assert coordinator._energy_stats_consecutive_failures == 1
        # energy_today should be None since stats failed
        assert smart_meters[0]["energy_today_calculated"] is None

    @pytest.mark.asyncio
    async def test_stats_success_resets_counter(self, calc_method, mock_hass):
        """Test that a successful stats call resets the failure counter."""
        coordinator, calc = calc_method
        coordinator._energy_stats_consecutive_failures = 5

        smart_meters = [{"name": "Meter A", "id": "meter_a", "energy_data_month": []}]

        mock_hass.async_add_executor_job.return_value = {}

        day1 = datetime(2024, 3, 1, 12, 0, 0, tzinfo=_UTC)
        with _patch_dt_now(day1):
            await calc(smart_meters)

        assert coordinator._energy_stats_consecutive_failures == 0


def _patch_dt_now(fixed_time):
    """Context manager to patch dt_util.now to return a fixed time."""
    import homeassistant.util.dt as dt_util

    original = dt_util.now

    def mock_now():
        return fixed_time

    dt_util.now = mock_now
    return contextlib.contextmanager(lambda: (setattr(dt_util, "now", mock_now), (yield), setattr(dt_util, "now", original)))()
