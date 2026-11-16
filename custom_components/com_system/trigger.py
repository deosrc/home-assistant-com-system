"""Automation triggers: a notification action was received."""

from __future__ import annotations

from typing import Any, override

import voluptuous as vol

from homeassistant.const import CONF_OPTIONS
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.trigger import (
    Trigger,
    TriggerActionRunner,
    TriggerConfig,
    TriggerNotTriggeredReporter,
)
from homeassistant.helpers.typing import ConfigType

from .const import EVENT_ACTION

CONF_ACTION = "action"
CONF_NOTIFICATION_ID = "notification_id"
CONF_TAG = "tag"


def _needs_notification_id_or_tag(options: dict[str, Any]) -> dict[str, Any]:
    """The action must be narrowed to a notification or a tag."""
    if not options.get(CONF_NOTIFICATION_ID) and not options.get(CONF_TAG):
        raise vol.Invalid("Give either a notification_id or a tag")
    return options


_OPTIONS_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Required(CONF_ACTION): vol.All(cv.string, vol.Length(min=1)),
            vol.Optional(CONF_NOTIFICATION_ID): cv.string,
            vol.Optional(CONF_TAG): cv.string,
        }
    ),
    _needs_notification_id_or_tag,
)

_TRIGGER_SCHEMA = vol.Schema({vol.Required(CONF_OPTIONS): _OPTIONS_SCHEMA})


class ActionReceivedTrigger(Trigger):
    """Fires when someone responds to a notification action.

    The action ID is required, together with the notification ID or the tag
    (or both, in which case both must match).
    """

    @override
    @classmethod
    async def async_validate_config(
        cls, hass: HomeAssistant, config: ConfigType
    ) -> ConfigType:
        """Validate the options."""
        return _TRIGGER_SCHEMA(config)

    def __init__(self, hass: HomeAssistant, config: TriggerConfig) -> None:
        """Initialize the trigger."""
        super().__init__(hass, config)
        self._options = config.options or {}

    @override
    async def async_attach_runner(
        self,
        run_action: TriggerActionRunner,
        did_not_trigger: TriggerNotTriggeredReporter | None = None,
    ) -> CALLBACK_TYPE:
        """Listen for ``com_system_action`` events."""
        options = self._options

        @callback
        def _handle(event: Event) -> None:
            data = event.data
            if data.get("action") != options[CONF_ACTION]:
                return
            for key in (CONF_NOTIFICATION_ID, CONF_TAG):
                if options.get(key) and data.get(key) != options[key]:
                    return
            run_action(
                dict(data),
                f"notification action {data['action']} received",
                event.context,
            )

        return self._hass.bus.async_listen(EVENT_ACTION, _handle)


TRIGGERS: dict[str, type[Trigger]] = {
    "action_received": ActionReceivedTrigger,
}


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return the triggers of Com System."""
    return TRIGGERS
