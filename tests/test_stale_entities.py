"""Tests for _async_cleanup_stale_entities in __init__.py."""

from __future__ import annotations

import pytest

from tests.conftest import requires_ha_test_framework


@requires_ha_test_framework
class TestStaleEntityCleanup:
    """Integration tests for stale entity cleanup."""

    @pytest.mark.asyncio
    async def test_stale_entity_removed(self, hass, mock_config_entry_v2, mock_evon_api_class):
        """Test that entities not in API response are removed from the registry."""
        mock_config_entry_v2.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
        await hass.async_block_till_done()

        # Manually add a stale entity to the entity registry that does NOT exist
        # in the coordinator data (simulating a device that was removed from Evon)
        from homeassistant.helpers import entity_registry as er

        ent_reg = er.async_get(hass)
        stale_entry = ent_reg.async_get_or_create(
            domain="light",
            platform="evon",
            unique_id="evon_light_STALE.Device1",
            config_entry=mock_config_entry_v2,
        )

        # Verify it was created
        assert ent_reg.async_get(stale_entry.entity_id) is not None

        # Re-run stale cleanup
        from custom_components.evon import _async_cleanup_stale_entities

        coordinator = hass.data["evon"][mock_config_entry_v2.entry_id]["coordinator"]
        await _async_cleanup_stale_entities(hass, mock_config_entry_v2, coordinator)

        # The stale entity should be removed
        assert ent_reg.async_get(stale_entry.entity_id) is None

    @pytest.mark.asyncio
    async def test_valid_entities_preserved(self, hass, mock_config_entry_v2, mock_evon_api_class):
        """Test that entities present in API response are NOT removed."""
        mock_config_entry_v2.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
        await hass.async_block_till_done()

        from homeassistant.helpers import entity_registry as er

        ent_reg = er.async_get(hass)

        # Count entities belonging to this config entry before cleanup
        entities_before = er.async_entries_for_config_entry(ent_reg, mock_config_entry_v2.entry_id)
        count_before = len(entities_before)

        # Run cleanup again — should not remove any valid entities
        from custom_components.evon import _async_cleanup_stale_entities

        coordinator = hass.data["evon"][mock_config_entry_v2.entry_id]["coordinator"]
        await _async_cleanup_stale_entities(hass, mock_config_entry_v2, coordinator)

        entities_after = er.async_entries_for_config_entry(ent_reg, mock_config_entry_v2.entry_id)
        assert len(entities_after) == count_before

    @pytest.mark.asyncio
    async def test_empty_coordinator_data_skips_cleanup(self, hass, mock_config_entry_v2, mock_evon_api_class):
        """Test that cleanup is skipped when coordinator data is empty."""
        mock_config_entry_v2.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
        await hass.async_block_till_done()

        from homeassistant.helpers import entity_registry as er

        ent_reg = er.async_get(hass)

        # Add a stale entity
        stale_entry = ent_reg.async_get_or_create(
            domain="light",
            platform="evon",
            unique_id="evon_light_STALE.Device2",
            config_entry=mock_config_entry_v2,
        )

        # Run cleanup with empty coordinator data — should NOT remove anything
        from custom_components.evon import _async_cleanup_stale_entities

        coordinator = hass.data["evon"][mock_config_entry_v2.entry_id]["coordinator"]
        original_data = coordinator.data
        coordinator.data = {}
        await _async_cleanup_stale_entities(hass, mock_config_entry_v2, coordinator)

        # The stale entity should still exist because cleanup was skipped
        assert ent_reg.async_get(stale_entry.entity_id) is not None

        # Restore
        coordinator.data = original_data

    @pytest.mark.asyncio
    async def test_none_coordinator_data_skips_cleanup(self, hass, mock_config_entry_v2, mock_evon_api_class):
        """Test that cleanup is skipped when coordinator data is None."""
        mock_config_entry_v2.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
        await hass.async_block_till_done()

        from homeassistant.helpers import entity_registry as er

        ent_reg = er.async_get(hass)

        stale_entry = ent_reg.async_get_or_create(
            domain="light",
            platform="evon",
            unique_id="evon_light_STALE.Device3",
            config_entry=mock_config_entry_v2,
        )

        from custom_components.evon import _async_cleanup_stale_entities

        coordinator = hass.data["evon"][mock_config_entry_v2.entry_id]["coordinator"]
        original_data = coordinator.data
        coordinator.data = None
        await _async_cleanup_stale_entities(hass, mock_config_entry_v2, coordinator)

        # Should still exist
        assert ent_reg.async_get(stale_entry.entity_id) is not None

        coordinator.data = original_data

    @pytest.mark.asyncio
    async def test_special_entities_not_removed(self, hass, mock_config_entry_v2, mock_evon_api_class):
        """Test that special entities (home_state, season_mode, websocket) are never removed."""
        mock_config_entry_v2.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry_v2.entry_id)
        await hass.async_block_till_done()

        from homeassistant.helpers import entity_registry as er

        ent_reg = er.async_get(hass)
        entry_id = mock_config_entry_v2.entry_id

        # Create special entities that should never be cleaned up
        special_entry = ent_reg.async_get_or_create(
            domain="select",
            platform="evon",
            unique_id=f"evon_home_state_{entry_id}",
            config_entry=mock_config_entry_v2,
        )

        from custom_components.evon import _async_cleanup_stale_entities

        coordinator = hass.data["evon"][entry_id]["coordinator"]
        await _async_cleanup_stale_entities(hass, mock_config_entry_v2, coordinator)

        # Special entity should be preserved
        assert ent_reg.async_get(special_entry.entity_id) is not None
