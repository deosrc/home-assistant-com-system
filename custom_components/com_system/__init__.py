"""The Com System integration.

There is one hub config entry and one config entry per receiver. Integration
level parts (registry, notify action, websocket API) belong in
``async_setup`` so receiver entries can load in any order.
"""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the integration once, independent of config entries."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the hub or a receiver from a config entry."""
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload the hub or a receiver."""
    return True


__all__ = ["DOMAIN"]
