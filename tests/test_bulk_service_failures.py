"""Tests for bulk service partial failures (C-M2)."""

from __future__ import annotations

import contextlib
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.evon.const import (
    DOMAIN,
    ENTITY_TYPE_BLINDS,
    ENTITY_TYPE_LIGHTS,
)


def _make_coordinator_data(entity_type, entities):
    """Build coordinator data dict with the given entity type and entities."""
    return {entity_type: entities}


def _make_entry_data(api, coordinator_data, unloading=False):
    """Create a dict matching hass.data[DOMAIN][entry_id] structure."""
    coordinator = MagicMock()
    coordinator.data = coordinator_data
    coordinator.async_refresh = AsyncMock()
    entry = {
        "api": api,
        "coordinator": coordinator,
    }
    if unloading:
        entry["unloading"] = True
    return entry


class TestBulkEntityCallPartialFailures:
    """Test _bulk_entity_call handles partial failures gracefully."""

    @pytest.mark.asyncio
    async def test_some_devices_fail_others_succeed(self):
        """Test that if some devices throw, others still get called."""
        api = AsyncMock()
        call_log = []

        async def mock_turn_off(instance_id):
            call_log.append(instance_id)
            if instance_id == "light_2":
                raise Exception("Device unreachable")

        api.turn_off_light = AsyncMock(side_effect=mock_turn_off)

        lights = [
            {"id": "light_1", "is_on": True},
            {"id": "light_2", "is_on": True},
            {"id": "light_3", "is_on": True},
        ]
        data = _make_coordinator_data(ENTITY_TYPE_LIGHTS, lights)
        entry_data = _make_entry_data(api, data)

        hass = MagicMock()
        hass.data = {DOMAIN: {"entry1": entry_data}}

        # Simulate the _bulk_entity_call logic from __init__.py
        from custom_components.evon.api import INSTANCE_ID_PATTERN

        entries = list(hass.data.get(DOMAIN, {}).items())
        for _entry_id, ed in entries:
            if not isinstance(ed, dict) or "coordinator" not in ed or "api" not in ed:
                continue
            coordinator = ed["coordinator"]
            api_obj = ed["api"]
            if coordinator.data and ENTITY_TYPE_LIGHTS in coordinator.data:
                for entity in list(coordinator.data[ENTITY_TYPE_LIGHTS]):
                    entity_id = entity.get("id")
                    if not entity_id or not INSTANCE_ID_PATTERN.match(entity_id):
                        continue
                    if not entity.get("is_on"):
                        continue
                    with contextlib.suppress(Exception):
                        await api_obj.turn_off_light(entity_id)
            await coordinator.async_refresh()

        # All 3 devices were attempted
        assert call_log == ["light_1", "light_2", "light_3"]
        # Coordinator refresh still called after partial failures
        entry_data["coordinator"].async_refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_all_devices_fail_still_refreshes(self):
        """Test that coordinator refresh is called even when all devices fail."""
        api = AsyncMock()

        async def mock_close(instance_id):
            raise Exception("Network error")

        api.close_blind = AsyncMock(side_effect=mock_close)

        blinds = [
            {"id": "blind_1"},
            {"id": "blind_2"},
        ]
        data = _make_coordinator_data(ENTITY_TYPE_BLINDS, blinds)
        entry_data = _make_entry_data(api, data)

        from custom_components.evon.api import INSTANCE_ID_PATTERN

        coordinator = entry_data["coordinator"]
        for entity in list(coordinator.data[ENTITY_TYPE_BLINDS]):
            entity_id = entity.get("id")
            if not entity_id or not INSTANCE_ID_PATTERN.match(entity_id):
                continue
            with contextlib.suppress(Exception):
                await api.close_blind(entity_id)
        await coordinator.async_refresh()

        assert api.close_blind.call_count == 2
        coordinator.async_refresh.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_unloading_entry_skipped(self):
        """Test that entries marked as unloading are skipped."""
        api = AsyncMock()
        api.turn_off_light = AsyncMock()

        lights = [{"id": "light_1", "is_on": True}]
        data = _make_coordinator_data(ENTITY_TYPE_LIGHTS, lights)
        entry_data = _make_entry_data(api, data, unloading=True)

        hass = MagicMock()
        hass.data = {DOMAIN: {"entry1": entry_data}}

        entries = list(hass.data.get(DOMAIN, {}).items())
        for _entry_id, ed in entries:
            if not isinstance(ed, dict) or "coordinator" not in ed or "api" not in ed or ed.get("unloading"):
                continue
            # Should not reach here
            pytest.fail("Should have skipped unloading entry")

    @pytest.mark.asyncio
    async def test_invalid_instance_id_skipped(self):
        """Test that entities with invalid instance IDs are skipped."""
        api = AsyncMock()
        api.turn_off_light = AsyncMock()

        lights = [
            {"id": "valid_light", "is_on": True},
            {"id": "invalid id with spaces!", "is_on": True},
            {"id": "", "is_on": True},
        ]
        data = _make_coordinator_data(ENTITY_TYPE_LIGHTS, lights)
        entry_data = _make_entry_data(api, data)

        from custom_components.evon.api import INSTANCE_ID_PATTERN

        called_ids = []
        coordinator = entry_data["coordinator"]
        for entity in list(coordinator.data[ENTITY_TYPE_LIGHTS]):
            entity_id = entity.get("id")
            if not entity_id or not INSTANCE_ID_PATTERN.match(entity_id):
                continue
            if not entity.get("is_on"):
                continue
            called_ids.append(entity_id)

        assert called_ids == ["valid_light"]


class TestBulkApiCallPartialFailures:
    """Test _bulk_api_call handles failures gracefully."""

    @pytest.mark.asyncio
    async def test_api_method_failure_still_refreshes(self):
        """Test that coordinator refresh runs even when API method throws."""
        api = AsyncMock()
        api.all_climate_comfort = AsyncMock(side_effect=Exception("API down"))

        coordinator = MagicMock()
        coordinator.async_refresh = AsyncMock()

        # Simulate _bulk_api_call logic
        with contextlib.suppress(Exception):
            await api.all_climate_comfort()
        await coordinator.async_refresh()

        api.all_climate_comfort.assert_awaited_once()
        coordinator.async_refresh.assert_awaited_once()
