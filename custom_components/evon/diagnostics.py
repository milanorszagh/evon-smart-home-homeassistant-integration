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

    # Entity types to include in diagnostics
    entity_types = [
        ENTITY_TYPE_LIGHTS,
        ENTITY_TYPE_BLINDS,
        ENTITY_TYPE_CLIMATES,
        ENTITY_TYPE_SWITCHES,
        ENTITY_TYPE_SMART_METERS,
        ENTITY_TYPE_AIR_QUALITY,
        ENTITY_TYPE_VALVES,
        ENTITY_TYPE_SCENES,
        ENTITY_TYPE_BATHROOM_RADIATORS,
        ENTITY_TYPE_SECURITY_DOORS,
        ENTITY_TYPE_INTERCOMS,
        ENTITY_TYPE_CAMERAS,
    ]

    # Get device counts from coordinator data
    device_counts: dict[str, int] = {}
    if coordinator.data:
        device_counts = {et: len(coordinator.data.get(et, [])) for et in entity_types}
        device_counts["rooms"] = len(coordinator.data.get("rooms", {}))

    # Summary field definitions: entity_type -> list of (output_key, source_key_or_callable)
    # Callables receive the entity dict and return the value
    summary_fields: dict[str, list[tuple[str, str | Any]]] = {
        ENTITY_TYPE_LIGHTS: [
            ("id", "id"),
            ("name", "name"),
            ("is_on", "is_on"),
            ("has_brightness", lambda e: "brightness" in e),
        ],
        ENTITY_TYPE_BLINDS: [
            ("id", "id"),
            ("name", "name"),
            ("position", "position"),
            ("has_tilt", lambda e: "angle" in e),
        ],
        ENTITY_TYPE_CLIMATES: [
            ("id", "id"),
            ("name", "name"),
            ("current_temp", "current_temperature"),
            ("target_temp", "target_temperature"),
        ],
        ENTITY_TYPE_SWITCHES: [("id", "id"), ("name", "name"), ("is_on", "is_on")],
        ENTITY_TYPE_SMART_METERS: [
            ("id", "id"),
            ("name", "name"),
            ("power", "power"),
            ("energy", "energy"),
        ],
        ENTITY_TYPE_AIR_QUALITY: [
            ("id", "id"),
            ("name", "name"),
            ("has_co2", lambda e: e.get("co2") is not None),
            ("has_humidity", lambda e: e.get("humidity") is not None),
        ],
        ENTITY_TYPE_VALVES: [("id", "id"), ("name", "name"), ("is_open", "is_open")],
        ENTITY_TYPE_SCENES: [("id", "id"), ("name", "name")],
        ENTITY_TYPE_BATHROOM_RADIATORS: [("id", "id"), ("name", "name"), ("is_on", "is_on")],
        ENTITY_TYPE_SECURITY_DOORS: [("id", "id"), ("name", "name"), ("is_locked", "is_locked")],
        ENTITY_TYPE_INTERCOMS: [("id", "id"), ("name", "name")],
        ENTITY_TYPE_CAMERAS: [("id", "id"), ("name", "name"), ("error", "error")],
    }

    # Build device summaries (without sensitive data)
    device_summaries: dict[str, list[dict[str, Any]]] = {}
    if coordinator.data:
        for etype, fields in summary_fields.items():
            device_summaries[etype] = [
                {out_key: (src(entity) if callable(src) else entity.get(src)) for out_key, src in fields}
                for entity in coordinator.data.get(etype, [])
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
