"""Receiver type definitions: the extension point for new receiver types."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.service import async_get_all_descriptions

from .const import RECEIVER_TYPE_CUSTOM, SCRIPT_FIELD
from .receiver import Receiver


@dataclass(frozen=True, slots=True)
class DiscoveryCandidate:
    """A receiver a type found that could be offered as a discovery."""

    source_id: str
    name: str


class ReceiverType:
    """Defines how receivers of one type behave.

    Subclass, set ``type_id`` and ``name``, override what differs, and pass
    an instance to ``register_receiver_type``.
    """

    type_id: str
    name: str
    # Typed fields and ``data`` keys the type supports. Empty means the type
    # declares none (no unsupported-content warnings).
    capabilities: frozenset[str] = frozenset()
    # Whether receivers of the type are created from discoveries (built-in
    # types) and so need a source to detect. Custom receivers are manual.
    discoverable: bool = False
    # Whether receivers of the type can relate to people. When False the
    # options form has no people field and no person target reaches them.
    supports_people: bool = True

    async def async_deliver(
        self, hass: HomeAssistant, receiver: Receiver, notification: Mapping[str, Any]
    ) -> list[str]:
        """Deliver a notification to a receiver of this type.

        ``notification`` has ``message`` and, when given, ``title``. Return
        warnings for content the type dropped (empty when none). Raise to
        report a failure; the dispatcher records it and carries on with the
        other receivers. The default raises ``NotImplementedError``, which
        the dispatcher reports as a failure.
        """
        raise NotImplementedError

    def associated_people(self, receiver: Receiver) -> tuple[str, ...]:
        """Return the people the receiver relates to."""
        return receiver.people if self.supports_people else ()

    def source_device_identifiers(
        self, receiver: Receiver
    ) -> set[tuple[str, str]] | None:
        """Return the identifiers of the device the receiver attaches to.

        None (the default) means the receiver has no source device and gets
        its own device.
        """
        return None

    async def async_detect(self, hass: HomeAssistant) -> list[DiscoveryCandidate]:
        """Return receivers that could be offered as discoveries."""
        return []

    def is_source_available(self, hass: HomeAssistant, receiver: Receiver) -> bool:
        """Return whether the receiver's source device or entry still exists.

        A receiver whose source is gone is kept and shown as unavailable.
        """
        return True


def notification_script_problems(description: Mapping[str, Any]) -> list[str]:
    """Return why a script's service description is not a notification script.

    It must have a ``notification`` field with an object selector. Any other
    fields must be optional, because only ``notification`` is passed. An
    empty list means it is one.
    """
    fields = description.get("fields") or {}
    if not fields:
        return ["The script has no fields."]
    problems = []
    if SCRIPT_FIELD not in fields:
        problems.append(f"There is no field named {SCRIPT_FIELD}.")
    elif "object" not in (fields[SCRIPT_FIELD].get("selector") or {}):
        problems.append(f"The {SCRIPT_FIELD} field does not use the object selector.")
    required = sorted(
        name
        for name, field in fields.items()
        if name != SCRIPT_FIELD and (field or {}).get("required")
    )
    if required:
        problems.append(
            f"These fields are required but only {SCRIPT_FIELD} is passed: "
            f"{', '.join(required)}. Make them optional."
        )
    return problems


def is_notification_script(description: Mapping[str, Any]) -> bool:
    """Return whether a script's service description is a notification script."""
    return not notification_script_problems(description)


class CustomReceiverType(ReceiverType):
    """Receivers that are scripts taking a ``notification`` object.

    The source id is the script's object id (``script.<id>``). The whole
    notification is passed to the script in its one field.
    """

    type_id = RECEIVER_TYPE_CUSTOM
    name = "Script"
    discoverable = True

    async def async_detect(self, hass: HomeAssistant) -> list[DiscoveryCandidate]:
        """Return a candidate for each script that takes a notification."""
        descriptions = (await async_get_all_descriptions(hass)).get("script", {})
        candidates = []
        for object_id, description in descriptions.items():
            # reload, turn_on, turn_off and toggle are not scripts.
            if object_id in ("reload", "turn_on", "turn_off", "toggle"):
                continue
            if is_notification_script(description):
                state = hass.states.get(f"script.{object_id}")
                name = state.name if state else object_id
                candidates.append(DiscoveryCandidate(object_id, name))
        return candidates

    def is_source_available(self, hass: HomeAssistant, receiver: Receiver) -> bool:
        """Return whether the script still exists."""
        return bool(receiver.source_id) and hass.services.has_service(
            "script", receiver.source_id
        )

    async def async_deliver(
        self, hass: HomeAssistant, receiver: Receiver, notification: Mapping[str, Any]
    ) -> list[str]:
        """Run the script with the notification in its ``notification`` field."""
        if not self.is_source_available(hass, receiver):
            raise HomeAssistantError(f"Script {receiver.source_id} is not available")
        await hass.services.async_call(
            "script",
            receiver.source_id,
            {SCRIPT_FIELD: dict(notification)},
            blocking=True,
        )
        return []


_RECEIVER_TYPES: dict[str, ReceiverType] = {}


def register_receiver_type(receiver_type: ReceiverType) -> None:
    """Register a receiver type; the id must be unused."""
    if receiver_type.type_id in _RECEIVER_TYPES:
        raise ValueError(f"Receiver type {receiver_type.type_id} already registered")
    _RECEIVER_TYPES[receiver_type.type_id] = receiver_type


def unregister_receiver_type(type_id: str) -> None:
    """Remove a registered receiver type (used by tests)."""
    _RECEIVER_TYPES.pop(type_id, None)


def get_receiver_type(type_id: str) -> ReceiverType | None:
    """Return the registered type for an id, or None if unknown."""
    return _RECEIVER_TYPES.get(type_id)


def receiver_types() -> list[ReceiverType]:
    """Return all registered receiver types."""
    return list(_RECEIVER_TYPES.values())


register_receiver_type(CustomReceiverType())
