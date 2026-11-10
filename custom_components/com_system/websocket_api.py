"""Websocket commands backing the panel.

Every command requires an admin user: the panel exposes receivers and, later,
notification contents. Commands only read the registry and the config
entries; the enabled state is owned by each receiver's switch entity.
"""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.config_entries import SOURCE_INTEGRATION_DISCOVERY, ConfigEntryState
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.service import async_get_all_descriptions

from .const import (
    CONF_ENTRY_TYPE,
    CONF_NAME,
    CONF_PEOPLE,
    CONF_RECEIVER_TYPE,
    CONF_SOURCE_ID,
    DATA_REGISTRY,
    DOMAIN,
    ENTRY_TYPE_HUB,
    NOTIFICATION_RECEIVER_DOMAIN,
    RECEIVER_ENTRY_TYPES,
    RECEIVER_TYPE_CUSTOM,
)
from .detection import discovery_unique_id
from .dispatcher import REASON_DISABLED
from .notify import (
    ATTR_MESSAGE,
    ATTR_PERSON,
    ATTR_RECEIVERS,
    ATTR_TITLE,
    NOTIFY_DOMAIN,
    SERVICE_NAME,
    resolve_call_targets,
    validate_person,
    validate_receivers,
)
from .receiver import Receiver
from .receiver_type import notification_script_problems

SWITCH_DOMAIN = "switch"
ENABLED_KEY = "enabled"


@callback
def async_register_commands(hass: HomeAssistant) -> None:
    """Register the websocket commands."""
    websocket_api.async_register_command(hass, ws_ping)
    websocket_api.async_register_command(hass, ws_dashboard)
    websocket_api.async_register_command(hass, ws_receivers_list)
    websocket_api.async_register_command(hass, ws_receivers_set_enabled)
    websocket_api.async_register_command(hass, ws_discoveries_list)
    websocket_api.async_register_command(hass, ws_receivers_update)
    websocket_api.async_register_command(hass, ws_receivers_remove)
    websocket_api.async_register_command(hass, ws_scripts_check)
    websocket_api.async_register_command(hass, ws_scripts_rescan)
    websocket_api.async_register_command(hass, ws_notify_preview)
    websocket_api.async_register_command(hass, ws_notify_test)


def _switch_entity_id(hass: HomeAssistant, entry_id: str) -> str | None:
    """Return the entity id of a receiver's enabled switch."""
    return er.async_get(hass).async_get_entity_id(
        SWITCH_DOMAIN, DOMAIN, f"{entry_id}_{ENABLED_KEY}"
    )


def _receiver_info(hass: HomeAssistant, receiver: Receiver) -> dict[str, Any]:
    """Describe a receiver for the panel.

    ``enabled`` is the state of the enabled switch (null when it cannot be
    read, for example while the receiver is not loaded). ``available`` is
    false when the receiver is not loaded or its source is gone.
    """
    registry = hass.data[DOMAIN][DATA_REGISTRY]
    receiver_type = registry.type_of(receiver)
    entry = hass.config_entries.async_get_entry(receiver.entry_id)
    entity_id = _switch_entity_id(hass, receiver.entry_id)
    state = hass.states.get(entity_id) if entity_id else None
    enabled: bool | None = None
    if state is not None and state.state in (STATE_ON, STATE_OFF):
        enabled = state.state == STATE_ON
    available = (
        entry is not None
        and entry.state is ConfigEntryState.LOADED
        and (receiver_type is None or receiver_type.is_source_available(hass, receiver))
        and (state is None or state.state != STATE_UNAVAILABLE)
    )
    return {
        "entry_id": receiver.entry_id,
        "name": receiver.name,
        "type_id": receiver.type_id,
        # An unknown type stays listed, with its id as the name.
        "type": receiver_type.name if receiver_type else receiver.type_id,
        "type_known": receiver_type is not None,
        "enabled": enabled,
        "available": available,
        "entity_id": entity_id,
        "receiver_entity_id": er.async_get(hass).async_get_entity_id(
            NOTIFICATION_RECEIVER_DOMAIN, DOMAIN, f"{receiver.entry_id}_receiver"
        ),
        "people": list(registry.people_of(receiver)),
        "areas": list(registry.areas_of(receiver)),
    }


def _pending_discoveries(hass: HomeAssistant) -> list[dict[str, Any]]:
    """Return the discovery flows waiting for the user to add or ignore."""
    return [
        {
            "flow_id": flow["flow_id"],
            "name": flow["context"].get("title_placeholders", {}).get("name", ""),
            "type": flow["context"].get("title_placeholders", {}).get("type", ""),
        }
        for flow in hass.config_entries.flow.async_progress_by_handler(
            DOMAIN, match_context={"source": SOURCE_INTEGRATION_DISCOVERY}
        )
    ]


@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required("type"): "com_system/ping"})
@callback
def ws_ping(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Return a pong; admin only."""
    connection.send_result(msg["id"], {"pong": True})


@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required("type"): "com_system/receivers/list"})
@callback
def ws_receivers_list(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """List every receiver with its type, enabled state and availability."""
    receivers = hass.data[DOMAIN][DATA_REGISTRY].all()
    connection.send_result(
        msg["id"], {"receivers": [_receiver_info(hass, r) for r in receivers]}
    )


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "com_system/receivers/set_enabled",
        vol.Required("entry_id"): str,
        vol.Required("enabled"): bool,
    }
)
@websocket_api.async_response
async def ws_receivers_set_enabled(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Enable or disable a receiver through its enabled switch."""
    entity_id = _switch_entity_id(hass, msg["entry_id"])
    if hass.data[DOMAIN][DATA_REGISTRY].get(msg["entry_id"]) is None or not entity_id:
        connection.send_error(msg["id"], "not_found", "Receiver not found")
        return
    await hass.services.async_call(
        SWITCH_DOMAIN,
        "turn_on" if msg["enabled"] else "turn_off",
        {"entity_id": entity_id},
        blocking=True,
        context=connection.context(msg),
    )
    connection.send_result(msg["id"])


@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required("type"): "com_system/discoveries/list"})
@callback
def ws_discoveries_list(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """List the pending discoveries."""
    connection.send_result(msg["id"], {"discoveries": _pending_discoveries(hass)})


@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required("type"): "com_system/dashboard"})
@callback
def ws_dashboard(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Return receiver counts and the number of pending discoveries.

    ``enabled`` and ``disabled`` count by the enabled switch; a receiver
    whose state cannot be read is in neither. ``unavailable`` counts
    receivers that are not loaded or whose source is gone, and overlaps the
    other two. ``by_type`` counts receivers per type name.
    """
    receivers = [
        _receiver_info(hass, r) for r in hass.data[DOMAIN][DATA_REGISTRY].all()
    ]
    by_type: dict[str, int] = {}
    for receiver in receivers:
        by_type[receiver["type"]] = by_type.get(receiver["type"], 0) + 1
    connection.send_result(
        msg["id"],
        {
            "total": len(receivers),
            "enabled": sum(r["enabled"] is True for r in receivers),
            "disabled": sum(r["enabled"] is False for r in receivers),
            "unavailable": sum(not r["available"] for r in receivers),
            "pending_discoveries": len(_pending_discoveries(hass)),
            "by_type": by_type,
        },
    )


_TARGET_FIELDS = {
    vol.Optional(ATTR_PERSON): validate_person,
    vol.Optional(ATTR_RECEIVERS): validate_receivers,
}


@websocket_api.require_admin
@websocket_api.websocket_command(
    {vol.Required("type"): "com_system/notify/preview", **_TARGET_FIELDS}
)
@callback
def ws_notify_preview(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Show which receivers a notification with these targets would reach.

    Takes the same target fields as the action and sends nothing. Each entry
    is ``reached`` (enabled) or ``skipped`` (disabled, with the reason).
    """
    registry = hass.data[DOMAIN][DATA_REGISTRY]
    resolved = resolve_call_targets(hass, msg)

    def describe(receiver: Receiver, outcome: str, reason: str | None) -> dict:
        receiver_type = registry.type_of(receiver)
        return {
            "entry_id": receiver.entry_id,
            "name": receiver.name,
            "type": receiver_type.name if receiver_type else receiver.type_id,
            "outcome": outcome,
            "reason": reason,
        }

    entries = [describe(r, "reached", None) for r in resolved.receivers] + [
        describe(r, "skipped", REASON_DISABLED) for r in resolved.skipped
    ]
    entries.sort(key=lambda e: (e["name"].casefold(), e["entry_id"]))
    connection.send_result(msg["id"], {"receivers": entries})


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "com_system/notify/test",
        vol.Required(ATTR_MESSAGE): str,
        vol.Optional(ATTR_TITLE): str,
        **_TARGET_FIELDS,
    }
)
@websocket_api.async_response
async def ws_notify_test(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Send a test notification by calling the ``notify.com_system`` action.

    It goes through the action itself, so it behaves exactly as an
    automation's call does and returns the same response data.
    """
    data = {k: v for k, v in msg.items() if k not in ("id", "type")}
    try:
        response = await hass.services.async_call(
            NOTIFY_DOMAIN,
            SERVICE_NAME,
            data,
            blocking=True,
            return_response=True,
            context=connection.context(msg),
        )
    except (HomeAssistantError, vol.Invalid) as err:
        connection.send_error(msg["id"], "send_failed", str(err))
        return
    connection.send_result(msg["id"], response)


_PEOPLE = vol.All(cv.ensure_list, [cv.entity_id], [cv.entity_domain("person")])


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "com_system/receivers/update",
        vol.Required("entry_id"): str,
        vol.Optional(CONF_NAME): str,
        vol.Optional(CONF_PEOPLE): _PEOPLE,
    }
)
@callback
def ws_receivers_update(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Rename a receiver or set its people; only the given fields change.

    The receiver reloads (the update listener).
    """
    entry = hass.config_entries.async_get_entry(msg["entry_id"])
    if hass.data[DOMAIN][DATA_REGISTRY].get(msg["entry_id"]) is None or entry is None:
        connection.send_error(msg["id"], "not_found", "Receiver not found")
        return
    name = msg.get(CONF_NAME, entry.data[CONF_NAME]).strip()
    if not name:
        connection.send_error(msg["id"], "name_required", "Enter a name")
        return
    options = dict(entry.options)
    if CONF_PEOPLE in msg:
        options[CONF_PEOPLE] = msg[CONF_PEOPLE]
    hass.config_entries.async_update_entry(
        entry, title=name, data={**entry.data, CONF_NAME: name}, options=options
    )
    receiver = hass.data[DOMAIN][DATA_REGISTRY].get(entry.entry_id)
    connection.send_result(msg["id"], _receiver_info(hass, receiver))


@websocket_api.require_admin
@websocket_api.websocket_command(
    {vol.Required("type"): "com_system/receivers/remove", vol.Required("entry_id"): str}
)
@websocket_api.async_response
async def ws_receivers_remove(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Remove a receiver (its config entry, entities and device)."""
    if hass.data[DOMAIN][DATA_REGISTRY].get(msg["entry_id"]) is None:
        connection.send_error(msg["id"], "not_found", "Receiver not found")
        return
    await hass.config_entries.async_remove(msg["entry_id"])
    connection.send_result(msg["id"])


def _check(check_id: str, ok: bool, message: str) -> dict[str, Any]:
    return {"id": check_id, "ok": ok, "message": message}


async def _script_checks(hass: HomeAssistant, entity_id: str) -> dict[str, Any]:
    """Explain whether a script is, or would be, a custom receiver.

    ``can_rescan`` is true when the script would be offered by a rescan: it
    is a notification script and is neither a receiver, ignored nor already
    waiting as a discovery.
    """
    object_id = entity_id.removeprefix("script.")
    checks: list[dict[str, Any]] = []
    description = (
        (await async_get_all_descriptions(hass)).get("script", {}).get(object_id)
    )
    exists = description is not None and hass.services.has_service("script", object_id)
    checks.append(
        _check(
            "exists",
            exists,
            "The script exists." if exists else "The script was not found.",
        )
    )
    structural_ok = False
    if exists:
        problems = notification_script_problems(description)
        structural_ok = not problems
        if structural_ok:
            checks.append(
                _check("fields", True, "It has one object field named notification.")
            )
        else:
            checks.extend(_check("fields", False, p) for p in problems)

    registered = ignored = pending = False
    if structural_ok:
        unique_id = discovery_unique_id(RECEIVER_TYPE_CUSTOM, object_id)
        for entry in hass.config_entries.async_entries(DOMAIN):
            if entry.unique_id == unique_id and entry.source == "ignore":
                ignored = True
            elif (
                entry.data.get(CONF_ENTRY_TYPE) in RECEIVER_ENTRY_TYPES
                and entry.data.get(CONF_RECEIVER_TYPE, RECEIVER_TYPE_CUSTOM)
                == RECEIVER_TYPE_CUSTOM
                and entry.data.get(CONF_SOURCE_ID) == object_id
            ):
                registered = True
        pending = any(
            flow["context"].get("unique_id") == unique_id
            for flow in hass.config_entries.flow.async_progress_by_handler(
                DOMAIN, match_context={"source": SOURCE_INTEGRATION_DISCOVERY}
            )
        )
        if registered:
            message = "It is already a receiver."
        elif ignored:
            message = (
                "It was ignored. Delete the ignored entry in Devices & "
                "services to offer it again."
            )
        elif pending:
            message = "It is waiting to be added in Devices & services."
        else:
            message = "It is not a receiver yet."
        checks.append(_check("registered", not (registered or ignored), message))
    can_rescan = structural_ok and not (registered or ignored or pending)
    return {"entity_id": entity_id, "checks": checks, "can_rescan": can_rescan}


@websocket_api.require_admin
@websocket_api.websocket_command(
    {vol.Required("type"): "com_system/scripts/check", vol.Required("entity_id"): str}
)
@websocket_api.async_response
async def ws_scripts_check(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Check why a script is, or is not, detected as a custom receiver."""
    if not msg["entity_id"].startswith("script."):
        connection.send_error(msg["id"], "invalid_entity", "Choose a script")
        return
    connection.send_result(msg["id"], await _script_checks(hass, msg["entity_id"]))


@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required("type"): "com_system/scripts/rescan"})
@websocket_api.async_response
async def ws_scripts_rescan(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Run detection now, so a new script is offered without waiting."""
    hub = next(
        (
            entry
            for entry in hass.config_entries.async_entries(DOMAIN)
            if entry.data.get(CONF_ENTRY_TYPE) == ENTRY_TYPE_HUB
            and entry.state is ConfigEntryState.LOADED
        ),
        None,
    )
    if hub is None:
        connection.send_error(msg["id"], "no_hub", "The Com System hub is not loaded")
        return
    await hub.runtime_data.async_detect()
    connection.send_result(msg["id"])
