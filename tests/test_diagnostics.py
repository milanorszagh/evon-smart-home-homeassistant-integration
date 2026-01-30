"""Tests for Evon Smart Home diagnostics."""

from __future__ import annotations

import pytest

from tests.conftest import (
    HAS_HA_TEST_FRAMEWORK,
    TEST_HOST,
    TEST_USERNAME,
    TEST_PASSWORD,
    requires_ha_test_framework,
)

if HAS_HA_TEST_FRAMEWORK:
    from homeassistant.core import HomeAssistant
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.evon.diagnostics import async_get_config_entry_diagnostics
    from custom_components.evon.const import DOMAIN


@requires_ha_test_framework
class TestDiagnostics:
    """Test the diagnostics module."""

    @pytest.fixture
    def mock_config_entry(self) -> MockConfigEntry:
        """Create a mock config entry."""
        return MockConfigEntry(
            domain="evon",
            title="Evon Smart Home",
            data={
                "host": TEST_HOST,
                "username": TEST_USERNAME,
                "password": TEST_PASSWORD,
            },
            options={
                "scan_interval": 30,
                "sync_areas": False,
            },
            entry_id="test_diagnostics_entry",
        )

    async def test_diagnostics_with_data(
        self,
        hass: HomeAssistant,
        mock_evon_api_class,
        mock_config_entry: MockConfigEntry,
    ) -> None:
        """Test diagnostics returns correct data structure."""
        # Setup the integration
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        # Get diagnostics
        result = await async_get_config_entry_diagnostics(hass, mock_config_entry)

        # Verify structure
        assert "entry" in result
        assert "coordinator" in result
        assert "device_counts" in result
        assert "devices" in result

        # Verify entry data is redacted
        assert result["entry"]["entry_id"] == mock_config_entry.entry_id
        assert result["entry"]["domain"] == "evon"
        assert result["entry"]["data"]["host"] == "**REDACTED**"
        assert result["entry"]["data"]["username"] == "**REDACTED**"
        assert result["entry"]["data"]["password"] == "**REDACTED**"

        # Verify coordinator info
        assert "last_update_success" in result["coordinator"]
        assert "update_interval" in result["coordinator"]

        # Verify device counts exist
        device_counts = result["device_counts"]
        assert "lights" in device_counts
        assert "blinds" in device_counts
        assert "climates" in device_counts
        assert "switches" in device_counts
        assert "smart_meters" in device_counts
        assert "air_quality" in device_counts
        assert "valves" in device_counts
        assert "scenes" in device_counts
        assert "bathroom_radiators" in device_counts

        # Verify devices summaries exist
        devices = result["devices"]
        assert "lights" in devices
        assert "blinds" in devices
        assert "climates" in devices

    async def test_diagnostics_device_summaries(
        self,
        hass: HomeAssistant,
        mock_evon_api_class,
        mock_config_entry: MockConfigEntry,
    ) -> None:
        """Test diagnostics device summaries contain expected fields."""
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        result = await async_get_config_entry_diagnostics(hass, mock_config_entry)

        # Check lights summary
        if result["devices"]["lights"]:
            light = result["devices"]["lights"][0]
            assert "id" in light
            assert "name" in light
            assert "is_on" in light
            assert "has_brightness" in light

        # Check blinds summary
        if result["devices"]["blinds"]:
            blind = result["devices"]["blinds"][0]
            assert "id" in blind
            assert "name" in blind
            assert "position" in blind
            assert "has_tilt" in blind

        # Check climates summary
        if result["devices"]["climates"]:
            climate = result["devices"]["climates"][0]
            assert "id" in climate
            assert "name" in climate
            assert "current_temp" in climate
            assert "target_temp" in climate
