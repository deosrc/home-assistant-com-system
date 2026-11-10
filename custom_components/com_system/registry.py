"""The receiver registry."""

from __future__ import annotations

from homeassistant.core import HomeAssistant

from .const import CONF_ENTRY_TYPE, DOMAIN, RECEIVER_ENTRY_TYPES
from .receiver import Receiver
from .receiver_type import ReceiverType, get_receiver_type


class ReceiverRegistry:
    """Receivers built from the receiver config entries.

    The config entries are the storage, so the registry reads them when
    asked and is always in step with adds, removals and updates. It does not
    depend on the hub or on entries being set up, so it works whatever the
    load order.
    """

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialise the registry."""
        self._hass = hass

    def all(self) -> list[Receiver]:
        """Return every configured receiver."""
        return [
            Receiver.from_entry(entry)
            for entry in self._hass.config_entries.async_entries(DOMAIN)
            if entry.data.get(CONF_ENTRY_TYPE) in RECEIVER_ENTRY_TYPES
        ]

    def get(self, entry_id: str) -> Receiver | None:
        """Return a receiver by its config entry id."""
        return next((r for r in self.all() if r.entry_id == entry_id), None)

    def type_of(self, receiver: Receiver) -> ReceiverType | None:
        """Return the receiver's type, or None when its type is unknown."""
        return get_receiver_type(receiver.type_id)

    def by_person(self, person: str) -> list[Receiver]:
        """Return receivers associated with a person."""
        return [r for r in self.all() if person in self._people(r)]

    def by_area(self, area: str) -> list[Receiver]:
        """Return receivers associated with an area."""
        return [r for r in self.all() if area in self._areas(r)]

    def _people(self, receiver: Receiver) -> tuple[str, ...]:
        receiver_type = self.type_of(receiver)
        if receiver_type is None:
            return receiver.people
        return receiver_type.associated_people(receiver)

    def _areas(self, receiver: Receiver) -> tuple[str, ...]:
        receiver_type = self.type_of(receiver)
        if receiver_type is None:
            return receiver.areas
        return receiver_type.associated_areas(receiver)
