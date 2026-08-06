"""Repair flows for the Evon integration.

Home Assistant discovers repair fix flows only from the ``<domain>/repairs.py``
platform module: the repairs manager loads this module and calls
``async_create_fix_flow`` when a user clicks "Fix" on a fixable issue. The flow
previously lived in ``config_flow.py`` where HA never found it, so the "Fix"
button on the ``stale_entities_cleaned`` and ``relay_migrated_to_light`` issues
errored out.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.repairs import RepairsFlow
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.core import HomeAssistant

from .const import REPAIR_RELAY_MIGRATED, REPAIR_STALE_ENTITIES_CLEANED


class EvonStaleEntitiesRepairFlow(RepairsFlow):
    """Handler for stale entities repair flow."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle the initial step."""
        return await self.async_step_confirm()

    async def async_step_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle the confirm step."""
        if user_input is not None:
            return self.async_create_entry(data={})

        return self.async_show_form(step_id="confirm")


async def async_create_fix_flow(hass: HomeAssistant, issue_id: str, data: dict[str, Any] | None) -> RepairsFlow:
    """Create a repair flow for the given issue."""
    if issue_id.startswith(REPAIR_STALE_ENTITIES_CLEANED) or issue_id.startswith(REPAIR_RELAY_MIGRATED):
        return EvonStaleEntitiesRepairFlow()
    raise ValueError(f"Unknown issue: {issue_id}")
