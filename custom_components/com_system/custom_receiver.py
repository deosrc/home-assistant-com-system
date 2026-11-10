"""Custom receivers: validation and delivery through a mapped action."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, TemplateError
from homeassistant.helpers.template import Template

from .const import (
    CONF_ACTION,
    CONF_ACTION_DATA,
    CONF_ENTRY_TYPE,
    CONF_NAME,
    DOMAIN,
    RECEIVER_ENTRY_TYPES,
)

ERROR_NAME_REQUIRED = "name_required"
ERROR_NAME_EXISTS = "name_exists"
ERROR_INVALID_ACTION = "invalid_action"
ERROR_UNKNOWN_ACTION = "unknown_action"
ERROR_INVALID_DATA = "invalid_action_data"
ERROR_INVALID_TEMPLATE = "invalid_template"


def split_action(action: str) -> tuple[str, str] | None:
    """Split ``domain.service`` into its parts, or None if malformed."""
    domain, dot, service = action.strip().partition(".")
    if not dot or not domain or not service or "." in service or " " in action.strip():
        return None
    return domain.lower(), service.lower()


def _check_templates(hass: HomeAssistant, value: Any) -> None:
    """Raise ``TemplateError`` when a string in ``value`` is not a template."""
    if isinstance(value, str):
        Template(value, hass).ensure_valid()
    elif isinstance(value, Mapping):
        for item in value.values():
            _check_templates(hass, item)
    elif isinstance(value, list | tuple):
        for item in value:
            _check_templates(hass, item)


def validate_custom_receiver(
    hass: HomeAssistant,
    *,
    name: str,
    action: str,
    action_data: Any,
    exclude_entry_id: str | None = None,
) -> str | None:
    """Return an error key for an invalid custom receiver, else None.

    The action must exist now; it may disappear later, in which case
    delivery fails with a clear result.
    """
    name = (name or "").strip()
    if not name:
        return ERROR_NAME_REQUIRED
    for entry in hass.config_entries.async_entries(DOMAIN):
        if (
            entry.data.get(CONF_ENTRY_TYPE) in RECEIVER_ENTRY_TYPES
            and entry.entry_id != exclude_entry_id
            and entry.data.get(CONF_NAME, entry.title).strip().casefold()
            == name.casefold()
        ):
            return ERROR_NAME_EXISTS
    parts = split_action(action or "")
    if parts is None:
        return ERROR_INVALID_ACTION
    if not hass.services.has_service(*parts):
        return ERROR_UNKNOWN_ACTION
    if action_data is not None and not isinstance(action_data, Mapping):
        return ERROR_INVALID_DATA
    try:
        _check_templates(hass, action_data or {})
    except TemplateError:
        return ERROR_INVALID_TEMPLATE
    return None


def custom_receiver_data(
    name: str, action: str, action_data: Mapping[str, Any] | None
) -> dict[str, Any]:
    """Return the cleaned values stored in a custom receiver's entry."""
    return {
        CONF_NAME: name.strip(),
        CONF_ACTION: action.strip().lower(),
        CONF_ACTION_DATA: dict(action_data or {}),
    }


def _render(hass: HomeAssistant, value: Any, variables: Mapping[str, Any]) -> Any:
    if isinstance(value, str):
        return Template(value, hass).async_render(variables, parse_result=True)
    if isinstance(value, Mapping):
        return {k: _render(hass, v, variables) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_render(hass, v, variables) for v in value]
    return value


async def async_deliver_custom(
    hass: HomeAssistant,
    action: str | None,
    action_data: Mapping[str, Any],
    notification: Mapping[str, Any],
) -> list[str]:
    """Call the mapped action with the rendered data.

    The templates see ``title``, ``message``, ``priority``, ``image`` and
    ``data``. Content the action does not use is not a warning.
    """
    parts = split_action(action or "")
    if parts is None:
        raise HomeAssistantError("The receiver has no valid action")
    if not hass.services.has_service(*parts):
        raise HomeAssistantError(f"Action {action} is not available")
    variables = {
        "title": notification.get("title"),
        "message": notification.get("message"),
        "priority": notification.get("priority"),
        "image": notification.get("image"),
        "data": notification.get("data") or {},
    }
    try:
        payload = _render(hass, action_data, variables)
    except TemplateError as err:
        raise HomeAssistantError(f"Could not render the action data: {err}") from err
    await hass.services.async_call(*parts, payload, blocking=True)
    return []
