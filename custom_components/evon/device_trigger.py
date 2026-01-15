"""Device triggers for Evon Smart Home switches."""

from __future__ import annotations

from typing import Any

from homeassistant.components.device_automation import DEVICE_TRIGGER_BASE_SCHEMA
from homeassistant.components.homeassistant.triggers import event as event_trigger
from homeassistant.const import CONF_DEVICE_ID, CONF_DOMAIN, CONF_PLATFORM, CONF_TYPE
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.trigger import TriggerActionType, TriggerInfo
from homeassistant.helpers.typing import ConfigType
import voluptuous as vol

from .const import (
    DOMAIN,
    EVENT_DOUBLE_CLICK,
    EVENT_LONG_PRESS,
    EVENT_SINGLE_CLICK,
)

TRIGGER_TYPES = {EVENT_SINGLE_CLICK, EVENT_DOUBLE_CLICK, EVENT_LONG_PRESS}

TRIGGER_SCHEMA = DEVICE_TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): vol.In(TRIGGER_TYPES),
    }
)


async def async_get_triggers(hass: HomeAssistant, device_id: str) -> list[dict[str, Any]]:
    """List device triggers for Evon switches."""
    device_registry = dr.async_get(hass)
    device = device_registry.async_get(device_id)

    if device is None:
        return []

    # Check if this is an Evon switch device
    triggers = []
    for entry_id in device.config_entries:
        if entry_id not in hass.data.get(DOMAIN, {}):
            continue

        coordinator = hass.data[DOMAIN][entry_id].get("coordinator")
        if coordinator is None or coordinator.data is None:
            continue

        # Check if device is a switch
        for identifier in device.identifiers:
            if identifier[0] != DOMAIN:
                continue

            instance_id = identifier[1]
            switch_data = coordinator.get_switch_data(instance_id)
            if switch_data:
                # This is a switch, add triggers
                for trigger_type in TRIGGER_TYPES:
                    triggers.append(
                        {
                            CONF_PLATFORM: "device",
                            CONF_DEVICE_ID: device_id,
                            CONF_DOMAIN: DOMAIN,
                            CONF_TYPE: trigger_type,
                        }
                    )
                break

    return triggers


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: TriggerActionType,
    trigger_info: TriggerInfo,
) -> CALLBACK_TYPE:
    """Attach a trigger."""
    device_registry = dr.async_get(hass)
    device = device_registry.async_get(config[CONF_DEVICE_ID])

    if device is None:
        return lambda: None

    # Get the Evon instance ID from device identifiers
    instance_id = None
    for identifier in device.identifiers:
        if identifier[0] == DOMAIN:
            instance_id = identifier[1]
            break

    if instance_id is None:
        return lambda: None

    event_config = {
        event_trigger.CONF_PLATFORM: "event",
        event_trigger.CONF_EVENT_TYPE: f"{DOMAIN}_event",
        event_trigger.CONF_EVENT_DATA: {
            "device_id": instance_id,
            "event_type": config[CONF_TYPE],
        },
    }

    return await event_trigger.async_attach_trigger(hass, event_config, action, trigger_info, platform_type="device")
