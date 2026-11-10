"""The Com System integration.

There is one hub config entry and one config entry per receiver. Integration
level parts (registry, notify action, websocket API) belong in
``async_setup`` so receiver entries can load in any order.
"""

from __future__ import annotations

import logging

from homeassistant.components.event import EventEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_ENTRY_TYPE,
    DATA_COMPONENT,
    DATA_ENTITIES,
    DATA_REGISTRY,
    DOMAIN,
    NOTIFICATION_RECEIVER_DOMAIN,
    RECEIVER_ENTRY_TYPES,
)
from .registry import ReceiverRegistry

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the integration once, independent of config entries."""
    hass.data[DOMAIN] = {
        DATA_REGISTRY: ReceiverRegistry(hass),
        DATA_ENTITIES: {},
        # The notification_receiver domain is provided by this integration.
        DATA_COMPONENT: EntityComponent[EventEntity](
            _LOGGER, NOTIFICATION_RECEIVER_DOMAIN, hass
        ),
    }
    return True


def _is_receiver(entry: ConfigEntry) -> bool:
    return entry.data.get(CONF_ENTRY_TYPE) in RECEIVER_ENTRY_TYPES


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the hub or a receiver from a config entry."""
    if not _is_receiver(entry):
        return True
    # Do not forward to the notification_receiver platform: it is not an
    # integration, so forwarding fails. Hand the entry to the component.
    await hass.data[DOMAIN][DATA_COMPONENT].async_setup_entry(entry)
    await hass.config_entries.async_forward_entry_setups(entry, [Platform.SWITCH])
    # Editing a receiver reloads only that receiver.
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    return True


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload the hub or a receiver."""
    if not _is_receiver(entry):
        return True
    unloaded = await hass.config_entries.async_unload_platforms(
        entry, [Platform.SWITCH]
    )
    unloaded = (
        await hass.data[DOMAIN][DATA_COMPONENT].async_unload_entry(entry) and unloaded
    )
    return unloaded


__all__ = ["DOMAIN"]
