from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import COORDINATOR_KEY, DOMAIN

_REDACTED = "**REDACTED**"
_SENSITIVE = {"password", "access_token", "refresh_token", "code_verifier", "csrf"}


def _redact(data: dict) -> dict:
    return {k: (_REDACTED if k in _SENSITIVE else v) for k, v in data.items()}


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: ConfigEntry) -> dict[str, Any]:
    coordinator = hass.data.get(DOMAIN, {}).get(entry.entry_id, {}).get(COORDINATOR_KEY)
    coordinator_data: dict[str, Any] = {}
    if coordinator and coordinator.data:
        coordinator_data = {
            "gateway_id": coordinator.data.get("gateway_id"),
            "plant_id": coordinator.data.get("plant_id"),
            "module_count": len(coordinator.data.get("modules", {})),
        }
    return {
        "config_entry": {"data": _redact(dict(entry.data)), "options": dict(entry.options)},
        "coordinator_data": coordinator_data,
    }
