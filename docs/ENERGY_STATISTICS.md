# Energy Statistics

This document describes how the Evon integration imports and displays daily energy consumption data in Home Assistant.

## Overview

The Evon Smart Home system provides accurate daily energy consumption data through its SmartMeter devices. The integration uses a **hybrid approach**:

- **Historical data (previous days)**: Imported from Evon's `EnergyDataMonth` into HA external statistics
- **Today's consumption**: Calculated from HA statistics on the Energy Total sensor
- **This month's consumption**: Combined from Evon's daily data + today's statistics

The integration now provides **built-in Energy Today and Energy This Month sensors** that handle this automatically.

## Data Source: EnergyDataMonth

The SmartMeter provides `EnergyDataMonth` via the WebSocket API - a rolling window array of daily energy consumption values.

### Key Characteristics

| Property | Description |
|----------|-------------|
| **Array Length** | 31 elements (rolling window) |
| **First Element** | Energy consumption from 31 days ago |
| **Last Element** | Energy consumption from **yesterday** (NOT today) |
| **Today's Value** | NOT in this array - see built-in Energy Today sensor |
| **Unit** | kWh |
| **Update Frequency** | Daily (values finalized at midnight) |

### Example WebSocket Response

```json
{
  "InstanceId": "SmartMeter3006939",
  "EnergyDataMonth": [7.6, 6.4, 9.8, 6.5, 10.2, ...],  // 31 elements
  "Energy": 1046.3
}
```

- `EnergyDataMonth`: Array of daily values for PREVIOUS 31 days (last = yesterday)
- `Energy`: Current total meter reading

### Other Available Data Arrays (Reference)

| Array | Length | Description | Used |
|-------|--------|-------------|------|
| `EnergyDataDay` | 1 | Today's consumption value (single numeric) | Yes (today's consumption) |
| `EnergyDataYear` | 12 | Monthly values, rolling 12-month window | Yes (monthly statistics) |
| `EnergyDataWeek` | 7 | Daily values for past 7 days (last = yesterday) | No |
| `EnergyDataActual` | 96 | 15-min intervals, rolling 24h window (last = now) | No |

## How Data is Imported into Home Assistant

### External Statistics (Historical Data)

The integration imports `EnergyDataMonth` into Home Assistant's **external statistics** system. This allows the data to be displayed using HA's native `statistics-graph` card.

**Statistic ID**: `evon:energy_smartmeter{ID}` (e.g., `evon:energy_smartmeter3006939`)

**Note**: Dots in meter IDs are normalized to underscores. For example, `SC1.SmartMeter1` becomes `evon:energy_sc1_smartmeter1`.

### Import Process (`statistics.py`)

1. **Rate Limiting**: Statistics are imported at most once per hour
2. **Date Mapping**:
   - Window calculated as: `yesterday - 30 days` to `yesterday`
   - Last array element → yesterday's date
   - First array element → 31 days ago
   - **Today is NOT included** (chart shows up to yesterday)
3. **Cumulative Sum**: HA statistics require cumulative `sum` values:
   - Baseline point added at `sum=0` before the data window
   - Each day: Previous sum + daily consumption
4. **Statistics Type**: `sum` with `change` stat_type for daily consumption display

### Code Flow

```
Evon WebSocket → Coordinator → statistics.py → HA Recorder Database
                                    ↓
                    async_add_external_statistics()
```

## Today's Energy Consumption

The integration provides a built-in **Energy Today** sensor that calculates today's consumption from HA statistics.

### Built-in Sensor (Recommended)

The `sensor.smart_meter_energy_today` sensor is automatically created and:
- Queries HA's statistics database for hourly changes on the Energy Total sensor
- Sums all hourly changes since midnight
- Updates with each coordinator refresh

### Alternative: utility_meter

You can still use a manual `utility_meter` in `configuration.yaml` if preferred:

```yaml
utility_meter:
  energy_today:
    source: sensor.smart_meter_energy_total
    name: Energy Today
    cycle: daily
```

### Why This Approach?

1. **Accuracy**: Evon's `EnergyDataMonth` provides accurate historical data
2. **Real-time**: HA statistics provide real-time today tracking
3. **Resilience**: If HA has a glitch, it only affects today - tomorrow the historical data comes from Evon's accurate values

## This Month's Energy Consumption

The integration provides a built-in **Energy This Month** sensor that combines:
- Previous days of this month from Evon's `EnergyDataMonth` array
- Today's consumption from HA statistics

This gives you accurate monthly totals without needing any manual configuration.

## Monthly Statistics Import

The integration also imports monthly consumption statistics from Evon's `EnergyDataYear` array (a 12-element rolling window of monthly values, last element = previous month).

The `_import_monthly_statistics()` function in `statistics.py` creates external statistics with the ID format `evon:energy_monthly_{safe_meter_id}` (e.g., `evon:energy_monthly_smartmeter3006939`). These work the same way as daily statistics: a baseline point is added before the window, and cumulative sums are built so that `stat_types: [change]` shows per-month consumption.

## Dashboard Configuration

### Statistics Graph (Historical Data)

```yaml
type: statistics-graph
entities:
  - entity: evon:energy_smartmeter3006939
    name: Daily Energy
stat_types:
  - change
period: day
days_to_show: 31
```

This shows daily consumption for the **past 31 days** (up to yesterday). Today is not included.

### Energy Today (Text Display)

Use the built-in Energy Today sensor:

```yaml
type: entities
entities:
  - entity: sensor.smart_meter_energy_today
    name: Energy Today
```

### Complete Example Dashboard Card

```yaml
type: vertical-stack
cards:
  - type: entities
    entities:
      - entity: sensor.smart_meter_power
        name: Current Power
      - entity: sensor.smart_meter_energy_today
        name: Energy Today
      - entity: sensor.smart_meter_energy_total
        name: Energy Total
  - type: statistics-graph
    title: Daily Consumption
    entities:
      - entity: evon:energy_smartmeter3006939
        name: Daily Energy
    stat_types:
      - change
    period: day
    days_to_show: 31
```

## Troubleshooting

### Chart Shows Data for Today with 0 or Low Value

The statistics only include data up to **yesterday**. Today's value is not in the chart - this is intentional. Use the built-in `sensor.smart_meter_energy_today` sensor for today's consumption.

### Wrong Dates in Chart

If dates appear shifted:
1. Check the window calculation in logs: `STATS DEBUG: ... window: YYYY-MM-DD to YYYY-MM-DD (yesterday)`
2. The last date should always be yesterday

### Statistics Not Updating

- Statistics import is rate-limited to once per hour
- Force reimport by restarting Home Assistant
- Check logs for `custom_components.evon.statistics`

### "Energy Today" or "Energy This Month" Shows Unavailable

1. Check that the Energy Total sensor (`sensor.smart_meter_energy_total`) exists and has data
2. The calculated sensors need HA statistics to exist - they may show 0.0 initially
3. Wait for a coordinator refresh cycle or reload the integration

## Technical Reference

### Files

| File | Purpose |
|------|---------|
| `statistics.py` | Imports EnergyDataMonth into HA external statistics |
| `sensor.py` | Smart meter sensors (Power, Energy Total, Energy Today, Energy This Month) |
| `coordinator/__init__.py` | Contains `_calculate_energy_today_and_month()` method |
| `coordinator/processors/smart_meters.py` | Fetches SmartMeter data from API |
| `ws_mappings.py` | WebSocket subscription fields |

### Evon API Fields Used

| Field | Description |
|-------|-------------|
| `EnergyDataMonth` | 31-day rolling window of daily values (last = yesterday) |
| `EnergyDataYear` | 12-month rolling window of monthly values (last = previous month) |
| `EnergyDataDay` | Today's consumption value (single numeric) |
| `Energy` | Current total meter reading |
| `PowerActual` | Current power consumption (W) |

### Calculated Sensor Implementation

The coordinator's `_calculate_energy_today_and_month()` method:
1. Queries HA's `statistics_during_period()` for today's hourly changes on the Energy Total sensor
2. Sums the hourly changes to get today's consumption
3. Takes the last N days from `EnergyDataMonth` (where N = day of month - 1)
4. Adds today's consumption to get this month's total
5. Stores values in meter data as `energy_today_calculated` and `energy_this_month_calculated`

**Note**: `statistics_during_period()` is a blocking call and must be run via `async_add_executor_job()`.

### Feed-in Energy (Solar Export)

If your SmartMeter supports feed-in:
- WebSocket field: `FeedInDataMonth`
- Statistic ID: `evon:feed_in_smartmeter{ID}`

Same date mapping applies for historical data.
