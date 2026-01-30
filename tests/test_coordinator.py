"""Tests for Evon Smart Home coordinator."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch
import pytest

from tests.conftest import (
    HAS_HA_TEST_FRAMEWORK,
    TEST_HOST,
    TEST_USERNAME,
    TEST_PASSWORD,
    MOCK_INSTANCES,
    MOCK_INSTANCE_DETAILS,
    requires_ha_test_framework,
)

if HAS_HA_TEST_FRAMEWORK:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.update_coordinator import UpdateFailed
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.evon.coordinator import EvonDataUpdateCoordinator
    from custom_components.evon.api import EvonApiError
    from custom_components.evon.const import DOMAIN


@requires_ha_test_framework
class TestCoordinatorGetters:
    """Test coordinator getter methods."""

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
            entry_id="test_coordinator_entry",
        )

    async def test_get_light_data(
        self,
        hass: HomeAssistant,
        mock_evon_api_class,
        mock_config_entry: MockConfigEntry,
    ) -> None:
        """Test getting light data by ID."""
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        coordinator = hass.data[DOMAIN][mock_config_entry.entry_id]["coordinator"]

        # Test existing light
        light_data = coordinator.get_light_data("light_1")
        assert light_data is not None
        assert light_data["id"] == "light_1"

        # Test non-existing light
        assert coordinator.get_light_data("nonexistent") is None

    async def test_get_blind_data(
        self,
        hass: HomeAssistant,
        mock_evon_api_class,
        mock_config_entry: MockConfigEntry,
    ) -> None:
        """Test getting blind data by ID."""
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        coordinator = hass.data[DOMAIN][mock_config_entry.entry_id]["coordinator"]

        blind_data = coordinator.get_blind_data("blind_1")
        assert blind_data is not None
        assert blind_data["id"] == "blind_1"

        assert coordinator.get_blind_data("nonexistent") is None

    async def test_get_climate_data(
        self,
        hass: HomeAssistant,
        mock_evon_api_class,
        mock_config_entry: MockConfigEntry,
    ) -> None:
        """Test getting climate data by ID."""
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        coordinator = hass.data[DOMAIN][mock_config_entry.entry_id]["coordinator"]

        climate_data = coordinator.get_climate_data("climate_1")
        assert climate_data is not None
        assert climate_data["id"] == "climate_1"

        assert coordinator.get_climate_data("nonexistent") is None

    async def test_get_switch_data(
        self,
        hass: HomeAssistant,
        mock_evon_api_class,
        mock_config_entry: MockConfigEntry,
    ) -> None:
        """Test getting switch data by ID."""
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        coordinator = hass.data[DOMAIN][mock_config_entry.entry_id]["coordinator"]

        # light_2 is a SmartCOM.Light.Light (relay/switch)
        switch_data = coordinator.get_switch_data("light_2")
        assert switch_data is not None
        assert switch_data["id"] == "light_2"

        assert coordinator.get_switch_data("nonexistent") is None

    async def test_get_smart_meter_data(
        self,
        hass: HomeAssistant,
        mock_evon_api_class,
        mock_config_entry: MockConfigEntry,
    ) -> None:
        """Test getting smart meter data by ID."""
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        coordinator = hass.data[DOMAIN][mock_config_entry.entry_id]["coordinator"]

        meter_data = coordinator.get_smart_meter_data("smart_meter_1")
        assert meter_data is not None
        assert meter_data["id"] == "smart_meter_1"

        assert coordinator.get_smart_meter_data("nonexistent") is None

    async def test_get_air_quality_data(
        self,
        hass: HomeAssistant,
        mock_evon_api_class,
        mock_config_entry: MockConfigEntry,
    ) -> None:
        """Test getting air quality data by ID."""
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        coordinator = hass.data[DOMAIN][mock_config_entry.entry_id]["coordinator"]

        aq_data = coordinator.get_air_quality_data("air_quality_1")
        assert aq_data is not None
        assert aq_data["id"] == "air_quality_1"

        assert coordinator.get_air_quality_data("nonexistent") is None

    async def test_get_valve_data(
        self,
        hass: HomeAssistant,
        mock_evon_api_class,
        mock_config_entry: MockConfigEntry,
    ) -> None:
        """Test getting valve data by ID."""
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        coordinator = hass.data[DOMAIN][mock_config_entry.entry_id]["coordinator"]

        valve_data = coordinator.get_valve_data("valve_1")
        assert valve_data is not None
        assert valve_data["id"] == "valve_1"

        assert coordinator.get_valve_data("nonexistent") is None

    async def test_get_home_state_data(
        self,
        hass: HomeAssistant,
        mock_evon_api_class,
        mock_config_entry: MockConfigEntry,
    ) -> None:
        """Test getting home state data by ID."""
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        coordinator = hass.data[DOMAIN][mock_config_entry.entry_id]["coordinator"]

        state_data = coordinator.get_home_state_data("HomeStateAtHome")
        assert state_data is not None
        assert state_data["id"] == "HomeStateAtHome"

        assert coordinator.get_home_state_data("nonexistent") is None

    async def test_get_bathroom_radiator_data(
        self,
        hass: HomeAssistant,
        mock_evon_api_class,
        mock_config_entry: MockConfigEntry,
    ) -> None:
        """Test getting bathroom radiator data by ID."""
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        coordinator = hass.data[DOMAIN][mock_config_entry.entry_id]["coordinator"]

        radiator_data = coordinator.get_bathroom_radiator_data("bathroom_radiator_1")
        assert radiator_data is not None
        assert radiator_data["id"] == "bathroom_radiator_1"

        assert coordinator.get_bathroom_radiator_data("nonexistent") is None

    async def test_get_scene_data(
        self,
        hass: HomeAssistant,
        mock_evon_api_class,
        mock_config_entry: MockConfigEntry,
    ) -> None:
        """Test getting scene data by ID."""
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        coordinator = hass.data[DOMAIN][mock_config_entry.entry_id]["coordinator"]

        scene_data = coordinator.get_scene_data("SceneApp1234")
        assert scene_data is not None
        assert scene_data["id"] == "SceneApp1234"

        assert coordinator.get_scene_data("nonexistent") is None

    async def test_get_active_home_state(
        self,
        hass: HomeAssistant,
        mock_evon_api_class,
        mock_config_entry: MockConfigEntry,
    ) -> None:
        """Test getting active home state."""
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        coordinator = hass.data[DOMAIN][mock_config_entry.entry_id]["coordinator"]

        active_state = coordinator.get_active_home_state()
        assert active_state == "HomeStateAtHome"

    async def test_get_home_states(
        self,
        hass: HomeAssistant,
        mock_evon_api_class,
        mock_config_entry: MockConfigEntry,
    ) -> None:
        """Test getting all home states."""
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        coordinator = hass.data[DOMAIN][mock_config_entry.entry_id]["coordinator"]

        home_states = coordinator.get_home_states()
        assert len(home_states) > 0
        assert any(s["id"] == "HomeStateAtHome" for s in home_states)

    async def test_get_season_mode(
        self,
        hass: HomeAssistant,
        mock_evon_api_class,
        mock_config_entry: MockConfigEntry,
    ) -> None:
        """Test getting season mode."""
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        coordinator = hass.data[DOMAIN][mock_config_entry.entry_id]["coordinator"]

        # Default is heating mode (False)
        assert coordinator.get_season_mode() is False

    async def test_get_scenes(
        self,
        hass: HomeAssistant,
        mock_evon_api_class,
        mock_config_entry: MockConfigEntry,
    ) -> None:
        """Test getting all scenes."""
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        coordinator = hass.data[DOMAIN][mock_config_entry.entry_id]["coordinator"]

        scenes = coordinator.get_scenes()
        assert len(scenes) > 0
        assert any(s["id"] == "SceneApp1234" for s in scenes)


@requires_ha_test_framework
class TestCoordinatorUpdateInterval:
    """Test coordinator update interval methods."""

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
            entry_id="test_interval_entry",
        )

    async def test_set_update_interval(
        self,
        hass: HomeAssistant,
        mock_evon_api_class,
        mock_config_entry: MockConfigEntry,
    ) -> None:
        """Test setting update interval."""
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        coordinator = hass.data[DOMAIN][mock_config_entry.entry_id]["coordinator"]

        # Change interval
        coordinator.set_update_interval(60)
        assert coordinator.update_interval.total_seconds() == 60

    async def test_set_sync_areas(
        self,
        hass: HomeAssistant,
        mock_evon_api_class,
        mock_config_entry: MockConfigEntry,
    ) -> None:
        """Test setting sync areas option."""
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        coordinator = hass.data[DOMAIN][mock_config_entry.entry_id]["coordinator"]

        # Initially False
        assert coordinator._sync_areas is False

        # Change to True
        coordinator.set_sync_areas(True)
        assert coordinator._sync_areas is True


@requires_ha_test_framework
class TestCoordinatorEntityData:
    """Test coordinator entity data method."""

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
            entry_id="test_entity_data_entry",
        )

    async def test_get_entity_data(
        self,
        hass: HomeAssistant,
        mock_evon_api_class,
        mock_config_entry: MockConfigEntry,
    ) -> None:
        """Test generic get_entity_data method."""
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        coordinator = hass.data[DOMAIN][mock_config_entry.entry_id]["coordinator"]

        # Test with valid entity type and ID
        data = coordinator.get_entity_data("lights", "light_1")
        assert data is not None
        assert data["id"] == "light_1"

        # Test with invalid entity type
        assert coordinator.get_entity_data("invalid_type", "light_1") is None

        # Test with invalid ID
        assert coordinator.get_entity_data("lights", "invalid_id") is None
