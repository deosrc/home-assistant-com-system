"""Content parameters: priority, image and per-type data.

``priority`` and ``image`` are typed fields; everything else receiver
specific goes in ``data``, an object keyed by receiver type id
(``data: {mobile_app: {...}, pushover: {...}}``). A receiver type reads only
its own block. Each type declares its capabilities, and the dispatcher drops
the content a type does not support, with a warning, before delivery.
"""

from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

if TYPE_CHECKING:
    from .receiver_type import ReceiverType

_LOGGER = logging.getLogger(__name__)

ATTR_TITLE = "title"
ATTR_MESSAGE = "message"
ATTR_PRIORITY = "priority"
ATTR_IMAGE = "image"
ATTR_DATA = "data"

PRIORITY_LOW = "low"
PRIORITY_NORMAL = "normal"
PRIORITY_HIGH = "high"
PRIORITY_CRITICAL = "critical"
PRIORITIES = (PRIORITY_LOW, PRIORITY_NORMAL, PRIORITY_HIGH, PRIORITY_CRITICAL)

# Capabilities a receiver type declares: the typed fields it supports, and
# its ``data`` keys. ``data`` alone accepts any key in the type's block;
# ``data.<key>`` accepts only that key.
CAP_TITLE = ATTR_TITLE
CAP_PRIORITY = ATTR_PRIORITY
CAP_IMAGE = ATTR_IMAGE
CAP_DATA = ATTR_DATA
DATA_PREFIX = "data."

MEDIA_SOURCE_PREFIX = "media-source://"
LOCAL_PREFIX = "/local/"


def validate_priority(value: Any) -> str:
    """Validate a priority: low, normal, high or critical."""
    return vol.In(PRIORITIES)(value)


def validate_image(value: Any) -> str:
    """Validate an image: an http(s) URL, a /local/ path or a media source ID."""
    image = cv.string(value).strip()
    if image.startswith(("http://", "https://")):
        return cv.url(image)
    if image.startswith(LOCAL_PREFIX) and len(image) > len(LOCAL_PREFIX):
        return image
    if image.startswith(MEDIA_SOURCE_PREFIX) and len(image) > len(MEDIA_SOURCE_PREFIX):
        return image
    raise vol.Invalid(
        "image must be an http(s) URL, a /local/ path or a media-source:// ID"
    )


def validate_data(value: Any) -> dict[str, dict[str, Any]]:
    """Validate ``data``: an object of per-receiver-type objects."""
    return vol.Schema({cv.string: dict})(value)


def data_capabilities(capabilities: frozenset[str]) -> tuple[bool, frozenset[str]]:
    """Return whether any data key is accepted, and the accepted keys."""
    keys = frozenset(
        c[len(DATA_PREFIX) :] for c in capabilities if c.startswith(DATA_PREFIX)
    )
    return CAP_DATA in capabilities, keys


def apply_capabilities(
    receiver_type: ReceiverType, notification: Mapping[str, Any]
) -> tuple[dict[str, Any], list[str]]:
    """Return the notification as one receiver type receives it, and warnings.

    Content the type does not support is dropped and named in a warning.
    ``data`` becomes the type's own block (absent when empty). A priority of
    ``normal`` is the default, so it is never reported as dropped. A type
    that accepts any content (scripts) gets everything.
    """
    content = dict(notification)
    block = (notification.get(ATTR_DATA) or {}).get(receiver_type.type_id)
    content.pop(ATTR_DATA, None)
    if block:
        content[ATTR_DATA] = dict(block)
    if receiver_type.accepts_any_content:
        return content, []

    caps = receiver_type.capabilities
    name = receiver_type.name
    warnings: list[str] = []
    for field, cap in (
        (ATTR_TITLE, CAP_TITLE),
        (ATTR_PRIORITY, CAP_PRIORITY),
        (ATTR_IMAGE, CAP_IMAGE),
    ):
        if field not in content or cap in caps:
            continue
        if field == ATTR_PRIORITY and content[field] == PRIORITY_NORMAL:
            del content[field]
            continue
        del content[field]
        warnings.append(f"The {field} is not supported by {name} and was dropped")
    if block:
        any_key, keys = data_capabilities(caps)
        if not any_key:
            kept = {k: v for k, v in block.items() if k in keys}
            for key in block:
                if key not in keys:
                    warnings.append(
                        f"The data key {key} is not supported by {name} and was dropped"
                    )
            if kept:
                content[ATTR_DATA] = kept
            else:
                del content[ATTR_DATA]
    return content, warnings


async def async_image_url(hass: HomeAssistant, image: str) -> str:
    """Return a URL a device can fetch for an image.

    URLs and ``/local/`` paths are returned as they are; a media source ID is
    resolved. Raises ``HomeAssistantError`` when it cannot be resolved.
    """
    if not image.startswith(MEDIA_SOURCE_PREFIX):
        return image
    try:
        from homeassistant.components.media_player import (
            async_process_play_media_url,
        )
        from homeassistant.components.media_source import (
            async_resolve_media,
        )

        item = await async_resolve_media(hass, image, None)
        return async_process_play_media_url(hass, item.url)
    except HomeAssistantError:
        raise
    except Exception as err:  # media source not set up, unknown source
        raise HomeAssistantError(
            f"The media source {image} cannot be resolved"
        ) from err


def local_image_path(hass: HomeAssistant, image: str) -> str:
    """Return the file an image refers to on this Home Assistant.

    Only ``/local/`` paths (the ``www`` folder) and local media sources are
    files; a URL is not. The file must be in ``allowlist_external_dirs``.
    Raises ``HomeAssistantError`` otherwise. Does not check it exists.
    """
    if image.startswith(LOCAL_PREFIX):
        base = hass.config.path("www")
        relative = image[len(LOCAL_PREFIX) :]
    elif image.startswith(MEDIA_SOURCE_PREFIX):
        # media-source://media_source/<source dir>/<path>
        rest = image[len(MEDIA_SOURCE_PREFIX) :].partition("/")[2]
        source_dir, _, relative = rest.partition("/")
        media_dir = hass.config.media_dirs.get(source_dir)
        if media_dir is None or not relative:
            raise HomeAssistantError(f"{image} is not a local media file")
        base = media_dir
    else:
        raise HomeAssistantError("A URL is not a local file")
    path = os.path.realpath(os.path.join(base, relative))
    if os.path.commonpath([path, os.path.realpath(base)]) != os.path.realpath(base):
        raise HomeAssistantError("The image path is outside its folder")
    if not hass.config.is_allowed_path(path):
        raise HomeAssistantError(
            f"{path} is not in allowlist_external_dirs, so it cannot be attached"
        )
    return path


async def async_existing_local_image(hass: HomeAssistant, image: str) -> str:
    """Return the local file for an image, checking it exists."""
    path = local_image_path(hass, image)
    if not await asyncio.to_thread(os.path.isfile, path):
        raise HomeAssistantError(f"{path} does not exist")
    return path


def merge(base: dict[str, Any], extra: Mapping[str, Any]) -> dict[str, Any]:
    """Deep-merge ``extra`` over ``base`` (objects merge, other values replace)."""
    result = dict(base)
    for key, value in extra.items():
        if isinstance(value, Mapping) and isinstance(result.get(key), Mapping):
            result[key] = merge(dict(result[key]), value)
        else:
            result[key] = value
    return result
