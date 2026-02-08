"""External statistics support for Evon Smart Home integration.

This module imports historical energy data from Evon's SmartMeter into
Home Assistant's long-term statistics, providing accurate daily energy
values for PREVIOUS days (not including today).

## Data Source: EnergyDataMonth

The Evon SmartMeter provides `EnergyDataMonth`, a 31-element rolling window:
- First element: Energy consumption from 31 days ago
- Last element: Energy consumption from YESTERDAY (not today)
- Today's consumption: Use HA's utility_meter on Energy Total sensor

## How Statistics Work

HA statistics store cumulative `sum` values. To display daily consumption,
use `stat_types: [change]` which calculates the difference between days.

## Dashboard Display

```yaml
type: statistics-graph
entities:
  - entity: evon:energy_smartmeter{ID}
    name: Daily Energy
stat_types:
  - change
period: day
days_to_show: 31
```

For today's consumption, use a utility_meter in configuration.yaml:
```yaml
utility_meter:
  energy_today:
    source: sensor.smart_meter_energy_total
    cycle: daily
```
"""

from __future__ import annotations

from datetime import datetime, timedelta
import logging

from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.models import StatisticData, StatisticMetaData
from homeassistant.components.recorder.models.statistics import StatisticMeanType
from homeassistant.components.recorder.statistics import async_add_external_statistics
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)

# Minimum interval between statistics imports (avoid spamming)
MIN_IMPORT_INTERVAL = timedelta(hours=1)

# Key for storing rate-limit state in hass.data (survives reloads correctly)
_HASS_DATA_KEY = "evon_statistics_last_import_times"


def _get_last_import_times(hass: HomeAssistant) -> dict[str, datetime]:
    """Get the per-meter last import times dict from hass.data."""
    if _HASS_DATA_KEY not in hass.data:
        hass.data[_HASS_DATA_KEY] = {}
    return hass.data[_HASS_DATA_KEY]


async def import_energy_statistics(
    hass: HomeAssistant,
    meter_id: str,
    meter_name: str,
    energy_data_month: list[float],
    feed_in_data_month: list[float] | None = None,
    energy_data_year: list[float] | None = None,
    force: bool = False,
) -> None:
    """Import daily and monthly energy statistics from Evon SmartMeter data.

    This function imports the EnergyDataMonth array into HA's external statistics
    for daily consumption, and EnergyDataYear for monthly consumption.

    Args:
        hass: Home Assistant instance
        meter_id: SmartMeter instance ID (e.g., "SmartMeter3006939")
        meter_name: Display name for the meter
        energy_data_month: Array of daily energy values (kWh), first element = N days ago,
                          last element = yesterday. Does NOT include today.
        feed_in_data_month: Optional array of daily feed-in values (same format)
        energy_data_year: Optional array of monthly energy values (kWh), first = 12 months ago,
                         last = previous month. Does NOT include current month.
        force: If True, bypass rate limiting (for initial backfill)
    """
    if not energy_data_month:
        return

    # Rate limiting: avoid importing too frequently (unless forced)
    now = dt_util.now()
    last_import_times = _get_last_import_times(hass)
    last_import = last_import_times.get(meter_id)
    if not force and last_import and (now - last_import) < MIN_IMPORT_INTERVAL:
        return

    _LOGGER.debug(
        "Importing energy statistics for %s with %d days of data",
        meter_id,
        len(energy_data_month),
    )

    # Check if recorder is available
    if not get_instance(hass):
        _LOGGER.debug("Recorder not available, skipping statistics import")
        return

    # Normalize meter_id for statistic_id (lowercase, no special chars)
    safe_meter_id = meter_id.lower().replace(".", "_")

    # Import consumption statistics
    await _import_meter_statistics(
        hass=hass,
        statistic_id=f"evon:energy_{safe_meter_id}",
        name=f"{meter_name} Energy",
        daily_values=energy_data_month,
    )

    # Import feed-in statistics if available
    if feed_in_data_month:
        await _import_meter_statistics(
            hass=hass,
            statistic_id=f"evon:feed_in_{safe_meter_id}",
            name=f"{meter_name} Feed-in",
            daily_values=feed_in_data_month,
        )

    # Import monthly consumption statistics if available
    if energy_data_year:
        await _import_monthly_statistics(
            hass=hass,
            statistic_id=f"evon:energy_monthly_{safe_meter_id}",
            name=f"{meter_name} Monthly Energy",
            monthly_values=energy_data_year,
        )

    # Update last import time for rate limiting
    _get_last_import_times(hass)[meter_id] = dt_util.now()


async def _import_meter_statistics(
    hass: HomeAssistant,
    statistic_id: str,
    name: str,
    daily_values: list[float],
) -> None:
    """Import statistics for a single meter.

    Args:
        hass: Home Assistant instance
        statistic_id: Unique statistic ID (e.g., "evon:energy_smartmeter3006939")
        name: Display name
        daily_values: Array of daily values (rolling window, last element = yesterday)
    """
    # Filter out None/invalid values and convert strings to floats
    cleaned_values: list[float] = []
    for v in daily_values:
        if v is None:
            cleaned_values.append(0.0)
        elif isinstance(v, str):
            try:
                cleaned_values.append(float(v))
            except ValueError:
                cleaned_values.append(0.0)
        else:
            cleaned_values.append(float(v))

    if not cleaned_values:
        return

    # Create metadata
    metadata = StatisticMetaData(
        has_mean=False,
        has_sum=True,
        mean_type=StatisticMeanType.NONE,
        name=name,
        source="evon",
        statistic_id=statistic_id,
        unit_class=None,
        unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
    )

    # EnergyDataMonth is a rolling window of PREVIOUS days (NOT including today)
    # Last element = yesterday's consumption
    # First element = N days ago (where N = array length)
    num_days = len(cleaned_values)
    yesterday = dt_util.now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)
    window_start = yesterday - timedelta(days=num_days - 1)

    _LOGGER.debug(
        "Importing statistics for %s: %d days from %s to %s (yesterday)",
        statistic_id,
        num_days,
        window_start.date(),
        yesterday.date(),
    )

    # Build statistics data with a baseline point before the window
    # This ensures the first day's "change" value is correct regardless of old data
    statistics: list[StatisticData] = []

    # Add baseline point (day before window starts) with sum=0
    # This overwrites any old data at this point and ensures correct change calculation
    baseline_date = window_start - timedelta(days=1)
    statistics.append(
        StatisticData(
            start=baseline_date,
            sum=0.0,
        )
    )

    cumulative_sum = 0.0
    for day_index, daily_value in enumerate(cleaned_values):
        # Calculate the date for this entry
        day_date = window_start + timedelta(days=day_index)

        # Skip future dates (shouldn't happen since we end at yesterday)
        if day_date > yesterday:
            break

        # Add daily value to cumulative sum
        cumulative_sum += daily_value

        # Create statistic entry for the start of this day
        statistics.append(
            StatisticData(
                start=day_date,
                sum=cumulative_sum,
            )
        )

    if statistics:
        _LOGGER.debug(
            "Importing %d daily statistics for %s (from %s to %s)",
            len(statistics),
            statistic_id,
            statistics[0]["start"].date(),
            statistics[-1]["start"].date(),
        )
        async_add_external_statistics(hass, metadata, statistics)
        _LOGGER.debug("Statistics import completed for %s", statistic_id)
    else:
        _LOGGER.debug("No new statistics to import for %s (already up to date)", statistic_id)


async def _import_monthly_statistics(
    hass: HomeAssistant,
    statistic_id: str,
    name: str,
    monthly_values: list[float],
) -> None:
    """Import monthly statistics for a meter.

    Args:
        hass: Home Assistant instance
        statistic_id: Unique statistic ID (e.g., "evon:energy_monthly_smartmeter3006939")
        name: Display name
        monthly_values: Array of monthly values (rolling window, last element = previous month)
    """
    # Filter out None/invalid values and convert strings to floats
    cleaned_values: list[float] = []
    for v in monthly_values:
        if v is None:
            cleaned_values.append(0.0)
        elif isinstance(v, str):
            try:
                cleaned_values.append(float(v))
            except ValueError:
                cleaned_values.append(0.0)
        else:
            cleaned_values.append(float(v))

    if not cleaned_values:
        return

    # Create metadata
    metadata = StatisticMetaData(
        has_mean=False,
        has_sum=True,
        mean_type=StatisticMeanType.NONE,
        name=name,
        source="evon",
        statistic_id=statistic_id,
        unit_class=None,
        unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
    )

    # EnergyDataYear is a rolling window of PREVIOUS months (NOT including current month)
    # Last element = previous month's consumption
    # First element = N months ago (where N = array length)
    num_months = len(cleaned_values)
    now = dt_util.now()

    # Previous month's first day
    if now.month == 1:
        prev_month_start = now.replace(year=now.year - 1, month=12, day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        prev_month_start = now.replace(month=now.month - 1, day=1, hour=0, minute=0, second=0, microsecond=0)

    # Calculate the start month (N months before previous month)
    window_start_year = prev_month_start.year
    window_start_month = prev_month_start.month - (num_months - 1)
    while window_start_month <= 0:
        window_start_month += 12
        window_start_year -= 1
    window_start = prev_month_start.replace(year=window_start_year, month=window_start_month)

    _LOGGER.debug(
        "Importing monthly statistics for %s: %d months from %s to %s",
        statistic_id,
        num_months,
        window_start.strftime("%Y-%m"),
        prev_month_start.strftime("%Y-%m"),
    )

    # Build statistics data with a baseline point before the window
    statistics: list[StatisticData] = []

    # Add baseline point (month before window starts) with sum=0
    baseline_year = window_start.year
    baseline_month = window_start.month - 1
    if baseline_month <= 0:
        baseline_month = 12
        baseline_year -= 1
    baseline_date = window_start.replace(year=baseline_year, month=baseline_month, day=1)
    statistics.append(
        StatisticData(
            start=baseline_date,
            sum=0.0,
        )
    )

    cumulative_sum = 0.0
    for month_index, monthly_value in enumerate(cleaned_values):
        # Calculate the month for this entry
        month_year = window_start.year
        month_num = window_start.month + month_index
        while month_num > 12:
            month_num -= 12
            month_year += 1

        month_date = window_start.replace(year=month_year, month=month_num, day=1)

        # Skip future months
        if month_date > prev_month_start:
            break

        # Add monthly value to cumulative sum
        cumulative_sum += monthly_value

        # Create statistic entry for the start of this month
        statistics.append(
            StatisticData(
                start=month_date,
                sum=cumulative_sum,
            )
        )

    if statistics:
        _LOGGER.debug(
            "Importing %d monthly statistics for %s (from %s to %s)",
            len(statistics),
            statistic_id,
            statistics[0]["start"].strftime("%Y-%m"),
            statistics[-1]["start"].strftime("%Y-%m"),
        )
        async_add_external_statistics(hass, metadata, statistics)
        _LOGGER.debug("Monthly statistics import completed for %s", statistic_id)
    else:
        _LOGGER.debug("No monthly statistics to import for %s", statistic_id)
