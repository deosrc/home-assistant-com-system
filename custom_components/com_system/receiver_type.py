"""Receiver type definitions: the extension point for new receiver types."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from homeassistant.core import HomeAssistant

from .const import RECEIVER_TYPE_CUSTOM
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

    async def async_deliver(
        self, hass: HomeAssistant, receiver: Receiver, notification: Mapping[str, Any]
    ) -> None:
        """Deliver a notification (implemented with the dispatcher)."""
        raise NotImplementedError

    def associated_people(self, receiver: Receiver) -> tuple[str, ...]:
        """Return the people the receiver relates to."""
        return receiver.people

    def associated_areas(self, receiver: Receiver) -> tuple[str, ...]:
        """Return the areas the receiver relates to."""
        return receiver.areas

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


class CustomReceiverType(ReceiverType):
    """The generic type for receivers mapped to user-defined actions."""

    type_id = RECEIVER_TYPE_CUSTOM
    name = "Custom"


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
