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
from homeassistant.helpers.start import async_at_started
from homeassistant.helpers.typing import ConfigType

from .builtin_types import register_builtin_receiver_types
from .const import (
    CONF_ENTRY_TYPE,
    DATA_COMPONENT,
    DATA_ENTITIES,
    DATA_REGISTRY,
    DOMAIN,
    ENTRY_TYPE_HUB,
    NOTIFICATION_RECEIVER_DOMAIN,
    RECEIVER_ENTRY_TYPES,
)
from .detection import ReceiverDetector
from .notify import async_register_notify_action
from .panel import async_register_panel
from .registry import ReceiverRegistry
from .websocket_api import async_register_commands

type ComSystemConfigEntry = ConfigEntry[ReceiverDetector]

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the integration once, independent of config entries."""
    register_builtin_receiver_types()
    hass.data[DOMAIN] = {
        DATA_REGISTRY: ReceiverRegistry(hass),
        DATA_ENTITIES: {},
        # The notification_receiver domain is provided by this integration.
        DATA_COMPONENT: EntityComponent[EventEntity](
            _LOGGER, NOTIFICATION_RECEIVER_DOMAIN, hass
        ),
    }
    async_register_notify_action(hass)
    async_register_commands(hass)
    await async_register_panel(hass)
    return True


def _is_receiver(entry: ConfigEntry) -> bool:
    return entry.data.get(CONF_ENTRY_TYPE) in RECEIVER_ENTRY_TYPES


async def async_setup_entry(hass: HomeAssistant, entry: ComSystemConfigEntry) -> bool:
    """Set up the hub or a receiver from a config entry.

    The hub starts detection once Home Assistant has started, so the
    registries are loaded. Pending discoveries are not stored, so this runs
    on every setup.
    """
    if entry.data.get(CONF_ENTRY_TYPE) == ENTRY_TYPE_HUB:
        detector = ReceiverDetector(hass)
        entry.runtime_data = detector
        detector.async_start()
        entry.async_on_unload(detector.async_stop)
        entry.async_on_unload(async_at_started(hass, detector.async_start_detection))
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


async def async_unload_entry(hass: HomeAssistant, entry: ComSystemConfigEntry) -> bool:
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
