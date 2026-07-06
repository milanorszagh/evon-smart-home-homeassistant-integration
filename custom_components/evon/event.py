"""Event platform for Evon Smart Home integration."""

from __future__ import annotations

from homeassistant.components.event import EventDeviceClass, EventEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .base_entity import EvonEntity
from .const import DOMAIN, ENTITY_TYPE_BUTTON_EVENTS, ENTITY_TYPE_INTERCOMS
from .coordinator import EvonDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Evon event entities from a config entry."""
    coordinator: EvonDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    entities: list[EventEntity] = []

    if coordinator.data and ENTITY_TYPE_INTERCOMS in coordinator.data:
        for intercom in coordinator.data[ENTITY_TYPE_INTERCOMS]:
            entities.append(
                EvonDoorbellEvent(
                    coordinator,
                    intercom["id"],
                    intercom["name"],
                    intercom.get("room_name", ""),
                    entry,
                )
            )

    if coordinator.data and ENTITY_TYPE_BUTTON_EVENTS in coordinator.data:
        for button in coordinator.data[ENTITY_TYPE_BUTTON_EVENTS]:
            entities.append(
                EvonButtonEvent(
                    coordinator,
                    button["id"],
                    button["name"],
                    button.get("room_name", ""),
                    entry,
                )
            )

    if entities:
        async_add_entities(entities)


class EvonDoorbellEvent(EvonEntity, EventEntity):
    """Event entity for Evon 2N intercom doorbell press."""

    _attr_device_class = EventDeviceClass.DOORBELL
    _attr_event_types = ["ring"]
    _attr_translation_key = "doorbell"
    _entity_type = ENTITY_TYPE_INTERCOMS

    def __init__(
        self,
        coordinator: EvonDataUpdateCoordinator,
        instance_id: str,
        name: str,
        room_name: str,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the event entity."""
        super().__init__(coordinator, instance_id, name, room_name, entry)
        self._attr_unique_id = f"evon_doorbell_{instance_id}"
        self._last_doorbell_state: bool = False

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return self._build_device_info("Intercom")

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        data = self._get_data()
        if data is None:
            super()._handle_coordinator_update()
            return

        current_state = data.get("doorbell_triggered", False)

        # Fire event on False -> True transition only
        if current_state and not self._last_doorbell_state:
            self._trigger_event("ring")

        self._last_doorbell_state = current_state
        super()._handle_coordinator_update()


class EvonButtonEvent(EvonEntity, EventEntity):
    """Event entity for Evon physical wall button (Taster) press events."""

    _attr_device_class = EventDeviceClass.BUTTON
    _attr_event_types = ["single_press", "double_press", "long_press"]
    _attr_translation_key = "button"
    _entity_type = ENTITY_TYPE_BUTTON_EVENTS

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
        self._attr_unique_id = f"evon_button_{instance_id}"
        self._last_event_id: int = 0

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return self._build_device_info("Button")

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        data = self._get_data()
        if data is None:
            super()._handle_coordinator_update()
            return

        current_event_type = data.get("last_event_type")
        current_event_id = data.get("last_event_id", 0)

        # Fire the event when the coordinator's monotonic counter advances.
        if current_event_type and current_event_id != self._last_event_id:
            self._trigger_event(current_event_type)

        # Always resync to the coordinator's counter — including the reset to 0
        # that every HTTP safety-net poll performs when it rebuilds the button
        # dict (last_event_id=0, last_event_type=None). Without resyncing on the
        # reset, a stored id of 1 collides with the next press — which
        # re-increments 0->1 — so `1 != 1` is False and the press is silently
        # dropped. This is the common "one press, pause, one press" pattern.
        self._last_event_id = current_event_id

        super()._handle_coordinator_update()
