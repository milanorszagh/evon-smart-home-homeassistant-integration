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

        # Switch processor currently returns empty (no switch classes)
        assert coordinator.get_entity_data("switches", "light_2") is None
        assert coordinator.get_entity_data("switches", "nonexistent") is None

        # light_2 (SmartCOM.Light.Light) is now in lights
        light_data = coordinator.get_entity_data("lights", "light_2")
        assert light_data is not None
        assert light_data["id"] == "light_2"

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

    async def test_auth_error_raises_config_entry_auth_failed(
        self,
        hass: HomeAssistant,
        mock_evon_api_class,
        mock_config_entry: MockConfigEntry,
    ) -> None:
        """Test that EvonAuthError from the API raises ConfigEntryAuthFailed."""
        from homeassistant.exceptions import ConfigEntryAuthFailed

        from custom_components.evon.api import EvonAuthError

        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        coordinator = hass.data[DOMAIN][mock_config_entry.entry_id]["coordinator"]

        mock_evon_api_class.get_instances = AsyncMock(side_effect=EvonAuthError("Token expired"))

        with pytest.raises(ConfigEntryAuthFailed):
            await coordinator._async_update_data()

    async def test_reentrant_refresh_skipped_while_poll_in_progress(
        self,
        hass: HomeAssistant,
        mock_evon_api_class,
        mock_config_entry: MockConfigEntry,
    ) -> None:
        """RV-D5: a re-entrant refresh while a poll is in flight must not start a
        second concurrent fetch — HA core doesn't serialize _async_refresh, so the
        guard returns current data instead of racing a second ~930-instance poll."""
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        coordinator = hass.data[DOMAIN][mock_config_entry.entry_id]["coordinator"]

        # Simulate a poll already running.
        coordinator._update_in_progress = True
        mock_evon_api_class.get_instances.reset_mock()

        result = await coordinator._async_update_data()

        # Guard returned current data without fetching, and left the flag alone
        # (it belongs to the in-flight poll).
        assert result is coordinator.data
        mock_evon_api_class.get_instances.assert_not_called()
        assert coordinator._update_in_progress is True

    async def test_partial_instance_failure_sets_flag(
        self,
        hass: HomeAssistant,
        mock_evon_api_class,
        mock_config_entry: MockConfigEntry,
    ) -> None:
        """RV-D6: a transient per-instance fetch error marks the poll as having
        partial failures (so setup can skip stale-entity cleanup)."""
        from custom_components.evon.api import EvonApiError

        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        coordinator = hass.data[DOMAIN][mock_config_entry.entry_id]["coordinator"]
        # Clean initial poll: no partial failures.
        assert coordinator._last_poll_had_partial_failures is False

        # One instance now fails transiently; the rest succeed.
        def _get_instance(instance_id):
            if instance_id == "light_1":
                raise EvonApiError("transient fetch error")
            return MOCK_INSTANCE_DETAILS.get(instance_id, {})

        mock_evon_api_class.get_instance = AsyncMock(side_effect=_get_instance)
        await coordinator.async_refresh()

        assert coordinator._last_poll_had_partial_failures is True

    async def test_setup_skips_cleanup_on_partial_failure(
        self,
        hass: HomeAssistant,
        mock_evon_api_class,
        mock_config_entry: MockConfigEntry,
    ) -> None:
        """RV-D6: setup must not run stale-entity cleanup when the setup poll had
        partial instance-fetch failures (else transiently-missing entities are
        deleted along with their registry customizations)."""
        from unittest.mock import patch

        from custom_components.evon.api import EvonApiError

        def _get_instance(instance_id):
            if instance_id == "light_1":
                raise EvonApiError("transient fetch error")
            return MOCK_INSTANCE_DETAILS.get(instance_id, {})

        mock_evon_api_class.get_instance = AsyncMock(side_effect=_get_instance)
        mock_config_entry.add_to_hass(hass)

        with patch("custom_components.evon._async_cleanup_stale_entities") as mock_cleanup:
            await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

        mock_cleanup.assert_not_called()

    async def test_setup_runs_cleanup_on_clean_poll(
        self,
        hass: HomeAssistant,
        mock_evon_api_class,
        mock_config_entry: MockConfigEntry,
    ) -> None:
        """RV-D6: a clean setup poll (no partial failures) still runs cleanup."""
        from unittest.mock import patch

        mock_config_entry.add_to_hass(hass)

        with patch("custom_components.evon._async_cleanup_stale_entities") as mock_cleanup:
            await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

        mock_cleanup.assert_called_once()

    async def test_ws_disconnect_creates_repair_issue(
        self,
        hass: HomeAssistant,
        mock_evon_api_class,
        mock_config_entry: MockConfigEntry,
    ) -> None:
        """Test that WebSocket disconnect creates a repair issue."""
        from homeassistant.helpers import issue_registry as ir

        from custom_components.evon.const import REPAIR_WEBSOCKET_DISCONNECTED

        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        coordinator = hass.data[DOMAIN][mock_config_entry.entry_id]["coordinator"]

        # Simulate WebSocket disconnect
        coordinator._handle_ws_connection_state(False)

        issue_registry = ir.async_get(hass)
        issue_id = f"{REPAIR_WEBSOCKET_DISCONNECTED}_{mock_config_entry.entry_id}"
        issue = issue_registry.async_get_issue(DOMAIN, issue_id)
        assert issue is not None

    async def test_ws_reconnect_clears_repair_issue(
        self,
        hass: HomeAssistant,
        mock_evon_api_class,
        mock_config_entry: MockConfigEntry,
    ) -> None:
        """Test that WebSocket reconnect removes the disconnect repair issue."""
        from homeassistant.helpers import issue_registry as ir

        from custom_components.evon.const import REPAIR_WEBSOCKET_DISCONNECTED

        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        coordinator = hass.data[DOMAIN][mock_config_entry.entry_id]["coordinator"]
        issue_id = f"{REPAIR_WEBSOCKET_DISCONNECTED}_{mock_config_entry.entry_id}"

        # Disconnect first to create the issue
        coordinator._handle_ws_connection_state(False)
        issue_registry = ir.async_get(hass)
        assert issue_registry.async_get_issue(DOMAIN, issue_id) is not None

        # Reconnect — issue should be cleared
        coordinator._handle_ws_connection_state(True)
        assert issue_registry.async_get_issue(DOMAIN, issue_id) is None


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


@requires_ha_test_framework
class TestShutdownSuppression:
    """Intentional WS shutdown must not masquerade as a connection failure.

    `EvonWsClient.stop()` fires `_on_connection_state(False)` when the socket
    was connected. Without a shutdown guard, every unload/reload (= every
    non-debug options save) pops a spurious 'WebSocket disconnected' repair
    issue and schedules a full poll against a session that is about to close.
    """

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
            entry_id="test_shutdown_entry",
        )

    async def test_shutdown_websocket_suppresses_repair_and_refresh(
        self,
        hass: HomeAssistant,
        mock_evon_api_class,
        mock_config_entry: MockConfigEntry,
    ) -> None:
        """The disconnect callback fired from stop() during shutdown must not
        create a repair issue nor schedule a refresh."""
        from homeassistant.helpers import issue_registry as ir

        from custom_components.evon.const import REPAIR_WEBSOCKET_DISCONNECTED

        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        coordinator = hass.data[DOMAIN][mock_config_entry.entry_id]["coordinator"]

        # Fake WS client that mimics the real one: stop() notifies the
        # connection-state callback with False (see EvonWsClient.disconnect).
        class _FakeWsClient:
            def __init__(self, callback):
                self._callback = callback

            async def stop(self):
                self._callback(False)

        from unittest.mock import patch

        coordinator._ws_client = _FakeWsClient(coordinator._handle_ws_connection_state)
        coordinator._ws_connected = True

        with patch.object(coordinator, "async_request_refresh", new_callable=AsyncMock) as mock_refresh:
            await coordinator.async_shutdown_websocket()
            await hass.async_block_till_done()

        issue_registry = ir.async_get(hass)
        issue_id = f"{REPAIR_WEBSOCKET_DISCONNECTED}_{mock_config_entry.entry_id}"
        assert issue_registry.async_get_issue(DOMAIN, issue_id) is None
        mock_refresh.assert_not_called()
        assert coordinator.ws_connected is False

    async def test_unexpected_disconnect_still_creates_repair(
        self,
        hass: HomeAssistant,
        mock_evon_api_class,
        mock_config_entry: MockConfigEntry,
    ) -> None:
        """A real (non-shutdown) disconnect keeps the repair behavior — the
        guard must apply ONLY during intentional shutdown."""
        from homeassistant.helpers import issue_registry as ir

        from custom_components.evon.const import REPAIR_WEBSOCKET_DISCONNECTED

        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        coordinator = hass.data[DOMAIN][mock_config_entry.entry_id]["coordinator"]

        # First, run a full shutdown cycle (flag must not stick afterwards).
        class _FakeWsClient:
            def __init__(self, callback):
                self._callback = callback

            async def stop(self):
                self._callback(False)

        coordinator._ws_client = _FakeWsClient(coordinator._handle_ws_connection_state)
        coordinator._ws_connected = True
        await coordinator.async_shutdown_websocket()
        await hass.async_block_till_done()

        # Now a genuine disconnect arrives — repair must be created.
        coordinator._handle_ws_connection_state(False)

        issue_registry = ir.async_get(hass)
        issue_id = f"{REPAIR_WEBSOCKET_DISCONNECTED}_{mock_config_entry.entry_id}"
        assert issue_registry.async_get_issue(DOMAIN, issue_id) is not None


@requires_ha_test_framework
class TestCoordinatorConcurrency:
    """Concurrent-refresh hardening beyond the RV-D5 fast-path skip."""

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
            entry_id="test_concurrency_entry",
        )

    async def test_concurrent_first_refresh_serialized(
        self,
        hass: HomeAssistant,
        mock_evon_api_class,
        mock_config_entry: MockConfigEntry,
    ) -> None:
        """With no data yet (first refresh), the RV-D5 skip cannot return cached
        data — two concurrent refreshes must serialize instead of racing on
        _instances_cache / _rooms_cache / _ws_update_timestamps."""
        import asyncio

        from tests.conftest import MOCK_INSTANCES

        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        coordinator = hass.data[DOMAIN][mock_config_entry.entry_id]["coordinator"]

        # Simulate the first-refresh state: no data yet.
        coordinator.data = None

        in_flight = 0
        max_in_flight = 0

        async def slow_get_instances():
            nonlocal in_flight, max_in_flight
            in_flight += 1
            max_in_flight = max(max_in_flight, in_flight)
            # Yield so a concurrent caller can interleave if unserialized.
            await asyncio.sleep(0)
            await asyncio.sleep(0)
            in_flight -= 1
            return MOCK_INSTANCES

        mock_evon_api_class.get_instances = AsyncMock(side_effect=slow_get_instances)

        await asyncio.gather(
            coordinator._async_update_data(),
            coordinator._async_update_data(),
        )

        assert max_in_flight == 1, "two polls ran concurrently over shared caches"

    async def test_partial_failures_exposed_as_property(
        self,
        hass: HomeAssistant,
        mock_evon_api_class,
        mock_config_entry: MockConfigEntry,
    ) -> None:
        """Setup code reads the partial-failure flag via a public property."""
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        coordinator = hass.data[DOMAIN][mock_config_entry.entry_id]["coordinator"]

        assert coordinator.last_poll_had_partial_failures is False
        coordinator._last_poll_had_partial_failures = True
        assert coordinator.last_poll_had_partial_failures is True


@requires_ha_test_framework
class TestEnergyImportRateLimitPreCheck:
    """The WS path must not spawn a task per meter event only to rate-limit it.

    Smart meters push every few seconds; creating an asyncio task each time —
    whose body immediately returns on the 1h rate limit — is constant churn.
    The rate-limit check must happen BEFORE task creation.
    """

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
            entry_id="test_ratelimit_entry",
        )

    async def test_rate_limited_meter_creates_no_task(
        self,
        hass: HomeAssistant,
        mock_evon_api_class,
        mock_config_entry: MockConfigEntry,
    ) -> None:
        from homeassistant.util import dt as dt_util

        from custom_components.evon.statistics import _HASS_DATA_KEY

        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        coordinator = hass.data[DOMAIN][mock_config_entry.entry_id]["coordinator"]

        # Meter imported moments ago — well inside the 1h rate limit.
        hass.data[_HASS_DATA_KEY] = {"SmartMeter1": dt_util.now()}

        from unittest.mock import patch

        entity_data = {"name": "Meter", "energy_data_month": [1.0, 2.0]}
        with patch.object(hass, "async_create_task") as mock_create_task:
            coordinator._maybe_import_energy_statistics("SmartMeter1", entity_data)

        mock_create_task.assert_not_called()

    async def test_fresh_meter_still_creates_task(
        self,
        hass: HomeAssistant,
        mock_evon_api_class,
        mock_config_entry: MockConfigEntry,
    ) -> None:
        from custom_components.evon.statistics import _HASS_DATA_KEY

        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        coordinator = hass.data[DOMAIN][mock_config_entry.entry_id]["coordinator"]

        hass.data[_HASS_DATA_KEY] = {}

        entity_data = {"name": "Meter", "energy_data_month": [1.0, 2.0]}
        from unittest.mock import MagicMock, patch

        created = []

        def _capture(coro, *args, **kwargs):
            created.append(coro)
            # Close instead of running: the import itself needs the recorder,
            # which isn't set up here — this test only asserts task creation.
            coro.close()
            return MagicMock()

        with patch.object(hass, "async_create_task", side_effect=_capture):
            coordinator._maybe_import_energy_statistics("SmartMeter1", entity_data)
        await hass.async_block_till_done()

        assert len(created) == 1

    async def test_force_bypasses_pre_check(
        self,
        hass: HomeAssistant,
        mock_evon_api_class,
        mock_config_entry: MockConfigEntry,
    ) -> None:
        from homeassistant.util import dt as dt_util

        from custom_components.evon.statistics import _HASS_DATA_KEY

        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        coordinator = hass.data[DOMAIN][mock_config_entry.entry_id]["coordinator"]

        hass.data[_HASS_DATA_KEY] = {"SmartMeter1": dt_util.now()}

        entity_data = {"name": "Meter", "energy_data_month": [1.0, 2.0]}
        from unittest.mock import MagicMock, patch

        created = []

        def _capture(coro, *args, **kwargs):
            created.append(coro)
            # Close instead of running: the import itself needs the recorder,
            # which isn't set up here — this test only asserts task creation.
            coro.close()
            return MagicMock()

        with patch.object(hass, "async_create_task", side_effect=_capture):
            coordinator._maybe_import_energy_statistics("SmartMeter1", entity_data, force=True)
        await hass.async_block_till_done()

        assert len(created) == 1
