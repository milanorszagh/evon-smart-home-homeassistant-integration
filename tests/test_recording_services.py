"""Tests for start/stop recording service handlers in __init__.py."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.evon import _find_camera_entity
from custom_components.evon.const import DOMAIN
from tests.conftest import requires_ha_test_framework


class TestFindCameraEntity:
    """Unit tests for _find_camera_entity helper."""

    def test_finds_matching_camera(self):
        """Test that a camera entity is found by entity_id."""
        mock_camera = MagicMock()
        mock_camera.entity_id = "camera.intercom_camera"

        hass = MagicMock()
        hass.data = {
            DOMAIN: {
                "entry_1": {
                    "cameras": {
                        "intercom_1.Cam": mock_camera,
                    },
                },
            },
        }

        result = _find_camera_entity(hass, "camera.intercom_camera")
        assert result is mock_camera

    def test_returns_none_for_missing_camera(self):
        """Test that None is returned when camera is not found."""
        hass = MagicMock()
        hass.data = {
            DOMAIN: {
                "entry_1": {
                    "cameras": {},
                },
            },
        }

        result = _find_camera_entity(hass, "camera.nonexistent")
        assert result is None

    def test_returns_none_for_empty_domain_data(self):
        """Test that None is returned when domain data is empty."""
        hass = MagicMock()
        hass.data = {}

        result = _find_camera_entity(hass, "camera.intercom_camera")
        assert result is None

    def test_skips_non_dict_entries(self):
        """Test that non-dict entries in domain data are skipped."""
        mock_camera = MagicMock()
        mock_camera.entity_id = "camera.intercom_camera"

        hass = MagicMock()
        hass.data = {
            DOMAIN: {
                "entry_1": "not_a_dict",
                "entry_2": {
                    "cameras": {
                        "intercom_1.Cam": mock_camera,
                    },
                },
            },
        }

        result = _find_camera_entity(hass, "camera.intercom_camera")
        assert result is mock_camera


@requires_ha_test_framework
class TestRecordingServicesIntegration:
    """Integration tests for recording service handlers."""

    @pytest.mark.asyncio
    async def test_start_recording_calls_camera(self, hass, mock_config_entry_v2, mock_evon_api_class):
        """Test that start_recording service finds camera and calls start."""
        mock_config_entry_v2.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
        await hass.async_block_till_done()

        # Create a mock camera entity and register it
        mock_camera = MagicMock()
        mock_camera.entity_id = "camera.evon_intercom_camera"
        mock_camera.async_start_recording = AsyncMock()

        hass.data[DOMAIN][mock_config_entry_v2.entry_id]["cameras"] = {
            "intercom_1.Cam": mock_camera,
        }

        # Set up a mock state so hass.states.get() returns something
        hass.states.async_set("camera.evon_intercom_camera", "idle")

        await hass.services.async_call(
            DOMAIN,
            "start_recording",
            {"entity_id": "camera.evon_intercom_camera"},
            blocking=True,
        )

        mock_camera.async_start_recording.assert_called_once_with(duration=None)

    @pytest.mark.asyncio
    async def test_start_recording_with_duration(self, hass, mock_config_entry_v2, mock_evon_api_class):
        """Test start_recording with a duration parameter."""
        mock_config_entry_v2.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
        await hass.async_block_till_done()

        mock_camera = MagicMock()
        mock_camera.entity_id = "camera.evon_intercom_camera"
        mock_camera.async_start_recording = AsyncMock()

        hass.data[DOMAIN][mock_config_entry_v2.entry_id]["cameras"] = {
            "intercom_1.Cam": mock_camera,
        }
        hass.states.async_set("camera.evon_intercom_camera", "idle")

        await hass.services.async_call(
            DOMAIN,
            "start_recording",
            {"entity_id": "camera.evon_intercom_camera", "duration": 30},
            blocking=True,
        )

        mock_camera.async_start_recording.assert_called_once_with(duration=30)

    @pytest.mark.asyncio
    async def test_stop_recording_calls_camera(self, hass, mock_config_entry_v2, mock_evon_api_class):
        """Test that stop_recording service finds camera and calls stop."""
        mock_config_entry_v2.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
        await hass.async_block_till_done()

        mock_camera = MagicMock()
        mock_camera.entity_id = "camera.evon_intercom_camera"
        mock_camera.async_stop_recording = AsyncMock()

        hass.data[DOMAIN][mock_config_entry_v2.entry_id]["cameras"] = {
            "intercom_1.Cam": mock_camera,
        }

        await hass.services.async_call(
            DOMAIN,
            "stop_recording",
            {"entity_id": "camera.evon_intercom_camera"},
            blocking=True,
        )

        mock_camera.async_stop_recording.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_recording_missing_entity_id(self, hass, mock_config_entry_v2, mock_evon_api_class):
        """Test start_recording handles missing entity_id gracefully."""
        mock_config_entry_v2.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
        await hass.async_block_till_done()

        # Should not raise — just logs an error
        await hass.services.async_call(
            DOMAIN,
            "start_recording",
            {},
            blocking=True,
        )

    @pytest.mark.asyncio
    async def test_stop_recording_missing_entity_id(self, hass, mock_config_entry_v2, mock_evon_api_class):
        """Test stop_recording handles missing entity_id gracefully."""
        mock_config_entry_v2.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
        await hass.async_block_till_done()

        # Should not raise
        await hass.services.async_call(
            DOMAIN,
            "stop_recording",
            {},
            blocking=True,
        )

    @pytest.mark.asyncio
    async def test_start_recording_camera_not_found(self, hass, mock_config_entry_v2, mock_evon_api_class):
        """Test start_recording logs error when camera entity not in registry."""
        mock_config_entry_v2.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
        await hass.async_block_till_done()

        # Set up a state but no camera object in cameras dict
        hass.states.async_set("camera.nonexistent", "idle")

        # Should not raise
        await hass.services.async_call(
            DOMAIN,
            "start_recording",
            {"entity_id": "camera.nonexistent"},
            blocking=True,
        )
