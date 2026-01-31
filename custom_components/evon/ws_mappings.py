"""WebSocket property mappings for Evon Smart Home."""

from __future__ import annotations

from typing import Any

from .const import (
    EVON_CLASS_BATHROOM_RADIATOR,
    EVON_CLASS_BLIND,
    EVON_CLASS_CLIMATE,
    EVON_CLASS_CLIMATE_UNIVERSAL,
    EVON_CLASS_HOME_STATE,
    EVON_CLASS_LIGHT,
    EVON_CLASS_LIGHT_DIM,
    EVON_CLASS_SWITCH,
)

# Map Evon class names to entity types (coordinator data keys)
CLASS_TO_TYPE: dict[str, str] = {
    EVON_CLASS_LIGHT: "lights",
    EVON_CLASS_LIGHT_DIM: "lights",
    "Base.bLight": "lights",
    "SmartCOM.Light.DynamicRGBWLight": "lights",
    EVON_CLASS_BLIND: "blinds",
    "Base.bBlind": "blinds",
    "Base.ehBlind": "blinds",
    EVON_CLASS_CLIMATE: "climates",
    EVON_CLASS_CLIMATE_UNIVERSAL: "climates",
    EVON_CLASS_SWITCH: "switches",
    "Base.bSwitch": "switches",
    EVON_CLASS_HOME_STATE: "home_states",
    EVON_CLASS_BATHROOM_RADIATOR: "bathroom_radiators",
}

# Properties to subscribe for each entity type
# These are the WebSocket property names
SUBSCRIBE_PROPERTIES: dict[str, list[str]] = {
    "lights": ["IsOn", "ScaledBrightness"],  # Only ScaledBrightness (0-100), not raw Brightness
    "blinds": ["Position", "Angle"],
    "climates": ["SetTemperature", "ActualTemperature", "ModeSaved", "IsOn", "Mode"],
    "switches": ["IsOn", "State"],
    "home_states": ["Active"],
    "bathroom_radiators": ["Output", "NextSwitchPoint"],
}

# Map WebSocket property names to coordinator data keys
PROPERTY_MAPPINGS: dict[str, dict[str, str]] = {
    "lights": {
        "IsOn": "is_on",
        "ScaledBrightness": "brightness",  # 0-100 scale
    },
    "blinds": {
        "Position": "position",
        "Angle": "angle",
    },
    "climates": {
        "SetTemperature": "target_temp",
        "ActualTemperature": "current_temp",
        "ModeSaved": "mode_saved",
        "IsOn": "is_on",
        "Mode": "mode",
    },
    "switches": {
        "IsOn": "is_on",
        "State": "is_on",  # Some switches use State instead
    },
    "home_states": {
        "Active": "active",
    },
    "bathroom_radiators": {
        "Output": "is_on",
        "NextSwitchPoint": "next_switch_point",
    },
}


def get_entity_type(class_name: str) -> str | None:
    """Get the entity type for a given Evon class name.

    Args:
        class_name: The Evon class name.

    Returns:
        The entity type (e.g., "lights", "blinds") or None if unknown.
    """
    return CLASS_TO_TYPE.get(class_name)


def get_subscribe_properties(entity_type: str) -> list[str]:
    """Get the WebSocket properties to subscribe for an entity type.

    Args:
        entity_type: The entity type (e.g., "lights").

    Returns:
        List of property names to subscribe to.
    """
    return SUBSCRIBE_PROPERTIES.get(entity_type, [])


def ws_to_coordinator_data(
    entity_type: str,
    ws_properties: dict[str, Any],
) -> dict[str, Any]:
    """Convert WebSocket property values to coordinator data format.

    Args:
        entity_type: The entity type (e.g., "lights").
        ws_properties: Dictionary of WebSocket property names to values.

    Returns:
        Dictionary of coordinator data keys to values.
    """
    mappings = PROPERTY_MAPPINGS.get(entity_type, {})
    result: dict[str, Any] = {}

    for ws_prop, value in ws_properties.items():
        if ws_prop in mappings:
            coord_key = mappings[ws_prop]
            result[coord_key] = value

    return result


def build_subscription_list(
    instances: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Build a list of WebSocket subscriptions from coordinator instances.

    Args:
        instances: List of instance dictionaries with ID and ClassName.

    Returns:
        List of subscription dicts for subscribe_instances().
    """
    subscriptions: list[dict[str, Any]] = []

    for instance in instances:
        class_name = instance.get("ClassName", "")
        instance_id = instance.get("ID", "")

        if not instance_id or not class_name:
            continue

        entity_type = get_entity_type(class_name)
        if not entity_type:
            continue

        properties = get_subscribe_properties(entity_type)
        if not properties:
            continue

        subscriptions.append({
            "Instanceid": instance_id,
            "Properties": properties,
        })

    return subscriptions
