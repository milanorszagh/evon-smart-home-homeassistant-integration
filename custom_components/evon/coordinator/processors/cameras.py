"""Camera processor for Evon Smart Home coordinator."""

from __future__ import annotations

from collections.abc import Callable
import logging
from typing import Any

from ...const import EVON_CLASS_INTERCOM_2N_CAM

_LOGGER = logging.getLogger(__name__)


def process_cameras(
    instance_details: dict[str, dict[str, Any]],
    instances: list[dict[str, Any]],
    get_room_name: Callable[[str], str],
) -> list[dict[str, Any]]:
    """Process camera instances.

    Args:
        instance_details: Pre-fetched instance details keyed by instance ID
        instances: List of all device instances
        get_room_name: Function to get room name from group ID

    Returns:
        List of processed camera data dictionaries
    """
    cameras = []
    for instance in instances:
        if instance.get("ClassName") != EVON_CLASS_INTERCOM_2N_CAM:
            continue
        if not instance.get("Name"):
            continue

        instance_id = instance.get("ID", "")
        details = instance_details.get(instance_id)
        if details is None:
            _LOGGER.warning("No details available for camera %s", instance_id)
            continue

        cameras.append(
            {
                "id": instance_id,
                "name": instance.get("Name"),
                "room_name": get_room_name(instance.get("Group", "")),
                "image_path": details.get("Image", ""),
                "image_request": details.get("ImageRequest", False),
                "ip_address": details.get("IPAddress", ""),
                "error": details.get("Error", False),
                # Note: Username/Password for direct camera access intentionally
                # excluded from coordinator data to avoid exposure in diagnostics
            }
        )
    return cameras
