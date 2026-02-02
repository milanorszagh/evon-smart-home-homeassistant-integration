"""Integration tests for Evon sensor platform."""

from __future__ import annotations

import sys

import pytest

from tests.conftest import requires_ha_test_framework


# Tests for daily energy helper functions
# These require Python 3.10+ due to dataclass kw_only parameter in sensor.py
@pytest.mark.skipif(sys.version_info < (3, 10), reason="Requires Python 3.10+")
class TestDailyEnergyHelpers:
    """Test daily energy helper functions."""

    def test_get_today_energy_valid_data(self):
        """Test getting today's energy from valid data."""
        from datetime import datetime
        from unittest.mock import patch

        from custom_components.evon.sensor import _get_today_energy

        # Mock today as day 3 of month
        with patch("custom_components.evon.sensor.dt_util") as mock_dt:
            mock_dt.now.return_value = datetime(2024, 1, 3, 12, 0, 0)

            data = {"energy_data_month": [7.5, 8.3, 9.1, 6.2, 10.0]}
            result = _get_today_energy(data)
            # Day 3 = index 2 = 9.1
            assert result == 9.1

    def test_get_today_energy_string_values(self):
        """Test getting today's energy when values are strings."""
        from datetime import datetime
        from unittest.mock import patch

        from custom_components.evon.sensor import _get_today_energy

        with patch("custom_components.evon.sensor.dt_util") as mock_dt:
            mock_dt.now.return_value = datetime(2024, 1, 2, 12, 0, 0)

            data = {"energy_data_month": ["7.50", "8.30", "9.10"]}
            result = _get_today_energy(data)
            assert result == 8.3

    def test_get_today_energy_missing_data(self):
        """Test getting today's energy when data is missing."""
        from custom_components.evon.sensor import _get_today_energy

        result = _get_today_energy({})
        assert result is None

        result = _get_today_energy({"energy_data_month": None})
        assert result is None

        result = _get_today_energy({"energy_data_month": []})
        assert result is None

    def test_get_today_energy_day_out_of_range(self):
        """Test getting today's energy when day exceeds array length."""
        from datetime import datetime
        from unittest.mock import patch

        from custom_components.evon.sensor import _get_today_energy

        with patch("custom_components.evon.sensor.dt_util") as mock_dt:
            mock_dt.now.return_value = datetime(2024, 1, 31, 12, 0, 0)

            # Only 3 days of data
            data = {"energy_data_month": [7.5, 8.3, 9.1]}
            result = _get_today_energy(data)
            assert result is None

    def test_get_today_energy_none_value_in_array(self):
        """Test getting today's energy when today's value is None."""
        from datetime import datetime
        from unittest.mock import patch

        from custom_components.evon.sensor import _get_today_energy

        with patch("custom_components.evon.sensor.dt_util") as mock_dt:
            mock_dt.now.return_value = datetime(2024, 1, 2, 12, 0, 0)

            data = {"energy_data_month": [7.5, None, 9.1]}
            result = _get_today_energy(data)
            assert result is None

    def test_get_today_feed_in_valid_data(self):
        """Test getting today's feed-in from valid data."""
        from datetime import datetime
        from unittest.mock import patch

        from custom_components.evon.sensor import _get_today_feed_in

        with patch("custom_components.evon.sensor.dt_util") as mock_dt:
            mock_dt.now.return_value = datetime(2024, 1, 1, 12, 0, 0)

            data = {"feed_in_data_month": [3.2, 4.1, 5.0]}
            result = _get_today_feed_in(data)
            # Day 1 = index 0 = 3.2
            assert result == 3.2

    def test_get_today_feed_in_missing_data(self):
        """Test getting today's feed-in when data is missing."""
        from custom_components.evon.sensor import _get_today_feed_in

        result = _get_today_feed_in({})
        assert result is None


pytestmark = requires_ha_test_framework


@pytest.mark.asyncio
async def test_temperature_sensor_setup(hass, mock_config_entry_v2, mock_evon_api_class):
    """Test temperature sensor is created from climate device."""
    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    # Temperature sensor from climate device
    state = hass.states.get("sensor.living_room_climate_temperature")
    assert state is not None
    assert float(state.state) == 21.5
    assert state.attributes.get("unit_of_measurement") == "°C"
    assert state.attributes.get("device_class") == "temperature"


@pytest.mark.asyncio
async def test_smart_meter_power_sensor(hass, mock_config_entry_v2, mock_evon_api_class):
    """Test smart meter power sensor."""
    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.smart_meter_power")
    assert state is not None
    assert float(state.state) == 1500.0
    assert state.attributes.get("unit_of_measurement") == "W"
    assert state.attributes.get("device_class") == "power"


@pytest.mark.asyncio
async def test_smart_meter_energy_sensor(hass, mock_config_entry_v2, mock_evon_api_class):
    """Test smart meter energy sensor."""
    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.smart_meter_energy_total")
    assert state is not None
    assert float(state.state) == 12345.67
    assert state.attributes.get("unit_of_measurement") == "kWh"
    assert state.attributes.get("device_class") == "energy"


@pytest.mark.asyncio
async def test_smart_meter_daily_energy_sensor(hass, mock_config_entry_v2, mock_evon_api_class):
    """Test smart meter rolling 24h energy sensor."""
    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    # Note: Entity ID derived from name "Energy (24h Rolling)"
    state = hass.states.get("sensor.smart_meter_energy_24h_rolling")
    assert state is not None
    assert float(state.state) == 45.5
    assert state.attributes.get("unit_of_measurement") == "kWh"


@pytest.mark.asyncio
async def test_smart_meter_voltage_sensors(hass, mock_config_entry_v2, mock_evon_api_class):
    """Test smart meter voltage sensors for all phases."""
    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    # Check voltage L1
    state = hass.states.get("sensor.smart_meter_voltage_l1")
    assert state is not None
    assert float(state.state) == 230.1
    assert state.attributes.get("unit_of_measurement") == "V"
    assert state.attributes.get("device_class") == "voltage"

    # Check voltage L2
    state = hass.states.get("sensor.smart_meter_voltage_l2")
    assert state is not None
    assert float(state.state) == 229.8

    # Check voltage L3
    state = hass.states.get("sensor.smart_meter_voltage_l3")
    assert state is not None
    assert float(state.state) == 230.5


@pytest.mark.asyncio
async def test_smart_meter_current_sensors(hass, mock_config_entry_v2, mock_evon_api_class):
    """Test smart meter current sensors for all phases."""
    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    # Check current L1
    state = hass.states.get("sensor.smart_meter_current_l1")
    assert state is not None
    assert float(state.state) == 2.5
    assert state.attributes.get("unit_of_measurement") == "A"
    assert state.attributes.get("device_class") == "current"

    # Check current L2
    state = hass.states.get("sensor.smart_meter_current_l2")
    assert state is not None
    assert float(state.state) == 1.8

    # Check current L3
    state = hass.states.get("sensor.smart_meter_current_l3")
    assert state is not None
    assert float(state.state) == 2.1


@pytest.mark.asyncio
async def test_smart_meter_frequency_sensor(hass, mock_config_entry_v2, mock_evon_api_class):
    """Test smart meter frequency sensor."""
    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.smart_meter_frequency")
    assert state is not None
    assert float(state.state) == 50.0
    assert state.attributes.get("unit_of_measurement") == "Hz"
    assert state.attributes.get("device_class") == "frequency"


@pytest.mark.asyncio
async def test_smart_meter_feed_in_energy_sensor(hass, mock_config_entry_v2, mock_evon_api_class):
    """Test smart meter feed-in energy sensor for solar/grid export."""
    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.smart_meter_feed_in_energy_total")
    assert state is not None
    assert float(state.state) == 100.5
    assert state.attributes.get("unit_of_measurement") == "kWh"
    assert state.attributes.get("device_class") == "energy"


@pytest.mark.asyncio
async def test_air_quality_co2_sensor(hass, mock_config_entry_v2, mock_evon_api_class):
    """Test air quality CO2 sensor."""
    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.air_quality_co2")
    assert state is not None
    assert float(state.state) == 650
    assert state.attributes.get("unit_of_measurement") == "ppm"
    assert state.attributes.get("device_class") == "carbon_dioxide"


@pytest.mark.asyncio
async def test_air_quality_humidity_sensor(hass, mock_config_entry_v2, mock_evon_api_class):
    """Test air quality humidity sensor."""
    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.air_quality_humidity")
    assert state is not None
    assert float(state.state) == 45.5
    assert state.attributes.get("unit_of_measurement") == "%"
    assert state.attributes.get("device_class") == "humidity"
