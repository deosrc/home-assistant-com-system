"""Notification channels.

A channel is a config entry (entry type ``channel``) with a
``notification_channel`` entity. Its title is the channel name and its
options are the default content (``title``, ``priority``, ``image`` and
``data``). A notification that names a channel entity gets the defaults for
anything it does not set itself; what the call sets always wins (``data`` is
deep-merged). The mobile app receivers also use the name as the Android
notification channel.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er

from .const import (
    CONF_ENTRY_TYPE,
    CONF_NAME,
    DOMAIN,
    ENTRY_TYPE_CHANNEL,
    NOTIFICATION_CHANNEL_DOMAIN,
)
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
from .mobile_app import async_remove_channel

_LOGGER = logging.getLogger(__name__)

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


def validate_channel(value: Any) -> str:
    """Validate the channel field: a ``notification_channel`` entity id."""
    return cv.entity_domain(NOTIFICATION_CHANNEL_DOMAIN)(value)


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


def channel_entries(hass: HomeAssistant) -> list[ConfigEntry]:
    """Return the channel entries, sorted by name."""
    return sorted(
        (
            entry
            for entry in hass.config_entries.async_entries(DOMAIN)
            if entry.data.get(CONF_ENTRY_TYPE) == ENTRY_TYPE_CHANNEL
        ),
        key=lambda e: e.title.casefold(),
    )


def channel_info(hass: HomeAssistant, entry: ConfigEntry) -> dict[str, Any]:
    """Describe a channel for the panel."""
    return {
        "entry_id": entry.entry_id,
        "name": entry.title,
        "entity_id": er.async_get(hass).async_get_entity_id(
            NOTIFICATION_CHANNEL_DOMAIN, DOMAIN, entry.entry_id
        ),
        "defaults": dict(entry.options),
    }


def _checked(
    hass: HomeAssistant,
    name: str,
    defaults: Mapping[str, Any],
    entry: ConfigEntry | None,
) -> tuple[str, dict[str, Any]]:
    """Validate a name (unique ignoring case) and the defaults."""
    name = cv.string(name).strip()
    if not name:
        raise ServiceValidationError("A channel needs a name")
    taken = {e.title.casefold() for e in channel_entries(hass) if e is not entry}
    if name.casefold() in taken:
        raise ServiceValidationError(f"The channel {name} already exists")
    try:
        return name, DEFAULTS_SCHEMA(dict(defaults))
    except vol.Invalid as err:
        raise ServiceValidationError(str(err)) from err


async def async_create_channel(
    hass: HomeAssistant, name: str, defaults: Mapping[str, Any]
) -> ConfigEntry:
    """Create a channel through a config flow with the ``channel`` source."""
    name, clean = _checked(hass, name, defaults, None)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "channel"},
        data={CONF_NAME: name, "defaults": clean},
    )
    return result["result"]


async def async_update_channel(
    hass: HomeAssistant,
    entry: ConfigEntry,
    name: str,
    defaults: Mapping[str, Any],
) -> None:
    """Rename a channel and replace its defaults.

    A rename tells Android devices to drop the old channel. Updating
    reloads the entry, which refreshes the entity.
    """
    name, clean = _checked(hass, name, defaults, entry)
    if name != entry.title:
        await async_remove_channel_from_devices(hass, entry.title)
    hass.config_entries.async_update_entry(entry, title=name, options=clean)


async def async_remove_channel_from_devices(hass: HomeAssistant, name: str) -> None:
    """Send ``remove_channel`` to Android devices; failures are only logged."""
    try:
        await async_remove_channel(hass, name)
    except HomeAssistantError as err:  # the channel goes regardless
        _LOGGER.warning("Could not remove channel %s: %s", name, err)


def apply_channel(hass: HomeAssistant, data: Mapping[str, Any]) -> dict[str, Any]:
    """Apply the channel a call names, and replace it with the channel's name.

    Raises ``ServiceValidationError`` when the entity is not one of this
    integration's channels. Data without a channel is returned unchanged.
    """
    entity_id = data.get(ATTR_CHANNEL)
    if entity_id is None:
        return dict(data)
    registered = er.async_get(hass).async_get(entity_id)
    entry = (
        hass.config_entries.async_get_entry(registered.config_entry_id)
        if registered is not None and registered.config_entry_id
        else None
    )
    if (
        registered is None
        or registered.platform != DOMAIN
        or entry is None
        or entry.data.get(CONF_ENTRY_TYPE) != ENTRY_TYPE_CHANNEL
    ):
        raise ServiceValidationError(f"{entity_id} is not a Com System channel")
    result = apply_defaults(data, entry.options)
    result[ATTR_CHANNEL] = entry.title
    return result
