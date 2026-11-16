"""The notification channel store.

A channel is a name plus default content (``title``, ``priority``, ``image``
and ``data``). A notification that names a channel gets the channel's
defaults for anything it does not set itself; what the call sets always wins
(``data`` is deep-merged). The mobile app receivers also use the name as the
Android notification channel. Channels live in Home Assistant's JSON
``Store``, created once in ``async_setup``.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.storage import Store

from .const import DOMAIN
from .content import (
    ATTR_DATA,
    ATTR_IMAGE,
    ATTR_PRIORITY,
    ATTR_TITLE,
    merge,
    validate_data,
    validate_image,
    validate_priority,
)

_LOGGER = logging.getLogger(__name__)

STORAGE_KEY = f"{DOMAIN}.channels"
STORAGE_VERSION = 1

ATTR_CHANNEL = "channel"

DEFAULT_KEYS = (ATTR_TITLE, ATTR_PRIORITY, ATTR_IMAGE, ATTR_DATA)

DEFAULTS_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_TITLE): cv.string,
        vol.Optional(ATTR_PRIORITY): validate_priority,
        vol.Optional(ATTR_IMAGE): validate_image,
        vol.Optional(ATTR_DATA): validate_data,
    }
)


def validate_channel_name(value: Any) -> str:
    """Validate a channel name: a non-empty string without outer spaces."""
    name = cv.string(value).strip()
    if not name:
        raise vol.Invalid("A channel needs a name")
    return name


def apply_defaults(
    data: Mapping[str, Any], defaults: Mapping[str, Any]
) -> dict[str, Any]:
    """Return call data with a channel's defaults under it.

    A field the call gives is kept; ``data`` is merged with the call's keys
    winning.
    """
    result = dict(data)
    for key in DEFAULT_KEYS:
        if key not in defaults:
            continue
        if key == ATTR_DATA and key in result:
            result[key] = merge(dict(defaults[key]), result[key])
        elif key not in result:
            result[key] = defaults[key]
    return result


class ChannelStore:
    """Channels by name, kept in storage."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Create the store; it loads from storage on first use."""
        self._hass = hass
        self._store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self._channels: dict[str, dict[str, Any]] | None = None
        self._lock = asyncio.Lock()

    async def async_load(self) -> dict[str, dict[str, Any]]:
        """Load the channels (once) and return them."""
        if self._channels is None:
            data = await self._store.async_load()
            self._channels = dict((data or {}).get("channels", {}))
        return self._channels

    async def async_list(self) -> list[dict[str, Any]]:
        """Return the channels sorted by name."""
        channels = await self.async_load()
        return [
            {"name": name, "defaults": dict(channels[name])}
            for name in sorted(channels, key=str.casefold)
        ]

    async def async_get(self, name: str) -> dict[str, Any] | None:
        """Return a channel's defaults, or None if there is no such channel."""
        defaults = (await self.async_load()).get(name)
        return dict(defaults) if defaults is not None else None

    async def async_set(
        self,
        name: str,
        defaults: Mapping[str, Any],
        *,
        previous_name: str | None = None,
    ) -> dict[str, Any]:
        """Create or replace a channel, optionally renaming ``previous_name``.

        Raises ``ServiceValidationError`` if the name is taken by another
        channel. A rename removes the old channel from mobile apps too.
        """
        name = validate_channel_name(name)
        clean = DEFAULTS_SCHEMA(dict(defaults))
        async with self._lock:
            channels = await self.async_load()
            taken = name in channels and name != previous_name
            if taken or (previous_name and previous_name not in channels):
                raise ServiceValidationError(
                    f"The channel {name} already exists"
                    if taken
                    else f"The channel {previous_name} does not exist"
                )
            if previous_name and previous_name != name:
                del channels[previous_name]
            channels[name] = clean
            self._store.async_delay_save(self._data_to_save, 1)
        if previous_name and previous_name != name:
            await self.async_remove_from_devices(previous_name)
        return {"name": name, "defaults": dict(clean)}

    async def async_remove(self, name: str) -> None:
        """Remove a channel and delete it from Android mobile apps."""
        async with self._lock:
            channels = await self.async_load()
            if name not in channels:
                raise ServiceValidationError(f"The channel {name} does not exist")
            del channels[name]
            self._store.async_delay_save(self._data_to_save, 1)
        await self.async_remove_from_devices(name)

    async def async_remove_from_devices(self, name: str) -> None:
        """Send ``remove_channel`` to every Android mobile app receiver."""
        from .mobile_app import async_remove_channel  # avoids an import cycle

        try:
            await async_remove_channel(self._hass, name)
        except HomeAssistantError as err:  # the channel is removed regardless
            _LOGGER.warning("Could not remove channel %s: %s", name, err)

    def _data_to_save(self) -> dict[str, Any]:
        return {"channels": self._channels or {}}

    async def async_apply(self, data: Mapping[str, Any]) -> dict[str, Any]:
        """Apply the defaults of the channel a call names.

        Raises ``ServiceValidationError`` for an unknown channel. Data
        without a channel is returned unchanged.
        """
        name = data.get(ATTR_CHANNEL)
        if name is None:
            return dict(data)
        defaults = await self.async_get(name)
        if defaults is None:
            raise ServiceValidationError(f"The channel {name} does not exist")
        return apply_defaults(data, defaults)
