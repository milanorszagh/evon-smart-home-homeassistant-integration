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
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import EvonDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

# Evon preset modes
PRESET_COMFORT = "comfort"
PRESET_ENERGY_SAVING = "energy_saving"
PRESET_FREEZE_PROTECTION = "freeze_protection"

PRESET_MODES = [PRESET_COMFORT, PRESET_ENERGY_SAVING, PRESET_FREEZE_PROTECTION]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Evon climate entities from a config entry."""
    coordinator: EvonDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    api = hass.data[DOMAIN][entry.entry_id]["api"]

    entities = []
    if coordinator.data and "climates" in coordinator.data:
        for climate in coordinator.data["climates"]:
            entities.append(EvonClimate(coordinator, api, climate["id"], climate["name"]))

    async_add_entities(entities)


class EvonClimate(CoordinatorEntity[EvonDataUpdateCoordinator], ClimateEntity):
    """Representation of an Evon climate control."""

    _attr_has_entity_name = True
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.PRESET_MODE
    )
    _attr_preset_modes = PRESET_MODES
    _enable_turn_on_off_backwards_compat = False

    def __init__(
        self,
        coordinator: EvonDataUpdateCoordinator,
        api,
        instance_id: str,
        name: str,
    ) -> None:
        """Initialize the climate entity."""
        super().__init__(coordinator)
        self._api = api
        self._instance_id = instance_id
        self._attr_name = name
        self._attr_unique_id = f"evon_climate_{instance_id}"
        self._current_preset = PRESET_COMFORT

    @property
    def hvac_mode(self) -> HVACMode:
        """Return current HVAC mode."""
        # Evon climate is always heating, use preset for freeze protection as "off-like"
        if self._current_preset == PRESET_FREEZE_PROTECTION:
            return HVACMode.OFF
        return HVACMode.HEAT

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        data = self.coordinator.get_climate_data(self._instance_id)
        if data:
            return data.get("current_temperature")
        return None

    @property
    def target_temperature(self) -> float | None:
        """Return the target temperature."""
        data = self.coordinator.get_climate_data(self._instance_id)
        if data:
            return data.get("target_temperature")
        return None

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        data = self.coordinator.get_climate_data(self._instance_id)
        if data:
            return data.get("min_temp", 15)
        return 15

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        data = self.coordinator.get_climate_data(self._instance_id)
        if data:
            return data.get("max_temp", 25)
        return 25

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode."""
        return self._current_preset

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target HVAC mode."""
        if hvac_mode == HVACMode.OFF:
            await self._api.set_climate_freeze_protection_mode(self._instance_id)
            self._current_preset = PRESET_FREEZE_PROTECTION
        else:
            await self._api.set_climate_comfort_mode(self._instance_id)
            self._current_preset = PRESET_COMFORT
        await self.coordinator.async_request_refresh()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if ATTR_TEMPERATURE in kwargs:
            await self._api.set_climate_temperature(
                self._instance_id, kwargs[ATTR_TEMPERATURE]
            )
            await self.coordinator.async_request_refresh()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        if preset_mode == PRESET_COMFORT:
            await self._api.set_climate_comfort_mode(self._instance_id)
        elif preset_mode == PRESET_ENERGY_SAVING:
            await self._api.set_climate_energy_saving_mode(self._instance_id)
        elif preset_mode == PRESET_FREEZE_PROTECTION:
            await self._api.set_climate_freeze_protection_mode(self._instance_id)

        self._current_preset = preset_mode
        await self.coordinator.async_request_refresh()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()
