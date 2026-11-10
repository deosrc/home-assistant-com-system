"""The Com System integration.

There is one hub config entry and one config entry per receiver. Integration
level parts (registry, notify action, websocket API) belong in
``async_setup`` so receiver entries can load in any order.
"""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.start import async_at_started
from homeassistant.helpers.typing import ConfigType

from .builtin_types import register_builtin_receiver_types
from .const import CONF_ENTRY_TYPE, DOMAIN, ENTRY_TYPE_HUB
from .detection import ReceiverDetector
from .registry import ReceiverRegistry

type ComSystemConfigEntry = ConfigEntry[ReceiverDetector]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the integration once, independent of config entries."""
    register_builtin_receiver_types()
    hass.data[DOMAIN] = {"registry": ReceiverRegistry(hass)}
    return True


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
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ComSystemConfigEntry) -> bool:
    """Unload the hub or a receiver."""
    return True


__all__ = ["DOMAIN"]
