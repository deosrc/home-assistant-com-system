"""The ``notify.com_system`` action."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import voluptuous as vol

from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.service import async_set_service_schema
from homeassistant.helpers.target import (
    TargetSelection,
    async_extract_referenced_entity_ids,
)

from .const import DOMAIN, NOTIFICATION_RECEIVER_DOMAIN, RESULTS
from .dispatcher import ReceiverResult, async_dispatch
from .targets import ResolvedTargets, resolve_targets

NOTIFY_DOMAIN = "notify"
SERVICE_NAME = "com_system"

ATTR_MESSAGE = "message"
ATTR_TITLE = "title"
ATTR_PERSON = "person"
ATTR_RECEIVERS = "receivers"
ATTR_AREA_ID = "area_id"
ATTR_ENTITY_ID = "entity_id"
ATTR_DEVICE_ID = "device_id"
ATTR_FLOOR_ID = "floor_id"
ATTR_LABEL_ID = "label_id"

# The people field is a choose selector: everyone, or individual people. Its
# value is ``{"active_choice": ..., <choice>: <value>}``. The choice names
# are the labels the form shows. A plain person or list of people is also
# accepted and means individuals.
CHOICE_EVERYONE = "Everyone"
CHOICE_INDIVIDUALS = "Individuals"


def validate_person(value: Any) -> dict[str, Any]:
    """Validate the people field and return it in the choose form."""
    if isinstance(value, dict):
        choice = value.get("active_choice")
        if choice == CHOICE_EVERYONE:
            return {"active_choice": CHOICE_EVERYONE, CHOICE_EVERYONE: True}
        if choice != CHOICE_INDIVIDUALS:
            raise vol.Invalid(
                f"active_choice must be {CHOICE_EVERYONE} or {CHOICE_INDIVIDUALS}"
            )
        value = value.get(CHOICE_INDIVIDUALS, [])
    people = vol.All(cv.ensure_list, [cv.entity_domain("person")])(value)
    return {"active_choice": CHOICE_INDIVIDUALS, CHOICE_INDIVIDUALS: people}


# The receivers field is a choose selector: every receiver with an area, or a
# selection made with a target selector limited to receiver entities.
CHOICE_SELECT = "Select"
CHOICE_ALL_AREAS = "All Areas"

_SELECT_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_ENTITY_ID): vol.All(
            cv.ensure_list, [cv.entity_domain(NOTIFICATION_RECEIVER_DOMAIN)]
        ),
        **{
            vol.Optional(key): vol.All(cv.ensure_list, [cv.string])
            for key in (ATTR_AREA_ID, ATTR_DEVICE_ID, ATTR_FLOOR_ID, ATTR_LABEL_ID)
        },
    }
)


def validate_receivers(value: Any) -> dict[str, Any]:
    """Validate the receivers field and return it in the choose form.

    A plain target (``entity_id``, ``area_id`` and so on) means Select.
    """
    if isinstance(value, dict) and "active_choice" in value:
        choice = value["active_choice"]
        if choice == CHOICE_ALL_AREAS:
            return {"active_choice": CHOICE_ALL_AREAS, CHOICE_ALL_AREAS: True}
        if choice != CHOICE_SELECT:
            raise vol.Invalid(
                f"active_choice must be {CHOICE_SELECT} or {CHOICE_ALL_AREAS}"
            )
        value = value.get(CHOICE_SELECT) or {}
    return {
        "active_choice": CHOICE_SELECT,
        CHOICE_SELECT: _SELECT_SCHEMA(value),
    }


SERVICE_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_TITLE): cv.string,
        vol.Required(ATTR_MESSAGE): cv.string,
        vol.Optional(ATTR_PERSON): validate_person,
        vol.Optional(ATTR_RECEIVERS): validate_receivers,
    }
)

SERVICE_DESCRIPTION: dict[str, Any] = {
    "name": "Send a Com System notification",
    "description": (
        "Sends a notification to the receivers that match the targets. "
        "A target that is not given is not used."
    ),
    "fields": {
        ATTR_TITLE: {
            "name": "Title",
            "description": "An optional title.",
            "example": "Laundry",
            "selector": {"text": None},
        },
        ATTR_MESSAGE: {
            "name": "Message",
            "description": "The message to send.",
            "required": True,
            "example": "The washing has finished",
            "selector": {"text": {"multiline": True}},
        },
        ATTR_PERSON: {
            "name": "People",
            "description": (
                "Notify receivers associated with individual people, or with everyone."
            ),
            "selector": {
                "choose": {
                    "choices": {
                        CHOICE_INDIVIDUALS: {
                            "selector": {
                                "entity": {"domain": "person", "multiple": True}
                            }
                        },
                        CHOICE_EVERYONE: {
                            "selector": {
                                "constant": {"value": True, "label": CHOICE_EVERYONE}
                            }
                        },
                    }
                }
            },
        },
        ATTR_RECEIVERS: {
            "name": "Receivers",
            "description": (
                "Notify the receivers you select (by receiver, area, device, "
                "floor or label), or every receiver that has an area."
            ),
            "selector": {
                "choose": {
                    "choices": {
                        CHOICE_SELECT: {
                            "selector": {
                                "target": {
                                    "entity": {
                                        "domain": NOTIFICATION_RECEIVER_DOMAIN,
                                        "integration": DOMAIN,
                                    }
                                }
                            }
                        },
                        CHOICE_ALL_AREAS: {
                            "selector": {
                                "constant": {"value": True, "label": CHOICE_ALL_AREAS}
                            }
                        },
                    }
                }
            },
        },
    },
}


def _receiver_entry_ids(hass: HomeAssistant, entity_ids: Iterable[str]) -> list[str]:
    """Map receiver entity ids to receiver config entry ids.

    Entities that do not exist or are not Com System's match nothing.
    """
    registry = er.async_get(hass)
    entries = (registry.async_get(entity_id) for entity_id in entity_ids)
    return [
        entry.config_entry_id
        for entry in entries
        if entry is not None and entry.platform == DOMAIN and entry.config_entry_id
    ]


def _select_targets(
    hass: HomeAssistant, target: dict[str, list[str]]
) -> tuple[list[str], list[str]]:
    """Turn a selected target into ``(areas, receiver entry ids)``.

    Areas stay areas, matched against each receiver's area. A floor is its
    areas. Devices and labels are expanded by Home Assistant to entities,
    and the Com System receiver entities among them are named receivers.
    """
    areas = list(target.get(ATTR_AREA_ID, []))
    area_registry = ar.async_get(hass)
    for floor_id in target.get(ATTR_FLOOR_ID, []):
        areas.extend(a.id for a in area_registry.areas.get_areas_for_floor(floor_id))
    entry_ids = _receiver_entry_ids(hass, target.get(ATTR_ENTITY_ID, []))
    indirect = {k: target[k] for k in (ATTR_DEVICE_ID, ATTR_LABEL_ID) if k in target}
    if indirect:
        selected = async_extract_referenced_entity_ids(
            hass, TargetSelection(indirect), primary_entities_only=False
        )
        entry_ids.extend(
            _receiver_entry_ids(
                hass, selected.referenced | selected.indirectly_referenced
            )
        )
    return areas, entry_ids


def resolve_call_targets(hass: HomeAssistant, data: dict[str, Any]) -> ResolvedTargets:
    """Resolve the target fields of an action call to receivers.

    A field that is not given targets nothing, so a call with neither
    ``person`` nor ``receivers`` resolves to no receivers.
    """
    person = validate_person(data[ATTR_PERSON]) if ATTR_PERSON in data else None
    receivers = (
        validate_receivers(data[ATTR_RECEIVERS]) if ATTR_RECEIVERS in data else None
    )
    areas: list[str] = []
    entry_ids: list[str] = []
    if receivers and receivers["active_choice"] == CHOICE_SELECT:
        areas, entry_ids = _select_targets(hass, receivers[CHOICE_SELECT])
    return resolve_targets(
        hass,
        all_people=bool(person and person["active_choice"] == CHOICE_EVERYONE),
        people=person.get(CHOICE_INDIVIDUALS) if person else None,
        areas=areas,
        all_areas=bool(receivers and receivers["active_choice"] == CHOICE_ALL_AREAS),
        receivers=entry_ids,
    )


def notification_from(data: dict[str, Any]) -> dict[str, Any]:
    """Return the content of an action call: message and optional title."""
    return {k: data[k] for k in (ATTR_TITLE, ATTR_MESSAGE) if k in data}


def response_data(results: list[ReceiverResult]) -> dict[str, Any]:
    """Build the action's response data from per-receiver results."""
    return {
        "results": [r.as_dict() for r in results],
        "counts": {k: sum(r.result == k for r in results) for k in RESULTS},
    }


async def async_send(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Resolve, deliver and return the response data.

    Raises ``ServiceValidationError`` only when no receiver could be
    attempted (no target given, none matched, or all that matched are
    disabled). Receivers
    that fail are reported in the response instead.
    """
    if ATTR_PERSON not in data and ATTR_RECEIVERS not in data:
        raise ServiceValidationError("No targets given: set people, receivers or both")
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
