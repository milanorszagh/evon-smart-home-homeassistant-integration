"""Climate platform for Evon Smart Home integration."""

from __future__ import annotations

import time
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
    DEFAULT_MAX_TEMP,
    DEFAULT_MIN_TEMP,
    DOMAIN,
    ENTITY_TYPE_CLIMATES,
    EVON_PRESET_COOLING,
    EVON_PRESET_HEATING,
    OPTIMISTIC_STATE_TIMEOUT,
)
from .coordinator import EvonDataUpdateCoordinator

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
    if coordinator.data and ENTITY_TYPE_CLIMATES in coordinator.data:
        for climate in coordinator.data[ENTITY_TYPE_CLIMATES]:
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

    if entities:
        async_add_entities(entities)


class EvonClimate(EvonEntity, ClimateEntity):
    """Representation of an Evon climate control."""

    _attr_icon = "mdi:thermostat"
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
        # Timestamp when optimistic state was set (for timeout-based clearance)
        self._optimistic_state_set_at: float | None = None

    def _clear_optimistic_state_if_expired(self) -> None:
        """Clear optimistic state if timeout has expired.

        This prevents stale UI state when recovering from network issues.
        If the coordinator hasn't confirmed the state within the timeout period,
        we clear the optimistic state so the UI shows real device state.
        """
        if (
            self._optimistic_state_set_at is not None
            and time.monotonic() - self._optimistic_state_set_at > OPTIMISTIC_STATE_TIMEOUT
        ):
            self._optimistic_preset = None
            self._optimistic_target_temp = None
            self._optimistic_hvac_mode = None
            self._optimistic_state_set_at = None

    @property
    def hvac_modes(self) -> list[HVACMode]:
        """Return the list of available HVAC modes."""
        data = self.coordinator.get_entity_data(ENTITY_TYPE_CLIMATES, self._instance_id)
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
        # Clear expired optimistic state to prevent stale UI on network recovery
        self._clear_optimistic_state_if_expired()

        # Return optimistic value if set (prevents UI flicker during updates)
        if self._optimistic_hvac_mode is not None:
            return self._optimistic_hvac_mode

        data = self.coordinator.get_entity_data(ENTITY_TYPE_CLIMATES, self._instance_id)
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
        data = self.coordinator.get_entity_data(ENTITY_TYPE_CLIMATES, self._instance_id)
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
        data = self.coordinator.get_entity_data(ENTITY_TYPE_CLIMATES, self._instance_id)
        if data:
            return data.get("current_temperature")
        return None

    @property
    def current_humidity(self) -> int | None:
        """Return the current humidity."""
        data = self.coordinator.get_entity_data(ENTITY_TYPE_CLIMATES, self._instance_id)
        if data and data.get("humidity") is not None:
            return int(data["humidity"])
        return None

    @property
    def target_temperature(self) -> float | None:
        """Return the target temperature.

        Note: Evon may store temperatures outside the device's min/max range
        (e.g., freeze protection at 15°C when min_temp is 18°C). We clamp
        the displayed value to the allowed range to show the effective target.
        """
        # Clear expired optimistic state to prevent stale UI on network recovery
        self._clear_optimistic_state_if_expired()

        # Return optimistic value if set (prevents UI flicker during updates)
        if self._optimistic_target_temp is not None:
            return self._optimistic_target_temp

        data = self.coordinator.get_entity_data(ENTITY_TYPE_CLIMATES, self._instance_id)
        if data:
            temp = data.get("target_temperature")
            if temp is not None:
                # Clamp to min/max range - Evon may store values outside allowed range
                min_t = data.get("min_temp", DEFAULT_MIN_TEMP)
                max_t = data.get("max_temp", DEFAULT_MAX_TEMP)
                return max(min_t, min(max_t, temp))
        return None

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        data = self.coordinator.get_entity_data(ENTITY_TYPE_CLIMATES, self._instance_id)
        if data:
            return data.get("min_temp", DEFAULT_MIN_TEMP)
        return DEFAULT_MIN_TEMP

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        data = self.coordinator.get_entity_data(ENTITY_TYPE_CLIMATES, self._instance_id)
        if data:
            return data.get("max_temp", DEFAULT_MAX_TEMP)
        return DEFAULT_MAX_TEMP

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode based on Evon's ModeSaved property.

        Note: ModeSaved values differ based on Season Mode:
        - HEATING (winter): 2=away, 3=eco, 4=comfort
        - COOLING (summer): 5=away, 6=eco, 7=comfort
        """
        # Clear expired optimistic state to prevent stale UI on network recovery
        self._clear_optimistic_state_if_expired()

        # Return optimistic value if set (prevents UI flicker during updates)
        if self._optimistic_preset is not None:
            return self._optimistic_preset

        data = self.coordinator.get_entity_data(ENTITY_TYPE_CLIMATES, self._instance_id)
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
        attrs = super().extra_state_attributes
        data = self.coordinator.get_entity_data(ENTITY_TYPE_CLIMATES, self._instance_id)
        if data:
            is_cooling = self.coordinator.get_season_mode()
            attrs["comfort_temperature"] = data.get("comfort_temp")
            attrs["eco_temperature"] = data.get("energy_saving_temp")
            attrs["protection_temperature"] = data.get("protection_temp")
            attrs["evon_mode_saved"] = data.get("mode_saved")
            attrs["season_mode"] = "cooling" if is_cooling else "heating"
            attrs["cooling_enabled"] = data.get("cooling_enabled")
        return attrs

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target HVAC mode."""
        # Set optimistic value immediately to prevent UI flicker
        self._optimistic_hvac_mode = hvac_mode
        self._optimistic_state_set_at = time.monotonic()
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
            # Clamp temperature to device min/max range
            temperature = max(self.min_temp, min(self.max_temp, float(temperature)))
            # Set optimistic value immediately to prevent UI flicker
            self._optimistic_target_temp = temperature
            self._optimistic_state_set_at = time.monotonic()
            self.async_write_ha_state()

            await self._api.set_climate_temperature(self._instance_id, temperature)
            await self.coordinator.async_request_refresh()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        # Set optimistic preset immediately to prevent UI flicker
        # Don't set optimistic target temp - let WebSocket push the actual value
        # (Evon may clamp the temp to device min/max limits)
        self._optimistic_preset = preset_mode
        self._optimistic_state_set_at = time.monotonic()
        self.async_write_ha_state()

        # Get seasonal mode to pass correct ModeSaved value for WebSocket
        is_cooling = self.coordinator.get_season_mode()

        if preset_mode == CLIMATE_MODE_COMFORT:
            await self._api.set_climate_comfort_mode(self._instance_id, is_cooling)
        elif preset_mode == CLIMATE_MODE_ENERGY_SAVING:
            await self._api.set_climate_energy_saving_mode(self._instance_id, is_cooling)
        elif preset_mode == CLIMATE_MODE_FREEZE_PROTECTION:
            await self._api.set_climate_freeze_protection_mode(self._instance_id, is_cooling)
        await self.coordinator.async_request_refresh()

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        # Only clear optimistic state when coordinator data matches expected value
        data = self.coordinator.get_entity_data(ENTITY_TYPE_CLIMATES, self._instance_id)
        if data:
            all_cleared = True

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
                else:
                    all_cleared = False

            if self._optimistic_target_temp is not None:
                actual_temp = data.get("target_temperature")
                if actual_temp == self._optimistic_target_temp:
                    self._optimistic_target_temp = None
                else:
                    all_cleared = False

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
                else:
                    all_cleared = False

            # Clear timestamp if all optimistic state has been confirmed
            if all_cleared:
                self._optimistic_state_set_at = None

        super()._handle_coordinator_update()
