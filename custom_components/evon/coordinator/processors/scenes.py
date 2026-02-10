"""Scene processor for Evon Smart Home coordinator."""

from __future__ import annotations

from typing import Any

from ...const import EVON_CLASS_SCENE


def process_scenes(
    instances: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Process scene instances.

    Args:
        instances: List of all device instances

    Returns:
        List of processed scene data dictionaries
    """
    scenes = []
    for instance in instances:
        if instance.get("ClassName") != EVON_CLASS_SCENE:
            continue
        if not instance.get("Name"):
            continue

        instance_id = instance.get("ID", "")
        if not instance_id:
            continue
        # Scenes don't need detailed state - just id and name
        scenes.append(
            {
                "id": instance_id,
                "name": instance.get("Name"),
            }
        )
    return scenes
