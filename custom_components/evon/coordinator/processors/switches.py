"""Switch processor for Evon Smart Home coordinator."""

from __future__ import annotations

from collections.abc import Callable
import logging
from typing import Any

_LOGGER = logging.getLogger(__name__)


def process_switches(
    instance_details: dict[str, dict[str, Any]],
    instances: list[dict[str, Any]],
    get_room_name: Callable[[str], str],
) -> list[dict[str, Any]]:
    """Process controllable switch instances.

    Args:
        instance_details: Pre-fetched instance details keyed by instance ID
        instances: List of all device instances
        get_room_name: Function to get room name from group ID

    Returns:
        List of processed switch data dictionaries
    """
    # No switch classes currently.
    # Base.bSwitch was removed as dead code — no real devices use it.
    # SmartCOM.Light.Light is the actual class for relay outputs (light platform).
    # Kept as a placeholder for future switch-type Evon classes.
    return []
