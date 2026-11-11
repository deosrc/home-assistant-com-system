"""The read-only receiver entity (``notification_receiver`` domain)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from homeassistant.components.event import EventEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DATA_REGISTRY, DOMAIN, RESULT_DELIVERED, RESULTS
from .entity import ReceiverEntity
from .receiver import Receiver

ENTITY_KEY = "receiver"

# Attributes of the last notification attempt.
ATTR_TITLE = "title"
ATTR_MESSAGE = "message"
ATTR_PRIORITY = "priority"
ATTR_IMAGE = "image"
ATTR_DATA = "data"
ATTR_WARNINGS = "warnings"
CONTENT_ATTRIBUTES = (ATTR_TITLE, ATTR_MESSAGE, ATTR_PRIORITY, ATTR_IMAGE, ATTR_DATA)

# Static attributes.
ATTR_RECEIVER_TYPE = "receiver_type"
ATTR_PEOPLE = "people"
ATTR_AREAS = "areas"


class NotificationReceiverEntity(ReceiverEntity, EventEntity):
    """Read-only record of the last notification attempt for a receiver.

    The state is the time of the last attempt and the event type is its
    result (delivered, failed or skipped). It has no actions and does not
    mirror the enabled switch.
    """

    entity_key = ENTITY_KEY
    _attr_icon = "mdi:message-text"

    def __init__(self, hass: HomeAssistant, receiver: Receiver) -> None:
        """Initialise with the delivery results as event types."""
        super().__init__(hass, receiver)
        self._attr_event_types = list(RESULTS)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the receiver's type, people and areas."""
        registry = self.hass.data[DOMAIN][DATA_REGISTRY]
        receiver = registry.get(self._receiver.entry_id) or self._receiver
        return {
            ATTR_RECEIVER_TYPE: receiver.type_id,
            ATTR_PEOPLE: list(registry.people_of(receiver)),
            ATTR_AREAS: list(registry.areas_of(receiver)),
        }

    def async_record_attempt(
        self,
        result: str = RESULT_DELIVERED,
        notification: Mapping[str, Any] | None = None,
        warnings: list[str] | None = None,
    ) -> None:
        """Record a notification attempt: its result, content and warnings."""
        notification = notification or {}
        attributes: dict[str, Any] = {
            key: notification[key] for key in CONTENT_ATTRIBUTES if key in notification
        }
        attributes[ATTR_WARNINGS] = list(warnings or [])
        self._trigger_event(result, attributes)
        self.async_write_ha_state()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the receiver entity of a receiver entry."""
    receiver = hass.data[DOMAIN][DATA_REGISTRY].get(entry.entry_id)
    if receiver is not None:
        async_add_entities([NotificationReceiverEntity(hass, receiver)])
