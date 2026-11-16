"""Notification channels.

Channels live in the hub entry's data (``data["channels"]``, a dict of
``{channel id: {"name", "defaults"}}``), which no config or options flow
touches. Each has a ``notification_channel`` entity (see
``notification_channel.py``). The defaults are content (``title``,
``priority``, ``image`` and ``data``). A notification that names a channel
entity gets the defaults for anything it does not set itself; what the call
sets always wins (``data`` is deep-merged). The mobile app receivers also use
the name as the Android notification channel.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er

from .const import (
    CONF_CHANNELS,
    CONF_ENTRY_TYPE,
    DATA_CHANNEL_MANAGER,
    DOMAIN,
    ENTRY_TYPE_HUB,
    NOTIFICATION_CHANNEL_DOMAIN,
)
from .content import (
    ATTR_ACTIONS,
    ATTR_CAR_UI,
    ATTR_CLICK_ACTION,
    ATTR_DATA,
    ATTR_IMAGE,
    ATTR_PRIORITY,
    ATTR_TAG,
    ATTR_TITLE,
    merge,
    validate_actions,
    validate_click_action,
    validate_data,
    validate_image,
    validate_priority,
    validate_tag,
)
from .mobile_app import async_remove_channel

_LOGGER = logging.getLogger(__name__)

ATTR_CHANNEL = "channel"

DEFAULT_KEYS = (
    ATTR_TITLE,
    ATTR_PRIORITY,
    ATTR_IMAGE,
    ATTR_CLICK_ACTION,
    ATTR_ACTIONS,
    ATTR_TAG,
    ATTR_CAR_UI,
    ATTR_DATA,
)

DEFAULTS_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_TITLE): cv.string,
        vol.Optional(ATTR_PRIORITY): validate_priority,
        vol.Optional(ATTR_IMAGE): validate_image,
        vol.Optional(ATTR_CLICK_ACTION): validate_click_action,
        vol.Optional(ATTR_ACTIONS): validate_actions,
        vol.Optional(ATTR_TAG): validate_tag,
        vol.Optional(ATTR_CAR_UI): cv.boolean,
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


def hub_entry(hass: HomeAssistant) -> ConfigEntry | None:
    """Return the hub entry, which holds the channels."""
    return next(
        (
            entry
            for entry in hass.config_entries.async_entries(DOMAIN)
            if entry.data.get(CONF_ENTRY_TYPE) == ENTRY_TYPE_HUB
        ),
        None,
    )


def get_channels(hub: ConfigEntry) -> dict[str, dict[str, Any]]:
    """Return the hub's channels by id (as stored; do not modify)."""
    return dict(hub.data.get(CONF_CHANNELS, {}))


def unique_id_of(hub: ConfigEntry, channel_id: str) -> str:
    """Return the unique id of a channel's entity."""
    return f"{hub.entry_id}_{channel_id}"


def channel_info(
    hass: HomeAssistant, hub: ConfigEntry, channel_id: str
) -> dict[str, Any]:
    """Describe a channel for the panel."""
    channel = get_channels(hub)[channel_id]
    return {
        "channel_id": channel_id,
        "name": channel["name"],
        "entity_id": er.async_get(hass).async_get_entity_id(
            NOTIFICATION_CHANNEL_DOMAIN, DOMAIN, unique_id_of(hub, channel_id)
        ),
        "defaults": dict(channel["defaults"]),
    }


def channel_list(hass: HomeAssistant) -> list[dict[str, Any]]:
    """Return every channel, sorted by name."""
    hub = hub_entry(hass)
    if hub is None:
        return []
    ids = sorted(
        get_channels(hub), key=lambda i: get_channels(hub)[i]["name"].casefold()
    )
    return [channel_info(hass, hub, i) for i in ids]


def _loaded_hub(hass: HomeAssistant) -> ConfigEntry:
    hub = hub_entry(hass)
    if hub is None:
        raise ServiceValidationError("The Com System hub does not exist")
    return hub


def _checked(
    channels: Mapping[str, Mapping[str, Any]],
    name: str,
    defaults: Mapping[str, Any],
    channel_id: str | None,
) -> tuple[str, dict[str, Any]]:
    """Validate a name (unique ignoring case) and the defaults."""
    name = cv.string(name).strip()
    if not name:
        raise ServiceValidationError("A channel needs a name")
    taken = {c["name"].casefold() for i, c in channels.items() if i != channel_id}
    if name.casefold() in taken:
        raise ServiceValidationError(f"The channel {name} already exists")
    try:
        return name, DEFAULTS_SCHEMA(dict(defaults))
    except vol.Invalid as err:
        raise ServiceValidationError(str(err)) from err


async def _async_save(
    hass: HomeAssistant, hub: ConfigEntry, channels: dict[str, dict[str, Any]]
) -> None:
    """Store the channels in the hub's data and bring the entities in step."""
    hass.config_entries.async_update_entry(
        hub, data={**hub.data, CONF_CHANNELS: channels}
    )
    manager = hass.data[DOMAIN].get(DATA_CHANNEL_MANAGER)
    if manager is not None:
        await manager.async_sync()


async def async_create_channel(
    hass: HomeAssistant, name: str, defaults: Mapping[str, Any]
) -> dict[str, Any]:
    """Create a channel and return its description."""
    hub = _loaded_hub(hass)
    channels = get_channels(hub)
    name, clean = _checked(channels, name, defaults, None)
    channel_id = uuid.uuid4().hex
    channels[channel_id] = {"name": name, "defaults": clean}
    await _async_save(hass, hub, channels)
    return channel_info(hass, hub, channel_id)


async def async_update_channel(
    hass: HomeAssistant, channel_id: str, name: str, defaults: Mapping[str, Any]
) -> dict[str, Any]:
    """Rename a channel and replace its defaults (a rename drops the old name
    from Android devices).
    """
    hub = _loaded_hub(hass)
    channels = get_channels(hub)
    if channel_id not in channels:
        raise ServiceValidationError("No such channel")
    name, clean = _checked(channels, name, defaults, channel_id)
    channels[channel_id] = {"name": name, "defaults": clean}
    await _async_save(hass, hub, channels)
    return channel_info(hass, hub, channel_id)


async def async_delete_channel(hass: HomeAssistant, channel_id: str) -> None:
    """Delete a channel; Android devices are told to drop it."""
    hub = _loaded_hub(hass)
    channels = get_channels(hub)
    if channel_id not in channels:
        raise ServiceValidationError("No such channel")
    del channels[channel_id]
    await _async_save(hass, hub, channels)


async def async_remove_channel_from_devices(hass: HomeAssistant, name: str) -> None:
    """Send ``remove_channel`` to Android devices; failures are only logged."""
    try:
        await async_remove_channel(hass, name)
    except HomeAssistantError as err:  # the channel goes regardless
        _LOGGER.warning("Could not remove channel %s: %s", name, err)


def channel_id_of(hass: HomeAssistant, entity_id: str) -> str:
    """Return the id of the channel a ``notification_channel`` entity is.

    Raises ``ServiceValidationError`` for any other entity.
    """
    registered = er.async_get(hass).async_get(entity_id)
    hub = hub_entry(hass)
    if registered is not None and registered.platform == DOMAIN and hub is not None:
        prefix = unique_id_of(hub, "")
        channel_id = registered.unique_id[len(prefix) :]
        if registered.unique_id.startswith(prefix) and channel_id in get_channels(hub):
            return channel_id
    raise ServiceValidationError(f"{entity_id} is not a Com System channel")


def apply_channel(hass: HomeAssistant, data: Mapping[str, Any]) -> dict[str, Any]:
    """Apply the channel a call names, and replace it with the channel's name.

    Raises ``ServiceValidationError`` when the entity is not one of this
    integration's channels. Data without a channel is returned unchanged.
    """
    entity_id = data.get(ATTR_CHANNEL)
    if entity_id is None:
        return dict(data)
    channel = get_channels(_loaded_hub(hass))[channel_id_of(hass, entity_id)]
    result = apply_defaults(data, channel["defaults"])
    result[ATTR_CHANNEL] = channel["name"]
    return result


# The channel actions. They are the only way to write channels; the panel's
# Channels page calls them through Home Assistant's own action form.
SERVICE_CREATE_CHANNEL = "create_channel"
SERVICE_UPDATE_CHANNEL = "update_channel"
SERVICE_DELETE_CHANNEL = "delete_channel"

ATTR_NAME = "name"

_DEFAULT_FIELDS = {
    vol.Optional(ATTR_TITLE): cv.string,
    vol.Optional(ATTR_PRIORITY): validate_priority,
    vol.Optional(ATTR_IMAGE): validate_image,
    vol.Optional(ATTR_CLICK_ACTION): validate_click_action,
    vol.Optional(ATTR_ACTIONS): validate_actions,
    vol.Optional(ATTR_TAG): validate_tag,
    vol.Optional(ATTR_CAR_UI): cv.boolean,
    vol.Optional(ATTR_DATA): validate_data,
}

CREATE_SCHEMA = vol.Schema({vol.Required(ATTR_NAME): cv.string, **_DEFAULT_FIELDS})
UPDATE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CHANNEL): validate_channel,
        vol.Optional(ATTR_NAME): cv.string,
        **_DEFAULT_FIELDS,
    }
)
DELETE_SCHEMA = vol.Schema({vol.Required(ATTR_CHANNEL): validate_channel})


def _defaults_of(data: Mapping[str, Any]) -> dict[str, Any]:
    return {k: data[k] for k in DEFAULT_KEYS if k in data}


async def _handle_create(call: ServiceCall) -> ServiceResponse:
    return await async_create_channel(
        call.hass, call.data[ATTR_NAME], _defaults_of(call.data)
    )


async def _handle_update(call: ServiceCall) -> ServiceResponse:
    """Replace a channel's defaults with the ones given (omitted ones are
    cleared); the name is kept unless one is given.
    """
    hass = call.hass
    channel_id = channel_id_of(hass, call.data[ATTR_CHANNEL])
    name = (
        call.data.get(ATTR_NAME) or get_channels(_loaded_hub(hass))[channel_id]["name"]
    )
    return await async_update_channel(hass, channel_id, name, _defaults_of(call.data))


async def _handle_delete(call: ServiceCall) -> None:
    await async_delete_channel(
        call.hass, channel_id_of(call.hass, call.data[ATTR_CHANNEL])
    )


@callback
def async_register_channel_actions(hass: HomeAssistant) -> None:
    """Register ``com_system.create_channel``, ``update_channel`` and
    ``delete_channel``. Their fields are in ``services.yaml``.
    """
    for service, handler, schema, response in (
        (SERVICE_CREATE_CHANNEL, _handle_create, CREATE_SCHEMA, True),
        (SERVICE_UPDATE_CHANNEL, _handle_update, UPDATE_SCHEMA, True),
        (SERVICE_DELETE_CHANNEL, _handle_delete, DELETE_SCHEMA, False),
    ):
        hass.services.async_register(
            DOMAIN,
            service,
            handler,
            schema=schema,
            supports_response=SupportsResponse.OPTIONAL
            if response
            else SupportsResponse.NONE,
        )
