"""Tests for _extract_instance_id_from_unique_id() in __init__.py."""

from __future__ import annotations

from custom_components.evon import _extract_instance_id_from_unique_id

ENTRY_ID = "test_entry_123"


class TestBasicPrefixes:
    """Test extraction for standard type prefixes."""

    def test_light(self):
        assert _extract_instance_id_from_unique_id("evon_light_SC1_M01.Light1", ENTRY_ID) == "SC1_M01.Light1"

    def test_cover(self):
        assert _extract_instance_id_from_unique_id("evon_cover_SC1_M01.Blind1", ENTRY_ID) == "SC1_M01.Blind1"

    def test_climate(self):
        assert _extract_instance_id_from_unique_id("evon_climate_Heating.Zone1", ENTRY_ID) == "Heating.Zone1"

    def test_switch(self):
        assert _extract_instance_id_from_unique_id("evon_switch_SC1_M01.Switch1", ENTRY_ID) == "SC1_M01.Switch1"

    def test_radiator(self):
        assert _extract_instance_id_from_unique_id("evon_radiator_Heating.Radiator1", ENTRY_ID) == "Heating.Radiator1"

    def test_valve(self):
        assert _extract_instance_id_from_unique_id("evon_valve_Heating.Valve1", ENTRY_ID) == "Heating.Valve1"

    def test_scene(self):
        assert _extract_instance_id_from_unique_id("evon_scene_System.Scene1", ENTRY_ID) == "System.Scene1"

    def test_identify(self):
        assert _extract_instance_id_from_unique_id("evon_identify_SC1_M01.Light1", ENTRY_ID) == "SC1_M01.Light1"

    def test_camera(self):
        assert _extract_instance_id_from_unique_id("evon_camera_Intercom2N1000.Cam", ENTRY_ID) == "Intercom2N1000.Cam"

    def test_camera_recording(self):
        assert (
            _extract_instance_id_from_unique_id("evon_camera_recording_Intercom2N1000.Cam", ENTRY_ID)
            == "Intercom2N1000.Cam"
        )

    def test_temp(self):
        assert _extract_instance_id_from_unique_id("evon_temp_SC1_M01.TempSensor", ENTRY_ID) == "SC1_M01.TempSensor"


class TestSuffixStripping:
    """Test suffix stripping for entities with _call, _connection, etc."""

    def test_security_door_call_suffix(self):
        assert (
            _extract_instance_id_from_unique_id("evon_security_door_Security.Door1_call", ENTRY_ID) == "Security.Door1"
        )

    def test_security_door_no_suffix(self):
        assert _extract_instance_id_from_unique_id("evon_security_door_Security.Door1", ENTRY_ID) == "Security.Door1"

    def test_intercom_connection_suffix(self):
        assert (
            _extract_instance_id_from_unique_id("evon_intercom_Intercom2N.Unit1_connection", ENTRY_ID)
            == "Intercom2N.Unit1"
        )

    def test_intercom_no_suffix(self):
        assert _extract_instance_id_from_unique_id("evon_intercom_Intercom2N.Unit1", ENTRY_ID) == "Intercom2N.Unit1"


class TestMeterSensors:
    """Test evon_meter_ prefix with various meter keys."""

    def test_meter_power(self):
        assert _extract_instance_id_from_unique_id("evon_meter_power_Energy.Meter1", ENTRY_ID) == "Energy.Meter1"

    def test_meter_energy(self):
        assert _extract_instance_id_from_unique_id("evon_meter_energy_Energy.Meter1", ENTRY_ID) == "Energy.Meter1"

    def test_meter_energy_today(self):
        assert _extract_instance_id_from_unique_id("evon_meter_energy_today_Energy.Meter1", ENTRY_ID) == "Energy.Meter1"

    def test_meter_energy_month(self):
        assert _extract_instance_id_from_unique_id("evon_meter_energy_month_Energy.Meter1", ENTRY_ID) == "Energy.Meter1"

    def test_meter_energy_24h(self):
        assert _extract_instance_id_from_unique_id("evon_meter_energy_24h_Energy.Meter1", ENTRY_ID) == "Energy.Meter1"

    def test_meter_feed_in_energy(self):
        assert (
            _extract_instance_id_from_unique_id("evon_meter_feed_in_energy_Energy.Meter1", ENTRY_ID) == "Energy.Meter1"
        )

    def test_meter_feed_in_today(self):
        assert (
            _extract_instance_id_from_unique_id("evon_meter_feed_in_today_Energy.Meter1", ENTRY_ID) == "Energy.Meter1"
        )

    def test_meter_feed_in_month(self):
        assert (
            _extract_instance_id_from_unique_id("evon_meter_feed_in_month_Energy.Meter1", ENTRY_ID) == "Energy.Meter1"
        )

    def test_meter_voltage_l1(self):
        assert _extract_instance_id_from_unique_id("evon_meter_voltage_l1_Energy.Meter1", ENTRY_ID) == "Energy.Meter1"

    def test_meter_voltage_l2(self):
        assert _extract_instance_id_from_unique_id("evon_meter_voltage_l2_Energy.Meter1", ENTRY_ID) == "Energy.Meter1"

    def test_meter_voltage_l3(self):
        assert _extract_instance_id_from_unique_id("evon_meter_voltage_l3_Energy.Meter1", ENTRY_ID) == "Energy.Meter1"

    def test_meter_current_l1(self):
        assert _extract_instance_id_from_unique_id("evon_meter_current_l1_Energy.Meter1", ENTRY_ID) == "Energy.Meter1"

    def test_meter_frequency(self):
        assert _extract_instance_id_from_unique_id("evon_meter_frequency_Energy.Meter1", ENTRY_ID) == "Energy.Meter1"

    def test_meter_unknown_key_with_dot_fallback(self):
        """Meter with unrecognized key falls back to dot-based detection."""
        result = _extract_instance_id_from_unique_id("evon_meter_unknown_Energy.Meter1", ENTRY_ID)
        assert result == "Energy.Meter1"

    def test_meter_unknown_key_no_dot_returns_none(self):
        """Meter with unrecognized key and no dot returns None."""
        result = _extract_instance_id_from_unique_id("evon_meter_unknown_nodotkeyhere", ENTRY_ID)
        assert result is None


class TestSnapshotEntities:
    """Test evon_snapshot_ prefix with index stripping."""

    def test_snapshot_with_index(self):
        assert _extract_instance_id_from_unique_id("evon_snapshot_Security.Door1_0", ENTRY_ID) == "Security.Door1"

    def test_snapshot_with_higher_index(self):
        assert _extract_instance_id_from_unique_id("evon_snapshot_Security.Door1_3", ENTRY_ID) == "Security.Door1"

    def test_snapshot_no_index(self):
        """Snapshot without underscore-digit suffix returns full remainder."""
        result = _extract_instance_id_from_unique_id("evon_snapshot_Security.Door1", ENTRY_ID)
        assert result == "Security.Door1"


class TestSpecialEntities:
    """Test special entities that should return None."""

    def test_home_state(self):
        assert _extract_instance_id_from_unique_id(f"evon_home_state_{ENTRY_ID}", ENTRY_ID) is None

    def test_season_mode(self):
        assert _extract_instance_id_from_unique_id(f"evon_season_mode_{ENTRY_ID}", ENTRY_ID) is None

    def test_websocket(self):
        assert _extract_instance_id_from_unique_id(f"evon_websocket_{ENTRY_ID}", ENTRY_ID) is None


class TestAirQualityFallback:
    """Test air quality fallback for evon_{key}_{instance_id}."""

    def test_air_quality_co2(self):
        result = _extract_instance_id_from_unique_id("evon_co2_AirQuality.Sensor1", ENTRY_ID)
        assert result == "AirQuality.Sensor1"

    def test_air_quality_humidity(self):
        result = _extract_instance_id_from_unique_id("evon_humidity_AirQuality.Sensor1", ENTRY_ID)
        assert result == "AirQuality.Sensor1"

    def test_air_quality_no_dot_returns_none(self):
        """Air quality with no dot in any part returns None."""
        result = _extract_instance_id_from_unique_id("evon_unknowntype_nodot", ENTRY_ID)
        assert result is None


class TestEdgeCases:
    """Test edge cases and invalid inputs."""

    def test_none_input(self):
        assert _extract_instance_id_from_unique_id(None, ENTRY_ID) is None

    def test_empty_string(self):
        assert _extract_instance_id_from_unique_id("", ENTRY_ID) is None

    def test_no_evon_prefix(self):
        assert _extract_instance_id_from_unique_id("some_other_unique_id", ENTRY_ID) is None

    def test_just_evon_prefix(self):
        assert _extract_instance_id_from_unique_id("evon_", ENTRY_ID) is None

    def test_instance_id_with_dots_preserved(self):
        """Instance IDs with dots should be preserved intact."""
        assert _extract_instance_id_from_unique_id("evon_light_SC1_M01.Sub.Light1", ENTRY_ID) == "SC1_M01.Sub.Light1"

    def test_instance_id_with_underscores_preserved(self):
        """Instance IDs with underscores should be preserved."""
        assert (
            _extract_instance_id_from_unique_id("evon_switch_SC1_M01.Switch_Relay", ENTRY_ID) == "SC1_M01.Switch_Relay"
        )
