"""Pushover receivers: delivery through the config entry's notify action."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import slugify

from .content import (
    PRIORITY_CRITICAL,
    PRIORITY_HIGH,
    PRIORITY_LOW,
    async_existing_local_image,
)
from .receiver import Receiver

_LOGGER = logging.getLogger(__name__)

PUSHOVER_DOMAIN = "pushover"
NOTIFY_DOMAIN = "notify"
# The ``data`` keys the notify action accepts.
PUSHOVER_DATA_KEYS = (
    "priority",
    "attachment",
    "url",
    "url_title",
    "sound",
    "html",
    "timestamp",
    "ttl",
    "retry",
    "expire",
    "callback_url",
    "tags",
)

# The normalised priority as Pushover's -2 to 2. Normal (0) is the default
# and is not sent. Critical (2) needs ``retry`` and ``expire``.
PRIORITY_VALUES = {PRIORITY_LOW: -1, PRIORITY_HIGH: 1, PRIORITY_CRITICAL: 2}
CRITICAL_RETRY = 60
CRITICAL_EXPIRE = 3600

# Separates the entry key from the device name in a source id. Pushover
# device names only use letters, digits, underscores and hyphens.
SEPARATOR = ":"


def entry_key(entry: ConfigEntry) -> str:
    """Return the entry's unique id, else its entry id."""
    return entry.unique_id or entry.entry_id


def source_id_of(entry: ConfigEntry, device: str) -> str:
    """Return the source id of a Pushover device (target) of an entry."""
    return f"{entry_key(entry)}{SEPARATOR}{device}"


def split_source_id(source_id: str | None) -> tuple[str, str] | None:
    """Return ``(entry key, device)`` from a source id, or None."""
    if not source_id or SEPARATOR not in source_id:
        return None
    key, _, device = source_id.partition(SEPARATOR)
    return (key, device) if key and device else None


def source_entry(hass: HomeAssistant, receiver: Receiver) -> ConfigEntry | None:
    """Return the Pushover config entry the receiver was detected from."""
    parts = split_source_id(receiver.source_id)
    if parts is None:
        return None
    for entry in hass.config_entries.async_entries(PUSHOVER_DOMAIN):
        if parts[0] in (entry.unique_id, entry.entry_id):
            return entry
    return None


async def async_entry_devices(hass: HomeAssistant, entry: ConfigEntry) -> list[str]:
    """Return the device names (targets) registered on the account.

    Asks the Pushover API to validate the user key, which lists the account's
    devices. Returns none when the entry is not loaded or the call fails.
    """
    runtime_data = getattr(entry, "runtime_data", None)
    api = getattr(runtime_data, "api", None)
    if api is None:
        return []
    try:
        response = await hass.async_add_executor_job(
            api.validate, entry.data["user_key"]
        )
    except Exception:  # any API or network failure
        _LOGGER.debug("Could not list Pushover devices of %s", entry.title)
        return []
    devices = response.get("devices") if isinstance(response, dict) else None
    return [d for d in devices or [] if isinstance(d, str)]


def notify_service_name(entry: ConfigEntry) -> str:
    """Return the name of the entry's notify action.

    Home Assistant registers it as ``notify.<slugified name>`` where the name
    is the one given when the entry was set up.
    """
    return slugify(entry.data.get("name") or entry.title)


async def async_deliver_pushover(
    hass: HomeAssistant, receiver: Receiver, notification: Mapping[str, Any]
) -> list[str]:
    """Send the notification to the device through the entry's action.

    ``priority`` maps to Pushover's (critical also sets ``retry`` and
    ``expire``), ``image`` becomes ``attachment`` when it is a local file the
    integration may read, and the ``pushover`` data block is merged last so
    it overrides these.
    """
    entry = source_entry(hass, receiver)
    parts = split_source_id(receiver.source_id)
    if entry is None or parts is None:
        raise HomeAssistantError("The Pushover entry no longer exists")
    service = notify_service_name(entry)
    if not hass.services.has_service(NOTIFY_DOMAIN, service):
        raise HomeAssistantError(f"The action notify.{service} is not available")
    data: dict[str, Any] = {
        "message": notification["message"],
        "target": [parts[1]],
    }
    if notification.get("title"):
        data["title"] = notification["title"]
    warnings: list[str] = []
    extra: dict[str, Any] = {}
    priority = PRIORITY_VALUES.get(notification.get("priority"))
    if priority is not None:
        extra["priority"] = priority
        if priority == 2:
            extra["retry"] = CRITICAL_RETRY
            extra["expire"] = CRITICAL_EXPIRE
    if notification.get("image"):
        try:
            extra["attachment"] = await async_existing_local_image(
                hass, notification["image"]
            )
        except HomeAssistantError as err:
            warnings.append(f"The image was dropped: {err}")
    extra.update(notification.get("data") or {})
    if extra:
        data["data"] = extra
    await hass.services.async_call(NOTIFY_DOMAIN, service, data, blocking=True)
    return warnings
