"""Switch platform for Evon Smart Home integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, EVENT_SINGLE_CLICK, EVENT_DOUBLE_CLICK, EVENT_LONG_PRESS
from .coordinator import EvonDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Evon switches from a config entry."""
    coordinator: EvonDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    api = hass.data[DOMAIN][entry.entry_id]["api"]

    entities = []
    if coordinator.data and "switches" in coordinator.data:
        for switch in coordinator.data["switches"]:
            entities.append(EvonSwitch(
                coordinator,
                api,
                switch["id"],
                switch["name"],
                switch.get("room_name", ""),
                entry,
            ))

    async_add_entities(entities)


class EvonSwitch(CoordinatorEntity[EvonDataUpdateCoordinator], SwitchEntity):
    """Representation of an Evon switch."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: EvonDataUpdateCoordinator,
        api,
        instance_id: str,
        name: str,
        room_name: str,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self._api = api
        self._instance_id = instance_id
        self._attr_name = None  # Use device name
        self._attr_unique_id = f"evon_switch_{instance_id}"
        self._device_name = name
        self._room_name = room_name
        self._entry = entry
        self._last_click: str | None = None

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for this switch."""
        info = DeviceInfo(
            identifiers={(DOMAIN, self._instance_id)},
            name=self._device_name,
            manufacturer="Evon",
            model="Switch",
            via_device=(DOMAIN, self._entry.entry_id),
        )
        if self._room_name:
            info["suggested_area"] = self._room_name
        return info

    @property
    def is_on(self) -> bool:
        """Return true if the switch is on."""
        data = self.coordinator.get_switch_data(self._instance_id)
        if data:
            return data.get("is_on", False)
        return False

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        data = self.coordinator.get_switch_data(self._instance_id)
        attrs = {}
        if data:
            last_click = data.get("last_click")
            if last_click:
                attrs["last_click_type"] = last_click
        return attrs

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch."""
        await self._api.turn_on_switch(self._instance_id)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch."""
        await self._api.turn_off_switch(self._instance_id)
        await self.coordinator.async_request_refresh()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        # Check for click events
        data = self.coordinator.get_switch_data(self._instance_id)
        if data:
            new_click = data.get("last_click")
            if new_click and new_click != self._last_click:
                self._last_click = new_click
                # Fire event for button press
                event_type = self._map_click_event(new_click)
                if event_type:
                    self.hass.bus.async_fire(
                        f"{DOMAIN}_event",
                        {
                            "device_id": self._instance_id,
                            "device_name": self._device_name,
                            "event_type": event_type,
                        },
                    )
                    _LOGGER.debug(
                        "Fired %s event for %s", event_type, self._device_name
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
        return click_type
