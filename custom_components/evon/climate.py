"""Climate platform for Evon Smart Home integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
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
    EVON_PRESET_COOLING,
    EVON_PRESET_HEATING,
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
        # Optimistic state to prevent UI flicker during updates
        self._optimistic_preset: str | None = None
        self._optimistic_target_temp: float | None = None
        self._optimistic_hvac_mode: HVACMode | None = None

    @property
    def hvac_modes(self) -> list[HVACMode]:
        """Return the list of available HVAC modes."""
        data = self.coordinator.get_entity_data("climates", self._instance_id)
        if data and data.get("cooling_enabled"):
            return [HVACMode.HEAT, HVACMode.COOL, HVACMode.OFF]
        return [HVACMode.HEAT, HVACMode.OFF]

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for this climate control."""
        return self._build_device_info("Climate Control")

    @property
    def hvac_mode(self) -> HVACMode:
        """Return current HVAC mode."""
        # Return optimistic value if set (prevents UI flicker during updates)
        if self._optimistic_hvac_mode is not None:
            return self._optimistic_hvac_mode

        data = self.coordinator.get_entity_data("climates", self._instance_id)
        if not data:
            return HVACMode.OFF

        # Check if climate is actively running
        is_on = data.get("is_on", False)
        if not is_on:
            return HVACMode.OFF

        # Check if in cooling or heating mode
        is_cooling = data.get("is_cooling", False)
        if is_cooling:
            return HVACMode.COOL
        return HVACMode.HEAT

    @property
    def hvac_action(self) -> HVACAction | None:
        """Return the current running hvac action (heating, cooling, idle).

        This indicates whether the climate system is actively heating/cooling
        or idle (target temperature reached). Based on Evon's IsOn property.
        """
        data = self.coordinator.get_entity_data("climates", self._instance_id)
        if not data:
            return None

        is_on = data.get("is_on", False)
        if not is_on:
            return HVACAction.IDLE

        # Actively heating or cooling based on season mode
        is_cooling_season = self.coordinator.get_season_mode()
        return HVACAction.COOLING if is_cooling_season else HVACAction.HEATING

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
        # Return optimistic value if set (prevents UI flicker during updates)
        if self._optimistic_target_temp is not None:
            return self._optimistic_target_temp

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
        """Return the current preset mode based on Evon's ModeSaved property.

        Note: ModeSaved values differ based on Season Mode:
        - HEATING (winter): 2=away, 3=eco, 4=comfort
        - COOLING (summer): 5=away, 6=eco, 7=comfort
        """
        # Return optimistic value if set (prevents UI flicker during updates)
        if self._optimistic_preset is not None:
            return self._optimistic_preset

        data = self.coordinator.get_entity_data("climates", self._instance_id)
        if not data:
            return CLIMATE_MODE_COMFORT

        mode_saved = data.get("mode_saved", 4)

        # Use appropriate mapping based on season mode
        is_cooling = self.coordinator.get_season_mode()
        if is_cooling:
            return EVON_PRESET_COOLING.get(mode_saved, CLIMATE_MODE_COMFORT)
        return EVON_PRESET_HEATING.get(mode_saved, CLIMATE_MODE_COMFORT)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        data = self.coordinator.get_entity_data("climates", self._instance_id)
        attrs = {}
        if data:
            is_cooling = self.coordinator.get_season_mode()
            attrs["comfort_temperature"] = data.get("comfort_temp")
            attrs["eco_temperature"] = data.get("energy_saving_temp")
            attrs["protection_temperature"] = data.get("protection_temp")
            attrs["evon_mode_saved"] = data.get("mode_saved")
            attrs["season_mode"] = "cooling" if is_cooling else "heating"
            attrs["cooling_enabled"] = data.get("cooling_enabled")
            attrs["evon_id"] = self._instance_id
        return attrs

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target HVAC mode."""
        # Set optimistic value immediately to prevent UI flicker
        self._optimistic_hvac_mode = hvac_mode
        self.async_write_ha_state()

        if hvac_mode == HVACMode.OFF:
            await self._api.set_climate_freeze_protection_mode(self._instance_id)
        else:
            await self._api.set_climate_comfort_mode(self._instance_id)
        await self.coordinator.async_request_refresh()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if ATTR_TEMPERATURE in kwargs:
            temperature = kwargs[ATTR_TEMPERATURE]
            # Set optimistic value immediately to prevent UI flicker
            self._optimistic_target_temp = temperature
            self.async_write_ha_state()

            await self._api.set_climate_temperature(self._instance_id, temperature)
            await self.coordinator.async_request_refresh()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        # Set optimistic values immediately to prevent UI flicker
        self._optimistic_preset = preset_mode

        # Set optimistic target temperature based on preset
        data = self.coordinator.get_entity_data("climates", self._instance_id)
        if data:
            if preset_mode == CLIMATE_MODE_COMFORT:
                self._optimistic_target_temp = data.get("comfort_temp")
            elif preset_mode == CLIMATE_MODE_ENERGY_SAVING:
                self._optimistic_target_temp = data.get("energy_saving_temp")
            elif preset_mode == CLIMATE_MODE_FREEZE_PROTECTION:
                self._optimistic_target_temp = data.get("protection_temp")

        self.async_write_ha_state()

        if preset_mode == CLIMATE_MODE_COMFORT:
            await self._api.set_climate_comfort_mode(self._instance_id)
        elif preset_mode == CLIMATE_MODE_ENERGY_SAVING:
            await self._api.set_climate_energy_saving_mode(self._instance_id)
        elif preset_mode == CLIMATE_MODE_FREEZE_PROTECTION:
            await self._api.set_climate_freeze_protection_mode(self._instance_id)
        await self.coordinator.async_request_refresh()

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        # Only clear optimistic state when coordinator data matches expected value
        data = self.coordinator.get_entity_data("climates", self._instance_id)
        if data:
            if self._optimistic_preset is not None:
                mode_saved = data.get("mode_saved", 4)
                # Use appropriate mapping based on season mode
                is_cooling = self.coordinator.get_season_mode()
                if is_cooling:
                    actual_preset = EVON_PRESET_COOLING.get(mode_saved, CLIMATE_MODE_COMFORT)
                else:
                    actual_preset = EVON_PRESET_HEATING.get(mode_saved, CLIMATE_MODE_COMFORT)
                if actual_preset == self._optimistic_preset:
                    self._optimistic_preset = None

            if self._optimistic_target_temp is not None:
                actual_temp = data.get("target_temperature")
                if actual_temp == self._optimistic_target_temp:
                    self._optimistic_target_temp = None

            if self._optimistic_hvac_mode is not None:
                # Determine actual HVAC mode from coordinator data
                is_on = data.get("is_on", False)
                if not is_on:
                    actual_hvac_mode = HVACMode.OFF
                elif data.get("is_cooling", False):
                    actual_hvac_mode = HVACMode.COOL
                else:
                    actual_hvac_mode = HVACMode.HEAT

                if actual_hvac_mode == self._optimistic_hvac_mode:
                    self._optimistic_hvac_mode = None

        super()._handle_coordinator_update()
