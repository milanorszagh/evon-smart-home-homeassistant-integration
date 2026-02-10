"""Integration tests for Evon energy statistics import."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from tests.conftest import HAS_HA_TEST_FRAMEWORK, requires_ha_test_framework

pytestmark = requires_ha_test_framework

if HAS_HA_TEST_FRAMEWORK:
    from unittest.mock import MagicMock

    from homeassistant.core import HomeAssistant

    from custom_components.evon.statistics import import_energy_statistics


@pytest.mark.asyncio
async def test_import_energy_statistics_basic(hass: HomeAssistant) -> None:
    """Test basic import flow with simple energy data."""
    mock_recorder_instance = MagicMock()
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


@pytest.mark.asyncio
async def test_import_energy_statistics_empty_data(hass: HomeAssistant) -> None:
    """Test that empty energy data returns early without importing."""
    mock_add_stats = MagicMock()

    with (
        patch(
            "custom_components.evon.statistics.get_instance",
            return_value=MagicMock(),
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


@pytest.mark.asyncio
async def test_import_energy_statistics_rate_limiting(hass: HomeAssistant) -> None:
    """Test that the second call without force is rate-limited."""
    mock_add_stats = MagicMock()

    with (
        patch(
            "custom_components.evon.statistics.get_instance",
            return_value=MagicMock(),
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


@pytest.mark.asyncio
async def test_import_energy_statistics_with_feed_in(hass: HomeAssistant) -> None:
    """Test import with both consumption and feed-in data."""
    mock_add_stats = MagicMock()

    with (
        patch(
            "custom_components.evon.statistics.get_instance",
            return_value=MagicMock(),
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


@pytest.mark.asyncio
async def test_import_energy_statistics_with_monthly(hass: HomeAssistant) -> None:
    """Test import with both daily and monthly energy data."""
    mock_add_stats = MagicMock()

    with (
        patch(
            "custom_components.evon.statistics.get_instance",
            return_value=MagicMock(),
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


@pytest.mark.asyncio
async def test_import_statistics_data_cleaning(hass: HomeAssistant) -> None:
    """Test that None values and string values are cleaned properly."""
    mock_add_stats = MagicMock()

    with (
        patch(
            "custom_components.evon.statistics.get_instance",
            return_value=MagicMock(),
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


@pytest.mark.asyncio
async def test_import_statistics_cumulative_sum(hass: HomeAssistant) -> None:
    """Test that the statistics have correct cumulative sums."""
    mock_add_stats = MagicMock()

    with (
        patch(
            "custom_components.evon.statistics.get_instance",
            return_value=MagicMock(),
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
