"""Security door processor for Evon Smart Home coordinator."""

from __future__ import annotations

from collections.abc import Callable
import logging
from typing import Any

from ...const import EVON_CLASS_SECURITY_DOOR

_LOGGER = logging.getLogger(__name__)


def _transform_saved_pictures(saved_pictures_raw: Any) -> list[dict[str, str]]:
    """Transform raw SavedPictures data to normalized format.

    Args:
        saved_pictures_raw: Raw SavedPictures list from Evon API/WebSocket.

    Returns:
        List of dicts with 'timestamp' and 'path' keys.
    """
    pictures: list[dict[str, str]] = []
    if not isinstance(saved_pictures_raw, list):
        return pictures
    for pic in saved_pictures_raw:
        if isinstance(pic, dict):
            timestamp = pic.get("datetime")
            if timestamp is None:
                continue
            pictures.append(
                {
                    "timestamp": timestamp,
                    "path": pic.get("imageUrlClient", ""),
                }
            )
    return pictures


def process_security_doors(
    instance_details: dict[str, dict[str, Any]],
    instances: list[dict[str, Any]],
    get_room_name: Callable[[str], str],
) -> list[dict[str, Any]]:
    """Process security door instances.

    Args:
        instance_details: Pre-fetched instance details keyed by instance ID
        instances: List of all device instances
        get_room_name: Function to get room name from group ID

    Returns:
        List of processed security door data dictionaries
    """
    security_doors = []
    for instance in instances:
        if instance.get("ClassName") != EVON_CLASS_SECURITY_DOOR:
            continue
        if not instance.get("Name"):
            continue

        instance_id = instance.get("ID", "")
        details = instance_details.get(instance_id)
        if details is None:
            _LOGGER.warning("No details available for security door %s", instance_id)
            continue

        # Parse saved pictures - convert timestamps to ISO format
        saved_pictures_raw = details.get("SavedPictures", [])
        saved_pictures = _transform_saved_pictures(saved_pictures_raw)
        security_doors.append(
            {
                "id": instance_id,
                "name": instance.get("Name"),
                "room_name": get_room_name(instance.get("Group", "")),
                "is_open": details.get("IsOpen", False) or details.get("DoorIsOpen", False),
                "call_in_progress": details.get("CallInProgress", False),
                "cam_instance_name": details.get("CamInstanceName", ""),
                "saved_pictures": saved_pictures,
            }
        )
    return security_doors
