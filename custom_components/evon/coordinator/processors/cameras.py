"""Camera processor for Evon Smart Home coordinator."""

from __future__ import annotations

from collections.abc import Callable
import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ...api import EvonApi

from ...api import EvonApiError
from ...const import EVON_CLASS_INTERCOM_2N_CAM

_LOGGER = logging.getLogger(__name__)


async def process_cameras(
    api: EvonApi,
    instances: list[dict[str, Any]],
    get_room_name: Callable[[str], str],
) -> list[dict[str, Any]]:
    """Process camera instances.

    Args:
        api: The Evon API client
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
        try:
            details = await api.get_instance(instance_id)
            cameras.append(
                {
                    "id": instance_id,
                    "name": instance.get("Name"),
                    "room_name": get_room_name(instance.get("Group", "")),
                    "image_path": details.get("Image", ""),
                    "image_request": details.get("ImageRequest", False),
                    "ip_address": details.get("IPAddress", ""),
                    "jpeg_url": details.get("JPEGUrl", ""),
                    "username": details.get("Username", ""),
                    "password": details.get("Password", ""),
                    "error": details.get("Error", False),
                    "http_preview_url": details.get("HTTPPreviewUrl", ""),
                }
            )
        except EvonApiError:
            _LOGGER.warning("Failed to get details for camera %s", instance_id)
    return cameras
