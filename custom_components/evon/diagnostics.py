"""Diagnostics support for Evon Smart Home integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .const import CONF_HOST, DOMAIN

TO_REDACT = {CONF_PASSWORD, CONF_USERNAME, CONF_HOST, "token", "x-elocs-token", "x-elocs-password"}


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: ConfigEntry) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    # Redact sensitive data from config
    config_data = async_redact_data(dict(entry.data), TO_REDACT)
    options_data = async_redact_data(dict(entry.options), TO_REDACT)

    # Get device counts from coordinator data
    device_counts = {}
    if coordinator.data:
        device_counts = {
            "lights": len(coordinator.data.get("lights", [])),
            "blinds": len(coordinator.data.get("blinds", [])),
            "climates": len(coordinator.data.get("climates", [])),
            "switches": len(coordinator.data.get("switches", [])),
            "smart_meters": len(coordinator.data.get("smart_meters", [])),
            "air_quality": len(coordinator.data.get("air_quality", [])),
            "valves": len(coordinator.data.get("valves", [])),
            "rooms": len(coordinator.data.get("rooms", {})),
        }

    # Build device summaries (without sensitive data)
    device_summaries = {}
    if coordinator.data:
        # Lights summary
        device_summaries["lights"] = [
            {
                "id": light["id"],
                "name": light["name"],
                "is_on": light.get("is_on"),
                "has_brightness": "brightness" in light,
            }
            for light in coordinator.data.get("lights", [])
        ]

        # Blinds summary
        device_summaries["blinds"] = [
            {
                "id": blind["id"],
                "name": blind["name"],
                "position": blind.get("position"),
                "has_tilt": "angle" in blind,
            }
            for blind in coordinator.data.get("blinds", [])
        ]

        # Climates summary
        device_summaries["climates"] = [
            {
                "id": climate["id"],
                "name": climate["name"],
                "current_temp": climate.get("current_temperature"),
                "target_temp": climate.get("target_temperature"),
            }
            for climate in coordinator.data.get("climates", [])
        ]

        # Switches summary
        device_summaries["switches"] = [
            {
                "id": switch["id"],
                "name": switch["name"],
                "is_on": switch.get("is_on"),
            }
            for switch in coordinator.data.get("switches", [])
        ]

        # Smart meters summary
        device_summaries["smart_meters"] = [
            {
                "id": meter["id"],
                "name": meter["name"],
                "power": meter.get("power"),
                "energy": meter.get("energy"),
            }
            for meter in coordinator.data.get("smart_meters", [])
        ]

        # Air quality summary
        device_summaries["air_quality"] = [
            {
                "id": aq["id"],
                "name": aq["name"],
                "has_co2": aq.get("co2") is not None,
                "has_humidity": aq.get("humidity") is not None,
            }
            for aq in coordinator.data.get("air_quality", [])
        ]

        # Valves summary
        device_summaries["valves"] = [
            {
                "id": valve["id"],
                "name": valve["name"],
                "is_open": valve.get("is_open"),
            }
            for valve in coordinator.data.get("valves", [])
        ]

    return {
        "entry": {
            "entry_id": entry.entry_id,
            "version": entry.version,
            "domain": entry.domain,
            "title": entry.title,
            "data": config_data,
            "options": options_data,
        },
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
            "update_interval": str(coordinator.update_interval),
        },
        "device_counts": device_counts,
        "devices": device_summaries,
    }
