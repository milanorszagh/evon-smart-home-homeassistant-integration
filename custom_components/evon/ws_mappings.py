"""WebSocket property mappings for Evon Smart Home."""

from __future__ import annotations

import logging
from typing import Any

from .const import (
    ENTITY_TYPE_AIR_QUALITY,
    ENTITY_TYPE_BATHROOM_RADIATORS,
    ENTITY_TYPE_BLINDS,
    ENTITY_TYPE_BUTTON_EVENTS,
    ENTITY_TYPE_CAMERAS,
    ENTITY_TYPE_CLIMATES,
    ENTITY_TYPE_HOME_STATES,
    ENTITY_TYPE_INTERCOMS,
    ENTITY_TYPE_LIGHTS,
    ENTITY_TYPE_SECURITY_DOORS,
    ENTITY_TYPE_SMART_METERS,
    ENTITY_TYPE_SWITCHES,
    ENTITY_TYPE_VALVES,
    EVON_CLASS_AIR_QUALITY,
    EVON_CLASS_BATHROOM_RADIATOR,
    EVON_CLASS_BLIND,
    EVON_CLASS_BLIND_GROUP,
    EVON_CLASS_CLIMATE,
    EVON_CLASS_CLIMATE_UNIVERSAL,
    EVON_CLASS_HOME_STATE,
    EVON_CLASS_INTERCOM_2N,
    EVON_CLASS_INTERCOM_2N_CAM,
    EVON_CLASS_LIGHT,
    EVON_CLASS_LIGHT_DIM,
    EVON_CLASS_LIGHT_GROUP,
    EVON_CLASS_LIGHT_RGBW,
    EVON_CLASS_PHYSICAL_BUTTON,
    EVON_CLASS_SECURITY_DOOR,
    EVON_CLASS_SMART_METER,
    EVON_CLASS_VALVE,
)

_LOGGER = logging.getLogger(__name__)

# Map Evon class names to entity types (coordinator data keys)
CLASS_TO_TYPE: dict[str, str] = {
    EVON_CLASS_LIGHT: ENTITY_TYPE_LIGHTS,
    EVON_CLASS_LIGHT_DIM: ENTITY_TYPE_LIGHTS,
    EVON_CLASS_LIGHT_GROUP: ENTITY_TYPE_LIGHTS,
    "Base.bLight": ENTITY_TYPE_LIGHTS,
    EVON_CLASS_LIGHT_RGBW: ENTITY_TYPE_LIGHTS,
    EVON_CLASS_BLIND: ENTITY_TYPE_BLINDS,
    EVON_CLASS_BLIND_GROUP: ENTITY_TYPE_BLINDS,
    "Base.bBlind": ENTITY_TYPE_BLINDS,
    "Base.ehBlind": ENTITY_TYPE_BLINDS,
    EVON_CLASS_CLIMATE: ENTITY_TYPE_CLIMATES,
    EVON_CLASS_CLIMATE_UNIVERSAL: ENTITY_TYPE_CLIMATES,
    EVON_CLASS_PHYSICAL_BUTTON: ENTITY_TYPE_BUTTON_EVENTS,
    EVON_CLASS_HOME_STATE: ENTITY_TYPE_HOME_STATES,
    EVON_CLASS_BATHROOM_RADIATOR: ENTITY_TYPE_BATHROOM_RADIATORS,
    EVON_CLASS_SMART_METER: ENTITY_TYPE_SMART_METERS,
    EVON_CLASS_AIR_QUALITY: ENTITY_TYPE_AIR_QUALITY,
    EVON_CLASS_VALVE: ENTITY_TYPE_VALVES,
    EVON_CLASS_SECURITY_DOOR: ENTITY_TYPE_SECURITY_DOORS,
    EVON_CLASS_INTERCOM_2N: ENTITY_TYPE_INTERCOMS,
    EVON_CLASS_INTERCOM_2N_CAM: ENTITY_TYPE_CAMERAS,
}

# Properties to subscribe for each entity type
# These are the WebSocket property names
SUBSCRIBE_PROPERTIES: dict[str, list[str]] = {
    ENTITY_TYPE_LIGHTS: ["IsOn", "ScaledBrightness", "ColorTemp", "MinColorTemperature", "MaxColorTemperature"],
    ENTITY_TYPE_BLINDS: ["Position", "Angle"],
    # Climate: Subscribe to BOTH ModeSaved AND MainState because different thermostat types use different properties:
    # - SmartCOM.Clima.ClimateControl uses MainState (only MainState exists)
    # - Heating.ClimateControlUniversal uses ModeSaved (only ModeSaved exists)
    ENTITY_TYPE_CLIMATES: [
        "SetTemperature",
        "ActualTemperature",
        "ModeSaved",
        "MainState",
        "IsOn",
        "Mode",
        "Humidity",
        "CoolingMode",
        "DisableCooling",
        # Heating setpoints and limits
        "SetValueComfortHeating",
        "SetValueEnergySavingHeating",
        "SetValueFreezeProtection",
        "MinSetValueHeat",
        "MaxSetValueHeat",
        # Cooling setpoints and limits
        "SetValueComfortCooling",
        "SetValueEnergySavingCooling",
        "SetValueHeatProtection",
        "MinSetValueCool",
        "MaxSetValueCool",
    ],
    ENTITY_TYPE_SWITCHES: ["IsOn", "State"],
    ENTITY_TYPE_BUTTON_EVENTS: ["IsOn"],
    ENTITY_TYPE_HOME_STATES: ["Active"],
    ENTITY_TYPE_BATHROOM_RADIATORS: ["Output", "NextSwitchPoint"],
    # SmartMeter: real-time measurements (P1+P2+P3 computed to power)
    # Plus historical energy data arrays for statistics import
    ENTITY_TYPE_SMART_METERS: [
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
        # Historical energy data arrays (for external statistics)
        "Energy",
        "Energy24h",
        "EnergyDataDay",  # Today's consumption (single value or small array)
        "EnergyDataMonth",  # Daily values - rolling window of previous days (not including today)
        "EnergyDataYear",  # Monthly values - rolling window of previous 12 months
        "FeedInEnergy",
        "FeedIn24h",
        "FeedInDataMonth",  # Daily feed-in values
    ],
    # Air Quality: humidity and temperature sensors
    ENTITY_TYPE_AIR_QUALITY: ["Humidity", "ActualTemperature", "CO2Value"],
    # Valves: open/closed state
    ENTITY_TYPE_VALVES: ["ActValue"],
    # Security doors: door state, call in progress, and saved pictures
    ENTITY_TYPE_SECURITY_DOORS: ["IsOpen", "DoorIsOpen", "CallInProgress", "SavedPictures", "CamInstanceName"],
    # Intercoms: doorbell, door open, connection status
    ENTITY_TYPE_INTERCOMS: ["DoorBellTriggered", "DoorOpenTriggered", "IsDoorOpen", "ConnectionToIntercomHasBeenLost"],
    # Cameras: image path updates for live feed
    ENTITY_TYPE_CAMERAS: ["Image", "ImageRequest", "Error"],
}

# Map WebSocket property names to coordinator data keys
PROPERTY_MAPPINGS: dict[str, dict[str, str]] = {
    ENTITY_TYPE_LIGHTS: {
        "IsOn": "is_on",
        "ScaledBrightness": "brightness",  # 0-100 scale
        "ColorTemp": "color_temp",  # Kelvin
        "MinColorTemperature": "min_color_temp",  # Kelvin
        "MaxColorTemperature": "max_color_temp",  # Kelvin
    },
    ENTITY_TYPE_BLINDS: {
        "Position": "position",
        "Angle": "angle",
    },
    ENTITY_TYPE_CLIMATES: {
        "SetTemperature": "target_temperature",
        "ActualTemperature": "current_temperature",
        "ModeSaved": "mode_saved",
        "MainState": "mode_saved",  # SmartCOM.Clima.ClimateControl uses MainState
        "IsOn": "is_on",
        "Mode": "mode",
        "CoolingMode": "is_cooling",
        "Humidity": "humidity",
    },
    ENTITY_TYPE_SWITCHES: {
        "IsOn": "is_on",
        "State": "is_on",  # Some switches use State instead
    },
    ENTITY_TYPE_BUTTON_EVENTS: {
        "IsOn": "is_on",
    },
    ENTITY_TYPE_HOME_STATES: {
        "Active": "active",
    },
    ENTITY_TYPE_BATHROOM_RADIATORS: {
        "Output": "is_on",
        "NextSwitchPoint": "time_remaining",
    },
    ENTITY_TYPE_SMART_METERS: {
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
        # Energy totals and historical data
        "Energy": "energy",
        "Energy24h": "energy_24h",
        "EnergyDataDay": "energy_today",  # Today's consumption
        "EnergyDataMonth": "energy_data_month",  # Array of daily values (previous days, not today)
        "EnergyDataYear": "energy_data_year",  # Array of monthly values (previous 12 months)
        "FeedInEnergy": "feed_in_energy",
        "FeedIn24h": "feed_in_24h",
        "FeedInDataMonth": "feed_in_data_month",  # Array of daily feed-in values
    },
    ENTITY_TYPE_AIR_QUALITY: {
        "Humidity": "humidity",
        "ActualTemperature": "temperature",
        "CO2Value": "co2",
    },
    ENTITY_TYPE_VALVES: {
        "ActValue": "is_open",
    },
    ENTITY_TYPE_SECURITY_DOORS: {
        "IsOpen": "is_open",
        "DoorIsOpen": "door_is_open",
        "CallInProgress": "call_in_progress",
        "SavedPictures": "saved_pictures",
        "CamInstanceName": "cam_instance_name",
    },
    ENTITY_TYPE_INTERCOMS: {
        "DoorBellTriggered": "doorbell_triggered",
        "DoorOpenTriggered": "door_open_triggered",
        "IsDoorOpen": "is_door_open",
        "ConnectionToIntercomHasBeenLost": "connection_lost",
    },
    ENTITY_TYPE_CAMERAS: {
        "Image": "image_path",
        "ImageRequest": "image_request",
        "Error": "error",
    },
}


def get_entity_type(class_name: str) -> str | None:
    """Get the entity type for a given Evon class name.

    Args:
        class_name: The Evon class name.

    Returns:
        The entity type (e.g., ENTITY_TYPE_LIGHTS, ENTITY_TYPE_BLINDS) or None if unknown.
    """
    # Base.bSwitch is legacy dead code — no real devices use it.
    # SmartCOM.Light.Light is the actual class for relay outputs (light platform).
    if class_name == "Base.bSwitch":
        _LOGGER.warning(
            "Encountered legacy class Base.bSwitch (instance will be ignored). "
            "Real relay outputs use SmartCOM.Light.Light on the light platform"
        )
        return None

    # Try exact match first
    if class_name in CLASS_TO_TYPE:
        return CLASS_TO_TYPE[class_name]

    # SmartMeter has variations (Energy.SmartMeter, Energy.SmartMeterModbus, etc.)
    # Use substring match to handle all variants
    if EVON_CLASS_SMART_METER in class_name:
        return ENTITY_TYPE_SMART_METERS

    # ClimateControlUniversal may have prefix (e.g., SmartCOM.Clima.ClimateControlUniversal)
    if EVON_CLASS_CLIMATE_UNIVERSAL in class_name:
        return ENTITY_TYPE_CLIMATES

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

    # Special handling for climate devices: derive setpoint ranges and presets
    if entity_type == ENTITY_TYPE_CLIMATES:
        is_cooling = None
        if "CoolingMode" in ws_properties:
            is_cooling = ws_properties.get("CoolingMode")
        elif existing_data:
            is_cooling = existing_data.get("is_cooling")

        # Update cooling_enabled if DisableCooling changed
        if "DisableCooling" in ws_properties:
            disable_cooling = ws_properties.get("DisableCooling")
            if disable_cooling is not None:
                result["cooling_enabled"] = not bool(disable_cooling)

        def _coalesce(*vals: Any) -> Any:
            for val in vals:
                if val is not None:
                    return val
            return None

        def _min_defined(*vals: Any) -> Any:
            defined = [v for v in vals if v is not None]
            return min(defined) if defined else None

        def _max_defined(*vals: Any) -> Any:
            defined = [v for v in vals if v is not None]
            return max(defined) if defined else None

        if is_cooling is not None:
            if is_cooling:
                if "MinSetValueCool" in ws_properties:
                    result["min_set_value_cool"] = ws_properties.get("MinSetValueCool")
                if "MaxSetValueCool" in ws_properties:
                    result["max_set_value_cool"] = ws_properties.get("MaxSetValueCool")

                comfort = _coalesce(
                    ws_properties.get("SetValueComfortCooling"),
                    existing_data.get("comfort_temp") if existing_data else None,
                )
                eco = _coalesce(
                    ws_properties.get("SetValueEnergySavingCooling"),
                    existing_data.get("energy_saving_temp") if existing_data else None,
                )
                protection = _coalesce(
                    ws_properties.get("SetValueHeatProtection"),
                    existing_data.get("protection_temp") if existing_data else None,
                )
                evon_min = _coalesce(
                    ws_properties.get("MinSetValueCool"),
                    existing_data.get("min_set_value_cool") if existing_data else None,
                )
                evon_max = _coalesce(
                    ws_properties.get("MaxSetValueCool"),
                    existing_data.get("max_set_value_cool") if existing_data else None,
                )

                min_temp = _min_defined(evon_min, comfort, eco, protection)
                max_temp = _max_defined(evon_max, comfort, eco, protection)
            else:
                if "MinSetValueHeat" in ws_properties:
                    result["min_set_value_heat"] = ws_properties.get("MinSetValueHeat")
                if "MaxSetValueHeat" in ws_properties:
                    result["max_set_value_heat"] = ws_properties.get("MaxSetValueHeat")

                comfort = _coalesce(
                    ws_properties.get("SetValueComfortHeating"),
                    existing_data.get("comfort_temp") if existing_data else None,
                )
                eco = _coalesce(
                    ws_properties.get("SetValueEnergySavingHeating"),
                    existing_data.get("energy_saving_temp") if existing_data else None,
                )
                protection = _coalesce(
                    ws_properties.get("SetValueFreezeProtection"),
                    existing_data.get("protection_temp") if existing_data else None,
                )
                evon_min = _coalesce(
                    ws_properties.get("MinSetValueHeat"),
                    existing_data.get("min_set_value_heat") if existing_data else None,
                )
                evon_max = _coalesce(
                    ws_properties.get("MaxSetValueHeat"),
                    existing_data.get("max_set_value_heat") if existing_data else None,
                )

                min_temp = _min_defined(evon_min, protection)
                max_temp = _max_defined(evon_max, comfort, eco)

            if comfort is not None:
                result["comfort_temp"] = comfort
            if eco is not None:
                result["energy_saving_temp"] = eco
            if protection is not None:
                result["protection_temp"] = protection
            if min_temp is not None:
                result["min_temp"] = min_temp
            if max_temp is not None:
                result["max_temp"] = max_temp

    # Special handling for security doors: transform SavedPictures array
    if entity_type == ENTITY_TYPE_SECURITY_DOORS and "SavedPictures" in ws_properties:
        from .coordinator.processors.security_doors import _transform_saved_pictures

        result["saved_pictures"] = _transform_saved_pictures(ws_properties["SavedPictures"])

    # Special handling for smart meters: compute total power from P1+P2+P3
    if entity_type == ENTITY_TYPE_SMART_METERS:
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
            try:
                result["power"] = float(p1) + float(p2) + float(p3)
            except (TypeError, ValueError) as err:
                _LOGGER.warning(
                    "Failed to compute smart meter power from phases P1=%r, P2=%r, P3=%r: %s",
                    p1,
                    p2,
                    p3,
                    err,
                )

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
