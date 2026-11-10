"""The ``notify.com_system`` action."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.service import async_set_service_schema

from .const import DOMAIN, NOTIFICATION_RECEIVER_DOMAIN, RESULTS
from .dispatcher import ReceiverResult, async_dispatch
from .targets import ResolvedTargets, resolve_targets

NOTIFY_DOMAIN = "notify"
SERVICE_NAME = "com_system"

ATTR_MESSAGE = "message"
ATTR_TITLE = "title"
ATTR_PERSON = "person"
ATTR_AREA_ID = "area_id"
ATTR_ENTITY_ID = "entity_id"

SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_MESSAGE): cv.string,
        vol.Optional(ATTR_TITLE): cv.string,
        vol.Optional(ATTR_PERSON): vol.All(
            cv.ensure_list, [cv.entity_domain("person")]
        ),
        vol.Optional(ATTR_AREA_ID): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(ATTR_ENTITY_ID): vol.All(
            cv.ensure_list, [cv.entity_domain(NOTIFICATION_RECEIVER_DOMAIN)]
        ),
    }
)

SERVICE_DESCRIPTION: dict[str, Any] = {
    "name": "Send a Com System notification",
    "description": (
        "Sends a notification to the receivers that match the targets. "
        "With no targets it goes to all people and all areas."
    ),
    "fields": {
        ATTR_MESSAGE: {
            "name": "Message",
            "description": "The message to send.",
            "required": True,
            "example": "The washing has finished",
            "selector": {"text": {"multiline": True}},
        },
        ATTR_TITLE: {
            "name": "Title",
            "description": "An optional title.",
            "example": "Laundry",
            "selector": {"text": None},
        },
        ATTR_PERSON: {
            "name": "People",
            "description": "Notify receivers associated with these people.",
            "selector": {"entity": {"domain": "person", "multiple": True}},
        },
        ATTR_AREA_ID: {
            "name": "Areas",
            "description": "Notify receivers in these areas.",
            "selector": {"area": {"multiple": True}},
        },
        ATTR_ENTITY_ID: {
            "name": "Receivers",
            "description": "Notify these receivers by name.",
            "selector": {
                "entity": {
                    "domain": NOTIFICATION_RECEIVER_DOMAIN,
                    "integration": DOMAIN,
                    "multiple": True,
                }
            },
        },
    },
}


def _receiver_entry_ids(hass: HomeAssistant, entity_ids: list[str]) -> list[str]:
    """Map receiver entity ids to receiver config entry ids.

    Entities that do not exist or are not Com System's match nothing. They
    are kept (as the entity id, which is never an entry id) so that a target
    list that names only such entities is still a target list and does not
    fall back to the default of all people and areas.
    """
    registry = er.async_get(hass)
    entry_ids = []
    for entity_id in entity_ids:
        entry = registry.async_get(entity_id)
        if entry is not None and entry.platform == DOMAIN and entry.config_entry_id:
            entry_ids.append(entry.config_entry_id)
        else:
            entry_ids.append(entity_id)
    return entry_ids


def resolve_call_targets(hass: HomeAssistant, data: dict[str, Any]) -> ResolvedTargets:
    """Resolve the target fields of an action call to receivers."""
    return resolve_targets(
        hass,
        people=data.get(ATTR_PERSON),
        areas=data.get(ATTR_AREA_ID),
        receivers=_receiver_entry_ids(hass, data.get(ATTR_ENTITY_ID, [])),
    )


def notification_from(data: dict[str, Any]) -> dict[str, Any]:
    """Return the content of an action call: message and optional title."""
    return {k: data[k] for k in (ATTR_MESSAGE, ATTR_TITLE) if k in data}


def response_data(results: list[ReceiverResult]) -> dict[str, Any]:
    """Build the action's response data from per-receiver results."""
    return {
        "results": [r.as_dict() for r in results],
        "counts": {k: sum(r.result == k for r in results) for k in RESULTS},
    }


async def async_send(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Resolve, deliver and return the response data.

    Raises ``ServiceValidationError`` only when no receiver could be
    attempted (none matched, or all that matched are disabled). Receivers
    that fail are reported in the response instead.
    """
    resolved = resolve_call_targets(hass, data)
    if not resolved.receivers:
        if resolved.skipped:
            names = ", ".join(r.name for r in resolved.skipped)
            raise ServiceValidationError(
                f"No receiver could be notified, they are disabled: {names}"
            )
        raise ServiceValidationError("No receiver matches the targets")
    results = await async_dispatch(hass, resolved, notification_from(data))
    return response_data(results)


async def _handle(call: ServiceCall) -> ServiceResponse:
    return await async_send(call.hass, dict(call.data))


def async_register_notify_action(hass: HomeAssistant) -> None:
    """Register ``notify.com_system`` and its UI description."""
    hass.services.async_register(
        NOTIFY_DOMAIN,
        SERVICE_NAME,
        _handle,
        schema=SERVICE_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    async_set_service_schema(hass, NOTIFY_DOMAIN, SERVICE_NAME, SERVICE_DESCRIPTION)
