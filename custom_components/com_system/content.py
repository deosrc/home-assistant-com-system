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
ATTR_MESSAGES = "messages"
ATTR_PRIORITY = "priority"
ATTR_IMAGE = "image"
ATTR_DATA = "data"
ATTR_CLICK_ACTION = "click_action"
ATTR_ACTIONS = "actions"
ATTR_TAG = "tag"
ATTR_CAR_UI = "car_ui"

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
CAP_CLICK_ACTION = ATTR_CLICK_ACTION
CAP_ACTIONS = ATTR_ACTIONS
CAP_TAG = ATTR_TAG
CAP_CAR_UI = ATTR_CAR_UI
DATA_PREFIX = "data."

# Message types: what a piece of message content is for. ``text`` is shown on
# a display, ``tts`` is spoken. A receiver type declares the types it takes in
# ``message_types``.
MESSAGE_TEXT = "text"
MESSAGE_TTS = "tts"
MESSAGE_TYPES = (MESSAGE_TEXT, MESSAGE_TTS)
MESSAGE_TYPE_LABELS = {MESSAGE_TEXT: "Text Display", MESSAGE_TTS: "Text-to-speech"}

MEDIA_SOURCE_PREFIX = "media-source://"
LOCAL_PREFIX = "/local/"


def validate_priority(value: Any) -> str:
    """Validate a priority: low, normal, high or critical (any case)."""
    return vol.In(PRIORITIES)(cv.string(value).strip().lower())


# The image field is a choose selector: a URL, or an image or camera entity.
CHOICE_URL = "URL"
CHOICE_ENTITY = "Entity"
IMAGE_ENTITY_DOMAINS = ("image", "camera")
_PROXY_PATHS = {"image": "/api/image_proxy/", "camera": "/api/camera_proxy/"}


def validate_image(value: Any) -> str:
    """Validate an image and return it as a string.

    The value is ``{active_choice: URL, URL: ...}`` or ``{active_choice:
    Entity, Entity: ...}`` (what the form sends), or a plain string that is
    either an image or camera entity id or a URL: http(s), a ``/local/`` path
    or a media source ID.
    """
    if isinstance(value, dict):
        choice = value.get("active_choice")
        if choice == CHOICE_ENTITY:
            return cv.entity_domain(list(IMAGE_ENTITY_DOMAINS))(
                value.get(CHOICE_ENTITY)
            )
        if choice != CHOICE_URL:
            raise vol.Invalid(f"active_choice must be {CHOICE_URL} or {CHOICE_ENTITY}")
        value = value.get(CHOICE_URL)
    image = cv.string(value).strip()
    if image.split(".", 1)[0] in IMAGE_ENTITY_DOMAINS and "/" not in image:
        return cv.entity_domain(list(IMAGE_ENTITY_DOMAINS))(image)
    if image.startswith(("http://", "https://")):
        return cv.url(image)
    if image.startswith(LOCAL_PREFIX) and len(image) > len(LOCAL_PREFIX):
        return image
    if image.startswith(MEDIA_SOURCE_PREFIX) and len(image) > len(MEDIA_SOURCE_PREFIX):
        return image
    raise vol.Invalid(
        "image must be an http(s) URL, a /local/ path, a media-source:// ID "
        "or an image or camera entity"
    )


def is_image_entity(image: str) -> bool:
    """Return whether an image is an image or camera entity id."""
    return image.split(".", 1)[0] in IMAGE_ENTITY_DOMAINS and "/" not in image


def _message_type(value: Any) -> str:
    """Validate a message type (the id or its label, any case)."""
    value = cv.string(value).strip().lower()
    for type_id, label in MESSAGE_TYPE_LABELS.items():
        if value in (type_id, label.lower()):
            return type_id
    raise vol.Invalid(f"type must be one of {', '.join(MESSAGE_TYPES)}")


_MESSAGE_ITEM_SCHEMA = vol.Schema(
    {
        vol.Optional("type", default=list(MESSAGE_TYPES)): vol.All(
            cv.ensure_list, [_message_type]
        ),
        vol.Required("content"): cv.string,
    }
)


def validate_message(value: Any) -> dict[str, str]:
    """Validate ``message`` and return it as ``{type: content}``.

    A plain string is the content for every type. Otherwise it is a list of
    ``{type, content}`` objects (a single object is accepted). ``type`` is
    one type or a list of types, so one content can serve several, and both
    when omitted. Each type may be given once.
    """
    if isinstance(value, str):
        if not value.strip():
            raise vol.Invalid("message must not be empty")
        return {t: value for t in MESSAGE_TYPES}
    if (
        isinstance(value, dict)
        and value
        and "type" not in value
        and set(value) <= set(MESSAGE_TYPES)
    ):
        # Already validated (``{type: content}``).
        value = [{"type": k, "content": v} for k, v in value.items()]
    items = vol.All(cv.ensure_list, [_MESSAGE_ITEM_SCHEMA])(value)
    messages: dict[str, str] = {}
    for item in items:
        if not item["type"]:
            raise vol.Invalid("message type must not be empty")
        for type_id in item["type"]:
            if type_id in messages:
                raise vol.Invalid(f"message type {type_id} is given twice")
            messages[type_id] = item["content"]
    if not messages:
        raise vol.Invalid("message must have at least one item")
    return messages


def display_message(messages: Mapping[str, str]) -> str:
    """Return the text to show for a message: the text, else the speech."""
    return messages.get(MESSAGE_TEXT) or messages.get(MESSAGE_TTS) or ""


def message_for(
    receiver_type: ReceiverType, notification: Mapping[str, Any]
) -> str | None:
    """Return the message a receiver type should get, or None if none applies.

    The first of the type's ``message_types`` (in the order of its tuple) that
    the notification has content for. A notification without ``messages``
    (built by code, not the action) has one ``message`` for every type.
    """
    messages = notification.get(ATTR_MESSAGES)
    if messages is None:
        return notification.get(ATTR_MESSAGE)
    for type_id in receiver_type.message_types:
        if messages.get(type_id):
            return messages[type_id]
    return None


def validate_click_action(value: Any) -> str:
    """Validate a click action: a non-empty URI or Home Assistant path."""
    value = cv.string(value).strip()
    if not value:
        raise vol.Invalid("click_action must not be empty")
    return value


def validate_tag(value: Any) -> str:
    """Validate a tag: a non-empty string."""
    value = cv.string(value).strip()
    if not value:
        raise vol.Invalid("tag must not be empty")
    return value


# One button on a notification: an ``id`` (sent back in the response) and a
# ``label`` (the button text). The mobile app receiver sends them as the app's
# ``action`` and ``title``. Other keys of the companion app (``behavior``,
# ``destructive``, ``icon`` and so on) are passed through.
_ACTION_SCHEMA = vol.Schema(
    {
        vol.Required("id"): cv.string,
        vol.Required("label"): cv.string,
        vol.Optional("uri"): cv.string,
    },
    extra=vol.ALLOW_EXTRA,
)


def validate_actions(value: Any) -> list[dict[str, Any]]:
    """Validate the actions: a list of ``{id, label, uri?}`` objects."""
    return vol.All(cv.ensure_list, [_ACTION_SCHEMA])(value)


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

    Content the type does not support is dropped and listed in one warning.
    ``data`` becomes the type's own block (absent when empty). A priority of
    ``normal`` is the default, so it is never reported as dropped. A type
    that accepts any content (scripts) gets everything.
    """
    content = dict(notification)
    message = message_for(receiver_type, notification)
    if message is not None:
        content[ATTR_MESSAGE] = message
    if receiver_type.accepts_any_content:
        # Scripts see every message type as well as the one chosen.
        pass
    else:
        content.pop(ATTR_MESSAGES, None)
    block = (notification.get(ATTR_DATA) or {}).get(receiver_type.type_id)
    content.pop(ATTR_DATA, None)
    if block:
        content[ATTR_DATA] = dict(block)
    if receiver_type.accepts_any_content:
        return content, []

    caps = receiver_type.capabilities
    name = receiver_type.name
    dropped: list[str] = []
    for field, cap in (
        (ATTR_TITLE, CAP_TITLE),
        (ATTR_PRIORITY, CAP_PRIORITY),
        (ATTR_IMAGE, CAP_IMAGE),
        (ATTR_CLICK_ACTION, CAP_CLICK_ACTION),
        (ATTR_ACTIONS, CAP_ACTIONS),
        (ATTR_TAG, CAP_TAG),
        (ATTR_CAR_UI, CAP_CAR_UI),
    ):
        if field not in content or cap in caps:
            continue
        if field == ATTR_PRIORITY and content[field] == PRIORITY_NORMAL:
            del content[field]
            continue
        del content[field]
        dropped.append(field)
    if block:
        any_key, keys = data_capabilities(caps)
        if not any_key:
            kept = {k: v for k, v in block.items() if k in keys}
            for key in block:
                if key not in keys:
                    dropped.append(f"data.{key}")
            if kept:
                content[ATTR_DATA] = kept
            else:
                del content[ATTR_DATA]
    warnings: list[str] = []
    if dropped:
        warnings.append(
            f"{name} does not support these properties, which were dropped: "
            + ", ".join(dropped)
        )
    return content, warnings


async def async_image_url(hass: HomeAssistant, image: str) -> str:
    """Return a URL a device can fetch for an image.

    URLs and ``/local/`` paths are returned as they are; a media source ID is
    resolved; an image or camera entity becomes its current ``entity_picture``
    (a path with an access token, which the companion app can fetch). Raises
    ``HomeAssistantError`` when it cannot be resolved.
    """
    if is_image_entity(image):
        state = hass.states.get(image)
        if state is None:
            raise HomeAssistantError(f"The entity {image} does not exist")
        return state.attributes.get("entity_picture") or (
            _PROXY_PATHS[image.split(".", 1)[0]] + image
        )
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
    if is_image_entity(image):
        raise HomeAssistantError("An entity is not a local file")
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
