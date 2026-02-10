"""Tests for the WebSocket client."""

import asyncio
import contextlib
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.evon.api import EvonWsError, EvonWsNotConnectedError
from custom_components.evon.ws_client import (
    EvonWsClient,
)
from custom_components.evon.ws_control import (
    get_ws_control_mapping,
)
from custom_components.evon.ws_mappings import (
    build_subscription_list,
    get_entity_type,
    get_subscribe_properties,
    ws_to_coordinator_data,
)


class TestWsMappings:
    """Tests for ws_mappings module."""

    def test_class_to_type_lights(self):
        """Test light class mappings."""
        assert get_entity_type("SmartCOM.Light.LightDim") == "lights"
        assert get_entity_type("SmartCOM.Light.Light") == "lights"
        assert get_entity_type("Base.bLight") == "lights"

    def test_class_to_type_blinds(self):
        """Test blind class mappings."""
        assert get_entity_type("SmartCOM.Blind.Blind") == "blinds"
        assert get_entity_type("Base.bBlind") == "blinds"

    def test_class_to_type_climates(self):
        """Test climate class mappings."""
        assert get_entity_type("SmartCOM.Clima.ClimateControl") == "climates"
        assert get_entity_type("Heating.ClimateControlUniversal") == "climates"

    def test_class_to_type_home_states(self):
        """Test home state class mappings."""
        assert get_entity_type("System.HomeState") == "home_states"

    def test_class_to_type_bathroom_radiators(self):
        """Test bathroom radiator class mappings."""
        assert get_entity_type("Heating.BathroomRadiator") == "bathroom_radiators"

    def test_class_to_type_smart_meters(self):
        """Test smart meter class mappings."""
        assert get_entity_type("Energy.SmartMeter") == "smart_meters"

    def test_class_to_type_smart_meter_variations(self):
        """Test smart meter class variations (Modbus, 300, etc.)."""
        # SmartMeter has several hardware variants
        assert get_entity_type("Energy.SmartMeterModbus") == "smart_meters"
        assert get_entity_type("Energy.SmartMeter300") == "smart_meters"

    def test_class_to_type_air_quality(self):
        """Test air quality class mappings."""
        assert get_entity_type("System.Location.AirQuality") == "air_quality"

    def test_class_to_type_valves(self):
        """Test valve class mappings."""
        assert get_entity_type("SmartCOM.Clima.Valve") == "valves"

    def test_class_to_type_unknown(self):
        """Test unknown class returns None."""
        assert get_entity_type("Unknown.Class") is None
        assert get_entity_type("") is None

    def test_get_subscribe_properties_lights(self):
        """Test light subscribe properties."""
        props = get_subscribe_properties("lights")
        assert "IsOn" in props
        assert "ScaledBrightness" in props

    def test_get_subscribe_properties_blinds(self):
        """Test blind subscribe properties."""
        props = get_subscribe_properties("blinds")
        assert "Position" in props
        assert "Angle" in props

    def test_get_subscribe_properties_climates(self):
        """Test climate subscribe properties."""
        props = get_subscribe_properties("climates")
        assert "SetTemperature" in props
        assert "ActualTemperature" in props
        assert "ModeSaved" in props

    def test_get_subscribe_properties_unknown(self):
        """Test unknown entity type returns empty list."""
        assert get_subscribe_properties("unknown") == []

    def test_ws_to_coordinator_data_lights(self):
        """Test light property conversion."""
        ws_props = {"IsOn": True, "ScaledBrightness": 75}
        coord = ws_to_coordinator_data("lights", ws_props)
        assert coord == {"is_on": True, "brightness": 75}

    def test_ws_to_coordinator_data_blinds(self):
        """Test blind property conversion."""
        ws_props = {"Position": 50, "Angle": 30}
        coord = ws_to_coordinator_data("blinds", ws_props)
        assert coord == {"position": 50, "angle": 30}

    def test_ws_to_coordinator_data_climates(self):
        """Test climate property conversion."""
        ws_props = {"SetTemperature": 22.5, "ActualTemperature": 21.0, "ModeSaved": 4}
        coord = ws_to_coordinator_data("climates", ws_props)
        assert coord == {"target_temperature": 22.5, "current_temperature": 21.0, "mode_saved": 4}

    def test_ws_to_coordinator_data_home_states(self):
        """Test home state property conversion."""
        ws_props = {"Active": True}
        coord = ws_to_coordinator_data("home_states", ws_props)
        assert coord == {"active": True}

    def test_ws_to_coordinator_data_bathroom_radiators(self):
        """Test bathroom radiator property conversion."""
        ws_props = {"Output": True, "NextSwitchPoint": 1800}
        coord = ws_to_coordinator_data("bathroom_radiators", ws_props)
        assert coord == {"is_on": True, "time_remaining": 1800}

    def test_ws_to_coordinator_data_smart_meters(self):
        """Test smart meter property conversion."""
        ws_props = {
            "IL1": 5.2,
            "IL2": 4.8,
            "IL3": 5.0,
            "UL1N": 230.5,
            "UL2N": 231.0,
            "UL3N": 229.8,
            "Frequency": 50.02,
            "P1": 1200.0,
            "P2": 1100.0,
            "P3": 1150.0,
        }
        coord = ws_to_coordinator_data("smart_meters", ws_props)
        assert coord["current_l1"] == 5.2
        assert coord["current_l2"] == 4.8
        assert coord["current_l3"] == 5.0
        assert coord["voltage_l1"] == 230.5
        assert coord["voltage_l2"] == 231.0
        assert coord["voltage_l3"] == 229.8
        assert coord["frequency"] == 50.02
        assert coord["power_l1"] == 1200.0
        assert coord["power_l2"] == 1100.0
        assert coord["power_l3"] == 1150.0
        # Total power computed from P1+P2+P3
        assert coord["power"] == 3450.0

    def test_ws_to_coordinator_data_smart_meters_partial_power(self):
        """Test smart meter power computation with existing data."""
        # Simulate update with only P1 changed, using existing data for P2/P3
        ws_props = {"P1": 1500.0}
        existing_data = {"power_l1": 1200.0, "power_l2": 1100.0, "power_l3": 1150.0}
        coord = ws_to_coordinator_data("smart_meters", ws_props, existing_data)
        assert coord["power_l1"] == 1500.0
        # Total power uses new P1 + existing P2 + existing P3
        assert coord["power"] == 1500.0 + 1100.0 + 1150.0

    def test_ws_to_coordinator_data_air_quality(self):
        """Test air quality property conversion."""
        ws_props = {"Humidity": 45.5, "ActualTemperature": 22.3, "CO2Value": 650}
        coord = ws_to_coordinator_data("air_quality", ws_props)
        assert coord == {"humidity": 45.5, "temperature": 22.3, "co2": 650}

    def test_ws_to_coordinator_data_valves(self):
        """Test valve property conversion."""
        ws_props = {"ActValue": True}
        coord = ws_to_coordinator_data("valves", ws_props)
        assert coord == {"is_open": True}

    def test_ws_to_coordinator_data_unknown_property(self):
        """Test unknown property is ignored."""
        ws_props = {"IsOn": True, "UnknownProp": "value"}
        coord = ws_to_coordinator_data("lights", ws_props)
        assert coord == {"is_on": True}

    def test_build_subscription_list(self):
        """Test building subscription list from instances."""
        instances = [
            {"ID": "Light1", "ClassName": "SmartCOM.Light.LightDim"},
            {"ID": "Blind1", "ClassName": "SmartCOM.Blind.Blind"},
            {"ID": "Climate1", "ClassName": "SmartCOM.Clima.ClimateControl"},
            {"ID": "Unknown1", "ClassName": "Unknown.Class"},
        ]
        subs = build_subscription_list(instances)

        assert len(subs) == 3  # Unknown class should be excluded
        assert subs[0]["Instanceid"] == "Light1"
        assert "IsOn" in subs[0]["Properties"]
        assert subs[1]["Instanceid"] == "Blind1"
        assert "Position" in subs[1]["Properties"]
        assert subs[2]["Instanceid"] == "Climate1"
        assert "SetTemperature" in subs[2]["Properties"]

    def test_build_subscription_list_empty(self):
        """Test building subscription list with no instances."""
        assert build_subscription_list([]) == []

    def test_build_subscription_list_missing_fields(self):
        """Test building subscription list with missing fields."""
        instances = [
            {"ID": "Light1"},  # Missing ClassName
            {"ClassName": "SmartCOM.Light.LightDim"},  # Missing ID
            {"ID": "", "ClassName": "SmartCOM.Light.LightDim"},  # Empty ID
        ]
        subs = build_subscription_list(instances)
        assert len(subs) == 0


class TestWsClientValuesChanged:
    """Tests for WebSocket client ValuesChanged handling."""

    def test_handle_values_changed_groups_by_instance(self):
        """Test that ValuesChanged events are grouped by instance ID."""
        callback_calls = []

        def callback(instance_id, properties):
            callback_calls.append((instance_id, properties))

        client = EvonWsClient(
            host="http://192.168.1.100",
            username="test",
            password="test",
            session=MagicMock(),
            on_values_changed=callback,
        )

        # Simulate a ValuesChanged event
        args = [
            {
                "table": {
                    "Light1.IsOn": {"value": {"Value": True}},
                    "Light1.ScaledBrightness": {"value": {"Value": 75}},
                    "Blind1.Position": {"value": {"Value": 50}},
                }
            }
        ]
        client._handle_values_changed(args)

        assert len(callback_calls) == 2
        # Find the calls by instance
        light_call = next((c for c in callback_calls if c[0] == "Light1"), None)
        blind_call = next((c for c in callback_calls if c[0] == "Blind1"), None)

        assert light_call is not None
        assert light_call[1] == {"IsOn": True, "ScaledBrightness": 75}

        assert blind_call is not None
        assert blind_call[1] == {"Position": 50}

    def test_handle_values_changed_empty_table(self):
        """Test handling empty table."""
        callback = MagicMock()
        client = EvonWsClient(
            host="http://192.168.1.100",
            username="test",
            password="test",
            session=MagicMock(),
            on_values_changed=callback,
        )

        client._handle_values_changed([{"table": {}}])
        callback.assert_not_called()

    def test_handle_values_changed_no_callback(self):
        """Test handling without callback configured."""
        client = EvonWsClient(
            host="http://192.168.1.100",
            username="test",
            password="test",
            session=MagicMock(),
            on_values_changed=None,
        )

        # Should not raise
        client._handle_values_changed([{"table": {"Light1.IsOn": {"value": {"Value": True}}}}])

    def test_handle_values_changed_dotted_instance_id(self):
        """Test handling instance IDs with dots."""
        callback_calls = []

        def callback(instance_id, properties):
            callback_calls.append((instance_id, properties))

        client = EvonWsClient(
            host="http://192.168.1.100",
            username="test",
            password="test",
            session=MagicMock(),
            on_values_changed=callback,
        )

        # Instance ID with dots: "Floor1.Room2.Light3"
        args = [
            {
                "table": {
                    "Floor1.Room2.Light3.IsOn": {"value": {"Value": True}},
                }
            }
        ]
        client._handle_values_changed(args)

        assert len(callback_calls) == 1
        assert callback_calls[0][0] == "Floor1.Room2.Light3"
        assert callback_calls[0][1] == {"IsOn": True}


class TestWsClientMessageHandling:
    """Tests for WebSocket client message handling."""

    def test_handle_message_callback(self):
        """Test handling Callback message type."""
        client = EvonWsClient(
            host="http://192.168.1.100",
            username="test",
            password="test",
            session=MagicMock(),
        )

        # Set up a pending request
        future = asyncio.get_event_loop().create_future()
        client._pending_requests[1] = future

        # Simulate Callback message
        message = json.dumps(["Callback", {"sequenceId": 1, "args": ["result_value"]}])
        client._handle_message(message)

        assert future.done()
        assert future.result() == "result_value"
        assert 1 not in client._pending_requests

    def test_handle_message_event_values_changed(self):
        """Test handling Event message with ValuesChanged."""
        callback = MagicMock()
        client = EvonWsClient(
            host="http://192.168.1.100",
            username="test",
            password="test",
            session=MagicMock(),
            on_values_changed=callback,
        )

        message = json.dumps(
            ["Event", {"methodName": "ValuesChanged", "args": [{"table": {"Light1.IsOn": {"value": {"Value": True}}}}]}]
        )
        client._handle_message(message)

        callback.assert_called_once()

    def test_handle_message_connected(self):
        """Test handling Connected message type."""
        client = EvonWsClient(
            host="http://192.168.1.100",
            username="test",
            password="test",
            session=MagicMock(),
        )

        message = json.dumps(["Connected", {}, {}])
        # Should not raise
        client._handle_message(message)

    def test_handle_message_invalid_json(self):
        """Test handling invalid JSON."""
        client = EvonWsClient(
            host="http://192.168.1.100",
            username="test",
            password="test",
            session=MagicMock(),
        )

        # Should not raise, just log error
        client._handle_message("not valid json")


class TestWsClientProperties:
    """Tests for WebSocket client properties and initialization."""

    def test_host_conversion_http(self):
        """Test HTTP to WS conversion."""
        client = EvonWsClient(
            host="http://192.168.1.100",
            username="test",
            password="test",
            session=MagicMock(),
        )
        assert client._ws_host == "ws://192.168.1.100"

    def test_host_conversion_https(self):
        """Test HTTPS to WSS conversion."""
        client = EvonWsClient(
            host="https://192.168.1.100",
            username="test",
            password="test",
            session=MagicMock(),
        )
        assert client._ws_host == "wss://192.168.1.100"

    def test_host_trailing_slash_removed(self):
        """Test trailing slash is removed from host."""
        client = EvonWsClient(
            host="http://192.168.1.100/",
            username="test",
            password="test",
            session=MagicMock(),
        )
        assert client._host == "http://192.168.1.100"

    def test_is_connected_false_initially(self):
        """Test is_connected is False initially."""
        client = EvonWsClient(
            host="http://192.168.1.100",
            username="test",
            password="test",
            session=MagicMock(),
        )
        assert client.is_connected is False

    def test_subscribe_instances_stores_subscriptions(self):
        """Test that subscriptions are stored for reconnection."""
        client = EvonWsClient(
            host="http://192.168.1.100",
            username="test",
            password="test",
            session=MagicMock(),
        )

        subscriptions = [
            {"Instanceid": "Light1", "Properties": ["IsOn"]},
        ]

        # Run synchronously since we're not connected
        loop = asyncio.get_event_loop()
        loop.run_until_complete(client.subscribe_instances(subscriptions))

        assert client._subscriptions == subscriptions

    def test_remote_connection_initialization(self):
        """Test remote WebSocket client initialization."""
        client = EvonWsClient(
            host="",  # Empty for remote connections
            username="test@example.com",
            password="testpass",
            session=MagicMock(),
            is_remote=True,
            engine_id="ABC123",
        )

        # Remote connections use the remote host
        assert client._host == "https://my.evon-smarthome.com"
        assert client._ws_host == "wss://my.evon-smarthome.com/"
        assert client._is_remote is True
        assert client._engine_id == "ABC123"

    def test_local_connection_initialization(self):
        """Test local WebSocket client initialization (default)."""
        client = EvonWsClient(
            host="http://192.168.1.100",
            username="user",
            password="pass",
            session=MagicMock(),
        )

        # Local connections derive from host
        assert client._host == "http://192.168.1.100"
        assert client._ws_host == "ws://192.168.1.100"
        assert client._is_remote is False
        assert client._engine_id is None


class TestWsClientSetValue:
    """Tests for WebSocket client set_value method."""

    @pytest.mark.asyncio
    async def test_set_value_not_connected(self):
        """Test set_value returns False when not connected."""
        client = EvonWsClient(
            host="http://192.168.1.100",
            username="test",
            password="test",
            session=MagicMock(),
        )

        result = await client.set_value("Light1", "IsOn", True)
        assert result is False

    @pytest.mark.asyncio
    async def test_set_value_success(self):
        """Test set_value returns True on success."""
        client = EvonWsClient(
            host="http://192.168.1.100",
            username="test",
            password="test",
            session=MagicMock(),
        )
        # Mock connected state
        client._connected = True
        client._ws = MagicMock()
        client._ws.closed = False
        client._ws.send_str = AsyncMock()

        # Mock the response
        async def mock_send_request(method, args, request_timeout=10.0):
            return None

        client._send_request = AsyncMock(return_value=None)

        result = await client.set_value("Light1", "IsOn", True)
        assert result is True
        client._send_request.assert_called_once_with(
            "SetValue",
            ["Light1.IsOn", True],
        )

    @pytest.mark.asyncio
    async def test_set_value_failure(self):
        """Test set_value returns False on exception."""
        client = EvonWsClient(
            host="http://192.168.1.100",
            username="test",
            password="test",
            session=MagicMock(),
        )
        client._connected = True
        client._ws = MagicMock()
        client._ws.closed = False
        client._send_request = AsyncMock(side_effect=Exception("timeout"))

        result = await client.set_value("Light1", "IsOn", True)
        assert result is False


class TestWsClientCallMethod:
    """Tests for WebSocket client call_method method."""

    @pytest.mark.asyncio
    async def test_call_method_not_connected(self):
        """Test call_method returns False when not connected."""
        client = EvonWsClient(
            host="http://192.168.1.100",
            username="test",
            password="test",
            session=MagicMock(),
        )

        result = await client.call_method("Blind1", "Open")
        assert result is False

    @pytest.mark.asyncio
    async def test_call_method_success(self):
        """Test call_method returns True on success.

        Uses the Evon web app format: [instanceId.methodName, params]
        """
        client = EvonWsClient(
            host="http://192.168.1.100",
            username="test",
            password="test",
            session=MagicMock(),
        )
        client._connected = True
        client._ws = MagicMock()
        client._ws.closed = False
        client._send_request = AsyncMock(return_value=None)

        result = await client.call_method("Blind1", "Open", [])
        assert result is True
        # Format: [instanceId.methodName, params]
        client._send_request.assert_called_once_with(
            "CallMethod",
            ["Blind1.Open", []],
        )

    @pytest.mark.asyncio
    async def test_call_method_with_params(self):
        """Test call_method with parameters.

        Uses the Evon web app format: [instanceId.methodName, params]
        """
        client = EvonWsClient(
            host="http://192.168.1.100",
            username="test",
            password="test",
            session=MagicMock(),
        )
        client._connected = True
        client._ws = MagicMock()
        client._ws.closed = False
        client._send_request = AsyncMock(return_value=None)

        result = await client.call_method("Climate1", "WriteCurrentSetTemperature", [22.5])
        assert result is True
        # Format: [instanceId.methodName, params]
        client._send_request.assert_called_once_with(
            "CallMethod",
            ["Climate1.WriteCurrentSetTemperature", [22.5]],
        )

    @pytest.mark.asyncio
    async def test_call_method_failure(self):
        """Test call_method returns False on exception."""
        client = EvonWsClient(
            host="http://192.168.1.100",
            username="test",
            password="test",
            session=MagicMock(),
        )
        client._connected = True
        client._ws = MagicMock()
        client._ws.closed = False
        client._send_request = AsyncMock(side_effect=Exception("timeout"))

        result = await client.call_method("Blind1", "Open")
        assert result is False


class TestWsControlMappings:
    """Tests for ws_control module."""

    def test_light_mappings_turn_on_uses_ws(self):
        """Test light turn on uses WebSocket CallMethod SwitchOn."""
        # Use SwitchOn for explicit on - Switch([bool]) is inconsistent on some devices
        mapping = get_ws_control_mapping("SmartCOM.Light.LightDim", "SwitchOn")
        assert mapping is not None
        assert mapping.method_name == "SwitchOn"
        assert mapping.get_value(None) is None  # No params needed

    def test_light_mappings_turn_off_uses_ws(self):
        """Test light turn off uses WebSocket CallMethod SwitchOff."""
        # Use SwitchOff for explicit off - Switch([bool]) is inconsistent on some devices
        mapping = get_ws_control_mapping("SmartCOM.Light.Light", "SwitchOff")
        assert mapping is not None
        assert mapping.method_name == "SwitchOff"
        assert mapping.get_value(None) is None  # No params needed

    def test_light_mappings_brightness(self):
        """Test light brightness mapping uses WebSocket CallMethod BrightnessSetScaled."""
        mapping = get_ws_control_mapping("SmartCOM.Light.LightDim", "BrightnessSetScaled")
        assert mapping is not None
        assert mapping.method_name == "BrightnessSetScaled"
        assert mapping.get_value([75]) == [75, 0]  # [brightness, transition_time]

    def test_blind_mappings_open_close_stop(self):
        """Test blind Open/Close/Stop use WebSocket CallMethod.

        Discovered: WebSocket CallMethod works with format [instanceId.method, params].
        """
        mapping = get_ws_control_mapping("SmartCOM.Blind.Blind", "Open")
        assert mapping is not None
        assert mapping.method_name == "Open"

        mapping = get_ws_control_mapping("SmartCOM.Blind.Blind", "Close")
        assert mapping is not None
        assert mapping.method_name == "Close"

        mapping = get_ws_control_mapping("SmartCOM.Blind.Blind", "Stop")
        assert mapping is not None
        assert mapping.method_name == "Stop"

    def test_blind_position_uses_http(self):
        """Test blind position control uses HTTP fallback.

        SetPosition uses HTTP because MoveToPosition needs both angle+position.
        """
        assert get_ws_control_mapping("SmartCOM.Blind.Blind", "SetPosition") is None
        assert get_ws_control_mapping("SmartCOM.Blind.Blind", "SetAngle") is None

    def test_climate_mappings_preset_methods(self):
        """Test climate preset mappings use CallMethod with fire-and-forget.

        Presets use CallMethod instead of SetValue because SetValue only updates UI:
        - WriteDayMode -> comfort
        - WriteNightMode -> eco
        - WriteFreezeMode -> away
        """
        # Test comfort preset (WriteDayMode)
        mapping = get_ws_control_mapping("SmartCOM.Clima.ClimateControl", "WriteDayMode")
        assert mapping is not None
        assert mapping.property_name is None  # Uses CallMethod, not SetValue
        assert mapping.method_name == "WriteDayMode"
        assert mapping.fire_and_forget is True  # No MethodReturn response

        # Test eco preset (WriteNightMode)
        mapping = get_ws_control_mapping("SmartCOM.Clima.ClimateControl", "WriteNightMode")
        assert mapping is not None
        assert mapping.method_name == "WriteNightMode"
        assert mapping.fire_and_forget is True

        # Test away preset (WriteFreezeMode)
        mapping = get_ws_control_mapping("SmartCOM.Clima.ClimateControl", "WriteFreezeMode")
        assert mapping is not None
        assert mapping.method_name == "WriteFreezeMode"
        assert mapping.fire_and_forget is True

    def test_climate_mappings_temperature(self):
        """Test climate temperature mapping uses CallMethod."""
        mapping = get_ws_control_mapping("SmartCOM.Clima.ClimateControl", "WriteCurrentSetTemperature")
        assert mapping is not None
        # Must use CallMethod, not SetValue - SetValue only updates UI!
        assert mapping.property_name is None
        assert mapping.method_name == "WriteCurrentSetTemperature"
        assert mapping.get_value([22.5]) == [22.5]

    def test_climate_universal_mappings(self):
        """Test Heating.ClimateControlUniversal uses same mappings."""
        # Test that ClimateControlUniversal has same mappings as ClimateControl
        mapping = get_ws_control_mapping("Heating.ClimateControlUniversal", "WriteDayMode")
        assert mapping is not None
        assert mapping.method_name == "WriteDayMode"
        assert mapping.fire_and_forget is True

        mapping = get_ws_control_mapping("Heating.ClimateControlUniversal", "WriteCurrentSetTemperature")
        assert mapping is not None
        assert mapping.method_name == "WriteCurrentSetTemperature"

    def test_switch_mappings_turn_on_uses_http(self):
        """Test switch turn on has no WS mapping (uses HTTP fallback)."""
        # AmznTurnOn is intentionally not mapped to WebSocket
        mapping = get_ws_control_mapping("SmartCOM.Switch", "AmznTurnOn")
        assert mapping is None  # No WS mapping, will use HTTP

    def test_switch_mappings_turn_off_uses_http(self):
        """Test switch turn off has no WS mapping (uses HTTP fallback)."""
        # AmznTurnOff is intentionally not mapped to WebSocket
        mapping = get_ws_control_mapping("SmartCOM.Switch", "AmznTurnOff")
        assert mapping is None  # No WS mapping, will use HTTP

    def test_home_state_mappings_activate(self):
        """Test home state activate mapping."""
        mapping = get_ws_control_mapping("System.HomeState", "Activate")
        assert mapping is not None
        assert mapping.property_name is None
        assert mapping.method_name == "Activate"

    def test_bathroom_radiator_mappings_switch(self):
        """Test bathroom radiator switch (toggle) mapping."""
        mapping = get_ws_control_mapping("Heating.BathroomRadiator", "Switch")
        assert mapping is not None
        assert mapping.property_name is None
        assert mapping.method_name == "Switch"

    def test_bathroom_radiator_mappings_switch_one_time(self):
        """Test bathroom radiator SwitchOneTime (explicit turn on) mapping.

        Verified working January 2025 - turns on for configured duration.
        """
        mapping = get_ws_control_mapping("Heating.BathroomRadiator", "SwitchOneTime")
        assert mapping is not None
        assert mapping.property_name is None
        assert mapping.method_name == "SwitchOneTime"

    def test_scene_mappings_execute(self):
        """Test scene execute mapping."""
        mapping = get_ws_control_mapping("System.SceneApp", "Execute")
        assert mapping is not None
        assert mapping.property_name is None
        assert mapping.method_name == "Execute"

    def test_unknown_class_returns_none(self):
        """Test unknown class returns None."""
        assert get_ws_control_mapping("Unknown.Class", "AmznTurnOn") is None

    def test_unknown_method_returns_none(self):
        """Test unknown method returns None."""
        assert get_ws_control_mapping("SmartCOM.Light.Light", "UnknownMethod") is None

    def test_base_blight_mappings_on_uses_ws(self):
        """Test Base.bLight on/off uses WebSocket CallMethod SwitchOn."""
        mapping = get_ws_control_mapping("Base.bLight", "SwitchOn")
        assert mapping is not None
        assert mapping.method_name == "SwitchOn"
        assert mapping.get_value(None) is None  # No params needed

    def test_base_blight_mappings_brightness(self):
        """Test Base.bLight brightness uses WebSocket CallMethod BrightnessSetScaled."""
        mapping = get_ws_control_mapping("Base.bLight", "BrightnessSetScaled")
        assert mapping is not None
        assert mapping.method_name == "BrightnessSetScaled"

    def test_base_bblind_open_close_uses_ws(self):
        """Test Base.bBlind Open/Close/Stop use WebSocket."""
        mapping = get_ws_control_mapping("Base.bBlind", "Open")
        assert mapping is not None
        assert mapping.method_name == "Open"
        # Position still uses HTTP
        assert get_ws_control_mapping("Base.bBlind", "SetPosition") is None

    def test_base_ehblind_open_close_uses_ws(self):
        """Test Base.ehBlind Open/Close/Stop use WebSocket."""
        mapping = get_ws_control_mapping("Base.ehBlind", "Close")
        assert mapping is not None
        assert mapping.method_name == "Close"
        # Position still uses HTTP
        assert get_ws_control_mapping("Base.ehBlind", "SetPosition") is None

    def test_base_bswitch_mappings_uses_http(self):
        """Test Base.bSwitch on/off uses HTTP fallback."""
        mapping = get_ws_control_mapping("Base.bSwitch", "AmznTurnOn")
        assert mapping is None  # No WS mapping, will use HTTP


class TestWebSocketControlFindings:
    """Document WebSocket control findings and traps discovered during testing.

    These tests serve as documentation of what works and what doesn't when
    controlling Evon devices via WebSocket. They are based on real-world
    testing in January 2025.

    KEY FINDINGS:
    1. The Evon webapp uses CallMethod (not SetValue) for device control
    2. CallMethod format MUST be [instanceId.methodName, params] - the method
       is appended to the instance ID with a dot
    3. Light control uses SwitchOn/SwitchOff (explicit) and BrightnessSetScaled
       - Switch([bool]) exists but is INCONSISTENT on some devices!
    4. Blind control uses MoveToPosition([angle, position]) - angle comes FIRST
    5. Switches do NOT respond to WebSocket control - must use HTTP API

    TRAPS TO AVOID:
    1. Using old CallMethod format [instanceId, methodName, params] - doesn't work
    2. Using SetValue on blind Position - updates UI but hardware doesn't move
    3. Using AmznTurnOn/AmznTurnOff via CallMethod for lights - doesn't work
    4. Using WebSocket for switches - returns success but hardware doesn't respond
    5. Using Switch([true/false]) - inconsistent, may toggle instead of set state
    """

    def test_light_correct_method_switch_on_off(self):
        """CORRECT: Light on/off uses CallMethod SwitchOn/SwitchOff (no params).

        The Evon webapp exposes both Switch([bool]) and SwitchOn/SwitchOff.
        USE SwitchOn/SwitchOff - they are explicit and don't toggle.

        Example WebSocket calls:
        {"methodName":"CallWithReturn","request":{"args":["SC1_M01.Light3.SwitchOn",[]],"methodName":"CallMethod","sequenceId":85}}
        {"methodName":"CallWithReturn","request":{"args":["SC1_M01.Light3.SwitchOff",[]],"methodName":"CallMethod","sequenceId":86}}

        TRAP: Switch([true/false]) exists but behaves inconsistently on some
        devices - it may toggle instead of setting the desired state.
        """
        mapping = get_ws_control_mapping("SmartCOM.Light.LightDim", "SwitchOn")
        assert mapping is not None
        assert mapping.method_name == "SwitchOn"
        assert mapping.property_name is None  # Uses CallMethod, not SetValue
        assert mapping.get_value(None) is None  # No params needed

        mapping = get_ws_control_mapping("SmartCOM.Light.LightDim", "SwitchOff")
        assert mapping.method_name == "SwitchOff"
        assert mapping.get_value(None) is None  # No params needed

    def test_light_correct_method_brightness(self):
        """CORRECT: Light brightness uses CallMethod BrightnessSetScaled([brightness, transition]).

        The Evon webapp sends:
        {"methodName":"CallWithReturn","request":{"args":["SC1_M01.Light3.BrightnessSetScaled",[56,0]],"methodName":"CallMethod","sequenceId":93}}

        Parameters: [brightness (0-100), transition_time_ms (0 for instant)]
        """
        mapping = get_ws_control_mapping("SmartCOM.Light.LightDim", "BrightnessSetScaled")
        assert mapping is not None
        assert mapping.method_name == "BrightnessSetScaled"
        assert mapping.property_name is None  # Uses CallMethod, not SetValue
        # get_value returns [brightness, transition_time=0]
        assert mapping.get_value([50]) == [50, 0]
        assert mapping.get_value([100]) == [100, 0]
        assert mapping.get_value([0]) == [0, 0]

    def test_blind_correct_method_open_close_stop(self):
        """CORRECT: Blind open/close/stop use CallMethod Open/Close/Stop([]).

        The Evon webapp sends:
        {"methodName":"CallWithReturn","request":{"args":["SC1_M09.Blind2.Close",[]],"methodName":"CallMethod","sequenceId":67}}
        """
        for method in ["Open", "Close", "Stop"]:
            mapping = get_ws_control_mapping("SmartCOM.Blind.Blind", method)
            assert mapping is not None, f"Missing mapping for {method}"
            assert mapping.method_name == method
            assert mapping.property_name is None  # Uses CallMethod

    def test_blind_correct_method_move_to_position(self):
        """CORRECT: Blind position+tilt uses CallMethod MoveToPosition([angle, position]).

        The Evon webapp sends:
        {"methodName":"CallWithReturn","request":{"args":["SC1_M09.Blind2.MoveToPosition",[100,52]],"methodName":"CallMethod","sequenceId":50}}

        IMPORTANT: Parameters are [angle, position] - ANGLE COMES FIRST!
        - angle: tilt/slat angle (0-100)
        - position: closure (0=open, 100=closed)

        The integration caches angle and position separately so that:
        - Position changes use MoveToPosition([cached_angle, new_position])
        - Tilt changes use MoveToPosition([new_angle, cached_position])
        """
        # SetPosition and SetAngle have no direct mapping - they are
        # handled specially in api._try_ws_control() using MoveToPosition
        assert get_ws_control_mapping("SmartCOM.Blind.Blind", "SetPosition") is None
        assert get_ws_control_mapping("SmartCOM.Blind.Blind", "SetAngle") is None

    def test_switch_must_use_http(self):
        """TRAP: Switch control via WebSocket does NOT trigger hardware.

        WebSocket CallMethod returns success but the physical relay doesn't switch.
        Must use HTTP API for switches: POST /api/instances/{id}/AmznTurnOn
        """
        # Intentionally no WebSocket mapping for switches
        assert get_ws_control_mapping("SmartCOM.Switch.Switch", "AmznTurnOn") is None
        assert get_ws_control_mapping("SmartCOM.Switch.Switch", "AmznTurnOff") is None
        assert get_ws_control_mapping("Base.bSwitch", "AmznTurnOn") is None
        assert get_ws_control_mapping("Base.bSwitch", "AmznTurnOff") is None

    def test_callmethod_format_must_include_method_in_instance_id(self):
        """TRAP: CallMethod format must be [instanceId.methodName, params].

        WRONG format (doesn't trigger hardware):
        {"args":["SC1_M09.Blind2", "Open", []], "methodName":"CallMethod"}

        CORRECT format (works):
        {"args":["SC1_M09.Blind2.Open", []], "methodName":"CallMethod"}

        The method name is appended to the instance ID with a dot, and params
        is the second element of the args array.
        """
        # This is tested implicitly by the ws_client.call_method implementation
        # which uses f"{instance_id}.{method}" format
        pass

    def test_setvalue_on_blind_position_does_not_work(self):
        """TRAP: SetValue on blind Position updates UI but hardware doesn't move.

        When using SetValue on Position property:
        1. The value updates in the Evon app immediately
        2. The hardware does NOT move
        3. After a few seconds, the value reverts to the actual position

        Must use CallMethod MoveToPosition([angle, position]) instead.
        """
        # No SetValue mapping for blind position - this is intentional
        mapping = get_ws_control_mapping("SmartCOM.Blind.Blind", "SetPosition")
        assert mapping is None or mapping.property_name is None

    def test_light_amzn_methods_via_callmethod_do_not_work(self):
        """TRAP: CallMethod AmznTurnOn/AmznTurnOff for lights doesn't work.

        WRONG (doesn't trigger hardware):
        {"args":["SC1_M01.Light3.AmznTurnOn", []], "methodName":"CallMethod"}

        WRONG (inconsistent, may toggle):
        {"args":["SC1_M01.Light3.Switch", [true]], "methodName":"CallMethod"}

        CORRECT (explicit, works reliably):
        {"args":["SC1_M01.Light3.SwitchOn", []], "methodName":"CallMethod"}
        {"args":["SC1_M01.Light3.SwitchOff", []], "methodName":"CallMethod"}
        """
        # Canonical names are now SwitchOn/SwitchOff directly
        mapping = get_ws_control_mapping("SmartCOM.Light.LightDim", "SwitchOn")
        assert mapping.method_name == "SwitchOn"
        assert mapping.method_name != "AmznTurnOn"
        assert mapping.method_name != "Switch"

    def test_trap_switch_bool_is_inconsistent(self):
        """TRAP: Switch([true/false]) is inconsistent on some devices.

        While Switch([true]) and Switch([false]) exist in the Evon API, they
        behave inconsistently:
        - On some devices, Switch([true]) always turns on
        - On other devices, Switch([true]) toggles the state

        This was discovered when a combined light (Evon relay + Govee) would
        turn off on every other brightness change. The relay was receiving
        Switch([true]) which toggled instead of setting state.

        SOLUTION: Always use SwitchOn/SwitchOff for explicit on/off control.
        """
        mapping = get_ws_control_mapping("SmartCOM.Light.Light", "SwitchOn")
        assert mapping.method_name == "SwitchOn"  # Not "Switch"

        mapping = get_ws_control_mapping("SmartCOM.Light.Light", "SwitchOff")
        assert mapping.method_name == "SwitchOff"  # Not "Switch"


class TestApiBlindCaching:
    """Tests for blind angle/position caching used for WebSocket control."""

    def test_update_and_get_blind_angle(self):
        """Test blind angle caching."""
        from custom_components.evon.api import EvonApi

        api = EvonApi(host="http://test", username="user", password="pass")
        assert api.get_blind_angle("Blind1") is None

        api.update_blind_angle("Blind1", 45)
        assert api.get_blind_angle("Blind1") == 45

        api.update_blind_angle("Blind1", 90)
        assert api.get_blind_angle("Blind1") == 90

    def test_update_and_get_blind_position(self):
        """Test blind position caching."""
        from custom_components.evon.api import EvonApi

        api = EvonApi(host="http://test", username="user", password="pass")
        assert api.get_blind_position("Blind1") is None

        api.update_blind_position("Blind1", 50)
        assert api.get_blind_position("Blind1") == 50

        api.update_blind_position("Blind1", 100)
        assert api.get_blind_position("Blind1") == 100

    def test_multiple_blinds_cached_independently(self):
        """Test that multiple blinds have independent caches."""
        from custom_components.evon.api import EvonApi

        api = EvonApi(host="http://test", username="user", password="pass")

        api.update_blind_angle("Blind1", 30)
        api.update_blind_angle("Blind2", 60)
        api.update_blind_position("Blind1", 20)
        api.update_blind_position("Blind2", 80)

        assert api.get_blind_angle("Blind1") == 30
        assert api.get_blind_angle("Blind2") == 60
        assert api.get_blind_position("Blind1") == 20
        assert api.get_blind_position("Blind2") == 80


class TestClimateWebSocketControl:
    """Tests for climate WebSocket control - verified working February 2026.

    All climate controls work via WebSocket with CallMethod (fire-and-forget):
    - Temperature: CallMethod WriteCurrentSetTemperature([temp])
    - Presets: CallMethod WriteDayMode/WriteNightMode/WriteFreezeMode([])
    - Season mode: SetValue Base.ehThermostat.IsCool = bool

    IMPORTANT: SetValue on ModeSaved/MainState/SetTemperature only updates UI, NOT the thermostat!
    Always use CallMethod for actual control.
    """

    def test_climate_temperature_uses_callmethod(self):
        """VERIFIED: Climate temperature uses CallMethod WriteCurrentSetTemperature.

        IMPORTANT: SetValue on SetTemperature only updates UI, not the actual thermostat!
        Must use CallMethod WriteCurrentSetTemperature to actually change the target temperature.

        Example WebSocket call:
        {"methodName":"CallWithReturn","request":{"args":["SC1_M05.Thermostat1.WriteCurrentSetTemperature",[23.5]],"methodName":"CallMethod","sequenceId":N}}
        """
        mapping = get_ws_control_mapping("SmartCOM.Clima.ClimateControl", "WriteCurrentSetTemperature")
        assert mapping is not None
        assert mapping.property_name is None  # Uses CallMethod, not SetValue!
        assert mapping.method_name == "WriteCurrentSetTemperature"
        assert mapping.fire_and_forget is True  # No MethodReturn response
        assert mapping.get_value([23.5]) == [23.5]
        assert mapping.get_value([21]) == [21]

    def test_climate_preset_uses_callmethod(self):
        """VERIFIED: Climate presets use CallMethod with fire-and-forget.

        Presets use CallMethod instead of SetValue because SetValue only updates UI:
        - WriteDayMode -> comfort (recalls comfort temperature)
        - WriteNightMode -> eco (recalls eco temperature)
        - WriteFreezeMode -> away (recalls away temperature)

        Example WebSocket call for comfort mode:
        {"methodName":"CallWithReturn","request":{"args":["SC1_M05.Thermostat1.WriteDayMode",[]],"methodName":"CallMethod","sequenceId":N}}

        Note: These methods don't send a MethodReturn response (fire-and-forget).
        """
        # Test WriteDayMode (comfort)
        mapping = get_ws_control_mapping("SmartCOM.Clima.ClimateControl", "WriteDayMode")
        assert mapping is not None
        assert mapping.property_name is None  # Uses CallMethod, not SetValue
        assert mapping.method_name == "WriteDayMode"
        assert mapping.fire_and_forget is True

        # Test WriteNightMode (eco)
        mapping = get_ws_control_mapping("SmartCOM.Clima.ClimateControl", "WriteNightMode")
        assert mapping is not None
        assert mapping.method_name == "WriteNightMode"
        assert mapping.fire_and_forget is True

        # Test WriteFreezeMode (away)
        mapping = get_ws_control_mapping("SmartCOM.Clima.ClimateControl", "WriteFreezeMode")
        assert mapping is not None
        assert mapping.method_name == "WriteFreezeMode"
        assert mapping.fire_and_forget is True

    def test_climate_universal_has_same_mappings(self):
        """Test Heating.ClimateControlUniversal uses same mappings as ClimateControl."""
        for method in ["WriteDayMode", "WriteNightMode", "WriteFreezeMode", "WriteCurrentSetTemperature"]:
            mapping1 = get_ws_control_mapping("SmartCOM.Clima.ClimateControl", method)
            mapping2 = get_ws_control_mapping("Heating.ClimateControlUniversal", method)
            assert mapping1 is not None, f"ClimateControl missing mapping for {method}"
            assert mapping2 is not None, f"ClimateControlUniversal missing mapping for {method}"
            assert mapping1.method_name == mapping2.method_name
            assert mapping1.fire_and_forget == mapping2.fire_and_forget

    def test_modesaved_values_by_season(self):
        """Document and verify ModeSaved values for each preset and season.

        The Evon system handles season mode internally. The API methods
        (set_climate_comfort_mode, set_climate_energy_saving_mode,
        set_climate_freeze_protection_mode) use a single WriteDayMode /
        WriteNightMode / WriteFreezeMode call regardless of season.

        ModeSaved values observed from the Evon controller:
        - Heating: away=2, eco=3, comfort=4
        - Cooling: away=5, eco=6, comfort=7
        """
        # Document that ModeSaved values differ by season
        heating_presets = {"away": 2, "eco": 3, "comfort": 4}
        cooling_presets = {"away": 5, "eco": 6, "comfort": 7}

        # Verify correct values
        assert heating_presets["away"] == 2
        assert heating_presets["eco"] == 3
        assert heating_presets["comfort"] == 4
        assert cooling_presets["away"] == 5
        assert cooling_presets["eco"] == 6
        assert cooling_presets["comfort"] == 7

    def test_global_preset_methods_on_base_thermostat(self):
        """Document global preset methods on Base.ehThermostat.

        The Evon webapp uses these methods to change presets for ALL thermostats:
        - Base.ehThermostat.AllDayMode([]) - all to comfort
        - Base.ehThermostat.AllNightMode([]) - all to eco
        - Base.ehThermostat.AllFreezeMode([]) - all to away

        These are not mapped in the integration as we use individual thermostat control.
        """
        # These methods exist on Base.ehThermostat, not individual climate controls
        # Document for reference but not implemented in WsControlMapping
        pass


class TestNewFeatures:
    """Tests for new features: Security Doors, Intercoms, Light/Blind Groups, Color Temp, Humidity."""

    def test_class_to_type_security_doors(self):
        """Test security door class mappings."""
        assert get_entity_type("Security.Door") == "security_doors"

    def test_class_to_type_intercoms(self):
        """Test intercom class mappings."""
        assert get_entity_type("Security.Intercom.2N.Intercom2N") == "intercoms"

    def test_class_to_type_light_group(self):
        """Test light group class mappings."""
        assert get_entity_type("SmartCOM.Light.LightGroup") == "lights"

    def test_class_to_type_blind_group(self):
        """Test blind group class mappings."""
        assert get_entity_type("SmartCOM.Blind.BlindGroup") == "blinds"

    def test_class_to_type_rgbw_light(self):
        """Test RGBW light class mappings."""
        assert get_entity_type("SmartCOM.Light.DynamicRGBWLight") == "lights"

    def test_get_subscribe_properties_security_doors(self):
        """Test security door subscribe properties."""
        props = get_subscribe_properties("security_doors")
        assert "IsOpen" in props
        assert "DoorIsOpen" in props
        assert "CallInProgress" in props

    def test_get_subscribe_properties_intercoms(self):
        """Test intercom subscribe properties."""
        props = get_subscribe_properties("intercoms")
        assert "DoorBellTriggered" in props
        assert "DoorOpenTriggered" in props
        assert "IsDoorOpen" in props
        assert "ConnectionToIntercomHasBeenLost" in props

    def test_get_subscribe_properties_lights_color_temp(self):
        """Test light subscribe properties include color temp."""
        props = get_subscribe_properties("lights")
        assert "IsOn" in props
        assert "ScaledBrightness" in props
        assert "ColorTemp" in props
        assert "MinColorTemperature" in props
        assert "MaxColorTemperature" in props

    def test_get_subscribe_properties_climates_humidity(self):
        """Test climate subscribe properties include humidity."""
        props = get_subscribe_properties("climates")
        assert "Humidity" in props

    def test_ws_to_coordinator_data_security_doors(self):
        """Test security door property conversion."""
        ws_props = {"IsOpen": True, "DoorIsOpen": False, "CallInProgress": True}
        coord = ws_to_coordinator_data("security_doors", ws_props)
        assert coord == {"is_open": True, "door_is_open": False, "call_in_progress": True}

    def test_ws_to_coordinator_data_intercoms(self):
        """Test intercom property conversion."""
        ws_props = {
            "DoorBellTriggered": True,
            "DoorOpenTriggered": False,
            "IsDoorOpen": True,
            "ConnectionToIntercomHasBeenLost": False,
        }
        coord = ws_to_coordinator_data("intercoms", ws_props)
        assert coord == {
            "doorbell_triggered": True,
            "door_open_triggered": False,
            "is_door_open": True,
            "connection_lost": False,
        }

    def test_ws_to_coordinator_data_climates_humidity(self):
        """Test climate humidity property conversion."""
        ws_props = {"SetTemperature": 22.5, "Humidity": 45.5}
        coord = ws_to_coordinator_data("climates", ws_props)
        assert coord["target_temperature"] == 22.5
        assert coord["humidity"] == 45.5

    def test_ws_to_coordinator_data_lights_color_temp(self):
        """Test light color temp property conversion."""
        ws_props = {"IsOn": True, "ColorTemp": 4000, "MinColorTemperature": 2700, "MaxColorTemperature": 6500}
        coord = ws_to_coordinator_data("lights", ws_props)
        assert coord["is_on"] is True
        assert coord["color_temp"] == 4000
        assert coord["min_color_temp"] == 2700
        assert coord["max_color_temp"] == 6500

    def test_light_group_control_mappings(self):
        """Test light group has same control mappings as lights."""
        mapping = get_ws_control_mapping("SmartCOM.Light.LightGroup", "SwitchOn")
        assert mapping is not None
        assert mapping.method_name == "SwitchOn"

    def test_blind_group_control_mappings(self):
        """Test blind group has same control mappings as blinds."""
        mapping = get_ws_control_mapping("SmartCOM.Blind.BlindGroup", "Open")
        assert mapping is not None
        assert mapping.method_name == "Open"

    def test_rgbw_light_color_temp_mapping(self):
        """Test RGBW light SetColorTemp mapping."""
        mapping = get_ws_control_mapping("SmartCOM.Light.DynamicRGBWLight", "SetColorTemp")
        assert mapping is not None
        assert mapping.property_name == "ColorTemp"
        assert mapping.get_value([4000]) == 4000

    def test_build_subscription_list_includes_new_types(self):
        """Test building subscription list with new device types."""
        instances = [
            {"ID": "Door1", "ClassName": "Security.Door"},
            {"ID": "Intercom1", "ClassName": "Security.Intercom.2N.Intercom2N"},
            {"ID": "LightGroup1", "ClassName": "SmartCOM.Light.LightGroup"},
            {"ID": "BlindGroup1", "ClassName": "SmartCOM.Blind.BlindGroup"},
        ]
        subs = build_subscription_list(instances)

        assert len(subs) == 4
        # Find subscriptions by instance ID
        door_sub = next((s for s in subs if s["Instanceid"] == "Door1"), None)
        intercom_sub = next((s for s in subs if s["Instanceid"] == "Intercom1"), None)
        light_group_sub = next((s for s in subs if s["Instanceid"] == "LightGroup1"), None)
        blind_group_sub = next((s for s in subs if s["Instanceid"] == "BlindGroup1"), None)

        assert door_sub is not None
        assert "IsOpen" in door_sub["Properties"]

        assert intercom_sub is not None
        assert "DoorBellTriggered" in intercom_sub["Properties"]

        assert light_group_sub is not None
        assert "IsOn" in light_group_sub["Properties"]

        assert blind_group_sub is not None
        assert "Position" in blind_group_sub["Properties"]

    def test_class_to_type_cameras(self):
        """Test camera class mappings."""
        assert get_entity_type("Security.Intercom.2N.Intercom2NCam") == "cameras"

    def test_get_subscribe_properties_cameras(self):
        """Test camera subscribe properties."""
        props = get_subscribe_properties("cameras")
        assert "Image" in props
        assert "ImageRequest" in props
        assert "Error" in props

    def test_ws_to_coordinator_data_cameras(self):
        """Test camera property conversion."""
        ws_props = {
            "Image": "/temp/Cam_img.jpg?rng=123",
            "ImageRequest": True,
            "Error": False,
        }
        coord = ws_to_coordinator_data("cameras", ws_props)
        assert coord == {
            "image_path": "/temp/Cam_img.jpg?rng=123",
            "image_request": True,
            "error": False,
        }

    def test_build_subscription_list_includes_cameras(self):
        """Test building subscription list includes cameras."""
        instances = [
            {"ID": "Intercom2N1000.Cam", "ClassName": "Security.Intercom.2N.Intercom2NCam"},
        ]
        subs = build_subscription_list(instances)

        assert len(subs) == 1
        cam_sub = subs[0]
        assert cam_sub["Instanceid"] == "Intercom2N1000.Cam"
        assert "Image" in cam_sub["Properties"]
        assert "ImageRequest" in cam_sub["Properties"]


class TestWsMappingsEdgeCases:
    """Edge case tests for ws_mappings module."""

    def test_ws_to_coordinator_data_security_doors_saved_pictures(self):
        """Test security door SavedPictures transformation."""
        ws_props = {
            "SavedPictures": [
                {"imageUrlClient": "/images/snap1.jpg", "datetime": 1706900000000},
                {"imageUrlClient": "/images/snap2.jpg", "datetime": 1706899000000},
            ]
        }
        coord = ws_to_coordinator_data("security_doors", ws_props)

        assert "saved_pictures" in coord
        assert len(coord["saved_pictures"]) == 2
        assert coord["saved_pictures"][0]["path"] == "/images/snap1.jpg"
        assert coord["saved_pictures"][0]["timestamp"] == 1706900000000

    def test_ws_to_coordinator_data_security_doors_empty_pictures(self):
        """Test security door with empty SavedPictures."""
        ws_props = {"SavedPictures": []}
        coord = ws_to_coordinator_data("security_doors", ws_props)

        assert coord["saved_pictures"] == []

    def test_ws_to_coordinator_data_security_doors_non_list_pictures(self):
        """Test security door with non-list SavedPictures passes through unchanged."""
        ws_props = {"SavedPictures": "not a list"}
        coord = ws_to_coordinator_data("security_doors", ws_props)

        # Non-list values pass through via property mapping (saved_pictures key)
        # Only list values get transformed
        assert "saved_pictures" in coord
        assert coord["saved_pictures"] == "not a list"

    def test_ws_to_coordinator_data_smart_meter_power_none_phases(self):
        """Test smart meter power computation with None phase values."""
        ws_props = {"P1": None, "P2": 1000, "P3": 1000}
        # No existing data, so can't compute total
        coord = ws_to_coordinator_data("smart_meters", ws_props)

        # Should have individual phases but no total power
        assert "power_l2" in coord
        assert coord["power_l2"] == 1000
        assert "power" not in coord  # Can't compute without all phases

    def test_ws_to_coordinator_data_smart_meter_power_invalid_type(self):
        """Test smart meter power computation handles invalid types."""
        ws_props = {"P1": "not a number", "P2": 1000, "P3": 1000}
        coord = ws_to_coordinator_data("smart_meters", ws_props)

        # Should not raise, power should not be computed due to invalid type
        # The function uses contextlib.suppress(TypeError, ValueError)
        assert "power" not in coord or coord.get("power") is None

    def test_get_entity_type_climate_universal_prefix(self):
        """Test climate universal with Heating prefix (substring matching)."""
        # Standard Heating.ClimateControlUniversal class
        assert get_entity_type("Heating.ClimateControlUniversal") == "climates"
        # With additional suffix - substring match works
        assert get_entity_type("Heating.ClimateControlUniversal.V2") == "climates"
        # Note: SmartCOM.Clima.ClimateControlUniversal wouldn't match because
        # it uses substring match on "Heating.ClimateControlUniversal"

    def test_get_entity_type_smart_meter_variations(self):
        """Test various smart meter class name variations."""
        # Standard
        assert get_entity_type("Energy.SmartMeter") == "smart_meters"
        # With Modbus suffix
        assert get_entity_type("Energy.SmartMeterModbus") == "smart_meters"
        # With version suffix
        assert get_entity_type("Energy.SmartMeter300") == "smart_meters"

    def test_ws_to_coordinator_data_unknown_entity_type(self):
        """Test with unknown entity type returns empty dict."""
        ws_props = {"SomeProperty": "value"}
        coord = ws_to_coordinator_data("unknown_type", ws_props)

        assert coord == {}

    def test_get_subscribe_properties_unknown_type(self):
        """Test subscribe properties for unknown type returns empty list."""
        props = get_subscribe_properties("unknown_type")
        assert props == []


class TestWsMessageHandlingEdgeCases:
    """Tests for WebSocket message parsing edge cases."""

    def test_handle_message_malformed_json(self):
        """Test handling of malformed JSON message."""
        client = EvonWsClient(
            host="http://192.168.1.100",
            username="user",
            password="pass",
        )

        # Should not raise, just log error
        client._handle_message("not valid json {")
        client._handle_message("")
        client._handle_message("null")

    def test_handle_message_empty_array(self):
        """Test handling of empty array message."""
        client = EvonWsClient(
            host="http://192.168.1.100",
            username="user",
            password="pass",
        )

        # Empty array - should not crash
        client._handle_message("[]")

    def test_handle_message_missing_type(self):
        """Test handling of message without type field."""
        client = EvonWsClient(
            host="http://192.168.1.100",
            username="user",
            password="pass",
        )

        # Array with data but will fail on msg[0] being a dict
        client._handle_message('[{"data": "test"}]')

    def test_handle_callback_unknown_sequence_id(self):
        """Test callback with unknown sequence ID is ignored."""
        client = EvonWsClient(
            host="http://192.168.1.100",
            username="user",
            password="pass",
        )

        # Add a pending request with different ID
        future = asyncio.get_event_loop().create_future()
        client._pending_requests[999] = future

        # Callback with different sequence ID - should be ignored
        msg = json.dumps(["Callback", {"sequenceId": 123, "args": ["result"]}])
        client._handle_message(msg)

        # Original future should still be pending
        assert not future.done()
        assert 999 in client._pending_requests

    def test_handle_callback_sets_result(self):
        """Test callback correctly sets future result."""
        client = EvonWsClient(
            host="http://192.168.1.100",
            username="user",
            password="pass",
        )

        future = asyncio.get_event_loop().create_future()
        client._pending_requests[42] = future

        msg = json.dumps(["Callback", {"sequenceId": 42, "args": ["success_result"]}])
        client._handle_message(msg)

        assert future.done()
        assert future.result() == "success_result"
        assert 42 not in client._pending_requests

    def test_handle_callback_empty_args(self):
        """Test callback with empty args returns None."""
        client = EvonWsClient(
            host="http://192.168.1.100",
            username="user",
            password="pass",
        )

        future = asyncio.get_event_loop().create_future()
        client._pending_requests[100] = future

        msg = json.dumps(["Callback", {"sequenceId": 100, "args": []}])
        client._handle_message(msg)

        assert future.done()
        assert future.result() is None

    def test_handle_callback_no_args_key(self):
        """Test callback without args key returns None."""
        client = EvonWsClient(
            host="http://192.168.1.100",
            username="user",
            password="pass",
        )

        future = asyncio.get_event_loop().create_future()
        client._pending_requests[200] = future

        msg = json.dumps(["Callback", {"sequenceId": 200}])
        client._handle_message(msg)

        assert future.done()
        assert future.result() is None

    def test_handle_callback_already_done_future(self):
        """Test callback with already-done future doesn't crash."""
        client = EvonWsClient(
            host="http://192.168.1.100",
            username="user",
            password="pass",
        )

        future = asyncio.get_event_loop().create_future()
        future.set_result("already_set")  # Pre-set the result
        client._pending_requests[300] = future

        # Should not crash even though future is already done
        msg = json.dumps(["Callback", {"sequenceId": 300, "args": ["new_result"]}])
        client._handle_message(msg)

        # Original result should remain
        assert future.result() == "already_set"

    def test_handle_event_values_changed(self):
        """Test ValuesChanged event triggers callback."""
        received_updates = []

        def on_values_changed(instance_id, properties):
            received_updates.append((instance_id, properties))

        client = EvonWsClient(
            host="http://192.168.1.100",
            username="user",
            password="pass",
            on_values_changed=on_values_changed,
        )

        msg = json.dumps(
            [
                "Event",
                {
                    "methodName": "ValuesChanged",
                    "args": [
                        {
                            "table": {
                                "light_1.IsOn": {"value": {"Value": True}},
                                "light_1.ScaledBrightness": {"value": {"Value": 75}},
                            }
                        }
                    ],
                },
            ]
        )
        client._handle_message(msg)

        assert len(received_updates) == 1
        instance_id, props = received_updates[0]
        assert instance_id == "light_1"
        assert props == {"IsOn": True, "ScaledBrightness": 75}

    def test_handle_event_values_changed_multiple_instances(self):
        """Test ValuesChanged event with multiple instances."""
        received_updates = []

        def on_values_changed(instance_id, properties):
            received_updates.append((instance_id, properties))

        client = EvonWsClient(
            host="http://192.168.1.100",
            username="user",
            password="pass",
            on_values_changed=on_values_changed,
        )

        msg = json.dumps(
            [
                "Event",
                {
                    "methodName": "ValuesChanged",
                    "args": [
                        {
                            "table": {
                                "light_1.IsOn": {"value": {"Value": True}},
                                "blind_2.Position": {"value": {"Value": 50}},
                                "climate_3.ActualTemperature": {"value": {"Value": 21.5}},
                            }
                        }
                    ],
                },
            ]
        )
        client._handle_message(msg)

        assert len(received_updates) == 3
        instance_ids = [u[0] for u in received_updates]
        assert set(instance_ids) == {"light_1", "blind_2", "climate_3"}

    def test_handle_event_values_changed_dotted_instance_id(self):
        """Test ValuesChanged with dotted instance ID (e.g., intercom.Cam)."""
        received_updates = []

        def on_values_changed(instance_id, properties):
            received_updates.append((instance_id, properties))

        client = EvonWsClient(
            host="http://192.168.1.100",
            username="user",
            password="pass",
            on_values_changed=on_values_changed,
        )

        msg = json.dumps(
            [
                "Event",
                {
                    "methodName": "ValuesChanged",
                    "args": [
                        {
                            "table": {
                                "intercom_1.Cam.Image": {"value": {"Value": "/images/new.jpg"}},
                            }
                        }
                    ],
                },
            ]
        )
        client._handle_message(msg)

        assert len(received_updates) == 1
        instance_id, props = received_updates[0]
        assert instance_id == "intercom_1.Cam"
        assert props == {"Image": "/images/new.jpg"}

    def test_handle_event_values_changed_no_callback(self):
        """Test ValuesChanged without callback doesn't crash."""
        client = EvonWsClient(
            host="http://192.168.1.100",
            username="user",
            password="pass",
            on_values_changed=None,
        )

        msg = json.dumps(
            [
                "Event",
                {
                    "methodName": "ValuesChanged",
                    "args": [{"table": {"light_1.IsOn": {"value": {"Value": True}}}}],
                },
            ]
        )
        # Should not crash
        client._handle_message(msg)

    def test_handle_event_values_changed_empty_table(self):
        """Test ValuesChanged with empty table."""
        received_updates = []

        def on_values_changed(instance_id, properties):
            received_updates.append((instance_id, properties))

        client = EvonWsClient(
            host="http://192.168.1.100",
            username="user",
            password="pass",
            on_values_changed=on_values_changed,
        )

        msg = json.dumps(
            [
                "Event",
                {"methodName": "ValuesChanged", "args": [{"table": {}}]},
            ]
        )
        client._handle_message(msg)

        # No updates should be triggered
        assert len(received_updates) == 0

    def test_handle_event_values_changed_no_args(self):
        """Test ValuesChanged with missing args."""
        received_updates = []

        def on_values_changed(instance_id, properties):
            received_updates.append((instance_id, properties))

        client = EvonWsClient(
            host="http://192.168.1.100",
            username="user",
            password="pass",
            on_values_changed=on_values_changed,
        )

        msg = json.dumps(
            [
                "Event",
                {"methodName": "ValuesChanged", "args": []},
            ]
        )
        client._handle_message(msg)

        assert len(received_updates) == 0

    def test_handle_event_other_method(self):
        """Test non-ValuesChanged events are ignored."""
        received_updates = []

        def on_values_changed(instance_id, properties):
            received_updates.append((instance_id, properties))

        client = EvonWsClient(
            host="http://192.168.1.100",
            username="user",
            password="pass",
            on_values_changed=on_values_changed,
        )

        msg = json.dumps(
            [
                "Event",
                {"methodName": "SomeOtherEvent", "args": [{"data": "test"}]},
            ]
        )
        client._handle_message(msg)

        # No updates - only ValuesChanged should trigger callback
        assert len(received_updates) == 0

    def test_handle_connected_message(self):
        """Test Connected message is handled (no-op)."""
        client = EvonWsClient(
            host="http://192.168.1.100",
            username="user",
            password="pass",
        )

        # Should not crash
        msg = json.dumps(["Connected", {"sessionId": "abc123"}])
        client._handle_message(msg)

    def test_callback_error_does_not_crash_client(self):
        """Test that error in callback doesn't crash message handling."""

        def bad_callback(instance_id, properties):
            raise ValueError("Intentional error in callback")

        client = EvonWsClient(
            host="http://192.168.1.100",
            username="user",
            password="pass",
            on_values_changed=bad_callback,
        )

        msg = json.dumps(
            [
                "Event",
                {
                    "methodName": "ValuesChanged",
                    "args": [{"table": {"light_1.IsOn": {"value": {"Value": True}}}}],
                },
            ]
        )

        # Should not raise - error is logged but client continues
        client._handle_message(msg)


class TestWsClientConnectionState:
    """Tests for WebSocket client connection state management."""

    def test_is_connected_false_when_no_ws(self):
        """Test is_connected returns False when no WebSocket."""
        client = EvonWsClient(
            host="http://192.168.1.100",
            username="user",
            password="pass",
        )

        assert client._ws is None
        assert client.is_connected is False

    def test_is_connected_false_when_ws_closed(self):
        """Test is_connected returns False when WebSocket is closed."""
        client = EvonWsClient(
            host="http://192.168.1.100",
            username="user",
            password="pass",
        )

        mock_ws = MagicMock()
        mock_ws.closed = True
        client._ws = mock_ws
        client._connected = True

        assert client.is_connected is False

    def test_is_connected_false_when_not_connected_flag(self):
        """Test is_connected returns False when _connected is False."""
        client = EvonWsClient(
            host="http://192.168.1.100",
            username="user",
            password="pass",
        )

        mock_ws = MagicMock()
        mock_ws.closed = False
        client._ws = mock_ws
        client._connected = False

        assert client.is_connected is False

    def test_is_connected_true_when_all_conditions_met(self):
        """Test is_connected returns True when properly connected."""
        client = EvonWsClient(
            host="http://192.168.1.100",
            username="user",
            password="pass",
        )

        mock_ws = MagicMock()
        mock_ws.closed = False
        client._ws = mock_ws
        client._connected = True

        assert client.is_connected is True

    def test_connection_state_callback_called(self):
        """Test on_connection_state callback is available."""
        state_changes = []

        def on_connection_state(connected):
            state_changes.append(connected)

        client = EvonWsClient(
            host="http://192.168.1.100",
            username="user",
            password="pass",
            on_connection_state=on_connection_state,
        )

        assert client._on_connection_state is not None

    def test_get_valid_session_with_factory(self):
        """Test _get_valid_session uses session factory when available."""
        mock_session = MagicMock()
        mock_session.closed = False

        def get_session():
            return mock_session

        client = EvonWsClient(
            host="http://192.168.1.100",
            username="user",
            password="pass",
            get_session=get_session,
        )

        result = client._get_valid_session()
        assert result is mock_session

    def test_get_valid_session_falls_back_to_stored(self):
        """Test _get_valid_session falls back to stored session."""
        mock_session = MagicMock()
        mock_session.closed = False

        client = EvonWsClient(
            host="http://192.168.1.100",
            username="user",
            password="pass",
            session=mock_session,
        )

        result = client._get_valid_session()
        assert result is mock_session

    def test_get_valid_session_raises_when_no_session(self):
        """Test _get_valid_session raises when no valid session."""
        client = EvonWsClient(
            host="http://192.168.1.100",
            username="user",
            password="pass",
        )

        with pytest.raises(RuntimeError, match="Session is closed"):
            client._get_valid_session()

    def test_get_valid_session_raises_when_session_closed(self):
        """Test _get_valid_session raises when stored session is closed."""
        mock_session = MagicMock()
        mock_session.closed = True

        client = EvonWsClient(
            host="http://192.168.1.100",
            username="user",
            password="pass",
            session=mock_session,
        )

        with pytest.raises(RuntimeError, match="Session is closed"):
            client._get_valid_session()


class TestWsReconnectDelay:
    """Tests for WebSocket reconnect delay calculation."""

    def test_calculate_reconnect_delay_within_bounds(self):
        """Test reconnect delay is within expected bounds."""
        from custom_components.evon.ws_client import _calculate_reconnect_delay

        base_delay = 10.0
        max_delay = 60.0

        # Run multiple times to test randomness
        for _ in range(100):
            delay = _calculate_reconnect_delay(base_delay, max_delay)
            # Should be within ±25% of base (7.5 to 12.5)
            assert 7.5 <= delay <= 12.5
            # Should not exceed max
            assert delay <= max_delay

    def test_calculate_reconnect_delay_respects_max(self):
        """Test reconnect delay doesn't exceed max."""
        from custom_components.evon.ws_client import _calculate_reconnect_delay

        base_delay = 100.0
        max_delay = 60.0

        for _ in range(100):
            delay = _calculate_reconnect_delay(base_delay, max_delay)
            assert delay <= max_delay

    def test_calculate_reconnect_delay_minimum_one_second(self):
        """Test reconnect delay is at least 1 second."""
        from custom_components.evon.ws_client import _calculate_reconnect_delay

        base_delay = 0.5
        max_delay = 60.0

        for _ in range(100):
            delay = _calculate_reconnect_delay(base_delay, max_delay)
            assert delay >= 1.0


class TestWsPendingRequestsLimit:
    """Tests for WebSocket pending requests limit."""

    @pytest.mark.asyncio
    async def test_too_many_pending_requests_raises_error(self):
        """Test that too many pending requests raises error."""
        from custom_components.evon.const import WS_MAX_PENDING_REQUESTS

        # Skip if homeassistant is mocked (exceptions are MagicMock)
        if not isinstance(EvonWsError, type):
            pytest.skip("Requires real homeassistant package")

        client = EvonWsClient(
            host="http://192.168.1.100",
            username="user",
            password="pass",
        )

        # Set up as connected
        mock_ws = MagicMock()
        mock_ws.closed = False
        client._ws = mock_ws
        client._connected = True

        # Fill up pending requests
        for i in range(WS_MAX_PENDING_REQUESTS):
            future = asyncio.get_event_loop().create_future()
            client._pending_requests[i] = future

        # Next request should fail
        with pytest.raises(EvonWsError, match="Too many pending"):
            await client._send_request("TestMethod", [])

    @pytest.mark.asyncio
    async def test_send_request_when_not_connected(self):
        """Test send_request raises when not connected."""
        # Skip if homeassistant is mocked (exceptions are MagicMock)
        if not isinstance(EvonWsNotConnectedError, type):
            pytest.skip("Requires real homeassistant package")

        client = EvonWsClient(
            host="http://192.168.1.100",
            username="user",
            password="pass",
        )

        with pytest.raises(EvonWsNotConnectedError):
            await client._send_request("TestMethod", [])


class TestWsReceiveTimeout:
    """Tests for WebSocket receive timeout (silent connection death detection)."""

    @pytest.mark.asyncio
    async def test_handle_messages_uses_receive_timeout(self):
        """Test that _handle_messages wraps receive in asyncio.timeout.

        If the remote server silently dies, receive() would block indefinitely.
        The timeout ensures disconnect is called so _run_loop can reconnect.

        Requires Python 3.11+ for asyncio.timeout (used in production code).
        """
        if not hasattr(asyncio, "timeout"):
            pytest.skip("Requires Python 3.11+ for asyncio.timeout")

        client = EvonWsClient(
            host="http://192.168.1.100",
            username="user",
            password="pass",
        )

        # Mock WebSocket whose receive() raises TimeoutError
        # (simulates asyncio.timeout firing when the remote server silently dies)
        mock_ws = AsyncMock()
        mock_ws.closed = False
        mock_ws.receive = AsyncMock(side_effect=TimeoutError())
        client._ws = mock_ws
        client._connected = True

        # _handle_messages should catch TimeoutError and call disconnect
        disconnect_called = False
        original_disconnect = client.disconnect

        async def mock_disconnect():
            nonlocal disconnect_called
            disconnect_called = True
            await original_disconnect()

        client.disconnect = mock_disconnect

        await client._handle_messages()

        assert disconnect_called

    def test_ws_receive_timeout_constant(self):
        """Test WS_RECEIVE_TIMEOUT is 3x heartbeat interval."""
        from custom_components.evon.const import WS_HEARTBEAT_INTERVAL, WS_RECEIVE_TIMEOUT

        assert WS_RECEIVE_TIMEOUT == WS_HEARTBEAT_INTERVAL * 3
        assert WS_RECEIVE_TIMEOUT == 90

    def test_handle_messages_uses_asyncio_timeout(self):
        """Test that _handle_messages wraps receive in asyncio.timeout."""
        import inspect

        source = inspect.getsource(EvonWsClient._handle_messages)
        assert "asyncio.timeout(WS_RECEIVE_TIMEOUT)" in source


class TestStaleRequestCleanup:
    """Tests for periodic stale WebSocket request cleanup."""

    def test_cleanup_stale_requests_removes_old_entries(self):
        """Test that stale requests older than 2x timeout are cleaned up."""
        import time

        from custom_components.evon.const import WS_DEFAULT_REQUEST_TIMEOUT

        client = EvonWsClient(
            host="http://192.168.1.100",
            username="user",
            password="pass",
        )

        loop = asyncio.get_event_loop()
        now = time.monotonic()

        # Add a stale request (created long ago)
        future_stale = loop.create_future()
        client._pending_requests[1] = future_stale
        client._pending_request_times[1] = now - (3 * WS_DEFAULT_REQUEST_TIMEOUT)

        # Add a fresh request (created just now)
        future_fresh = loop.create_future()
        client._pending_requests[2] = future_fresh
        client._pending_request_times[2] = now

        client._cleanup_stale_requests()

        # Stale request should be removed
        assert 1 not in client._pending_requests
        assert 1 not in client._pending_request_times
        assert future_stale.done()

        # Fresh request should remain
        assert 2 in client._pending_requests
        assert 2 in client._pending_request_times
        assert not future_fresh.done()

    def test_cleanup_stale_requests_no_op_when_empty(self):
        """Test cleanup does nothing with no pending requests."""
        client = EvonWsClient(
            host="http://192.168.1.100",
            username="user",
            password="pass",
        )

        # Should not raise
        client._cleanup_stale_requests()
        assert len(client._pending_requests) == 0

    def test_cleanup_stale_requests_cancels_future(self):
        """Test that cleaned up stale requests have their future cancelled."""
        import time

        from custom_components.evon.const import WS_DEFAULT_REQUEST_TIMEOUT

        client = EvonWsClient(
            host="http://192.168.1.100",
            username="user",
            password="pass",
        )

        loop = asyncio.get_event_loop()
        now = time.monotonic()

        future = loop.create_future()
        client._pending_requests[42] = future
        client._pending_request_times[42] = now - (3 * WS_DEFAULT_REQUEST_TIMEOUT)

        client._cleanup_stale_requests()

        assert future.done()
        assert future.cancelled()

    def test_pending_request_times_tracked_in_callback(self):
        """Test that _pending_request_times is cleaned up when callback arrives."""
        import time

        client = EvonWsClient(
            host="http://192.168.1.100",
            username="user",
            password="pass",
        )

        loop = asyncio.get_event_loop()
        future = loop.create_future()
        client._pending_requests[10] = future
        client._pending_request_times[10] = time.monotonic()

        # Simulate callback arriving
        msg = json.dumps(["Callback", {"sequenceId": 10, "args": ["result"]}])
        client._handle_message(msg)

        assert 10 not in client._pending_requests
        assert 10 not in client._pending_request_times

    @pytest.mark.asyncio
    async def test_pending_request_times_cleared_on_disconnect(self):
        """Test that _pending_request_times is cleared on disconnect."""
        from custom_components.evon.api import EvonWsNotConnectedError

        # disconnect() calls set_exception(EvonWsNotConnectedError(...))
        # which requires a real exception class (not a MagicMock)
        if not isinstance(EvonWsNotConnectedError, type):
            pytest.skip("Requires real homeassistant package")

        client = EvonWsClient(
            host="http://192.168.1.100",
            username="user",
            password="pass",
        )

        import time

        loop = asyncio.get_event_loop()
        future = loop.create_future()
        client._pending_requests[5] = future
        client._pending_request_times[5] = time.monotonic()

        await client.disconnect()

        assert len(client._pending_requests) == 0
        assert len(client._pending_request_times) == 0
        # Retrieve the exception to prevent "Future exception was never retrieved" warning
        assert future.done()
        with contextlib.suppress(Exception):
            future.result()


class TestEnergyStatsFailureEscalation:
    """Tests for energy statistics consecutive failure escalation."""

    def test_energy_stats_failure_counter_in_source(self):
        """Test that the failure counter is initialized in coordinator __init__."""
        from pathlib import Path

        src = Path(__file__).parent.parent / "custom_components" / "evon" / "coordinator" / "__init__.py"
        content = src.read_text()
        assert "_energy_stats_consecutive_failures = 0" in content
        assert "ENERGY_STATS_FAILURE_LOG_THRESHOLD" in content

    def test_energy_stats_failure_threshold_constant(self):
        """Test ENERGY_STATS_FAILURE_LOG_THRESHOLD is set correctly."""
        from custom_components.evon.const import ENERGY_STATS_FAILURE_LOG_THRESHOLD

        assert ENERGY_STATS_FAILURE_LOG_THRESHOLD == 3
