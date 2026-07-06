"""Tests for the Evon repair fix flows.

These pin the fact that the fix flow is reachable from repairs.py (HA discovers
fix flows only from <domain>/repairs.py) and maps the two fixable issue ids to
the confirm flow.
"""

from __future__ import annotations

import pytest

from custom_components.evon.const import (
    REPAIR_RELAY_MIGRATED,
    REPAIR_STALE_ENTITIES_CLEANED,
)
from custom_components.evon.repairs import (
    EvonStaleEntitiesRepairFlow,
    async_create_fix_flow,
)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "issue_id",
    [
        REPAIR_STALE_ENTITIES_CLEANED,
        REPAIR_RELAY_MIGRATED,
        f"{REPAIR_STALE_ENTITIES_CLEANED}_abc123",
        f"{REPAIR_RELAY_MIGRATED}_switch.foo",
    ],
)
async def test_create_fix_flow_returns_confirm_flow(issue_id):
    """Both fixable issue ids (and their per-entry suffixed forms) resolve to the flow."""
    flow = await async_create_fix_flow(None, issue_id, None)
    assert isinstance(flow, EvonStaleEntitiesRepairFlow)


@pytest.mark.asyncio
async def test_create_fix_flow_unknown_issue_raises():
    """An unknown issue id raises rather than returning a bogus flow."""
    with pytest.raises(ValueError, match="Unknown issue"):
        await async_create_fix_flow(None, "some_other_issue", None)
