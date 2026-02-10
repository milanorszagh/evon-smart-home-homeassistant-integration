"""Diagnostics support for Evon Smart Home integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .const import (
    CONF_ENGINE_ID,
    CONF_HOST,
    DOMAIN,
    ENTITY_TYPE_AIR_QUALITY,
    ENTITY_TYPE_BATHROOM_RADIATORS,
    ENTITY_TYPE_BLINDS,
    ENTITY_TYPE_CAMERAS,
    ENTITY_TYPE_CLIMATES,
    ENTITY_TYPE_INTERCOMS,
    ENTITY_TYPE_LIGHTS,
    ENTITY_TYPE_SCENES,
    ENTITY_TYPE_SECURITY_DOORS,
    ENTITY_TYPE_SMART_METERS,
    ENTITY_TYPE_SWITCHES,
    ENTITY_TYPE_VALVES,
)

TO_REDACT = {CONF_PASSWORD, CONF_USERNAME, CONF_HOST, CONF_ENGINE_ID, "token", "x-elocs-token", "x-elocs-password"}


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: ConfigEntry) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    entry_data = hass.data.get(DOMAIN, {}).get(entry.entry_id, {})
    coordinator = entry_data.get("coordinator")
    if not coordinator:
        return {"error": "Integration not fully loaded"}

    # Redact sensitive data from config
    config_data = async_redact_data(dict(entry.data), TO_REDACT)
    options_data = async_redact_data(dict(entry.options), TO_REDACT)

    # Get device counts from coordinator data
    device_counts = {}
    if coordinator.data:
        device_counts = {
            ENTITY_TYPE_LIGHTS: len(coordinator.data.get(ENTITY_TYPE_LIGHTS, [])),
            ENTITY_TYPE_BLINDS: len(coordinator.data.get(ENTITY_TYPE_BLINDS, [])),
            ENTITY_TYPE_CLIMATES: len(coordinator.data.get(ENTITY_TYPE_CLIMATES, [])),
            ENTITY_TYPE_SWITCHES: len(coordinator.data.get(ENTITY_TYPE_SWITCHES, [])),
            ENTITY_TYPE_SMART_METERS: len(coordinator.data.get(ENTITY_TYPE_SMART_METERS, [])),
            ENTITY_TYPE_AIR_QUALITY: len(coordinator.data.get(ENTITY_TYPE_AIR_QUALITY, [])),
            ENTITY_TYPE_VALVES: len(coordinator.data.get(ENTITY_TYPE_VALVES, [])),
            ENTITY_TYPE_SCENES: len(coordinator.data.get(ENTITY_TYPE_SCENES, [])),
            ENTITY_TYPE_BATHROOM_RADIATORS: len(coordinator.data.get(ENTITY_TYPE_BATHROOM_RADIATORS, [])),
            ENTITY_TYPE_SECURITY_DOORS: len(coordinator.data.get(ENTITY_TYPE_SECURITY_DOORS, [])),
            ENTITY_TYPE_INTERCOMS: len(coordinator.data.get(ENTITY_TYPE_INTERCOMS, [])),
            ENTITY_TYPE_CAMERAS: len(coordinator.data.get(ENTITY_TYPE_CAMERAS, [])),
            "rooms": len(coordinator.data.get("rooms", {})),
        }

    # Build device summaries (without sensitive data)
    device_summaries = {}
    if coordinator.data:
        # Lights summary
        device_summaries[ENTITY_TYPE_LIGHTS] = [
            {
                "id": light.get("id"),
                "name": light.get("name"),
                "is_on": light.get("is_on"),
                "has_brightness": "brightness" in light,
            }
            for light in coordinator.data.get(ENTITY_TYPE_LIGHTS, [])
        ]

        # Blinds summary
        device_summaries[ENTITY_TYPE_BLINDS] = [
            {
                "id": blind.get("id"),
                "name": blind.get("name"),
                "position": blind.get("position"),
                "has_tilt": "angle" in blind,
            }
            for blind in coordinator.data.get(ENTITY_TYPE_BLINDS, [])
        ]

        # Climates summary
        device_summaries[ENTITY_TYPE_CLIMATES] = [
            {
                "id": climate.get("id"),
                "name": climate.get("name"),
                "current_temp": climate.get("current_temperature"),
                "target_temp": climate.get("target_temperature"),
            }
            for climate in coordinator.data.get(ENTITY_TYPE_CLIMATES, [])
        ]

        # Switches summary
        device_summaries[ENTITY_TYPE_SWITCHES] = [
            {
                "id": switch.get("id"),
                "name": switch.get("name"),
                "is_on": switch.get("is_on"),
            }
            for switch in coordinator.data.get(ENTITY_TYPE_SWITCHES, [])
        ]

        # Smart meters summary
        device_summaries[ENTITY_TYPE_SMART_METERS] = [
            {
                "id": meter.get("id"),
                "name": meter.get("name"),
                "power": meter.get("power"),
                "energy": meter.get("energy"),
            }
            for meter in coordinator.data.get(ENTITY_TYPE_SMART_METERS, [])
        ]

        # Air quality summary
        device_summaries[ENTITY_TYPE_AIR_QUALITY] = [
            {
                "id": aq.get("id"),
                "name": aq.get("name"),
                "has_co2": aq.get("co2") is not None,
                "has_humidity": aq.get("humidity") is not None,
            }
            for aq in coordinator.data.get(ENTITY_TYPE_AIR_QUALITY, [])
        ]

        # Valves summary
        device_summaries[ENTITY_TYPE_VALVES] = [
            {
                "id": valve.get("id"),
                "name": valve.get("name"),
                "is_open": valve.get("is_open"),
            }
            for valve in coordinator.data.get(ENTITY_TYPE_VALVES, [])
        ]

        # Scenes summary
        device_summaries[ENTITY_TYPE_SCENES] = [
            {
                "id": scene.get("id"),
                "name": scene.get("name"),
            }
            for scene in coordinator.data.get(ENTITY_TYPE_SCENES, [])
        ]

        # Bathroom radiators summary
        device_summaries[ENTITY_TYPE_BATHROOM_RADIATORS] = [
            {
                "id": radiator.get("id"),
                "name": radiator.get("name"),
                "is_on": radiator.get("is_on"),
            }
            for radiator in coordinator.data.get(ENTITY_TYPE_BATHROOM_RADIATORS, [])
        ]

        # Security doors summary
        device_summaries[ENTITY_TYPE_SECURITY_DOORS] = [
            {
                "id": door.get("id"),
                "name": door.get("name"),
                "is_locked": door.get("is_locked"),
            }
            for door in coordinator.data.get(ENTITY_TYPE_SECURITY_DOORS, [])
        ]

        # Intercoms summary
        device_summaries[ENTITY_TYPE_INTERCOMS] = [
            {
                "id": intercom.get("id"),
                "name": intercom.get("name"),
            }
            for intercom in coordinator.data.get(ENTITY_TYPE_INTERCOMS, [])
        ]

        # Cameras summary
        device_summaries[ENTITY_TYPE_CAMERAS] = [
            {
                "id": camera.get("id"),
                "name": camera.get("name"),
                "error": camera.get("error"),
            }
            for camera in coordinator.data.get(ENTITY_TYPE_CAMERAS, [])
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
            "last_update_success": getattr(coordinator, "last_update_success", None),
            "update_interval": str(getattr(coordinator, "update_interval", "unknown")),
        },
        "device_counts": device_counts,
        "devices": device_summaries,
    }
