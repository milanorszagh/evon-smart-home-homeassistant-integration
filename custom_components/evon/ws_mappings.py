"""WebSocket property mappings for Evon Smart Home."""

from __future__ import annotations

import contextlib
from typing import Any

from .const import (
    EVON_CLASS_AIR_QUALITY,
    EVON_CLASS_BATHROOM_RADIATOR,
    EVON_CLASS_BLIND,
    EVON_CLASS_BLIND_GROUP,
    EVON_CLASS_CLIMATE,
    EVON_CLASS_CLIMATE_UNIVERSAL,
    EVON_CLASS_HOME_STATE,
    EVON_CLASS_INTERCOM_2N,
    EVON_CLASS_LIGHT,
    EVON_CLASS_LIGHT_DIM,
    EVON_CLASS_LIGHT_GROUP,
    EVON_CLASS_SECURITY_DOOR,
    EVON_CLASS_SMART_METER,
    EVON_CLASS_SWITCH,
    EVON_CLASS_VALVE,
)

# Map Evon class names to entity types (coordinator data keys)
CLASS_TO_TYPE: dict[str, str] = {
    EVON_CLASS_LIGHT: "lights",
    EVON_CLASS_LIGHT_DIM: "lights",
    EVON_CLASS_LIGHT_GROUP: "lights",
    "Base.bLight": "lights",
    "SmartCOM.Light.DynamicRGBWLight": "lights",
    EVON_CLASS_BLIND: "blinds",
    EVON_CLASS_BLIND_GROUP: "blinds",
    "Base.bBlind": "blinds",
    "Base.ehBlind": "blinds",
    EVON_CLASS_CLIMATE: "climates",
    EVON_CLASS_CLIMATE_UNIVERSAL: "climates",
    EVON_CLASS_SWITCH: "switches",
    "Base.bSwitch": "switches",
    EVON_CLASS_HOME_STATE: "home_states",
    EVON_CLASS_BATHROOM_RADIATOR: "bathroom_radiators",
    EVON_CLASS_SMART_METER: "smart_meters",
    EVON_CLASS_AIR_QUALITY: "air_quality",
    EVON_CLASS_VALVE: "valves",
    EVON_CLASS_SECURITY_DOOR: "security_doors",
    EVON_CLASS_INTERCOM_2N: "intercoms",
}

# Properties to subscribe for each entity type
# These are the WebSocket property names
SUBSCRIBE_PROPERTIES: dict[str, list[str]] = {
    "lights": ["IsOn", "ScaledBrightness", "ColorTemp", "MinColorTemperature", "MaxColorTemperature"],
    "blinds": ["Position", "Angle"],
    "climates": ["SetTemperature", "ActualTemperature", "ModeSaved", "IsOn", "Mode", "Humidity"],
    "switches": ["IsOn", "State"],
    "home_states": ["Active"],
    "bathroom_radiators": ["Output", "NextSwitchPoint"],
    # SmartMeter: real-time measurements (P1+P2+P3 computed to power)
    "smart_meters": [
        "IL1",
        "IL2",
        "IL3",  # Current per phase
        "UL1N",
        "UL2N",
        "UL3N",  # Voltage per phase
        "Frequency",  # Grid frequency
        "P1",
        "P2",
        "P3",  # Active power per phase (sum = total power)
    ],
    # Air Quality: humidity and temperature sensors
    "air_quality": ["Humidity", "ActualTemperature", "CO2Value"],
    # Valves: open/closed state
    "valves": ["ActValue"],
    # Security doors: door state and call in progress
    "security_doors": ["IsOpen", "DoorIsOpen", "CallInProgress"],
    # Intercoms: doorbell, door open, connection status
    "intercoms": ["DoorBellTriggered", "DoorOpenTriggered", "IsDoorOpen", "ConnectionToIntercomHasBeenLost"],
}

# Map WebSocket property names to coordinator data keys
PROPERTY_MAPPINGS: dict[str, dict[str, str]] = {
    "lights": {
        "IsOn": "is_on",
        "ScaledBrightness": "brightness",  # 0-100 scale
        "ColorTemp": "color_temp",  # Kelvin
        "MinColorTemperature": "min_color_temp",  # Kelvin
        "MaxColorTemperature": "max_color_temp",  # Kelvin
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
        "Humidity": "humidity",
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
        "NextSwitchPoint": "time_remaining",
    },
    "smart_meters": {
        "IL1": "current_l1",
        "IL2": "current_l2",
        "IL3": "current_l3",
        "UL1N": "voltage_l1",
        "UL2N": "voltage_l2",
        "UL3N": "voltage_l3",
        "Frequency": "frequency",
        "P1": "power_l1",  # Active power phase 1
        "P2": "power_l2",  # Active power phase 2
        "P3": "power_l3",  # Active power phase 3
    },
    "air_quality": {
        "Humidity": "humidity",
        "ActualTemperature": "temperature",
        "CO2Value": "co2",
    },
    "valves": {
        "ActValue": "is_open",
    },
    "security_doors": {
        "IsOpen": "is_open",
        "DoorIsOpen": "door_is_open",
        "CallInProgress": "call_in_progress",
    },
    "intercoms": {
        "DoorBellTriggered": "doorbell_triggered",
        "DoorOpenTriggered": "door_open_triggered",
        "IsDoorOpen": "is_door_open",
        "ConnectionToIntercomHasBeenLost": "connection_lost",
    },
}


def get_entity_type(class_name: str) -> str | None:
    """Get the entity type for a given Evon class name.

    Args:
        class_name: The Evon class name.

    Returns:
        The entity type (e.g., "lights", "blinds") or None if unknown.
    """
    # Try exact match first
    if class_name in CLASS_TO_TYPE:
        return CLASS_TO_TYPE[class_name]

    # SmartMeter has variations (Energy.SmartMeter, Energy.SmartMeterModbus, etc.)
    # Use substring match to handle all variants
    if EVON_CLASS_SMART_METER in class_name:
        return "smart_meters"

    # ClimateControlUniversal may have prefix (e.g., SmartCOM.Clima.ClimateControlUniversal)
    if EVON_CLASS_CLIMATE_UNIVERSAL in class_name:
        return "climates"

    return None


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
    existing_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Convert WebSocket property values to coordinator data format.

    Args:
        entity_type: The entity type (e.g., "lights").
        ws_properties: Dictionary of WebSocket property names to values.
        existing_data: Optional existing entity data for computing derived values.

    Returns:
        Dictionary of coordinator data keys to values.
    """
    mappings = PROPERTY_MAPPINGS.get(entity_type, {})
    result: dict[str, Any] = {}

    for ws_prop, value in ws_properties.items():
        if ws_prop in mappings:
            coord_key = mappings[ws_prop]
            result[coord_key] = value

    # Special handling for smart meters: compute total power from P1+P2+P3
    if entity_type == "smart_meters":
        # Get per-phase power values (from this update or existing data)
        p1 = ws_properties.get("P1")
        p2 = ws_properties.get("P2")
        p3 = ws_properties.get("P3")

        # If we have existing data, use it to fill in missing phases
        if existing_data:
            if p1 is None:
                p1 = existing_data.get("power_l1")
            if p2 is None:
                p2 = existing_data.get("power_l2")
            if p3 is None:
                p3 = existing_data.get("power_l3")

        # Compute total power if we have all phases
        if p1 is not None and p2 is not None and p3 is not None:
            with contextlib.suppress(TypeError, ValueError):
                result["power"] = float(p1) + float(p2) + float(p3)

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

        subscriptions.append(
            {
                "Instanceid": instance_id,
                "Properties": properties,
            }
        )

    return subscriptions
