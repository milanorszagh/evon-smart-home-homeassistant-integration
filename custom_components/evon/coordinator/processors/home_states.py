"""Home state processor for Evon Smart Home coordinator."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ...api import EvonApi

from ...api import EvonApiError
from ...const import EVON_CLASS_HOME_STATE

_LOGGER = logging.getLogger(__name__)


async def process_home_states(
    api: EvonApi,
    instances: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Process home state instances.

    Args:
        api: The Evon API client
        instances: List of all device instances

    Returns:
        List of processed home state data dictionaries
    """
    home_states = []
    for instance in instances:
        if instance.get("ClassName") != EVON_CLASS_HOME_STATE:
            continue
        # Skip template instances (ID starting with "System.")
        instance_id = instance.get("ID", "")
        if instance_id.startswith("System."):
            continue
        if not instance.get("Name"):
            continue

        try:
            details = await api.get_instance(instance_id)
            home_states.append(
                {
                    "id": instance_id,
                    "name": instance.get("Name"),
                    "active": details.get("Active", False),
                }
            )
        except EvonApiError:
            _LOGGER.warning("Failed to get details for home state %s", instance_id)
    return home_states
