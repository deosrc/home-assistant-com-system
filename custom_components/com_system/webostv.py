"""webOS TV receivers: delivery through the TV's notify action."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.util import slugify

from .receiver import Receiver
from .receiver_type import ReceiverSkipped

WEBOSTV_DOMAIN = "webostv"
NOTIFY_DOMAIN = "notify"
MEDIA_PLAYER_DOMAIN = "media_player"
REASON_DEVICE_OFF = "Device is off"


def source_entry(hass: HomeAssistant, receiver: Receiver) -> ConfigEntry | None:
    """Return the webostv config entry the receiver was detected from."""
    for entry in hass.config_entries.async_entries(WEBOSTV_DOMAIN):
        if receiver.source_id in (entry.unique_id, entry.entry_id):
            return entry
    return None


def _is_off(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Return whether the TV's media player is off or unavailable."""
    for entity in er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id):
        if entity.domain != MEDIA_PLAYER_DOMAIN:
            continue
        state = hass.states.get(entity.entity_id)
        if state is not None and state.state in ("off", "unavailable"):
            return True
    return False


async def async_deliver_webostv(
    hass: HomeAssistant, receiver: Receiver, notification: Mapping[str, Any]
) -> list[str]:
    """Send the message (and an optional icon) as a toast on the TV.

    The integration registers ``notify.<slugified config entry title>`` and
    reads only ``message`` and ``data.icon``; the dispatcher has already
    dropped everything else (with warnings). ``data`` is the type's block.
    A TV that is off or unavailable is expected, so it raises
    ``ReceiverSkipped`` rather than failing. Older versions of the
    integration only log when the TV is unreachable, which cannot be seen
    here.
    """
    entry = source_entry(hass, receiver)
    if entry is None:
        raise HomeAssistantError("The webOS TV is no longer configured")
    service = slugify(entry.title)
    if not hass.services.has_service(NOTIFY_DOMAIN, service):
        raise HomeAssistantError(f"The action notify.{service} is not available")
    if _is_off(hass, entry):
        raise ReceiverSkipped(REASON_DEVICE_OFF)
    data: dict[str, Any] = {"message": notification["message"]}
    extra = notification.get("data")
    if isinstance(extra, Mapping) and extra.get("icon"):
        data["data"] = {"icon": extra["icon"]}
    try:
        await hass.services.async_call(NOTIFY_DOMAIN, service, data, blocking=True)
    except HomeAssistantError:
        # The TV may have gone off after the check above.
        if _is_off(hass, entry):
            raise ReceiverSkipped(REASON_DEVICE_OFF) from None
        raise
    return []
