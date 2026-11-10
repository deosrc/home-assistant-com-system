"""The receiver model."""

from __future__ import annotations

from dataclasses import dataclass, field

from homeassistant.config_entries import ConfigEntry

from .const import (
    CONF_AREAS,
    CONF_NAME,
    CONF_PEOPLE,
    CONF_RECEIVER_TYPE,
    CONF_SOURCE_ID,
    RECEIVER_TYPE_CUSTOM,
)


@dataclass(frozen=True, slots=True)
class Receiver:
    """A configured receiver, read from its config entry."""

    entry_id: str
    type_id: str
    name: str
    source_id: str | None = None
    people: tuple[str, ...] = field(default_factory=tuple)
    areas: tuple[str, ...] = field(default_factory=tuple)

    @classmethod
    def from_entry(cls, entry: ConfigEntry) -> Receiver:
        """Build a receiver from a receiver config entry.

        Entries created before the type was stored have no receiver type and
        are custom receivers.
        """
        return cls(
            entry_id=entry.entry_id,
            type_id=entry.data.get(CONF_RECEIVER_TYPE, RECEIVER_TYPE_CUSTOM),
            name=entry.data.get(CONF_NAME, entry.title),
            source_id=entry.data.get(CONF_SOURCE_ID),
            people=tuple(entry.options.get(CONF_PEOPLE, ())),
            areas=tuple(entry.options.get(CONF_AREAS, ())),
        )
