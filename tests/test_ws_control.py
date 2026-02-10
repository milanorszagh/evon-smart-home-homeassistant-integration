"""Tests for ws_control.py — WebSocket control mappings."""

from __future__ import annotations

from custom_components.evon.const import (
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
from custom_components.evon.ws_control import (
    BATHROOM_RADIATOR_MAPPINGS,
    BLIND_MAPPINGS,
    CLASS_CONTROL_MAPPINGS,
    CLIMATE_MAPPINGS,
    HOME_STATE_MAPPINGS,
    LIGHT_MAPPINGS,
    SCENE_MAPPINGS,
    SWITCH_MAPPINGS,
    WsControlMapping,
    get_http_method_name,
    get_ws_control_mapping,
)


class TestWsControlMapping:
    """Test WsControlMapping dataclass."""

    def test_static_value(self):
        mapping = WsControlMapping("TestProp", None, 42)
        assert mapping.get_value(None) == 42
        assert mapping.get_value([1, 2]) == 42

    def test_callable_value(self):
        mapping = WsControlMapping(None, "TestMethod", lambda params: params[0] if params else 0)
        assert mapping.get_value([50]) == 50
        assert mapping.get_value(None) == 0

    def test_none_value(self):
        mapping = WsControlMapping(None, "SwitchOn", None)
        assert mapping.get_value(None) is None
        assert mapping.get_value([1]) is None

    def test_fire_and_forget_default_false(self):
        mapping = WsControlMapping(None, "Test", None)
        assert mapping.fire_and_forget is False

    def test_fire_and_forget_explicit_true(self):
        mapping = WsControlMapping(None, "Test", None, True)
        assert mapping.fire_and_forget is True


class TestLightMappings:
    """Test light control mappings."""

    def test_switch_on(self):
        m = LIGHT_MAPPINGS["SwitchOn"]
        assert m.property_name is None
        assert m.method_name == "SwitchOn"
        assert m.get_value(None) is None

    def test_switch_off(self):
        m = LIGHT_MAPPINGS["SwitchOff"]
        assert m.property_name is None
        assert m.method_name == "SwitchOff"

    def test_brightness_with_params(self):
        m = LIGHT_MAPPINGS["BrightnessSetScaled"]
        assert m.method_name == "BrightnessSetScaled"
        assert m.get_value([75]) == [75, 0]

    def test_brightness_no_params(self):
        m = LIGHT_MAPPINGS["BrightnessSetScaled"]
        assert m.get_value(None) == [0, 0]

    def test_set_color_temp_with_params(self):
        m = LIGHT_MAPPINGS["SetColorTemp"]
        assert m.property_name == "ColorTemp"
        assert m.get_value([3000]) == 3000

    def test_set_color_temp_no_params(self):
        m = LIGHT_MAPPINGS["SetColorTemp"]
        assert m.get_value(None) == 4000


class TestBlindMappings:
    """Test blind control mappings."""

    def test_open(self):
        m = BLIND_MAPPINGS["Open"]
        assert m.method_name == "Open"
        assert m.property_name is None

    def test_close(self):
        m = BLIND_MAPPINGS["Close"]
        assert m.method_name == "Close"

    def test_stop(self):
        m = BLIND_MAPPINGS["Stop"]
        assert m.method_name == "Stop"

    def test_set_position_not_in_mappings(self):
        """SetPosition is handled specially in api._try_ws_control, not in mappings."""
        assert "SetPosition" not in BLIND_MAPPINGS

    def test_set_angle_not_in_mappings(self):
        """SetAngle is handled specially in api._try_ws_control, not in mappings."""
        assert "SetAngle" not in BLIND_MAPPINGS


class TestClimateMappings:
    """Test climate control mappings."""

    def test_write_day_mode(self):
        m = CLIMATE_MAPPINGS["WriteDayMode"]
        assert m.method_name == "WriteDayMode"
        assert m.fire_and_forget is True
        assert m.get_value(None) == []

    def test_write_night_mode(self):
        m = CLIMATE_MAPPINGS["WriteNightMode"]
        assert m.fire_and_forget is True
        assert m.get_value([]) == []

    def test_write_freeze_mode(self):
        m = CLIMATE_MAPPINGS["WriteFreezeMode"]
        assert m.fire_and_forget is True

    def test_write_current_set_temperature(self):
        m = CLIMATE_MAPPINGS["WriteCurrentSetTemperature"]
        assert m.fire_and_forget is True
        assert m.get_value([22.5]) == [22.5]

    def test_write_current_set_temperature_no_params(self):
        m = CLIMATE_MAPPINGS["WriteCurrentSetTemperature"]
        assert m.get_value(None) == [0]


class TestSwitchMappings:
    """Test that switch mappings are intentionally empty (HTTP fallback)."""

    def test_empty(self):
        assert len(SWITCH_MAPPINGS) == 0

    def test_no_turn_on(self):
        assert "AmznTurnOn" not in SWITCH_MAPPINGS

    def test_no_turn_off(self):
        assert "AmznTurnOff" not in SWITCH_MAPPINGS


class TestHomeStateMappings:
    """Test home state control mappings."""

    def test_activate(self):
        m = HOME_STATE_MAPPINGS["Activate"]
        assert m.method_name == "Activate"
        assert m.property_name is None


class TestBathroomRadiatorMappings:
    """Test bathroom radiator control mappings."""

    def test_switch(self):
        m = BATHROOM_RADIATOR_MAPPINGS["Switch"]
        assert m.method_name == "Switch"

    def test_switch_one_time(self):
        m = BATHROOM_RADIATOR_MAPPINGS["SwitchOneTime"]
        assert m.method_name == "SwitchOneTime"


class TestSceneMappings:
    """Test scene control mappings."""

    def test_execute(self):
        m = SCENE_MAPPINGS["Execute"]
        assert m.method_name == "Execute"


class TestClassControlMappings:
    """Test that all Evon class names are mapped correctly."""

    def test_light_classes(self):
        for cls in [
            EVON_CLASS_LIGHT,
            EVON_CLASS_LIGHT_DIM,
            EVON_CLASS_LIGHT_GROUP,
            "Base.bLight",
            EVON_CLASS_LIGHT_RGBW,
        ]:
            assert CLASS_CONTROL_MAPPINGS[cls] is LIGHT_MAPPINGS

    def test_blind_classes(self):
        for cls in [EVON_CLASS_BLIND, EVON_CLASS_BLIND_GROUP, "Base.bBlind", "Base.ehBlind"]:
            assert CLASS_CONTROL_MAPPINGS[cls] is BLIND_MAPPINGS

    def test_climate_classes(self):
        for cls in [EVON_CLASS_CLIMATE, EVON_CLASS_CLIMATE_UNIVERSAL]:
            assert CLASS_CONTROL_MAPPINGS[cls] is CLIMATE_MAPPINGS

    def test_switch_classes(self):
        for cls in [EVON_CLASS_SWITCH, "Base.bSwitch"]:
            assert CLASS_CONTROL_MAPPINGS[cls] is SWITCH_MAPPINGS

    def test_home_state_class(self):
        assert CLASS_CONTROL_MAPPINGS[EVON_CLASS_HOME_STATE] is HOME_STATE_MAPPINGS

    def test_bathroom_radiator_class(self):
        assert CLASS_CONTROL_MAPPINGS[EVON_CLASS_BATHROOM_RADIATOR] is BATHROOM_RADIATOR_MAPPINGS

    def test_scene_class(self):
        assert CLASS_CONTROL_MAPPINGS[EVON_CLASS_SCENE] is SCENE_MAPPINGS


class TestGetHttpMethodName:
    """Test WS->HTTP method name translation."""

    def test_switch_on_to_amzn_turn_on(self):
        assert get_http_method_name("SwitchOn") == "AmznTurnOn"

    def test_switch_off_to_amzn_turn_off(self):
        assert get_http_method_name("SwitchOff") == "AmznTurnOff"

    def test_brightness_to_amzn_set_brightness(self):
        assert get_http_method_name("BrightnessSetScaled") == "AmznSetBrightness"

    def test_set_position_to_amzn_set_percentage(self):
        assert get_http_method_name("SetPosition") == "AmznSetPercentage"

    def test_passthrough_open(self):
        assert get_http_method_name("Open") == "Open"

    def test_passthrough_close(self):
        assert get_http_method_name("Close") == "Close"

    def test_passthrough_write_day_mode(self):
        assert get_http_method_name("WriteDayMode") == "WriteDayMode"

    def test_passthrough_unknown(self):
        assert get_http_method_name("SomeUnknownMethod") == "SomeUnknownMethod"


class TestGetWsControlMapping:
    """Test get_ws_control_mapping() function."""

    def test_light_switch_on(self):
        mapping = get_ws_control_mapping(EVON_CLASS_LIGHT_DIM, "SwitchOn")
        assert mapping is not None
        assert mapping.method_name == "SwitchOn"

    def test_blind_open(self):
        mapping = get_ws_control_mapping(EVON_CLASS_BLIND, "Open")
        assert mapping is not None
        assert mapping.method_name == "Open"

    def test_climate_write_day_mode(self):
        mapping = get_ws_control_mapping(EVON_CLASS_CLIMATE, "WriteDayMode")
        assert mapping is not None
        assert mapping.fire_and_forget is True

    def test_unknown_class_returns_none(self):
        mapping = get_ws_control_mapping("Unknown.Class", "SwitchOn")
        assert mapping is None

    def test_unknown_method_returns_none(self):
        mapping = get_ws_control_mapping(EVON_CLASS_LIGHT, "NonExistentMethod")
        assert mapping is None

    def test_switch_class_returns_none_for_all(self):
        """Switch mappings are empty, so all methods return None."""
        mapping = get_ws_control_mapping(EVON_CLASS_SWITCH, "AmznTurnOn")
        assert mapping is None
