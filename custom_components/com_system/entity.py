"""Shared base for the entities of a receiver."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceEntry, DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DATA_ENTITIES, DATA_REGISTRY, DOMAIN
from .receiver import Receiver


def _resolve_device(
    hass: HomeAssistant, receiver: Receiver
) -> tuple[DeviceInfo | None, DeviceEntry | None]:
    """Return the device info for the receiver's own device, or the source
    device to attach to.

    A device belongs to one config entry, so attaching to another
    integration's device means pointing ``device_entry`` at it and returning
    no ``device_info``.
    """
    receiver_type = hass.data[DOMAIN][DATA_REGISTRY].type_of(receiver)
    identifiers = (
        receiver_type.source_device_identifiers(receiver) if receiver_type else None
    )
    if identifiers:
        device = dr.async_get(hass).async_get_device(identifiers=identifiers)
        if device is not None:
            return None, device
    return (
        DeviceInfo(
            identifiers={(DOMAIN, receiver.entry_id)},
            name=receiver.name,
            manufacturer="Com System",
            model=receiver_type.name if receiver_type else None,
        ),
        None,
    )


class ReceiverEntity(Entity):
    """Base for the entities of one receiver, grouped on its device.

    Subclasses set ``entity_key`` and are findable by delivery through
    ``hass.data[DOMAIN][DATA_ENTITIES][entry_id][entity_key]``.
    """

    _attr_has_entity_name = True
    _attr_should_poll = False
    entity_key: str

    def __init__(self, hass: HomeAssistant, receiver: Receiver) -> None:
        """Initialise from the receiver."""
        self._receiver = receiver
        self._attr_unique_id = f"{receiver.entry_id}_{self.entity_key}"
        self._attr_device_info, device_entry = _resolve_device(hass, receiver)
        if device_entry is not None:
            self.device_entry = device_entry

    async def async_added_to_hass(self) -> None:
        """Make the entity findable by delivery."""
        await super().async_added_to_hass()
        self.hass.data[DOMAIN][DATA_ENTITIES].setdefault(self._receiver.entry_id, {})[
            self.entity_key
        ] = self

    async def async_will_remove_from_hass(self) -> None:
        """Stop being findable."""
        entities = self.hass.data[DOMAIN][DATA_ENTITIES].get(self._receiver.entry_id)
        if entities is not None:
            entities.pop(self.entity_key, None)
            if not entities:
                self.hass.data[DOMAIN][DATA_ENTITIES].pop(self._receiver.entry_id)
        await super().async_will_remove_from_hass()
