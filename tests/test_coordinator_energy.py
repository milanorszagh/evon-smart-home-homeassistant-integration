"""Tests for batched energy statistics calculation in the coordinator."""

from __future__ import annotations

from pathlib import Path
import types
from unittest.mock import AsyncMock, MagicMock

import pytest


class TestBatchedEnergyStatistics:
    """Test that _calculate_energy_today_and_month makes a single batched call."""

    @pytest.fixture
    def mock_hass(self):
        """Create a mock HomeAssistant instance."""
        hass = MagicMock()
        hass.async_add_executor_job = AsyncMock()
        hass.async_create_task = MagicMock()
        return hass

    @pytest.fixture
    def coordinator_and_method(self, mock_hass):
        """Create a coordinator-like object and bind the real method."""
        import contextlib

        # Import dependencies that the method uses
        from homeassistant.components.recorder.statistics import statistics_during_period
        from homeassistant.const import UnitOfEnergy
        from homeassistant.exceptions import HomeAssistantError
        from homeassistant.util import dt as dt_util

        from custom_components.evon.const import DOMAIN, ENERGY_STATS_FAILURE_LOG_THRESHOLD

        # Create a mock recorder instance with its own executor job
        mock_recorder = MagicMock()
        mock_recorder.async_add_executor_job = AsyncMock()

        # Create a namespace with all required names
        ns = {}
        ns["statistics_during_period"] = statistics_during_period
        ns["UnitOfEnergy"] = UnitOfEnergy
        ns["HomeAssistantError"] = HomeAssistantError
        ns["dt_util"] = dt_util
        ns["ENERGY_STATS_FAILURE_LOG_THRESHOLD"] = ENERGY_STATS_FAILURE_LOG_THRESHOLD
        ns["DOMAIN"] = DOMAIN
        ns["contextlib"] = contextlib
        ns["get_recorder_instance"] = lambda hass: mock_recorder
        # Create a mock entity registry that maps unique_ids to entity_ids
        mock_ent_reg = MagicMock()
        mock_ent_reg.async_get_entity_id.side_effect = lambda domain, platform, unique_id: (
            f"sensor.{unique_id.replace('evon_meter_energy_', '')}_energy_total"
        )
        mock_er = MagicMock()
        mock_er.async_get.return_value = mock_ent_reg
        ns["er"] = mock_er
        ns["_LOGGER"] = MagicMock()

        # Read and compile just the method as a standalone async function
        import ast
        import textwrap

        source_path = str(
            Path(__file__).resolve().parent.parent / "custom_components" / "evon" / "coordinator" / "__init__.py"
        )
        with open(source_path) as f:
            source = f.read()

        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.AsyncFunctionDef) and node.name == "_calculate_energy_today_and_month":
                lines = source.splitlines()
                func_lines = lines[node.lineno - 1 : node.end_lineno]
                func_source = "\n".join(func_lines)
                func_source = textwrap.dedent(func_source)
                break

        exec(compile(func_source, "<test>", "exec"), ns)
        real_method = ns["_calculate_energy_today_and_month"]

        # Create coordinator-like object
        obj = MagicMock()
        obj.hass = mock_hass
        obj._energy_stats_consecutive_failures = 0
        obj._mock_recorder = mock_recorder

        # Bind the real method
        bound = types.MethodType(real_method, obj)

        return obj, bound

    @pytest.mark.asyncio
    async def test_single_call_for_multiple_meters(self, coordinator_and_method, mock_hass):
        """Verify statistics_during_period is called exactly ONCE for 3 meters."""
        coordinator, calc = coordinator_and_method

        smart_meters = [
            {"name": "Meter A", "id": "meter_a"},
            {"name": "Meter B", "id": "meter_b"},
            {"name": "Meter C", "id": "meter_c"},
        ]

        coordinator._mock_recorder.async_add_executor_job.return_value = {
            "sensor.meter_a_energy_total": [{"change": 1.5}, {"change": 2.0}],
            "sensor.meter_b_energy_total": [{"change": 3.0}],
        }

        await calc(smart_meters)

        # The key assertion: exactly ONE call to recorder's async_add_executor_job
        assert coordinator._mock_recorder.async_add_executor_job.call_count == 1

        # Verify the call included all 3 entity IDs
        call_args = coordinator._mock_recorder.async_add_executor_job.call_args
        entity_ids_arg = call_args[0][4]  # 5th positional arg is the entity_ids list
        assert len(entity_ids_arg) == 3
        assert "sensor.meter_a_energy_total" in entity_ids_arg
        assert "sensor.meter_b_energy_total" in entity_ids_arg
        assert "sensor.meter_c_energy_total" in entity_ids_arg

    @pytest.mark.asyncio
    async def test_energy_today_calculated_from_stats(self, coordinator_and_method, mock_hass):
        """Verify energy_today is calculated correctly from hourly changes."""
        coordinator, calc = coordinator_and_method

        smart_meters = [
            {"name": "Meter A", "id": "meter_a"},
        ]

        coordinator._mock_recorder.async_add_executor_job.return_value = {
            "sensor.meter_a_energy_total": [
                {"change": 1.5},
                {"change": 2.0},
                {"change": 0.5},
            ],
        }

        await calc(smart_meters)

        assert smart_meters[0]["energy_today_calculated"] == 4.0

    @pytest.mark.asyncio
    async def test_no_stats_returns_none(self, coordinator_and_method, mock_hass):
        """Verify energy_today is None when no stats are available."""
        coordinator, calc = coordinator_and_method

        smart_meters = [
            {"name": "Meter A", "id": "meter_a"},
        ]

        coordinator._mock_recorder.async_add_executor_job.return_value = {}

        await calc(smart_meters)

        assert smart_meters[0]["energy_today_calculated"] is None

    @pytest.mark.asyncio
    async def test_empty_meters_no_call(self, coordinator_and_method, mock_hass):
        """Verify no call is made when there are no smart meters."""
        coordinator, calc = coordinator_and_method

        await calc([])

        assert coordinator._mock_recorder.async_add_executor_job.call_count == 0

    @pytest.mark.asyncio
    async def test_month_calculation_with_energy_data(self, coordinator_and_method, mock_hass):
        """Verify monthly energy calculation combines historical data and today."""
        coordinator, calc = coordinator_and_method

        smart_meters = [
            {
                "name": "Meter A",
                "id": "meter_a",
                "energy_data_month": [10.0] * 30,
            },
        ]

        coordinator._mock_recorder.async_add_executor_job.return_value = {
            "sensor.meter_a_energy_total": [{"change": 5.0}],
        }

        await calc(smart_meters)

        assert smart_meters[0]["energy_today_calculated"] == 5.0
        assert smart_meters[0]["energy_this_month_calculated"] is not None
        assert smart_meters[0]["energy_this_month_calculated"] > 0

    @pytest.mark.asyncio
    async def test_batch_error_handling(self, coordinator_and_method, mock_hass):
        """Verify error in batch call is handled gracefully."""
        coordinator, calc = coordinator_and_method

        smart_meters = [
            {"name": "Meter A", "id": "meter_a"},
            {"name": "Meter B", "id": "meter_b"},
        ]

        coordinator._mock_recorder.async_add_executor_job.side_effect = Exception("Recorder not ready")

        await calc(smart_meters)

        # Both meters should have None for energy_today
        assert smart_meters[0]["energy_today_calculated"] is None
        assert smart_meters[1]["energy_today_calculated"] is None
        # Failure counter should increment once (not twice)
        assert coordinator._energy_stats_consecutive_failures == 1
