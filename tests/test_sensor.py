"""Integration tests for Evon sensor platform."""

from __future__ import annotations

import pytest

from tests.conftest import requires_ha_test_framework

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
    """Test smart meter daily energy sensor."""
    mock_config_entry_v2.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.smart_meter_energy_today")
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
