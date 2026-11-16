"""Per-receiver notification conditions."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import probatio

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import condition, selector
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er

from .const import (
    CONF_CONDITIONS,
    DATA_REGISTRY,
    DOMAIN,
    NOTIFICATION_RECEIVER_DOMAIN,
)
from .receiver import Receiver

_LOGGER = logging.getLogger(__name__)

REASON_CONDITIONS = "Conditions did not pass"
REASON_CONDITION_ERROR = "Condition error"


class RawConditionSelector(selector.ConditionSelector):
    """The condition selector, keeping the value as it was entered.

    The validated output holds ``Template`` and ``timedelta`` objects that
    cannot be stored in a config entry, so this validates and returns the
    input unchanged. Conditions are validated again when they are evaluated.
    """

    def __call__(self, data: Any) -> Any:
        """Validate the conditions and return them unchanged."""
        super().__call__(data)
        return data


@dataclass(frozen=True, slots=True)
class ConditionOutcome:
    """The result of a receiver's conditions."""

    passed: bool
    # Why it did not pass (``REASON_CONDITIONS`` or the error message).
    reason: str | None = None


PASSED = ConditionOutcome(True)


def receiver_conditions(hass: HomeAssistant, receiver: Receiver) -> list[Any]:
    """Return the receiver's stored (raw) conditions."""
    entry = hass.config_entries.async_get_entry(receiver.entry_id)
    return list(entry.options.get(CONF_CONDITIONS) or ()) if entry else []


def condition_variables(
    hass: HomeAssistant,
    receiver: Receiver,
    notification: Mapping[str, Any],
    reasons: list[dict[str, str]] | None = None,
    requested: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the variables conditions are evaluated with.

    ``notification`` always has ``id``, ``title``, ``message``, ``priority``,
    ``image``, ``data`` (a dict) and ``targets`` (what the call asked for), so
    templates can use them without checking. Other content fields are present
    when given.
    """
    registry = hass.data[DOMAIN][DATA_REGISTRY]
    receiver_type = registry.type_of(receiver)
    entity_id = er.async_get(hass).async_get_entity_id(
        NOTIFICATION_RECEIVER_DOMAIN, DOMAIN, f"{receiver.entry_id}_receiver"
    )
    return {
        "notification": {
            "id": None,
            "title": None,
            "message": None,
            "priority": None,
            "image": None,
            **notification,
            "data": dict(notification.get("data") or {}),
            "targets": dict(requested or {}),
        },
        "receiver": {
            "name": receiver.name,
            "type": receiver_type.name if receiver_type else receiver.type_id,
            "type_id": receiver.type_id,
            "entry_id": receiver.entry_id,
            "entity_id": entity_id,
            "people": list(registry.people_of(receiver)),
            "areas": list(registry.areas_of(receiver)),
        },
        "resolved_targets": [dict(r) for r in reasons or ()],
    }


async def async_check_conditions(
    hass: HomeAssistant, receiver: Receiver, variables: dict[str, Any]
) -> ConditionOutcome:
    """Evaluate the receiver's conditions; all must pass.

    A receiver with none passes. A condition that errors, or stored
    conditions that no longer validate, do not pass and are logged; the
    reason says it was an error.
    """
    raw = receiver_conditions(hass, receiver)
    if not raw:
        return PASSED
    checkers: list[condition.ConditionChecker] = []
    try:
        validated = await condition.async_validate_conditions_config(
            hass, cv.CONDITIONS_SCHEMA(raw)
        )
        for config in validated:
            checkers.append(await condition.async_from_config(hass, config))
        for checker in checkers:
            if not checker(hass, variables):
                return ConditionOutcome(False, REASON_CONDITIONS)
    except (condition.ConditionError, HomeAssistantError, probatio.Invalid) as err:
        _LOGGER.warning("Conditions of %s errored: %s", receiver.name, err)
        return ConditionOutcome(False, f"{REASON_CONDITION_ERROR}: {err}")
    except Exception as err:  # a bad condition must never break a send
        _LOGGER.exception("Conditions of %s failed", receiver.name)
        return ConditionOutcome(False, f"{REASON_CONDITION_ERROR}: {err}")
    finally:
        for checker in checkers:
            checker.async_unload()
    return PASSED
