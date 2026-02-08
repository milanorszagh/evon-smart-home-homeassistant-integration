"""WebSocket control mappings for Evon Smart Home.

Maps HTTP API method calls to WebSocket operations (SetValue or CallMethod).

WebSocket Control Format:
    CallMethod: {"methodName":"CallWithReturn","request":{"args":["instanceId.method",params],"methodName":"CallMethod","sequenceId":N}}
    SetValue:   {"methodName":"CallWithReturn","request":{"args":["instanceId","property",value],"methodName":"SetValue","sequenceId":N}}

Key Findings (from Evon webapp reverse engineering):
    - CallMethod format: args = ["instanceId.methodName", params] (method appended with dot)
    - SetValue format: args = ["instanceId", "propertyName", value]

Light Control:
    - SwitchOn/SwitchOff: Explicit on/off (no params) - PREFERRED over Switch([bool])
    - Switch([true/false]): Exists but inconsistent behavior on some devices
    - BrightnessSetScaled([brightness, transition_ms]): Set brightness with optional fade

Blind Control:
    - MoveToPosition([angle, position]): Set both tilt and position - angle comes FIRST!
    - Open/Close/Stop: Simple commands with no params
    - TRAP: SetValue on Position updates the value but doesn't move the hardware

Climate Control:
    READING current mode (properties):
        - ModeSaved: Current mode for ClimateControlUniversal (bathrooms)
        - MainState: Current mode for SmartCOM.Clima.ClimateControl (other rooms)
        - Values: 2=away, 3=eco, 4=comfort (heating) | 5=away, 6=eco, 7=comfort (cooling)

    CHANGING preset (CallMethod - the correct way):
        - WriteDayMode([])      → switches to comfort, recalls comfort temperature
        - WriteNightMode([])    → switches to eco, recalls eco temperature
        - WriteFreezeMode([])   → switches to away, recalls away temperature
        - WriteCurrentSetTemperature([temp]) → sets target temp for CURRENT preset

    TRAPS (SetValue - DON'T use for control):
        - SetValue ModeSaved/MainState = N  → Only updates UI number, does NOT change preset or temperature!
        - SetValue SetTemperature = N       → Only updates UI, does NOT change actual thermostat target!

    Fire-and-forget mode:
        - Climate methods don't send MethodReturn response
        - Use fire_and_forget=True to avoid timeout waiting for response
        - Commands execute successfully despite no response

    Timing (WebSocket vs HTTP):
        - WebSocket push: ~0.8-1.5 seconds for state updates
        - HTTP polling: ~5-7 seconds and may return stale data
        - IMPORTANT: Don't trigger HTTP refresh after WS commands (causes race condition)

    Home Assistant integration:
        - Use optimistic state for immediate UI feedback
        - Let WebSocket push actual values (no HTTP refresh needed)
        - Subscribe to both MainState AND ModeSaved (different thermostat types)

    Global presets (all thermostats at once):
        - CallMethod Base.ehThermostat.AllDayMode([])    → comfort for all
        - CallMethod Base.ehThermostat.AllNightMode([])  → eco for all
        - CallMethod Base.ehThermostat.AllFreezeMode([]) → away for all

Switch Control:
    - WebSocket CallMethod doesn't work for switches - must use HTTP API fallback
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .const import (
    EVON_CLASS_BATHROOM_RADIATOR,
    EVON_CLASS_BLIND,
    EVON_CLASS_BLIND_GROUP,
    EVON_CLASS_CLIMATE,
    EVON_CLASS_CLIMATE_UNIVERSAL,
    EVON_CLASS_HOME_STATE,
    EVON_CLASS_LIGHT,
    EVON_CLASS_LIGHT_DIM,
    EVON_CLASS_LIGHT_GROUP,
    EVON_CLASS_LIGHT_RGBW,
    EVON_CLASS_SCENE,
    EVON_CLASS_SWITCH,
)


@dataclass
class WsControlMapping:
    """Mapping from HTTP method to WebSocket operation.

    Attributes:
        property_name: Property name for SetValue, or None for CallMethod.
        method_name: Method name for CallMethod (used when property_name is None).
        value_fn: Function to compute value from params, or static value.
        fire_and_forget: If True, don't wait for response (for methods that don't send MethodReturn).
    """

    property_name: str | None
    method_name: str | None
    value_fn: Any | Callable[[list | None], Any]
    fire_and_forget: bool = False

    def get_value(self, params: list | None) -> Any:
        """Get the value to set, evaluating value_fn if needed."""
        if callable(self.value_fn):
            return self.value_fn(params)
        return self.value_fn


# Light control mappings (SmartCOM.Light.Light, SmartCOM.Light.LightDim, Base.bLight)
# Evon webapp uses CallMethod with SwitchOn/SwitchOff and BrightnessSetScaled methods.
# - SwitchOn/SwitchOff for explicit on/off (no params, doesn't toggle)
# - BrightnessSetScaled([brightness, transition_time]) for brightness (transition=0 for instant)
# - SetValue ColorTemp for color temperature (Kelvin) on RGBW lights
# Note: Switch([true/false]) exists but behaves inconsistently - use SwitchOn/SwitchOff instead.
LIGHT_MAPPINGS: dict[str, WsControlMapping] = {
    "AmznTurnOn": WsControlMapping(None, "SwitchOn", None),
    "AmznTurnOff": WsControlMapping(None, "SwitchOff", None),
    "AmznSetBrightness": WsControlMapping(None, "BrightnessSetScaled", lambda params: [params[0] if params else 0, 0]),
    "SetColorTemp": WsControlMapping("ColorTemp", None, lambda params: params[0] if params else 4000),
}

# Blind control mappings (SmartCOM.Blind.Blind, Base.bBlind, Base.ehBlind)
# Discovered: WebSocket CallMethod works with format [instanceId.method, params]!
# - Open/Close/Stop work via CallMethod with empty params
# - MoveToPosition works with [angle, position] params
# - SetValue on Position does NOT work (updates value but hardware doesn't move)
# Note: AmznSetPercentage and SetAngle are handled specially in api._try_ws_control()
# using MoveToPosition with cached angle/position values.
BLIND_MAPPINGS: dict[str, WsControlMapping] = {
    "Open": WsControlMapping(None, "Open", None),
    "Close": WsControlMapping(None, "Close", None),
    "Stop": WsControlMapping(None, "Stop", None),
    # AmznSetPercentage/SetAngle handled specially in api._try_ws_control()
}

# Climate control mappings (SmartCOM.Clima.ClimateControl, ClimateControlUniversal)
# VERIFIED WORKING February 2026 - tested on both thermostat types.
#
# KEY INSIGHT: Use CallMethod to CHANGE presets, not SetValue!
#   - CallMethod WriteDayMode/WriteNightMode/WriteFreezeMode → actually switches preset AND recalls temperature
#   - SetValue ModeSaved/MainState → TRAP! Only updates the UI number, doesn't change anything
#
# The server doesn't send MethodReturn response for climate methods, but commands execute successfully.
# Each preset remembers its own target temperature - switching presets recalls the saved temp.
CLIMATE_MAPPINGS: dict[str, WsControlMapping] = {
    # Preset switching - use these to change modes (verified working on both thermostat types)
    # fire_and_forget=True because these methods don't send MethodReturn response
    "WriteDayMode": WsControlMapping(None, "WriteDayMode", lambda _params: [], True),  # → comfort
    "WriteNightMode": WsControlMapping(None, "WriteNightMode", lambda _params: [], True),  # → eco
    "WriteFreezeMode": WsControlMapping(None, "WriteFreezeMode", lambda _params: [], True),  # → away
    # Temperature - sets target temp for the CURRENT preset only
    "WriteCurrentSetTemperature": WsControlMapping(
        None, "WriteCurrentSetTemperature", lambda params: [params[0]] if params else [0], True
    ),
}

# Switch control mappings (SmartCOM.Switch.Switch, Base.bSwitch)
# Note: AmznTurnOn/Off are NOT mapped - they must use HTTP because WebSocket
# CallMethod doesn't trigger actual hardware control on Evon systems.
# Empty dict means all switch commands fall back to HTTP.
SWITCH_MAPPINGS: dict[str, WsControlMapping] = {
    # AmznTurnOn/Off intentionally omitted - use HTTP fallback
}

# Home state control mappings (System.HomeState)
HOME_STATE_MAPPINGS: dict[str, WsControlMapping] = {
    "Activate": WsControlMapping(None, "Activate", None),
}

# Bathroom radiator control mappings (Heating.BathroomRadiator)
# Verified January 2025:
# - SwitchOneTime: Explicit turn ON for configured duration (WORKS)
# - Switch: Toggle on/off (WORKS)
# - SwitchOff: Does NOT work (acknowledged but no effect)
BATHROOM_RADIATOR_MAPPINGS: dict[str, WsControlMapping] = {
    "Switch": WsControlMapping(None, "Switch", None),
    "SwitchOneTime": WsControlMapping(None, "SwitchOneTime", None),
}

# Scene control mappings (System.SceneApp)
SCENE_MAPPINGS: dict[str, WsControlMapping] = {
    "Execute": WsControlMapping(None, "Execute", None),
}

# Map class names to their control mappings
CLASS_CONTROL_MAPPINGS: dict[str, dict[str, WsControlMapping]] = {
    # Lights - SwitchOn/SwitchOff for on/off, BrightnessSetScaled for dimming
    EVON_CLASS_LIGHT: LIGHT_MAPPINGS,
    EVON_CLASS_LIGHT_DIM: LIGHT_MAPPINGS,
    EVON_CLASS_LIGHT_GROUP: LIGHT_MAPPINGS,
    "Base.bLight": LIGHT_MAPPINGS,
    EVON_CLASS_LIGHT_RGBW: LIGHT_MAPPINGS,
    # Blinds
    EVON_CLASS_BLIND: BLIND_MAPPINGS,
    EVON_CLASS_BLIND_GROUP: BLIND_MAPPINGS,
    "Base.bBlind": BLIND_MAPPINGS,
    "Base.ehBlind": BLIND_MAPPINGS,
    # Climate
    EVON_CLASS_CLIMATE: CLIMATE_MAPPINGS,
    EVON_CLASS_CLIMATE_UNIVERSAL: CLIMATE_MAPPINGS,
    # Switches
    EVON_CLASS_SWITCH: SWITCH_MAPPINGS,
    "Base.bSwitch": SWITCH_MAPPINGS,
    # Home states
    EVON_CLASS_HOME_STATE: HOME_STATE_MAPPINGS,
    # Bathroom radiators
    EVON_CLASS_BATHROOM_RADIATOR: BATHROOM_RADIATOR_MAPPINGS,
    # Scenes
    EVON_CLASS_SCENE: SCENE_MAPPINGS,
}


def get_ws_control_mapping(
    class_name: str,
    method: str,
) -> WsControlMapping | None:
    """Get the WebSocket control mapping for a class and method.

    Args:
        class_name: The Evon class name (e.g., "SmartCOM.Light.LightDim").
        method: The HTTP method name (e.g., "AmznTurnOn").

    Returns:
        The WsControlMapping if found, None otherwise.
    """
    class_mappings = CLASS_CONTROL_MAPPINGS.get(class_name)
    if not class_mappings:
        return None
    return class_mappings.get(method)
