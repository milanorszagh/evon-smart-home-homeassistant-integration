"""Climate platform for Evon Smart Home integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import EvonApi
from .base_entity import EvonEntity
from .const import (
    CLIMATE_MODE_COMFORT,
    CLIMATE_MODE_ENERGY_SAVING,
    CLIMATE_MODE_FREEZE_PROTECTION,
    DOMAIN,
)
from .coordinator import EvonDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

# Preset modes list
PRESET_MODES = [CLIMATE_MODE_COMFORT, CLIMATE_MODE_ENERGY_SAVING, CLIMATE_MODE_FREEZE_PROTECTION]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Evon climate entities from a config entry."""
    coordinator: EvonDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    api: EvonApi = hass.data[DOMAIN][entry.entry_id]["api"]

    entities = []
    if coordinator.data and "climates" in coordinator.data:
        for climate in coordinator.data["climates"]:
            entities.append(
                EvonClimate(
                    coordinator,
                    climate["id"],
                    climate["name"],
                    climate.get("room_name", ""),
                    entry,
                    api,
                )
            )

    async_add_entities(entities)


class EvonClimate(EvonEntity, ClimateEntity):
    """Representation of an Evon climate control."""

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF]
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.PRESET_MODE
    _attr_preset_modes = PRESET_MODES
    _enable_turn_on_off_backwards_compat = False

    def __init__(
        self,
        coordinator: EvonDataUpdateCoordinator,
        instance_id: str,
        name: str,
        room_name: str,
        entry: ConfigEntry,
        api: EvonApi,
    ) -> None:
        """Initialize the climate entity."""
        super().__init__(coordinator, instance_id, name, room_name, entry, api)
        self._attr_name = None  # Use device name
        self._attr_unique_id = f"evon_climate_{instance_id}"
        self._current_preset = CLIMATE_MODE_COMFORT

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for this climate control."""
        return self._build_device_info("Climate Control")

    @property
    def hvac_mode(self) -> HVACMode:
        """Return current HVAC mode."""
        # Evon climate is always heating, use preset for freeze protection as "off-like"
        if self._current_preset == CLIMATE_MODE_FREEZE_PROTECTION:
            return HVACMode.OFF
        return HVACMode.HEAT

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        data = self.coordinator.get_entity_data("climates", self._instance_id)
        if data:
            return data.get("current_temperature")
        return None

    @property
    def target_temperature(self) -> float | None:
        """Return the target temperature."""
        data = self.coordinator.get_entity_data("climates", self._instance_id)
        if data:
            return data.get("target_temperature")
        return None

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        data = self.coordinator.get_entity_data("climates", self._instance_id)
        if data:
            return data.get("min_temp", 15)
        return 15

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        data = self.coordinator.get_entity_data("climates", self._instance_id)
        if data:
            return data.get("max_temp", 25)
        return 25

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode."""
        return self._current_preset

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        data = self.coordinator.get_entity_data("climates", self._instance_id)
        attrs = {}
        if data:
            attrs["comfort_temperature"] = data.get("comfort_temp")
            attrs["energy_saving_temperature"] = data.get("energy_saving_temp")
            attrs["freeze_protection_temperature"] = data.get("freeze_protection_temp")
            attrs["evon_id"] = self._instance_id
        return attrs

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target HVAC mode."""
        if hvac_mode == HVACMode.OFF:
            await self._api.set_climate_freeze_protection_mode(self._instance_id)
            self._current_preset = CLIMATE_MODE_FREEZE_PROTECTION
        else:
            await self._api.set_climate_comfort_mode(self._instance_id)
            self._current_preset = CLIMATE_MODE_COMFORT
        await self.coordinator.async_request_refresh()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if ATTR_TEMPERATURE in kwargs:
            await self._api.set_climate_temperature(self._instance_id, kwargs[ATTR_TEMPERATURE])
            await self.coordinator.async_request_refresh()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        if preset_mode == CLIMATE_MODE_COMFORT:
            await self._api.set_climate_comfort_mode(self._instance_id)
        elif preset_mode == CLIMATE_MODE_ENERGY_SAVING:
            await self._api.set_climate_energy_saving_mode(self._instance_id)
        elif preset_mode == CLIMATE_MODE_FREEZE_PROTECTION:
            await self._api.set_climate_freeze_protection_mode(self._instance_id)

        self._current_preset = preset_mode
        await self.coordinator.async_request_refresh()
