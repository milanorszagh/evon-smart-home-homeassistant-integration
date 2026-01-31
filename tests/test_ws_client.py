"""Tests for the WebSocket client."""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from custom_components.evon.ws_client import (
    EvonWsClient,
    WS_MSG_CALLBACK,
    WS_MSG_CONNECTED,
    WS_MSG_EVENT,
)
from custom_components.evon.ws_mappings import (
    CLASS_TO_TYPE,
    PROPERTY_MAPPINGS,
    SUBSCRIBE_PROPERTIES,
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
        assert get_entity_type("ClimateControlUniversal") == "climates"

    def test_class_to_type_home_states(self):
        """Test home state class mappings."""
        assert get_entity_type("System.HomeState") == "home_states"

    def test_class_to_type_bathroom_radiators(self):
        """Test bathroom radiator class mappings."""
        assert get_entity_type("Heating.BathroomRadiator") == "bathroom_radiators"

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
        assert coord == {"target_temp": 22.5, "current_temp": 21.0, "mode_saved": 4}

    def test_ws_to_coordinator_data_home_states(self):
        """Test home state property conversion."""
        ws_props = {"Active": True}
        coord = ws_to_coordinator_data("home_states", ws_props)
        assert coord == {"active": True}

    def test_ws_to_coordinator_data_bathroom_radiators(self):
        """Test bathroom radiator property conversion."""
        ws_props = {"Output": True, "NextSwitchPoint": 1800}
        coord = ws_to_coordinator_data("bathroom_radiators", ws_props)
        assert coord == {"is_on": True, "next_switch_point": 1800}

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
        message = json.dumps([
            "Callback",
            {"sequenceId": 1, "args": ["result_value"]}
        ])
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

        message = json.dumps([
            "Event",
            {
                "methodName": "ValuesChanged",
                "args": [{"table": {"Light1.IsOn": {"value": {"Value": True}}}}]
            }
        ])
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
