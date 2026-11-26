"""Commands: actions that control receivers instead of notifying them.

A command (for example ``clear_notification``) is a Com System action,
``com_system.<command id>``, that takes the same ``people`` and ``receivers``
targets as ``notify.com_system``. Each receiver type says which commands it
supports and how to run them (``ReceiverType.commands`` and
``async_command``); a receiver whose type does not support a command, for
example because the device runs another OS, is skipped with a reason.

To add a command, define a ``Command``, add it to ``COMMANDS`` and implement
it in the receiver types that support it. For the mobile app that is one
entry in ``MOBILE_APP_COMMANDS`` (``mobile_app.py``).
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

import voluptuous as vol

from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv

from .const import (
    DATA_REGISTRY,
    DOMAIN,
    RESULT_DELIVERED,
    RESULT_FAILED,
    RESULT_SKIPPED,
)
from .content import ATTR_TAG
from .dispatcher import (
    REASON_DISABLED,
    REASON_NOT_IMPLEMENTED,
    REASON_UNKNOWN_TYPE,
    ReceiverResult,
)
from .notify import (
    ATTR_PEOPLE,
    ATTR_RECEIVERS,
    resolve_call_targets,
    response_data,
    validate_people,
    validate_receivers,
)
from .receiver import Receiver

_LOGGER = logging.getLogger(__name__)

SERVICE_CLEAR_NOTIFICATION = "clear_notification"

REASON_NOT_SUPPORTED = "The receiver does not support this command"


@dataclass(frozen=True, slots=True)
class Command:
    """A command: its action name and its own parameters.

    ``schema`` holds the command's parameters (the targets are added to every
    command). The UI description (name, fields and selectors) is in
    ``services.yaml`` and ``strings.json``, as for the channel actions.
    """

    command_id: str
    schema: Mapping[Any, Any] = field(default_factory=dict)


COMMANDS: dict[str, Command] = {
    command.command_id: command
    for command in (
        Command(SERVICE_CLEAR_NOTIFICATION, {vol.Required(ATTR_TAG): cv.string}),
    )
}


def command_schema(command: Command) -> vol.Schema:
    """Return the action schema: the targets and the command's parameters."""
    return vol.Schema(
        {
            vol.Optional(ATTR_PEOPLE): validate_people,
            vol.Optional(ATTR_RECEIVERS): validate_receivers,
            **command.schema,
        }
    )


async def _run(
    hass: HomeAssistant,
    receiver: Receiver,
    command: Command,
    data: Mapping[str, Any],
) -> ReceiverResult:
    """Run the command on one receiver. Never raises."""
    receiver_type = hass.data[DOMAIN][DATA_REGISTRY].type_of(receiver)
    if receiver_type is None:
        return ReceiverResult(
            receiver, receiver.type_id, RESULT_FAILED, REASON_UNKNOWN_TYPE
        )
    if not receiver_type.supports_command(hass, receiver, command.command_id):
        return ReceiverResult(
            receiver, receiver_type.name, RESULT_SKIPPED, REASON_NOT_SUPPORTED
        )
    try:
        warnings = await receiver_type.async_command(
            hass, receiver, command.command_id, data
        )
    except NotImplementedError:
        return ReceiverResult(
            receiver, receiver_type.name, RESULT_FAILED, REASON_NOT_IMPLEMENTED
        )
    except Exception as err:
        _LOGGER.warning(
            "Command %s on %s failed: %s", command.command_id, receiver.name, err
        )
        return ReceiverResult(
            receiver, receiver_type.name, RESULT_FAILED, str(err) or type(err).__name__
        )
    return ReceiverResult(
        receiver, receiver_type.name, RESULT_DELIVERED, warnings=list(warnings or ())
    )


async def async_run_command(
    hass: HomeAssistant, command: Command, data: Mapping[str, Any]
) -> dict[str, Any]:
    """Run a command on the receivers the targets match; return the response.

    Raises ``ServiceValidationError`` only when no target is given. Targets
    that match no receiver, or only disabled ones, give no results or only
    skipped ones, as do other outcomes, including failures. Commands are
    not recorded in the notification history.
    """
    if ATTR_PEOPLE not in data and ATTR_RECEIVERS not in data:
        raise ServiceValidationError("No targets given: set people, receivers or both")
    resolved = resolve_call_targets(hass, dict(data))
    params = {k: v for k, v in data.items() if k not in (ATTR_PEOPLE, ATTR_RECEIVERS)}
    ran = await asyncio.gather(
        *(_run(hass, r, command, params) for r in resolved.receivers)
    )
    disabled = [
        ReceiverResult(
            r,
            (
                t.name
                if (t := hass.data[DOMAIN][DATA_REGISTRY].type_of(r))
                else r.type_id
            ),
            RESULT_SKIPPED,
            REASON_DISABLED,
        )
        for r in resolved.skipped
    ]
    results = sorted(
        [*ran, *disabled],
        key=lambda x: (x.receiver.name.casefold(), x.receiver.entry_id),
    )
    return response_data(results)


def async_register_command_actions(hass: HomeAssistant) -> None:
    """Register ``com_system.<command id>`` for every command."""
    for command in COMMANDS.values():

        async def _handle(
            call: ServiceCall, command: Command = command
        ) -> ServiceResponse:
            return await async_run_command(call.hass, command, dict(call.data))

        hass.services.async_register(
            DOMAIN,
            command.command_id,
            _handle,
            schema=command_schema(command),
            supports_response=SupportsResponse.OPTIONAL,
        )
