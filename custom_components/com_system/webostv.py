"""webOS TV receivers: delivery through the TV's notify action."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import slugify

from .receiver import Receiver

WEBOSTV_DOMAIN = "webostv"
NOTIFY_DOMAIN = "notify"


def source_entry(hass: HomeAssistant, receiver: Receiver) -> ConfigEntry | None:
    """Return the webostv config entry the receiver was detected from."""
    for entry in hass.config_entries.async_entries(WEBOSTV_DOMAIN):
        if receiver.source_id in (entry.unique_id, entry.entry_id):
            return entry
    return None


async def async_deliver_webostv(
    hass: HomeAssistant, receiver: Receiver, notification: Mapping[str, Any]
) -> list[str]:
    """Send the message (and an optional icon) as a toast on the TV.

    The integration registers ``notify.<slugified config entry title>`` and
    reads only ``message`` and ``data.icon``, so the title is dropped with a
    warning. The integration logs, rather than raises, when the TV is
    unreachable, so such a failure cannot be reported here.
    """
    entry = source_entry(hass, receiver)
    if entry is None:
        raise HomeAssistantError("The webOS TV is no longer configured")
    service = slugify(entry.title)
    if not hass.services.has_service(NOTIFY_DOMAIN, service):
        raise HomeAssistantError(f"The action notify.{service} is not available")
    data: dict[str, Any] = {"message": notification["message"]}
    extra = notification.get("data")
    if isinstance(extra, Mapping) and extra.get("icon"):
        data["data"] = {"icon": extra["icon"]}
    warnings = []
    if notification.get("title"):
        warnings.append("The title is not shown on a webOS TV")
    await hass.services.async_call(NOTIFY_DOMAIN, service, data, blocking=True)
    return warnings
