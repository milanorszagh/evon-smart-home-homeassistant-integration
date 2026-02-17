"""Tests for Evon energy statistics import."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.evon.statistics import (
    _get_last_import_times,
    _import_meter_statistics,
    _import_monthly_statistics,
    import_energy_statistics,
)
from tests.conftest import HAS_HA_TEST_FRAMEWORK, requires_ha_test_framework

# =============================================================================
# Unit tests (run without HA test framework)
# =============================================================================


def _make_hass():
    """Create a minimal mock hass for statistics tests."""
    hass = MagicMock()
    hass.data = {}
    return hass


def _make_recorder_mock():
    """Create a recorder mock whose async_add_executor_job passes through to the function."""
    mock_recorder = MagicMock()
    mock_recorder.async_add_executor_job = AsyncMock(side_effect=lambda fn, *args: fn(*args))
    return mock_recorder


class TestGetLastImportTimes:
    """Test rate-limit state management."""

    def test_creates_dict_on_first_access(self):
        hass = _make_hass()
        times = _get_last_import_times(hass)
        assert isinstance(times, dict)
        assert len(times) == 0

    def test_returns_same_dict_on_subsequent_access(self):
        hass = _make_hass()
        times1 = _get_last_import_times(hass)
        times1["meter1"] = datetime.now(tz=timezone.utc)  # noqa: UP017
        times2 = _get_last_import_times(hass)
        assert times2 is times1
        assert "meter1" in times2


class TestImportEnergyStatisticsRateLimiting:
    """Test rate limiting in import_energy_statistics."""

    @pytest.mark.asyncio
    async def test_empty_data_returns_early(self):
        hass = _make_hass()
        mock_add = MagicMock()
        with (
            patch("custom_components.evon.statistics.get_instance", return_value=_make_recorder_mock()),
            patch("custom_components.evon.statistics.async_add_external_statistics", mock_add),
        ):
            await import_energy_statistics(hass, "Meter1", "Meter", [], force=True)
        mock_add.assert_not_called()

    @pytest.mark.asyncio
    async def test_rate_limited_within_interval(self):
        hass = _make_hass()
        mock_add = MagicMock()
        with (
            patch("custom_components.evon.statistics.get_instance", return_value=_make_recorder_mock()),
            patch("custom_components.evon.statistics.async_add_external_statistics", mock_add),
        ):
            # First call: forced
            await import_energy_statistics(hass, "Meter1", "Meter", [1.0], force=True)
            assert mock_add.call_count == 1

            # Second call: rate-limited
            await import_energy_statistics(hass, "Meter1", "Meter", [1.0], force=False)
            assert mock_add.call_count == 1  # No additional calls

    @pytest.mark.asyncio
    async def test_force_bypasses_rate_limit(self):
        hass = _make_hass()
        mock_add = MagicMock()
        with (
            patch("custom_components.evon.statistics.get_instance", return_value=_make_recorder_mock()),
            patch("custom_components.evon.statistics.async_add_external_statistics", mock_add),
        ):
            await import_energy_statistics(hass, "Meter1", "Meter", [1.0], force=True)
            await import_energy_statistics(hass, "Meter1", "Meter", [1.0], force=True)
            assert mock_add.call_count == 2

    @pytest.mark.asyncio
    async def test_no_recorder_returns_early(self):
        hass = _make_hass()
        mock_add = MagicMock()
        with (
            patch("custom_components.evon.statistics.get_instance", return_value=None),
            patch("custom_components.evon.statistics.async_add_external_statistics", mock_add),
        ):
            await import_energy_statistics(hass, "Meter1", "Meter", [1.0], force=True)
        mock_add.assert_not_called()


class TestImportMeterStatistics:
    """Test daily statistics import."""

    @pytest.mark.asyncio
    async def test_basic_daily_import(self):
        hass = _make_hass()
        mock_add = MagicMock()
        with (
            patch("custom_components.evon.statistics.get_instance", return_value=_make_recorder_mock()),
            patch("custom_components.evon.statistics.async_add_external_statistics", mock_add),
        ):
            await _import_meter_statistics(hass, "evon:energy_meter1", "Meter 1", [1.0, 2.0, 3.0])
        mock_add.assert_called_once()
        metadata, statistics = mock_add.call_args[0][1], mock_add.call_args[0][2]
        assert metadata["statistic_id"] == "evon:energy_meter1"
        assert metadata["has_sum"] is True
        assert metadata["has_mean"] is False
        assert metadata["source"] == "evon"
        # baseline + 3 data points
        assert len(statistics) == 4
        assert statistics[0]["sum"] == 0.0  # baseline
        assert statistics[1]["sum"] == 1.0
        assert statistics[2]["sum"] == 3.0
        assert statistics[3]["sum"] == 6.0

    @pytest.mark.asyncio
    async def test_none_values_cleaned_to_zero(self):
        hass = _make_hass()
        mock_add = MagicMock()
        with (
            patch("custom_components.evon.statistics.get_instance", return_value=_make_recorder_mock()),
            patch("custom_components.evon.statistics.async_add_external_statistics", mock_add),
        ):
            await _import_meter_statistics(hass, "evon:test", "Test", [None, 2.0, None])
        statistics = mock_add.call_args[0][2]
        # [0.0, 2.0, 0.0] → cumulative: [0.0, 2.0, 2.0]
        assert statistics[1]["sum"] == 0.0
        assert statistics[2]["sum"] == 2.0
        assert statistics[3]["sum"] == 2.0

    @pytest.mark.asyncio
    async def test_string_values_converted(self):
        hass = _make_hass()
        mock_add = MagicMock()
        with (
            patch("custom_components.evon.statistics.get_instance", return_value=_make_recorder_mock()),
            patch("custom_components.evon.statistics.async_add_external_statistics", mock_add),
        ):
            await _import_meter_statistics(hass, "evon:test", "Test", ["1.5", "invalid", "3.0"])
        statistics = mock_add.call_args[0][2]
        # [1.5, 0.0, 3.0] → cumulative: [1.5, 1.5, 4.5]
        assert statistics[1]["sum"] == 1.5
        assert statistics[2]["sum"] == 1.5
        assert statistics[3]["sum"] == 4.5

    @pytest.mark.asyncio
    async def test_empty_cleaned_values_returns_early(self):
        hass = _make_hass()
        mock_add = MagicMock()
        with (
            patch("custom_components.evon.statistics.get_instance", return_value=_make_recorder_mock()),
            patch("custom_components.evon.statistics.async_add_external_statistics", mock_add),
        ):
            await _import_meter_statistics(hass, "evon:test", "Test", [])
        mock_add.assert_not_called()

    @pytest.mark.asyncio
    async def test_single_day(self):
        hass = _make_hass()
        mock_add = MagicMock()
        with (
            patch("custom_components.evon.statistics.get_instance", return_value=_make_recorder_mock()),
            patch("custom_components.evon.statistics.async_add_external_statistics", mock_add),
        ):
            await _import_meter_statistics(hass, "evon:test", "Test", [5.0])
        statistics = mock_add.call_args[0][2]
        assert len(statistics) == 2  # baseline + 1 day
        assert statistics[0]["sum"] == 0.0
        assert statistics[1]["sum"] == 5.0


class TestImportMonthlyStatistics:
    """Test monthly statistics import."""

    @pytest.mark.asyncio
    async def test_basic_monthly_import(self):
        hass = _make_hass()
        mock_add = MagicMock()
        with (
            patch("custom_components.evon.statistics.get_instance", return_value=_make_recorder_mock()),
            patch("custom_components.evon.statistics.async_add_external_statistics", mock_add),
        ):
            await _import_monthly_statistics(hass, "evon:monthly_test", "Test Monthly", [10.0, 20.0, 30.0])
        mock_add.assert_called_once()
        metadata, statistics = mock_add.call_args[0][1], mock_add.call_args[0][2]
        assert metadata["statistic_id"] == "evon:monthly_test"
        # baseline + 3 months
        assert len(statistics) == 4
        assert statistics[0]["sum"] == 0.0
        assert statistics[1]["sum"] == 10.0
        assert statistics[2]["sum"] == 30.0
        assert statistics[3]["sum"] == 60.0

    @pytest.mark.asyncio
    async def test_empty_monthly_returns_early(self):
        hass = _make_hass()
        mock_add = MagicMock()
        with (
            patch("custom_components.evon.statistics.get_instance", return_value=_make_recorder_mock()),
            patch("custom_components.evon.statistics.async_add_external_statistics", mock_add),
        ):
            await _import_monthly_statistics(hass, "evon:test", "Test", [])
        mock_add.assert_not_called()

    @pytest.mark.asyncio
    async def test_monthly_none_values_cleaned(self):
        hass = _make_hass()
        mock_add = MagicMock()
        with (
            patch("custom_components.evon.statistics.get_instance", return_value=_make_recorder_mock()),
            patch("custom_components.evon.statistics.async_add_external_statistics", mock_add),
        ):
            await _import_monthly_statistics(hass, "evon:test", "Test", [None, 20.0])
        statistics = mock_add.call_args[0][2]
        assert statistics[1]["sum"] == 0.0
        assert statistics[2]["sum"] == 20.0

    @pytest.mark.asyncio
    async def test_single_month(self):
        hass = _make_hass()
        mock_add = MagicMock()
        with (
            patch("custom_components.evon.statistics.get_instance", return_value=_make_recorder_mock()),
            patch("custom_components.evon.statistics.async_add_external_statistics", mock_add),
        ):
            await _import_monthly_statistics(hass, "evon:test", "Test", [42.0])
        statistics = mock_add.call_args[0][2]
        assert len(statistics) == 2  # baseline + 1 month
        assert statistics[1]["sum"] == 42.0


class TestImportEnergyStatisticsFull:
    """Test the full import_energy_statistics function."""

    @pytest.mark.asyncio
    async def test_meter_id_normalized(self):
        hass = _make_hass()
        mock_add = MagicMock()
        with (
            patch("custom_components.evon.statistics.get_instance", return_value=_make_recorder_mock()),
            patch("custom_components.evon.statistics.async_add_external_statistics", mock_add),
        ):
            await import_energy_statistics(hass, "SmartMeter.123", "Meter", [1.0], force=True)
        metadata = mock_add.call_args[0][1]
        assert metadata["statistic_id"] == "evon:energy_smartmeter_123"

    @pytest.mark.asyncio
    async def test_with_feed_in_data(self):
        hass = _make_hass()
        mock_add = MagicMock()
        with (
            patch("custom_components.evon.statistics.get_instance", return_value=_make_recorder_mock()),
            patch("custom_components.evon.statistics.async_add_external_statistics", mock_add),
        ):
            await import_energy_statistics(hass, "Meter1", "Meter", [1.0], feed_in_data_month=[0.5], force=True)
        # 2 calls: consumption + feed-in
        assert mock_add.call_count == 2
        ids = [call[0][1]["statistic_id"] for call in mock_add.call_args_list]
        assert "evon:energy_meter1" in ids
        assert "evon:feed_in_meter1" in ids

    @pytest.mark.asyncio
    async def test_with_yearly_data(self):
        hass = _make_hass()
        mock_add = MagicMock()
        with (
            patch("custom_components.evon.statistics.get_instance", return_value=_make_recorder_mock()),
            patch("custom_components.evon.statistics.async_add_external_statistics", mock_add),
        ):
            await import_energy_statistics(hass, "Meter1", "Meter", [1.0], energy_data_year=[10.0], force=True)
        # 2 calls: daily + monthly
        assert mock_add.call_count == 2

    @pytest.mark.asyncio
    async def test_all_data_types(self):
        hass = _make_hass()
        mock_add = MagicMock()
        with (
            patch("custom_components.evon.statistics.get_instance", return_value=_make_recorder_mock()),
            patch("custom_components.evon.statistics.async_add_external_statistics", mock_add),
        ):
            await import_energy_statistics(
                hass,
                "Meter1",
                "Meter",
                [1.0],
                feed_in_data_month=[0.5],
                energy_data_year=[10.0],
                force=True,
            )
        # 3 calls: daily + feed-in + monthly
        assert mock_add.call_count == 3


# =============================================================================
# Integration tests (require pytest-homeassistant-custom-component)
# =============================================================================

if HAS_HA_TEST_FRAMEWORK:
    from homeassistant.core import HomeAssistant


@requires_ha_test_framework
@pytest.mark.asyncio
async def test_import_energy_statistics_basic(hass: HomeAssistant) -> None:
    """Test basic import flow with simple energy data."""
    mock_recorder_instance = _make_recorder_mock()
    mock_add_stats = MagicMock()

    with (
        patch(
            "custom_components.evon.statistics.get_instance",
            return_value=mock_recorder_instance,
        ),
        patch(
            "custom_components.evon.statistics.async_add_external_statistics",
            mock_add_stats,
        ),
    ):
        await import_energy_statistics(
            hass,
            "SmartMeter123",
            "Smart Meter",
            [1.0, 2.0, 3.0],
            force=True,
        )

    mock_add_stats.assert_called_once()
    call_args = mock_add_stats.call_args
    metadata = call_args[0][1]
    statistics = call_args[0][2]

    # Verify metadata
    assert metadata["statistic_id"] == "evon:energy_smartmeter123"
    assert metadata["name"] == "Smart Meter Energy"
    assert metadata["source"] == "evon"
    assert metadata["has_sum"] is True
    assert metadata["has_mean"] is False

    # Verify statistics: baseline + 3 data points = 4 entries
    assert len(statistics) == 4
    # Baseline should have sum=0.0
    assert statistics[0]["sum"] == 0.0
    # Cumulative sums: 1.0, 3.0, 6.0
    assert statistics[1]["sum"] == 1.0
    assert statistics[2]["sum"] == 3.0
    assert statistics[3]["sum"] == 6.0


@requires_ha_test_framework
@pytest.mark.asyncio
async def test_import_energy_statistics_empty_data(hass: HomeAssistant) -> None:
    """Test that empty energy data returns early without importing."""
    mock_add_stats = MagicMock()

    with (
        patch(
            "custom_components.evon.statistics.get_instance",
            return_value=_make_recorder_mock(),
        ),
        patch(
            "custom_components.evon.statistics.async_add_external_statistics",
            mock_add_stats,
        ),
    ):
        await import_energy_statistics(
            hass,
            "SmartMeter123",
            "Smart Meter",
            [],
            force=True,
        )

    mock_add_stats.assert_not_called()


@requires_ha_test_framework
@pytest.mark.asyncio
async def test_import_energy_statistics_rate_limiting(hass: HomeAssistant) -> None:
    """Test that the second call without force is rate-limited."""
    mock_add_stats = MagicMock()

    with (
        patch(
            "custom_components.evon.statistics.get_instance",
            return_value=_make_recorder_mock(),
        ),
        patch(
            "custom_components.evon.statistics.async_add_external_statistics",
            mock_add_stats,
        ),
    ):
        # First call with force=True should import
        await import_energy_statistics(
            hass,
            "SmartMeter123",
            "Smart Meter",
            [1.0, 2.0, 3.0],
            force=True,
        )
        assert mock_add_stats.call_count == 1

        # Second call without force should be rate-limited
        await import_energy_statistics(
            hass,
            "SmartMeter123",
            "Smart Meter",
            [1.0, 2.0, 3.0],
            force=False,
        )
        # Call count should remain 1 (rate-limited)
        assert mock_add_stats.call_count == 1


@requires_ha_test_framework
@pytest.mark.asyncio
async def test_import_energy_statistics_with_feed_in(hass: HomeAssistant) -> None:
    """Test import with both consumption and feed-in data."""
    mock_add_stats = MagicMock()

    with (
        patch(
            "custom_components.evon.statistics.get_instance",
            return_value=_make_recorder_mock(),
        ),
        patch(
            "custom_components.evon.statistics.async_add_external_statistics",
            mock_add_stats,
        ),
    ):
        await import_energy_statistics(
            hass,
            "SmartMeter123",
            "Smart Meter",
            energy_data_month=[1.0, 2.0, 3.0],
            feed_in_data_month=[0.5, 1.0, 1.5],
            force=True,
        )

    # Should be called twice: once for consumption, once for feed-in
    assert mock_add_stats.call_count == 2

    # First call: consumption
    consumption_metadata = mock_add_stats.call_args_list[0][0][1]
    assert consumption_metadata["statistic_id"] == "evon:energy_smartmeter123"
    assert consumption_metadata["name"] == "Smart Meter Energy"

    # Second call: feed-in
    feed_in_metadata = mock_add_stats.call_args_list[1][0][1]
    assert feed_in_metadata["statistic_id"] == "evon:feed_in_smartmeter123"
    assert feed_in_metadata["name"] == "Smart Meter Feed-in"


@requires_ha_test_framework
@pytest.mark.asyncio
async def test_import_energy_statistics_with_monthly(hass: HomeAssistant) -> None:
    """Test import with both daily and monthly energy data."""
    mock_add_stats = MagicMock()

    with (
        patch(
            "custom_components.evon.statistics.get_instance",
            return_value=_make_recorder_mock(),
        ),
        patch(
            "custom_components.evon.statistics.async_add_external_statistics",
            mock_add_stats,
        ),
    ):
        await import_energy_statistics(
            hass,
            "SmartMeter123",
            "Smart Meter",
            energy_data_month=[1.0, 2.0, 3.0],
            energy_data_year=[10.0, 20.0, 30.0],
            force=True,
        )

    # Should be called at least twice: daily consumption + monthly consumption
    assert mock_add_stats.call_count >= 2

    # First call: daily consumption
    daily_metadata = mock_add_stats.call_args_list[0][0][1]
    assert daily_metadata["statistic_id"] == "evon:energy_smartmeter123"

    # Second call: monthly consumption
    monthly_metadata = mock_add_stats.call_args_list[1][0][1]
    assert monthly_metadata["statistic_id"] == "evon:energy_monthly_smartmeter123"
    assert monthly_metadata["name"] == "Smart Meter Monthly Energy"


@requires_ha_test_framework
@pytest.mark.asyncio
async def test_import_statistics_data_cleaning(hass: HomeAssistant) -> None:
    """Test that None values and string values are cleaned properly."""
    mock_add_stats = MagicMock()

    with (
        patch(
            "custom_components.evon.statistics.get_instance",
            return_value=_make_recorder_mock(),
        ),
        patch(
            "custom_components.evon.statistics.async_add_external_statistics",
            mock_add_stats,
        ),
    ):
        await import_energy_statistics(
            hass,
            "SmartMeter123",
            "Smart Meter",
            [None, "1.5", 2.0, "invalid"],
            force=True,
        )

    mock_add_stats.assert_called_once()
    statistics = mock_add_stats.call_args[0][2]

    # Cleaned values: [0.0, 1.5, 2.0, 0.0]
    # baseline + 4 data points = 5 entries
    assert len(statistics) == 5
    # Baseline
    assert statistics[0]["sum"] == 0.0
    # Cumulative sums: 0.0, 1.5, 3.5, 3.5
    assert statistics[1]["sum"] == 0.0  # None -> 0.0
    assert statistics[2]["sum"] == 1.5  # "1.5" -> 1.5, cumulative = 0.0 + 1.5
    assert statistics[3]["sum"] == 3.5  # 2.0 -> 2.0, cumulative = 1.5 + 2.0
    assert statistics[4]["sum"] == 3.5  # "invalid" -> 0.0, cumulative = 3.5 + 0.0


@requires_ha_test_framework
@pytest.mark.asyncio
async def test_import_statistics_cumulative_sum(hass: HomeAssistant) -> None:
    """Test that the statistics have correct cumulative sums."""
    mock_add_stats = MagicMock()

    with (
        patch(
            "custom_components.evon.statistics.get_instance",
            return_value=_make_recorder_mock(),
        ),
        patch(
            "custom_components.evon.statistics.async_add_external_statistics",
            mock_add_stats,
        ),
    ):
        await import_energy_statistics(
            hass,
            "SmartMeter123",
            "Smart Meter",
            [1.0, 2.0, 3.0],
            force=True,
        )

    mock_add_stats.assert_called_once()
    statistics = mock_add_stats.call_args[0][2]

    # With data [1.0, 2.0, 3.0], the sums should be:
    # [0.0 (baseline), 1.0, 3.0, 6.0]
    assert len(statistics) == 4
    assert statistics[0]["sum"] == 0.0  # baseline
    assert statistics[1]["sum"] == 1.0  # 0.0 + 1.0
    assert statistics[2]["sum"] == 3.0  # 1.0 + 2.0
    assert statistics[3]["sum"] == 6.0  # 3.0 + 3.0


@requires_ha_test_framework
@pytest.mark.asyncio
async def test_import_statistics_no_recorder(hass: HomeAssistant) -> None:
    """Test that import is skipped when recorder is not available."""
    mock_add_stats = MagicMock()

    with (
        patch(
            "custom_components.evon.statistics.get_instance",
            return_value=None,
        ),
        patch(
            "custom_components.evon.statistics.async_add_external_statistics",
            mock_add_stats,
        ),
    ):
        await import_energy_statistics(
            hass,
            "SmartMeter123",
            "Smart Meter",
            [1.0, 2.0, 3.0],
            force=True,
        )

    mock_add_stats.assert_not_called()
