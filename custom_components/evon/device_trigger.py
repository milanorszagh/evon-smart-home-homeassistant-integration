"""Device triggers for Evon Smart Home integration."""

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

from .const import DOMAIN, ENTITY_TYPE_BUTTON_EVENTS, ENTITY_TYPE_INTERCOMS

# Trigger types
TRIGGER_TYPE_DOORBELL = "doorbell"
TRIGGER_TYPE_BUTTON_SINGLE = "button_single_press"
TRIGGER_TYPE_BUTTON_DOUBLE = "button_double_press"
TRIGGER_TYPE_BUTTON_LONG = "button_long_press"

TRIGGER_TYPES = {
    TRIGGER_TYPE_DOORBELL,
    TRIGGER_TYPE_BUTTON_SINGLE,
    TRIGGER_TYPE_BUTTON_DOUBLE,
    TRIGGER_TYPE_BUTTON_LONG,
}

# Map trigger types to bus event press_type values
_BUTTON_TRIGGER_TO_PRESS_TYPE = {
    TRIGGER_TYPE_BUTTON_SINGLE: "single_press",
    TRIGGER_TYPE_BUTTON_DOUBLE: "double_press",
    TRIGGER_TYPE_BUTTON_LONG: "long_press",
}

TRIGGER_SCHEMA = DEVICE_TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): vol.In(TRIGGER_TYPES),
    }
)


def _find_instance_in_data(
    hass: HomeAssistant,
    device: dr.DeviceEntry,
    entity_type: str,
) -> str | None:
    """Find instance_id for a device in coordinator data of given entity_type."""
    for identifier in device.identifiers:
        if identifier[0] == DOMAIN:
            instance_id = identifier[1]
            for entry_id in device.config_entries:
                entry_data = hass.data.get(DOMAIN, {}).get(entry_id, {})
                if entry_data:
                    coordinator = entry_data.get("coordinator")
                    if coordinator and coordinator.data:
                        entities = coordinator.data.get(entity_type, [])
                        for entity in entities:
                            if entity.get("id") == instance_id:
                                return instance_id
    return None


async def async_get_triggers(hass: HomeAssistant, device_id: str) -> list[dict[str, Any]]:
    """Return a list of triggers for a device."""
    device_registry = dr.async_get(hass)
    device = device_registry.async_get(device_id)

    if device is None:
        return []

    triggers = []

    # Check if this is an intercom device (has doorbell capability)
    if _find_instance_in_data(hass, device, ENTITY_TYPE_INTERCOMS):
        triggers.append(
            {
                CONF_PLATFORM: "device",
                CONF_DOMAIN: DOMAIN,
                CONF_DEVICE_ID: device_id,
                CONF_TYPE: TRIGGER_TYPE_DOORBELL,
            }
        )

    # Check if this is a button device
    if _find_instance_in_data(hass, device, ENTITY_TYPE_BUTTON_EVENTS):
        for trigger_type in (
            TRIGGER_TYPE_BUTTON_SINGLE,
            TRIGGER_TYPE_BUTTON_DOUBLE,
            TRIGGER_TYPE_BUTTON_LONG,
        ):
            triggers.append(
                {
                    CONF_PLATFORM: "device",
                    CONF_DOMAIN: DOMAIN,
                    CONF_DEVICE_ID: device_id,
                    CONF_TYPE: trigger_type,
                }
            )

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

    # Get the instance_id from device identifiers
    instance_id = None
    for identifier in device.identifiers:
        if identifier[0] == DOMAIN:
            instance_id = identifier[1]
            break

    if instance_id is None:
        return lambda: None

    trigger_type = config[CONF_TYPE]

    if trigger_type == TRIGGER_TYPE_DOORBELL:
        event_config = {
            event_trigger.CONF_PLATFORM: "event",
            event_trigger.CONF_EVENT_TYPE: f"{DOMAIN}_doorbell",
            event_trigger.CONF_EVENT_DATA: {
                "device_id": instance_id,
            },
        }
    elif trigger_type in _BUTTON_TRIGGER_TO_PRESS_TYPE:
        event_config = {
            event_trigger.CONF_PLATFORM: "event",
            event_trigger.CONF_EVENT_TYPE: f"{DOMAIN}_button_press",
            event_trigger.CONF_EVENT_DATA: {
                "device_id": instance_id,
                "press_type": _BUTTON_TRIGGER_TO_PRESS_TYPE[trigger_type],
            },
        }
    else:
        return lambda: None

    return await event_trigger.async_attach_trigger(hass, event_config, action, trigger_info, platform_type="device")


async def async_get_trigger_capabilities(hass: HomeAssistant, config: ConfigType) -> dict[str, vol.Schema]:
    """Return trigger capabilities."""
    return {}
