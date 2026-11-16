"""Mobile app receivers: the person link, personal/shared and delivery."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any, NamedTuple
from urllib.parse import quote, unquote

from homeassistant.components.person import persons_with_entity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from homeassistant.util import slugify

from .const import (
    AUDIENCE_PERSONAL,
    AUDIENCE_SHARED,
    DATA_ENTITIES,
    DATA_HISTORY,
    DATA_REGISTRY,
    DOMAIN,
    EVENT_ACTION,
    RECEIVER_TYPE_MOBILE_APP,
)
from .content import (
    PRIORITY_CRITICAL,
    PRIORITY_HIGH,
    PRIORITY_LOW,
    async_image_url,
    merge,
)
from .receiver import Receiver

REMOVE_CHANNEL_MESSAGE = "remove_channel"

_LOGGER = logging.getLogger(__name__)

MOBILE_APP_DOMAIN = "mobile_app"
NOTIFY_DOMAIN = "notify"
AUDIENCE_KEY = "audience"

# The app's event for a pressed notification action. The app returns only the
# pressed action's ID, so Com System encodes what it needs in the ID it sends
# (``com_system:<notification id>:<receiver id>:<tag>:<action id>``, the tag
# URL-encoded and empty when there is none) and decodes it when the event
# comes back. Nothing then has to be looked up, so a response still has its
# tag after the notification has left history.
MOBILE_APP_ACTION_EVENT = "mobile_app_notification_action"
ACTION_PREFIX = "com_system"


class DecodedAction(NamedTuple):
    """What an encoded action ID carries."""

    notification_id: str
    receiver_id: str
    tag: str | None
    action: str


def encode_action(
    notification_id: str, receiver_id: str, action: str, tag: str | None = None
) -> str:
    """Return the action ID the app is sent for a Com System notification."""
    quoted = quote(tag, safe="") if tag else ""
    return f"{ACTION_PREFIX}:{notification_id}:{receiver_id}:{quoted}:{action}"


def decode_action(value: Any) -> DecodedAction | None:
    """Return what an action ID carries, or None if Com System did not make it."""
    if not isinstance(value, str):
        return None
    parts = value.split(":", 4)
    if len(parts) != 5 or parts[0] != ACTION_PREFIX or not parts[1] or not parts[2]:
        return None
    return DecodedAction(parts[1], parts[2], unquote(parts[3]) or None, parts[4])


def source_entry(hass: HomeAssistant, receiver: Receiver) -> ConfigEntry | None:
    """Return the mobile_app config entry the receiver was detected from.

    The receiver's source id is the app's ``device_id``, which the entry
    stores in its data.
    """
    for entry in hass.config_entries.async_entries(MOBILE_APP_DOMAIN):
        if entry.data.get("device_id") == receiver.source_id:
            return entry
    return None


def linked_person(hass: HomeAssistant, receiver: Receiver) -> str | None:
    """Return the ``person.*`` entity the device belongs to, if any.

    First the person linked to the Home Assistant user the app registered
    with, then a person whose device trackers include the app's tracker.
    Resolved at each call because persons can change at any time.
    """
    entry = source_entry(hass, receiver)
    if entry is None:
        return None
    user_id = entry.data.get("user_id")
    if user_id:
        for state in sorted(hass.states.async_all("person"), key=lambda s: s.entity_id):
            if state.attributes.get("user_id") == user_id:
                return state.entity_id
    tracker = er.async_get(hass).async_get_entity_id(
        "device_tracker", MOBILE_APP_DOMAIN, entry.data["device_id"]
    )
    if tracker is None:
        return None
    persons = sorted(persons_with_entity(hass, tracker))
    if len(persons) > 1:
        _LOGGER.debug("Tracker %s is on several people; using %s", tracker, persons[0])
    return persons[0] if persons else None


def audience_of(hass: HomeAssistant, receiver: Receiver) -> str:
    """Return the receiver's personal/shared setting.

    It is the state of the select entity. Before that exists (or while the
    receiver is not loaded) it is inferred from the person link.
    """
    select = (
        hass.data[DOMAIN][DATA_ENTITIES].get(receiver.entry_id, {}).get(AUDIENCE_KEY)
    )
    if select is not None and select.current_option in (
        AUDIENCE_PERSONAL,
        AUDIENCE_SHARED,
    ):
        return select.current_option
    return default_audience(hass, receiver)


def default_audience(hass: HomeAssistant, receiver: Receiver) -> str:
    """Personal when a person is linked, otherwise shared."""
    if linked_person(hass, receiver):
        return AUDIENCE_PERSONAL
    return AUDIENCE_SHARED


def mobile_app_people(hass: HomeAssistant, receiver: Receiver) -> tuple[str, ...]:
    """Return the receiver's person: none if shared, else the linked one.

    A mobile app receiver has no people option, so any stored one is ignored.
    """
    if audience_of(hass, receiver) == AUDIENCE_SHARED:
        return ()
    person = linked_person(hass, receiver)
    return (person,) if person else ()


# How the normalised priority maps to the companion app's ``data`` keys.
# Android reads ``importance``, ``ttl`` and ``priority``; iOS reads
# ``push.interruption-level`` (and ``push.sound`` for critical alerts). Each
# platform ignores the other's keys.
PRIORITY_DATA: dict[str, dict[str, Any]] = {
    PRIORITY_LOW: {"importance": "low", "push": {"interruption-level": "passive"}},
    PRIORITY_HIGH: {
        "importance": "high",
        "ttl": 0,
        "priority": "high",
        "push": {"interruption-level": "time-sensitive"},
    },
    PRIORITY_CRITICAL: {
        "importance": "max",
        "ttl": 0,
        "priority": "high",
        "push": {
            "interruption-level": "critical",
            "sound": {"name": "default", "critical": 1, "volume": 1.0},
        },
    },
}


def android_entries(hass: HomeAssistant) -> list[ConfigEntry]:
    """Return the registered mobile app entries of Android devices."""
    return [
        entry
        for entry in hass.config_entries.async_entries(MOBILE_APP_DOMAIN)
        if str(entry.data.get("os_name", "")).lower() == "android"
    ]


async def async_remove_channel(hass: HomeAssistant, channel: str) -> None:
    """Tell every Android device with a mobile app receiver to drop a channel.

    Sends the companion app's ``remove_channel`` notification. A device whose
    notify action is missing is skipped.
    """
    receivers = hass.data[DOMAIN][DATA_REGISTRY].all()
    device_ids = {
        r.source_id for r in receivers if r.type_id == RECEIVER_TYPE_MOBILE_APP
    }
    for entry in android_entries(hass):
        if entry.data.get("device_id") not in device_ids:
            continue
        service = f"mobile_app_{slugify(entry.data['device_name'])}"
        if not hass.services.has_service(NOTIFY_DOMAIN, service):
            continue
        await hass.services.async_call(
            NOTIFY_DOMAIN,
            service,
            {"message": REMOVE_CHANNEL_MESSAGE, "data": {"channel": channel}},
            blocking=True,
        )


def _app_action(action: Mapping[str, Any]) -> dict[str, Any]:
    """Return an ``actions`` item as the companion app has it.

    ``id`` is the app's ``action`` and ``label`` its ``title``; other keys
    (``uri``, ``behavior`` and so on) are passed through.
    """
    result = {k: v for k, v in action.items() if k not in ("id", "label")}
    result["action"] = action["id"]
    result["title"] = action["label"]
    return result


async def async_deliver_mobile_app(
    hass: HomeAssistant, receiver: Receiver, notification: Mapping[str, Any]
) -> list[str]:
    """Send the notification through the device's notify action.

    ``priority`` maps through ``PRIORITY_DATA``, ``image`` is ``data.image``
    (a media source is resolved to a URL), and the ``mobile_app`` data block
    is merged over both, so it can override them.
    """
    entry = source_entry(hass, receiver)
    if entry is None:
        raise HomeAssistantError("The mobile app device is no longer registered")
    service = f"mobile_app_{slugify(entry.data['device_name'])}"
    if not hass.services.has_service(NOTIFY_DOMAIN, service):
        raise HomeAssistantError(f"The action notify.{service} is not available")
    data = {"message": notification["message"]}
    if notification.get("title") is not None:
        data["title"] = notification["title"]
    warnings: list[str] = []
    extra: dict[str, Any] = dict(PRIORITY_DATA.get(notification.get("priority"), {}))
    if notification.get("image"):
        try:
            extra["image"] = await async_image_url(hass, notification["image"])
        except HomeAssistantError as err:
            warnings.append(f"The image was dropped: {err}")
    if notification.get("channel"):
        extra["channel"] = notification["channel"]
    if notification.get("click_action"):
        # Android reads clickAction, iOS reads url.
        extra["clickAction"] = notification["click_action"]
        extra["url"] = notification["click_action"]
    if notification.get("actions"):
        extra["actions"] = [_app_action(a) for a in notification["actions"]]
    if notification.get("tag"):
        extra["tag"] = notification["tag"]
    if notification.get("car_ui"):
        extra["car_ui"] = True
    extra = merge(extra, notification.get("data") or {})
    if notification.get("id") and extra.get("actions"):
        # Actions that open a URI send no response, so they are left alone.
        extra["actions"] = [
            action
            if action.get("uri") or "action" not in action
            else {
                **action,
                "action": encode_action(
                    notification["id"],
                    receiver.entry_id,
                    str(action["action"]),
                    extra.get("tag"),
                ),
            }
            for action in extra["actions"]
        ]
    if extra:
        data["data"] = extra
    await hass.services.async_call(NOTIFY_DOMAIN, service, data, blocking=True)
    return warnings


async def _async_handle_action(hass: HomeAssistant, event: Event) -> None:
    """Turn the app's action event into ``com_system_action`` and history."""
    data = event.data
    decoded = decode_action(data.get("action"))
    if decoded is None:
        # Not a Com System notification (or its actions were not encoded).
        _LOGGER.debug("Ignoring mobile app action event: %s", dict(data))
        return
    notification_id, receiver_id, tag, action = decoded
    receiver = hass.data[DOMAIN][DATA_REGISTRY].get(receiver_id)
    person = None
    if receiver is not None:
        people = mobile_app_people(hass, receiver)
        person = people[0] if people else None
    response = {
        "notification_id": notification_id,
        "tag": tag,
        "receiver_id": receiver_id,
        "receiver": receiver.name if receiver else None,
        "person": person,
        "action": action,
        "reply_text": data.get("reply_text"),
    }
    stored = await hass.data[DOMAIN][DATA_HISTORY].async_add_response(
        response["notification_id"],
        {**response, "time": dt_util.utcnow().isoformat()},
    )
    if not stored:
        _LOGGER.debug("Response to %s: not in history", response["notification_id"])
    hass.bus.async_fire(EVENT_ACTION, response, context=event.context)


@callback
def async_setup_action_responses(hass: HomeAssistant) -> None:
    """Listen for pressed notification actions (once, from ``async_setup``)."""

    async def _listener(event: Event) -> None:
        await _async_handle_action(hass, event)

    hass.bus.async_listen(MOBILE_APP_ACTION_EVENT, _listener)
