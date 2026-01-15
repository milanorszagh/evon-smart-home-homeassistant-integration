"""Event platform for Evon Smart Home integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.event import EventEntity, EventDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .base_entity import EvonEntity
from .const import (
    DOMAIN,
    EVENT_SINGLE_CLICK,
    EVENT_DOUBLE_CLICK,
    EVENT_LONG_PRESS,
)
from .coordinator import EvonDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

# Event types that this entity can fire
BUTTON_EVENT_TYPES = [EVENT_SINGLE_CLICK, EVENT_DOUBLE_CLICK, EVENT_LONG_PRESS]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Evon button events from a config entry."""
    coordinator: EvonDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    entities = []
    if coordinator.data and "buttons" in coordinator.data:
        for button in coordinator.data["buttons"]:
            entities.append(EvonButtonEvent(
                coordinator,
                button["id"],
                button["name"],
                button.get("room_name", ""),
                entry,
            ))

    async_add_entities(entities)


class EvonButtonEvent(EvonEntity, EventEntity):
    """Representation of an Evon physical button as an event entity."""

    _attr_device_class = EventDeviceClass.BUTTON
    _attr_event_types = BUTTON_EVENT_TYPES

    def __init__(
        self,
        coordinator: EvonDataUpdateCoordinator,
        instance_id: str,
        name: str,
        room_name: str,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the button event entity."""
        super().__init__(coordinator, instance_id, name, room_name, entry)
        self._attr_name = None  # Use device name
        self._attr_unique_id = f"evon_button_{instance_id}"
        self._last_click: str | None = None

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for this button."""
        return self._build_device_info("Button")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        return {"evon_id": self._instance_id}

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        data = self.coordinator.get_entity_data("buttons", self._instance_id)
        if data:
            new_click = data.get("last_click")
            if new_click and new_click != self._last_click:
                self._last_click = new_click
                # Map Evon click type to event type and trigger
                event_type = self._map_click_event(new_click)
                if event_type:
                    self._trigger_event(event_type)
                    _LOGGER.debug(
                        "Triggered %s event for button %s", event_type, self._device_name
                    )
        self.async_write_ha_state()

    def _map_click_event(self, click_type: str | None) -> str | None:
        """Map Evon click type to event type."""
        if not click_type:
            return None
        click_lower = click_type.lower()
        if "double" in click_lower:
            return EVENT_DOUBLE_CLICK
        elif "long" in click_lower:
            return EVENT_LONG_PRESS
        elif "single" in click_lower or "click" in click_lower:
            return EVENT_SINGLE_CLICK
        return None
