"""Home state processor for Evon Smart Home coordinator."""

from __future__ import annotations

import logging
from typing import Any

from ...const import EVON_CLASS_HOME_STATE

_LOGGER = logging.getLogger(__name__)


def process_home_states(
    instance_details: dict[str, dict[str, Any]],
    instances: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Process home state instances.

    Args:
        instance_details: Pre-fetched instance details keyed by instance ID
        instances: List of all device instances

    Returns:
        List of processed home state data dictionaries
    """
    home_states = []
    for instance in instances:
        if instance.get("ClassName") != EVON_CLASS_HOME_STATE:
            continue
        # Skip empty IDs and template instances (ID starting with "System.")
        instance_id = instance.get("ID", "")
        if not instance_id or instance_id.startswith("System."):
            continue
        if not instance.get("Name"):
            continue

        details = instance_details.get(instance_id)
        if details is None:
            _LOGGER.warning("No details available for home state %s", instance_id)
            continue

        home_states.append(
            {
                "id": instance_id,
                "name": instance.get("Name"),
                "active": details.get("Active", False),
            }
        )
    return home_states
