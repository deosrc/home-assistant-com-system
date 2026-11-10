"""Mobile app receivers: the person link, personal/shared and delivery."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from homeassistant.components.person import persons_with_entity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.util import slugify

from .const import AUDIENCE_PERSONAL, AUDIENCE_SHARED, DATA_ENTITIES, DOMAIN
from .receiver import Receiver

_LOGGER = logging.getLogger(__name__)

MOBILE_APP_DOMAIN = "mobile_app"
NOTIFY_DOMAIN = "notify"
AUDIENCE_KEY = "audience"


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
    if receiver.people or linked_person(hass, receiver):
        return AUDIENCE_PERSONAL
    return AUDIENCE_SHARED


def mobile_app_people(hass: HomeAssistant, receiver: Receiver) -> tuple[str, ...]:
    """Return the receiver's person: none if shared, else manual, else linked."""
    if audience_of(hass, receiver) == AUDIENCE_SHARED:
        return ()
    if receiver.people:
        return receiver.people
    person = linked_person(hass, receiver)
    return (person,) if person else ()


async def async_deliver_mobile_app(
    hass: HomeAssistant, receiver: Receiver, notification: Mapping[str, Any]
) -> list[str]:
    """Send the message and title through the device's notify action."""
    entry = source_entry(hass, receiver)
    if entry is None:
        raise HomeAssistantError("The mobile app device is no longer registered")
    service = f"mobile_app_{slugify(entry.data['device_name'])}"
    if not hass.services.has_service(NOTIFY_DOMAIN, service):
        raise HomeAssistantError(f"The action notify.{service} is not available")
    data = {"message": notification["message"]}
    if notification.get("title") is not None:
        data["title"] = notification["title"]
    await hass.services.async_call(NOTIFY_DOMAIN, service, data, blocking=True)
    return []
