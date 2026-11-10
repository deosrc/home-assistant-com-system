"""The receiver registry."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from .const import (
    CONF_ENTRY_TYPE,
    DOMAIN,
    NOTIFICATION_RECEIVER_DOMAIN,
    RECEIVER_ENTRY_TYPES,
)
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
        return [r for r in self.all() if person in self.people_of(r)]

    def by_area(self, area: str) -> list[Receiver]:
        """Return receivers associated with an area."""
        return [r for r in self.all() if area in self.areas_of(r)]

    def people_of(self, receiver: Receiver) -> tuple[str, ...]:
        """Return the people a receiver relates to."""
        receiver_type = self.type_of(receiver)
        if receiver_type is None:
            return receiver.people
        return receiver_type.associated_people(receiver)

    def areas_of(self, receiver: Receiver) -> tuple[str, ...]:
        """Return the area of a receiver (none, or one).

        The area is not stored: it is the area of the receiver's
        ``notification_receiver`` entity, which is what Home Assistant uses
        when that entity is targeted by area. That entity has no name of its
        own, so it cannot have an area of its own and takes its device's.
        The enabled switch is not consulted.
        """
        entity_registry = er.async_get(self._hass)
        entity_id = entity_registry.async_get_entity_id(
            NOTIFICATION_RECEIVER_DOMAIN, DOMAIN, f"{receiver.entry_id}_receiver"
        )
        entity = entity_registry.async_get(entity_id) if entity_id else None
        if entity is None or entity.device_id is None:
            return ()
        device = dr.async_get(self._hass).async_get(entity.device_id)
        area_id = entity.area_id or (device.area_id if device else None)
        return (area_id,) if area_id else ()
