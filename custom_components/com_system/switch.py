"""The enabled switch of a receiver."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DATA_REGISTRY, DOMAIN
from .entity import ReceiverEntity

ENTITY_KEY = "enabled"


class ReceiverEnabledSwitch(ReceiverEntity, SwitchEntity, RestoreEntity):
    """Whether the receiver is enabled; the source of truth for that state.

    On means enabled. A new receiver is enabled. The state is restored on
    startup.
    """

    entity_key = ENTITY_KEY
    _attr_translation_key = "enabled"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_is_on = True

    async def async_added_to_hass(self) -> None:
        """Restore the previous state."""
        await super().async_added_to_hass()
        if (last := await self.async_get_last_state()) is not None:
            self._attr_is_on = last.state != "off"

    @property
    def icon(self) -> str:
        """Return a chat bubble, crossed out while notifications are off."""
        return "mdi:message-text" if self.is_on else "mdi:message-off"

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable the receiver."""
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable the receiver."""
        self._attr_is_on = False
        self.async_write_ha_state()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the enabled switch of a receiver entry."""
    receiver = hass.data[DOMAIN][DATA_REGISTRY].get(entry.entry_id)
    if receiver is not None:
        async_add_entities([ReceiverEnabledSwitch(hass, receiver)])
