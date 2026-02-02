"""Comprehensive tests for constants (no HA framework required)."""

from __future__ import annotations

import pytest


class TestDomainConstants:
    """Tests for domain and configuration constants."""

    def test_domain(self):
        """Test DOMAIN constant."""
        from custom_components.evon.const import DOMAIN

        assert DOMAIN == "evon"

    def test_configuration_keys(self):
        """Test configuration key constants."""
        from custom_components.evon.const import (
            CONF_CONNECTION_TYPE,
            CONF_ENGINE_ID,
            CONF_HOST,
            CONF_PASSWORD,
            CONF_SCAN_INTERVAL,
            CONF_SYNC_AREAS,
            CONF_USERNAME,
        )

        assert CONF_HOST == "host"
        assert CONF_USERNAME == "username"
        assert CONF_PASSWORD == "password"
        assert CONF_SCAN_INTERVAL == "scan_interval"
        assert CONF_SYNC_AREAS == "sync_areas"
        assert CONF_CONNECTION_TYPE == "connection_type"
        assert CONF_ENGINE_ID == "engine_id"

    def test_connection_types(self):
        """Test connection type constants."""
        from custom_components.evon.const import CONNECTION_TYPE_LOCAL, CONNECTION_TYPE_REMOTE

        assert CONNECTION_TYPE_LOCAL == "local"
        assert CONNECTION_TYPE_REMOTE == "remote"

    def test_remote_host(self):
        """Test remote host URL is HTTPS."""
        from custom_components.evon.const import EVON_REMOTE_HOST

        assert EVON_REMOTE_HOST.startswith("https://")
        assert "evon-smarthome.com" in EVON_REMOTE_HOST


class TestDefaultValues:
    """Tests for default value constants."""

    def test_default_scan_interval(self):
        """Test default scan interval is reasonable."""
        from custom_components.evon.const import DEFAULT_SCAN_INTERVAL

        assert DEFAULT_SCAN_INTERVAL == 30
        assert 5 <= DEFAULT_SCAN_INTERVAL <= 300

    def test_poll_interval_range(self):
        """Test poll interval range is valid."""
        from custom_components.evon.const import MAX_POLL_INTERVAL, MIN_POLL_INTERVAL

        assert MIN_POLL_INTERVAL == 5
        assert MAX_POLL_INTERVAL == 300
        assert MIN_POLL_INTERVAL < MAX_POLL_INTERVAL

    def test_default_timeouts(self):
        """Test default timeout values are reasonable."""
        from custom_components.evon.const import DEFAULT_LOGIN_TIMEOUT, DEFAULT_REQUEST_TIMEOUT

        assert DEFAULT_REQUEST_TIMEOUT == 30
        assert DEFAULT_LOGIN_TIMEOUT == 15
        assert DEFAULT_LOGIN_TIMEOUT < DEFAULT_REQUEST_TIMEOUT

    def test_temperature_defaults(self):
        """Test temperature defaults are reasonable for Celsius."""
        from custom_components.evon.const import DEFAULT_MAX_TEMP, DEFAULT_MIN_TEMP

        assert DEFAULT_MIN_TEMP == 15.0
        assert DEFAULT_MAX_TEMP == 25.0
        assert DEFAULT_MIN_TEMP < DEFAULT_MAX_TEMP


class TestValidationConstants:
    """Tests for validation constants."""

    def test_password_length(self):
        """Test password length validation."""
        from custom_components.evon.const import MIN_PASSWORD_LENGTH

        assert MIN_PASSWORD_LENGTH == 1

    def test_engine_id_length(self):
        """Test engine ID length validation."""
        from custom_components.evon.const import ENGINE_ID_MAX_LENGTH, ENGINE_ID_MIN_LENGTH

        assert ENGINE_ID_MIN_LENGTH == 4
        assert ENGINE_ID_MAX_LENGTH == 12
        assert ENGINE_ID_MIN_LENGTH < ENGINE_ID_MAX_LENGTH


class TestClimateConstants:
    """Tests for climate-related constants."""

    def test_season_modes(self):
        """Test season mode constants."""
        from custom_components.evon.const import SEASON_MODE_COOLING, SEASON_MODE_HEATING

        assert SEASON_MODE_HEATING == "heating"
        assert SEASON_MODE_COOLING == "cooling"

    def test_climate_preset_modes(self):
        """Test climate preset mode constants."""
        from custom_components.evon.const import (
            CLIMATE_MODE_COMFORT,
            CLIMATE_MODE_ENERGY_SAVING,
            CLIMATE_MODE_FREEZE_PROTECTION,
        )

        assert CLIMATE_MODE_COMFORT == "comfort"
        assert CLIMATE_MODE_ENERGY_SAVING == "eco"
        assert CLIMATE_MODE_FREEZE_PROTECTION == "away"

    def test_evon_preset_heating_mapping(self):
        """Test Evon preset heating mode mapping."""
        from custom_components.evon.const import (
            CLIMATE_MODE_COMFORT,
            CLIMATE_MODE_ENERGY_SAVING,
            CLIMATE_MODE_FREEZE_PROTECTION,
            EVON_PRESET_HEATING,
        )

        assert EVON_PRESET_HEATING[2] == CLIMATE_MODE_FREEZE_PROTECTION  # away
        assert EVON_PRESET_HEATING[3] == CLIMATE_MODE_ENERGY_SAVING  # eco
        assert EVON_PRESET_HEATING[4] == CLIMATE_MODE_COMFORT  # comfort

    def test_evon_preset_cooling_mapping(self):
        """Test Evon preset cooling mode mapping."""
        from custom_components.evon.const import (
            CLIMATE_MODE_COMFORT,
            CLIMATE_MODE_ENERGY_SAVING,
            CLIMATE_MODE_FREEZE_PROTECTION,
            EVON_PRESET_COOLING,
        )

        assert EVON_PRESET_COOLING[5] == CLIMATE_MODE_FREEZE_PROTECTION  # heat protection
        assert EVON_PRESET_COOLING[6] == CLIMATE_MODE_ENERGY_SAVING  # eco
        assert EVON_PRESET_COOLING[7] == CLIMATE_MODE_COMFORT  # comfort

    def test_heating_and_cooling_presets_are_disjoint(self):
        """Test that heating and cooling preset keys don't overlap."""
        from custom_components.evon.const import EVON_PRESET_COOLING, EVON_PRESET_HEATING

        heating_keys = set(EVON_PRESET_HEATING.keys())
        cooling_keys = set(EVON_PRESET_COOLING.keys())
        assert heating_keys.isdisjoint(cooling_keys)


class TestDeviceClassConstants:
    """Tests for device class name constants."""

    def test_light_classes(self):
        """Test light class constants."""
        from custom_components.evon.const import (
            EVON_CLASS_LIGHT,
            EVON_CLASS_LIGHT_DIM,
            EVON_CLASS_LIGHT_GROUP,
        )

        assert EVON_CLASS_LIGHT == "SmartCOM.Light.Light"
        assert EVON_CLASS_LIGHT_DIM == "SmartCOM.Light.LightDim"
        assert EVON_CLASS_LIGHT_GROUP == "SmartCOM.Light.LightGroup"
        # All should start with SmartCOM.Light
        assert all(c.startswith("SmartCOM.Light") for c in [EVON_CLASS_LIGHT, EVON_CLASS_LIGHT_DIM, EVON_CLASS_LIGHT_GROUP])

    def test_blind_classes(self):
        """Test blind class constants."""
        from custom_components.evon.const import EVON_CLASS_BLIND, EVON_CLASS_BLIND_GROUP

        assert EVON_CLASS_BLIND == "SmartCOM.Blind.Blind"
        assert EVON_CLASS_BLIND_GROUP == "SmartCOM.Blind.BlindGroup"

    def test_climate_classes(self):
        """Test climate class constants."""
        from custom_components.evon.const import EVON_CLASS_CLIMATE, EVON_CLASS_CLIMATE_UNIVERSAL

        assert EVON_CLASS_CLIMATE == "SmartCOM.Clima.ClimateControl"
        assert EVON_CLASS_CLIMATE_UNIVERSAL == "Heating.ClimateControlUniversal"

    def test_security_classes(self):
        """Test security-related class constants."""
        from custom_components.evon.const import (
            EVON_CLASS_INTERCOM_2N,
            EVON_CLASS_INTERCOM_2N_CAM,
            EVON_CLASS_SECURITY_DOOR,
        )

        assert EVON_CLASS_SECURITY_DOOR == "Security.Door"
        assert EVON_CLASS_INTERCOM_2N == "Security.Intercom.2N.Intercom2N"
        assert EVON_CLASS_INTERCOM_2N_CAM == "Security.Intercom.2N.Intercom2NCam"
        # Camera should contain the intercom class as prefix
        assert EVON_CLASS_INTERCOM_2N_CAM.startswith("Security.Intercom.2N")

    def test_other_device_classes(self):
        """Test other device class constants."""
        from custom_components.evon.const import (
            EVON_CLASS_AIR_QUALITY,
            EVON_CLASS_BATHROOM_RADIATOR,
            EVON_CLASS_HOME_STATE,
            EVON_CLASS_SCENE,
            EVON_CLASS_SMART_METER,
            EVON_CLASS_SWITCH,
            EVON_CLASS_VALVE,
        )

        assert EVON_CLASS_SWITCH == "SmartCOM.Switch"
        assert EVON_CLASS_SMART_METER == "Energy.SmartMeter"
        assert EVON_CLASS_AIR_QUALITY == "System.Location.AirQuality"
        assert EVON_CLASS_VALVE == "SmartCOM.Clima.Valve"
        assert EVON_CLASS_HOME_STATE == "System.HomeState"
        assert EVON_CLASS_BATHROOM_RADIATOR == "Heating.BathroomRadiator"
        assert EVON_CLASS_SCENE == "System.SceneApp"


class TestOptimisticStateConstants:
    """Tests for optimistic state handling constants."""

    def test_optimistic_state_tolerance(self):
        """Test optimistic state tolerance is small."""
        from custom_components.evon.const import OPTIMISTIC_STATE_TOLERANCE

        assert OPTIMISTIC_STATE_TOLERANCE == 2
        assert 0 < OPTIMISTIC_STATE_TOLERANCE <= 5

    def test_optimistic_state_timeout(self):
        """Test optimistic state timeout is reasonable."""
        from custom_components.evon.const import OPTIMISTIC_STATE_TIMEOUT

        assert OPTIMISTIC_STATE_TIMEOUT == 30.0
        assert 10.0 <= OPTIMISTIC_STATE_TIMEOUT <= 60.0

    def test_optimistic_settling_periods(self):
        """Test optimistic settling periods are reasonable."""
        from custom_components.evon.const import OPTIMISTIC_SETTLING_PERIOD, OPTIMISTIC_SETTLING_PERIOD_SHORT

        assert OPTIMISTIC_SETTLING_PERIOD == 2.5
        assert OPTIMISTIC_SETTLING_PERIOD_SHORT == 1.0
        assert OPTIMISTIC_SETTLING_PERIOD_SHORT < OPTIMISTIC_SETTLING_PERIOD

    def test_cover_stop_delay(self):
        """Test cover stop delay is small but non-zero."""
        from custom_components.evon.const import COVER_STOP_DELAY

        assert COVER_STOP_DELAY == 0.3
        assert 0 < COVER_STOP_DELAY < 1.0


class TestWebSocketConstants:
    """Tests for WebSocket configuration constants."""

    def test_websocket_defaults(self):
        """Test WebSocket default values."""
        from custom_components.evon.const import CONF_HTTP_ONLY, DEFAULT_HTTP_ONLY

        assert CONF_HTTP_ONLY == "http_only"
        assert DEFAULT_HTTP_ONLY is False  # WebSocket enabled by default

    def test_websocket_reconnect_delays(self):
        """Test WebSocket reconnect delay values."""
        from custom_components.evon.const import DEFAULT_WS_RECONNECT_DELAY, WS_RECONNECT_MAX_DELAY

        assert DEFAULT_WS_RECONNECT_DELAY == 5
        assert WS_RECONNECT_MAX_DELAY == 300
        assert DEFAULT_WS_RECONNECT_DELAY < WS_RECONNECT_MAX_DELAY

    def test_websocket_protocol(self):
        """Test WebSocket protocol constant."""
        from custom_components.evon.const import WS_PROTOCOL

        assert WS_PROTOCOL == "echo-protocol"

    def test_websocket_poll_interval(self):
        """Test WebSocket safety poll interval."""
        from custom_components.evon.const import WS_POLL_INTERVAL

        assert WS_POLL_INTERVAL == 60


class TestRepairConstants:
    """Tests for repair issue ID constants."""

    def test_repair_issue_ids(self):
        """Test repair issue ID constants."""
        from custom_components.evon.const import (
            REPAIR_CONFIG_MIGRATION,
            REPAIR_CONNECTION_FAILED,
            REPAIR_STALE_ENTITIES_CLEANED,
        )

        assert REPAIR_CONNECTION_FAILED == "connection_failed"
        assert REPAIR_STALE_ENTITIES_CLEANED == "stale_entities_cleaned"
        assert REPAIR_CONFIG_MIGRATION == "config_migration_needed"

    def test_connection_failure_threshold(self):
        """Test connection failure threshold."""
        from custom_components.evon.const import CONNECTION_FAILURE_THRESHOLD

        assert CONNECTION_FAILURE_THRESHOLD == 3
        assert CONNECTION_FAILURE_THRESHOLD > 0


class TestCameraConstants:
    """Tests for camera/image related constants."""

    def test_camera_image_capture_delay(self):
        """Test camera image capture delay."""
        from custom_components.evon.const import CAMERA_IMAGE_CAPTURE_DELAY

        assert CAMERA_IMAGE_CAPTURE_DELAY == 0.5
        assert 0 < CAMERA_IMAGE_CAPTURE_DELAY < 5.0

    def test_image_fetch_timeout(self):
        """Test image fetch timeout."""
        from custom_components.evon.const import CAMERA_IMAGE_CAPTURE_DELAY, IMAGE_FETCH_TIMEOUT

        assert IMAGE_FETCH_TIMEOUT == 10
        assert IMAGE_FETCH_TIMEOUT > CAMERA_IMAGE_CAPTURE_DELAY


class TestBathroomRadiatorConstants:
    """Tests for bathroom radiator constants."""

    def test_default_duration(self):
        """Test default bathroom radiator duration."""
        from custom_components.evon.const import DEFAULT_BATHROOM_RADIATOR_DURATION

        assert DEFAULT_BATHROOM_RADIATOR_DURATION == 30  # minutes
        assert 10 <= DEFAULT_BATHROOM_RADIATOR_DURATION <= 120


class TestOptionsConstants:
    """Tests for options key constants."""

    def test_non_dimmable_lights_option(self):
        """Test non-dimmable lights option key."""
        from custom_components.evon.const import CONF_NON_DIMMABLE_LIGHTS

        assert CONF_NON_DIMMABLE_LIGHTS == "non_dimmable_lights"
