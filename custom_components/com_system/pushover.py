"""Pushover receivers: delivery through the config entry's notify action."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import slugify

from .receiver import Receiver

PUSHOVER_DOMAIN = "pushover"
NOTIFY_DOMAIN = "notify"


def source_entry(hass: HomeAssistant, receiver: Receiver) -> ConfigEntry | None:
    """Return the Pushover config entry the receiver was detected from.

    The source id is the entry's unique id, else its entry id.
    """
    for entry in hass.config_entries.async_entries(PUSHOVER_DOMAIN):
        if receiver.source_id in (entry.unique_id, entry.entry_id):
            return entry
    return None


def notify_service_name(entry: ConfigEntry) -> str:
    """Return the name of the entry's notify action.

    Home Assistant registers it as ``notify.<slugified name>`` where the name
    is the one given when the entry was set up.
    """
    return slugify(entry.data.get("name") or entry.title)


async def async_deliver_pushover(
    hass: HomeAssistant, receiver: Receiver, notification: Mapping[str, Any]
) -> list[str]:
    """Send the message and title through the entry's notify action."""
    entry = source_entry(hass, receiver)
    if entry is None:
        raise HomeAssistantError("The Pushover entry no longer exists")
    service = notify_service_name(entry)
    if not hass.services.has_service(NOTIFY_DOMAIN, service):
        raise HomeAssistantError(f"The action notify.{service} is not available")
    data = {"message": notification["message"]}
    if notification.get("title"):
        data["title"] = notification["title"]
    await hass.services.async_call(NOTIFY_DOMAIN, service, data, blocking=True)
    return []
