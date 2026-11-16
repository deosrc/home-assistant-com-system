"""The channel entity (``notification_channel`` domain)."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity

from .channels import DEFAULT_KEYS


class NotificationChannelEntity(Entity):
    """A channel: its state is its name, its attributes its default content.

    It only exists to be selected in the action; the defaults live in the
    entry's options, and editing them reloads the entry.
    """

    _attr_should_poll = False
    _attr_icon = "mdi:message-badge"

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialise from the channel's entry."""
        self._entry = entry
        self._attr_unique_id = entry.entry_id
        self._attr_name = entry.title

    @property
    def state(self) -> str:
        """Return the channel name."""
        return self._entry.title

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the channel's default content."""
        return {
            k: self._entry.options[k] for k in DEFAULT_KEYS if k in self._entry.options
        }


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, add) -> None:
    """Add the channel entity."""
    add([NotificationChannelEntity(entry)])
