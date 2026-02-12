"""Tests for Evon Smart Home coordinator."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from tests.conftest import (
    HAS_HA_TEST_FRAMEWORK,
    MOCK_INSTANCE_DETAILS,
    TEST_HOST,
    TEST_PASSWORD,
    TEST_USERNAME,
    requires_ha_test_framework,
)

if HAS_HA_TEST_FRAMEWORK:
    from homeassistant.core import HomeAssistant
    from pytest_homeassistant_custom_component.common import MockConfigEntry

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

    async def test_get_entity_data_lights(
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
        light_data = coordinator.get_entity_data("lights", "light_1")
        assert light_data is not None
        assert light_data["id"] == "light_1"

        # Test non-existing light
        assert coordinator.get_entity_data("lights", "nonexistent") is None

    async def test_get_entity_data_blinds(
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

        blind_data = coordinator.get_entity_data("blinds", "blind_1")
        assert blind_data is not None
        assert blind_data["id"] == "blind_1"

        assert coordinator.get_entity_data("blinds", "nonexistent") is None

    async def test_get_entity_data_climates(
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

        climate_data = coordinator.get_entity_data("climates", "climate_1")
        assert climate_data is not None
        assert climate_data["id"] == "climate_1"

        assert coordinator.get_entity_data("climates", "nonexistent") is None

    async def test_get_entity_data_switches(
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
        switch_data = coordinator.get_entity_data("switches", "light_2")
        assert switch_data is not None
        assert switch_data["id"] == "light_2"

        assert coordinator.get_entity_data("switches", "nonexistent") is None

    async def test_get_entity_data_smart_meters(
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

        meter_data = coordinator.get_entity_data("smart_meters", "smart_meter_1")
        assert meter_data is not None
        assert meter_data["id"] == "smart_meter_1"

        assert coordinator.get_entity_data("smart_meters", "nonexistent") is None

    async def test_get_entity_data_air_quality(
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

        aq_data = coordinator.get_entity_data("air_quality", "air_quality_1")
        assert aq_data is not None
        assert aq_data["id"] == "air_quality_1"

        assert coordinator.get_entity_data("air_quality", "nonexistent") is None

    async def test_get_entity_data_valves(
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

        valve_data = coordinator.get_entity_data("valves", "valve_1")
        assert valve_data is not None
        assert valve_data["id"] == "valve_1"

        assert coordinator.get_entity_data("valves", "nonexistent") is None

    async def test_get_entity_data_home_states(
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

        state_data = coordinator.get_entity_data("home_states", "HomeStateAtHome")
        assert state_data is not None
        assert state_data["id"] == "HomeStateAtHome"

        assert coordinator.get_entity_data("home_states", "nonexistent") is None

    async def test_get_entity_data_bathroom_radiators(
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

        radiator_data = coordinator.get_entity_data("bathroom_radiators", "bathroom_radiator_1")
        assert radiator_data is not None
        assert radiator_data["id"] == "bathroom_radiator_1"

        assert coordinator.get_entity_data("bathroom_radiators", "nonexistent") is None

    async def test_get_entity_data_scenes(
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

        scene_data = coordinator.get_entity_data("scenes", "SceneApp1234")
        assert scene_data is not None
        assert scene_data["id"] == "SceneApp1234"

        assert coordinator.get_entity_data("scenes", "nonexistent") is None

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


@requires_ha_test_framework
class TestCoordinatorApiErrorHandling:
    """Test coordinator API error handling and recovery."""

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
                "http_only": True,
            },
            entry_id="test_error_entry",
        )

    async def test_transient_failure_returns_cached_data(
        self,
        hass: HomeAssistant,
        mock_evon_api_class,
        mock_config_entry: MockConfigEntry,
    ) -> None:
        """Test that transient API failures return cached data."""
        from custom_components.evon.api import EvonApiError

        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        coordinator = hass.data[DOMAIN][mock_config_entry.entry_id]["coordinator"]

        # Verify initial data was loaded
        assert coordinator.data is not None
        assert coordinator.data.get("lights") is not None

        # Make API fail on next update
        mock_evon_api_class.get_instances = AsyncMock(side_effect=EvonApiError("Connection timeout"))

        # Trigger refresh - should return cached data
        await coordinator.async_refresh()

        # Data should still be available (cached)
        assert coordinator.data is not None
        assert coordinator._consecutive_failures == 1

    async def test_failure_counter_increments(
        self,
        hass: HomeAssistant,
        mock_evon_api_class,
        mock_config_entry: MockConfigEntry,
    ) -> None:
        """Test that consecutive failure counter increments."""
        from custom_components.evon.api import EvonApiError

        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        coordinator = hass.data[DOMAIN][mock_config_entry.entry_id]["coordinator"]
        assert coordinator._consecutive_failures == 0

        # Make API fail
        mock_evon_api_class.get_instances = AsyncMock(side_effect=EvonApiError("Connection timeout"))

        # Multiple failures
        await coordinator.async_refresh()
        assert coordinator._consecutive_failures == 1

        await coordinator.async_refresh()
        assert coordinator._consecutive_failures == 2

    async def test_success_resets_failure_counter(
        self,
        hass: HomeAssistant,
        mock_evon_api_class,
        mock_config_entry: MockConfigEntry,
    ) -> None:
        """Test that successful update resets failure counter."""
        from custom_components.evon.api import EvonApiError
        from tests.conftest import MOCK_INSTANCES

        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        coordinator = hass.data[DOMAIN][mock_config_entry.entry_id]["coordinator"]

        # Simulate a failure
        mock_evon_api_class.get_instances = AsyncMock(side_effect=EvonApiError("Connection timeout"))
        await coordinator.async_refresh()
        assert coordinator._consecutive_failures == 1

        # Restore API and refresh
        mock_evon_api_class.get_instances = AsyncMock(return_value=MOCK_INSTANCES)
        mock_evon_api_class.get_instance = AsyncMock(
            side_effect=lambda instance_id: MOCK_INSTANCE_DETAILS.get(instance_id, {})
        )
        await coordinator.async_refresh()
        assert coordinator._consecutive_failures == 0


@requires_ha_test_framework
class TestCoordinatorSeasonMode:
    """Test coordinator season mode extraction."""

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
                "http_only": True,
            },
            entry_id="test_season_entry",
        )

    async def test_season_mode_heating(
        self,
        hass: HomeAssistant,
        mock_evon_api_class,
        mock_config_entry: MockConfigEntry,
    ) -> None:
        """Test season mode defaults to heating (False)."""
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        coordinator = hass.data[DOMAIN][mock_config_entry.entry_id]["coordinator"]
        # Default mock data has IsCool=False
        assert coordinator.get_season_mode() is False

    async def test_season_mode_cooling(
        self,
        hass: HomeAssistant,
        mock_evon_api_class,
        mock_config_entry: MockConfigEntry,
    ) -> None:
        """Test season mode set to cooling (True)."""
        original = MOCK_INSTANCE_DETAILS["Base.ehThermostat"]["IsCool"]
        try:
            MOCK_INSTANCE_DETAILS["Base.ehThermostat"]["IsCool"] = True

            mock_config_entry.add_to_hass(hass)
            await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

            coordinator = hass.data[DOMAIN][mock_config_entry.entry_id]["coordinator"]
            assert coordinator.get_season_mode() is True
        finally:
            MOCK_INSTANCE_DETAILS["Base.ehThermostat"]["IsCool"] = original

    async def test_season_mode_missing_thermostat(
        self,
        hass: HomeAssistant,
        mock_evon_api_class,
        mock_config_entry: MockConfigEntry,
    ) -> None:
        """Test season mode defaults to heating when thermostat data is missing."""

        def custom_get_instance(instance_id):
            if instance_id == "Base.ehThermostat":
                return {}
            return MOCK_INSTANCE_DETAILS.get(instance_id, {})

        mock_evon_api_class.get_instance = AsyncMock(side_effect=custom_get_instance)

        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        coordinator = hass.data[DOMAIN][mock_config_entry.entry_id]["coordinator"]
        # Should default to heating when no thermostat data
        assert coordinator.get_season_mode() is False


@requires_ha_test_framework
class TestCoordinatorWebSocketProperties:
    """Test coordinator WebSocket-related properties."""

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
                "http_only": True,
            },
            entry_id="test_ws_props_entry",
        )

    async def test_ws_connected_default_false(
        self,
        hass: HomeAssistant,
        mock_evon_api_class,
        mock_config_entry: MockConfigEntry,
    ) -> None:
        """Test ws_connected is False by default."""
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        coordinator = hass.data[DOMAIN][mock_config_entry.entry_id]["coordinator"]
        assert coordinator.ws_connected is False

    async def test_ws_client_default_none(
        self,
        hass: HomeAssistant,
        mock_evon_api_class,
        mock_config_entry: MockConfigEntry,
    ) -> None:
        """Test ws_client is None by default."""
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        coordinator = hass.data[DOMAIN][mock_config_entry.entry_id]["coordinator"]
        assert coordinator.ws_client is None

    async def test_use_websocket_default(
        self,
        hass: HomeAssistant,
        mock_evon_api_class,
        mock_config_entry: MockConfigEntry,
    ) -> None:
        """Test use_websocket matches config (http_only=True means WS disabled)."""
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        coordinator = hass.data[DOMAIN][mock_config_entry.entry_id]["coordinator"]
        # http_only=True means WebSocket is disabled
        assert coordinator.use_websocket is False

    async def test_set_use_websocket(
        self,
        hass: HomeAssistant,
        mock_evon_api_class,
        mock_config_entry: MockConfigEntry,
    ) -> None:
        """Test set_use_websocket updates the flag."""
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        coordinator = hass.data[DOMAIN][mock_config_entry.entry_id]["coordinator"]
        coordinator.set_use_websocket(True)
        assert coordinator.use_websocket is True

    async def test_set_update_interval_with_ws_connected(
        self,
        hass: HomeAssistant,
        mock_evon_api_class,
        mock_config_entry: MockConfigEntry,
    ) -> None:
        """Test that set_update_interval doesn't change interval when WS is connected."""
        from datetime import timedelta

        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        coordinator = hass.data[DOMAIN][mock_config_entry.entry_id]["coordinator"]

        # Simulate WS connected state
        coordinator._ws_connected = True
        coordinator.update_interval = timedelta(seconds=60)

        # set_update_interval should NOT change the interval when WS is connected
        coordinator.set_update_interval(15)
        assert coordinator._base_scan_interval == 15
        assert coordinator.update_interval.total_seconds() == 60  # unchanged


@requires_ha_test_framework
class TestCoordinatorRoomSync:
    """Test coordinator room sync functionality."""

    @pytest.fixture
    def mock_config_entry(self) -> MockConfigEntry:
        """Create a mock config entry with sync_areas enabled."""
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
                "sync_areas": True,
                "http_only": True,
            },
            entry_id="test_room_sync_entry",
        )

    async def test_rooms_fetched_when_sync_enabled(
        self,
        hass: HomeAssistant,
        mock_evon_api_class,
        mock_config_entry: MockConfigEntry,
    ) -> None:
        """Test that rooms are fetched when sync_areas is enabled."""
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        coordinator = hass.data[DOMAIN][mock_config_entry.entry_id]["coordinator"]
        # Rooms should be populated
        assert coordinator.data.get("rooms") is not None
        assert len(coordinator.data["rooms"]) > 0

    async def test_rooms_empty_when_sync_disabled(
        self,
        hass: HomeAssistant,
        mock_evon_api_class,
    ) -> None:
        """Test that rooms dict is empty when sync_areas is disabled."""
        entry = MockConfigEntry(
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
                "http_only": True,
            },
            entry_id="test_no_sync_entry",
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
        assert coordinator.data.get("rooms") == {}


@requires_ha_test_framework
class TestDoorbellEventTransition:
    """Tests for doorbell event transition detection."""

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
            entry_id="test_doorbell_entry",
        )

    @pytest.mark.asyncio
    async def test_doorbell_fires_on_false_to_true(
        self,
        hass: HomeAssistant,
        mock_evon_api_class,
        mock_config_entry: MockConfigEntry,
    ) -> None:
        """Test doorbell event fires when transitioning from False to True."""
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        coordinator = hass.data[DOMAIN][mock_config_entry.entry_id]["coordinator"]

        # Track fired events
        events = []
        hass.bus.async_listen("evon_doorbell", lambda event: events.append(event))

        # Simulate WS update: doorbell False → True
        coordinator._handle_ws_values_changed(
            "intercom_1",
            {"DoorBellTriggered": True},
        )
        await hass.async_block_till_done()

        assert len(events) == 1
        assert events[0].data["device_id"] == "intercom_1"

    @pytest.mark.asyncio
    async def test_doorbell_does_not_fire_on_true_to_true(
        self,
        hass: HomeAssistant,
        mock_evon_api_class,
        mock_config_entry: MockConfigEntry,
    ) -> None:
        """Test doorbell event does NOT fire when value stays True (no transition)."""
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        coordinator = hass.data[DOMAIN][mock_config_entry.entry_id]["coordinator"]

        # First set doorbell to True
        coordinator._handle_ws_values_changed(
            "intercom_1",
            {"DoorBellTriggered": True},
        )
        await hass.async_block_till_done()

        # Track events from this point
        events = []
        hass.bus.async_listen("evon_doorbell", lambda event: events.append(event))

        # Send another True — should NOT fire again (True → True, no transition)
        coordinator._handle_ws_values_changed(
            "intercom_1",
            {"DoorBellTriggered": True},
        )
        await hass.async_block_till_done()

        assert len(events) == 0

    @pytest.mark.asyncio
    async def test_doorbell_fires_again_after_reset(
        self,
        hass: HomeAssistant,
        mock_evon_api_class,
        mock_config_entry: MockConfigEntry,
    ) -> None:
        """Test doorbell fires again after resetting to False then True."""
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        coordinator = hass.data[DOMAIN][mock_config_entry.entry_id]["coordinator"]

        events = []
        hass.bus.async_listen("evon_doorbell", lambda event: events.append(event))

        # False → True: should fire
        coordinator._handle_ws_values_changed(
            "intercom_1",
            {"DoorBellTriggered": True},
        )
        await hass.async_block_till_done()
        assert len(events) == 1

        # True → False: reset
        coordinator._handle_ws_values_changed(
            "intercom_1",
            {"DoorBellTriggered": False},
        )
        await hass.async_block_till_done()

        # False → True again: should fire again
        coordinator._handle_ws_values_changed(
            "intercom_1",
            {"DoorBellTriggered": True},
        )
        await hass.async_block_till_done()
        assert len(events) == 2
