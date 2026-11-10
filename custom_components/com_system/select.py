"""The personal/shared select of a mobile app receiver."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import (
    AUDIENCES,
    DATA_REGISTRY,
    DOMAIN,
    RECEIVER_TYPE_MOBILE_APP,
)
from .entity import ReceiverEntity
from .mobile_app import AUDIENCE_KEY, default_audience
from .receiver import Receiver


class ReceiverAudienceSelect(ReceiverEntity, SelectEntity, RestoreEntity):
    """Whether a mobile app device is personal or shared.

    Personal devices are reached through their person; shared ones never are
    (only by area or by name). A new receiver starts personal when a person
    is linked, otherwise shared; after that the state is restored.
    """

    entity_key = AUDIENCE_KEY
    _attr_translation_key = "audience"

    def __init__(self, hass: HomeAssistant, receiver: Receiver) -> None:
        """Initialise with personal and shared as the options."""
        super().__init__(hass, receiver)
        self._attr_options = list(AUDIENCES)

    async def async_added_to_hass(self) -> None:
        """Restore the previous choice, or infer the default."""
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last is not None and last.state in AUDIENCES:
            self._attr_current_option = last.state
        else:
            self._attr_current_option = default_audience(self.hass, self._receiver)

    async def async_select_option(self, option: str) -> None:
        """Set personal or shared."""
        self._attr_current_option = option
        self.async_write_ha_state()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the select for mobile app receivers; other types have none."""
    receiver = hass.data[DOMAIN][DATA_REGISTRY].get(entry.entry_id)
    if receiver is not None and receiver.type_id == RECEIVER_TYPE_MOBILE_APP:
        async_add_entities([ReceiverAudienceSelect(hass, receiver)])
