"""Diagnostics for the Com System integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    CONF_CHANNELS,
    CONF_ENTRY_TYPE,
    CONF_NAME,
    CONF_PEOPLE,
    CONF_SOURCE_ID,
    DOMAIN,
    ENTRY_TYPE_HUB,
    RECEIVER_ENTRY_TYPES,
)

# Names, people and device identifiers are personal; keys and tokens are secret.
TO_REDACT = {
    CONF_NAME,
    CONF_PEOPLE,
    CONF_SOURCE_ID,
    "title",
    "api_key",
    "user_key",
    "token",
    "password",
    "access_token",
    "email",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for the hub or a receiver config entry.

    Notification content and history records are not included.
    """
    entries = hass.config_entries.async_entries(DOMAIN)
    result: dict[str, Any] = {
        "entry": async_redact_data(entry.as_dict(), TO_REDACT),
    }
    if entry.data.get(CONF_ENTRY_TYPE) == ENTRY_TYPE_HUB:
        result["channel_count"] = len(entry.data.get(CONF_CHANNELS, {}))
        result["receivers"] = [
            {
                "entry_id": e.entry_id,
                "type": e.data.get(CONF_ENTRY_TYPE),
                "receiver_type": e.data.get("receiver_type"),
                "state": e.state.value,
            }
            for e in entries
            if e.data.get(CONF_ENTRY_TYPE) in RECEIVER_ENTRY_TYPES
        ]
    return result
