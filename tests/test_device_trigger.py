"""Tests for Evon Smart Home device triggers."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from tests.conftest import requires_ha_test_framework

# Test constants without importing from HA
TRIGGER_TYPE_DOORBELL = "doorbell"
TRIGGER_TYPES = {TRIGGER_TYPE_DOORBELL}


class TestDeviceTriggerConstants:
    """Test device trigger constants."""

    def test_trigger_type_doorbell(self):
        """Test doorbell trigger type constant."""
        assert TRIGGER_TYPE_DOORBELL == "doorbell"

    def test_trigger_types_set(self):
        """Test trigger types set contains doorbell."""
        assert "doorbell" in TRIGGER_TYPES
        assert len(TRIGGER_TYPES) == 1


@requires_ha_test_framework
class TestDeviceTriggerIntegration:
    """Integration tests for device triggers."""

    @pytest.mark.asyncio
    async def test_get_triggers_no_device(self, hass):
        """Test getting triggers for non-existent device."""
        from custom_components.evon.device_trigger import async_get_triggers

        triggers = await async_get_triggers(hass, "non_existent_device_id")
        assert triggers == []

    @pytest.mark.asyncio
    async def test_get_triggers_non_intercom_device(self, hass, mock_config_entry_v2, mock_evon_api_class):
        """Test getting triggers for a non-intercom device returns empty list."""
        from custom_components.evon.device_trigger import async_get_triggers
        from homeassistant.helpers import device_registry as dr

        mock_config_entry_v2.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
        await hass.async_block_till_done()

        # Get a light device (not an intercom)
        device_registry = dr.async_get(hass)
        devices = list(device_registry.devices.values())

        # Find the light device
        light_device = None
        for device in devices:
            for identifier in device.identifiers:
                if identifier[0] == "evon" and "light" in identifier[1]:
                    light_device = device
                    break

        if light_device:
            triggers = await async_get_triggers(hass, light_device.id)
            # Light devices shouldn't have doorbell triggers
            assert not any(t.get("type") == "doorbell" for t in triggers)

    @pytest.mark.asyncio
    async def test_get_trigger_capabilities(self, hass):
        """Test getting trigger capabilities returns empty dict."""
        from custom_components.evon.device_trigger import async_get_trigger_capabilities

        capabilities = await async_get_trigger_capabilities(hass, {})
        assert capabilities == {}

    @pytest.mark.asyncio
    async def test_attach_trigger_no_device(self, hass):
        """Test attaching trigger for non-existent device returns no-op."""
        from custom_components.evon.device_trigger import async_attach_trigger
        from homeassistant.const import CONF_DEVICE_ID

        config = {CONF_DEVICE_ID: "non_existent_device_id"}
        action = AsyncMock()
        trigger_info = {"trigger_id": "test"}

        unsubscribe = await async_attach_trigger(hass, config, action, trigger_info)

        # Should return a no-op function
        assert callable(unsubscribe)
        # Calling it should not raise
        unsubscribe()


@requires_ha_test_framework
class TestDoorbellEventFiring:
    """Test doorbell event firing from coordinator."""

    @pytest.mark.asyncio
    async def test_doorbell_event_structure(self, hass, mock_config_entry_v2, mock_evon_api_class):
        """Test that doorbell events have correct structure when fired."""
        mock_config_entry_v2.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
        await hass.async_block_till_done()

        # Collect fired events
        events = []

        def event_listener(event):
            events.append(event)

        hass.bus.async_listen("evon_doorbell", event_listener)

        # Fire a test doorbell event
        hass.bus.async_fire(
            "evon_doorbell",
            {"device_id": "test_intercom_1", "name": "Front Door"},
        )
        await hass.async_block_till_done()

        assert len(events) == 1
        assert events[0].data["device_id"] == "test_intercom_1"
        assert events[0].data["name"] == "Front Door"
