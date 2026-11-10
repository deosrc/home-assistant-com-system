"""Config flow for Com System: hub, custom receivers and stubs."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_ACTION,
    CONF_ACTION_DATA,
    CONF_DISCOVERY_TYPE,
    CONF_ENTRY_TYPE,
    CONF_NAME,
    CONF_PEOPLE,
    CONF_RECEIVER_TYPE,
    CONF_SOURCE_ID,
    DOMAIN,
    ENTRY_TYPE_CUSTOM_RECEIVER,
    ENTRY_TYPE_HUB,
    ENTRY_TYPE_RECEIVER,
    RECEIVER_ENTRY_TYPES,
    RECEIVER_TYPE_CUSTOM,
)
from .custom_receiver import (
    ERROR_NAME_REQUIRED,
    custom_receiver_data,
    validate_custom_receiver,
)
from .detection import discovery_unique_id
from .receiver_type import get_receiver_type


def _custom_schema() -> vol.Schema:
    """The fields of a custom receiver."""
    return vol.Schema(
        {
            vol.Required(CONF_NAME): str,
            vol.Required(CONF_ACTION): str,
            vol.Optional(CONF_ACTION_DATA): selector.ObjectSelector(),
        }
    )


class ComSystemConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the config flows."""

    VERSION = 1

    _discovered: dict[str, Any]

    def _hub_exists(self) -> bool:
        """Return True when the hub entry has been created."""
        return any(
            entry.data.get(CONF_ENTRY_TYPE) == ENTRY_TYPE_HUB
            for entry in self._async_current_entries(include_ignore=False)
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Create the hub, or add a custom receiver once the hub exists."""
        if self._hub_exists():
            return await self.async_step_custom_receiver()

        if user_input is not None:
            return self.async_create_entry(
                title="Com System",
                data={CONF_ENTRY_TYPE: ENTRY_TYPE_HUB},
            )
        return self.async_show_form(step_id="user")

    async def async_step_custom_receiver(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Add a custom receiver: a name and the action it calls."""
        errors: dict[str, str] = {}
        if user_input is not None:
            error = validate_custom_receiver(
                self.hass,
                name=user_input[CONF_NAME],
                action=user_input[CONF_ACTION],
                action_data=user_input.get(CONF_ACTION_DATA),
            )
            if error is None:
                data = custom_receiver_data(
                    user_input[CONF_NAME],
                    user_input[CONF_ACTION],
                    user_input.get(CONF_ACTION_DATA),
                )
                return self.async_create_entry(
                    title=data[CONF_NAME],
                    data={
                        CONF_ENTRY_TYPE: ENTRY_TYPE_CUSTOM_RECEIVER,
                        CONF_RECEIVER_TYPE: RECEIVER_TYPE_CUSTOM,
                        **data,
                    },
                )
            errors["base"] = error
        return self.async_show_form(
            step_id="custom_receiver",
            data_schema=self.add_suggested_values_to_schema(
                _custom_schema(), user_input
            ),
            errors=errors,
        )

    async def async_step_integration_discovery(
        self, discovery_info: dict[str, Any]
    ) -> ConfigFlowResult:
        """Handle a receiver discovery raised by the hub.

        The unique id is the source device, so a pending discovery is never
        duplicated and a receiver that exists, or was ignored, is not offered.
        """
        receiver_type = get_receiver_type(discovery_info[CONF_DISCOVERY_TYPE])
        if receiver_type is None or not self._hub_exists():
            return self.async_abort(reason="not_available")

        await self.async_set_unique_id(
            discovery_unique_id(receiver_type.type_id, discovery_info[CONF_SOURCE_ID])
        )
        self._abort_if_unique_id_configured()

        self._discovered = {
            CONF_ENTRY_TYPE: ENTRY_TYPE_RECEIVER,
            CONF_RECEIVER_TYPE: receiver_type.type_id,
            CONF_SOURCE_ID: discovery_info[CONF_SOURCE_ID],
            CONF_NAME: discovery_info[CONF_NAME],
        }
        self.context["title_placeholders"] = {
            "name": discovery_info[CONF_NAME],
            "type": receiver_type.name,
        }
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm adding the discovered receiver (new receivers are enabled)."""
        if user_input is not None:
            return self.async_create_entry(
                title=self._discovered[CONF_NAME], data=self._discovered
            )
        self._set_confirm_only()
        return self.async_show_form(
            step_id="confirm",
            description_placeholders=self.context["title_placeholders"],
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edit a receiver: a custom receiver's name, action and data, or the
        name of a receiver created from a discovery. The hub has nothing to
        reconfigure.
        """
        entry = self._get_reconfigure_entry()
        entry_type = entry.data.get(CONF_ENTRY_TYPE)
        if entry_type not in RECEIVER_ENTRY_TYPES:
            return self.async_abort(reason="not_implemented")

        custom = entry_type == ENTRY_TYPE_CUSTOM_RECEIVER
        errors: dict[str, str] = {}
        if user_input is not None:
            if custom:
                error = validate_custom_receiver(
                    self.hass,
                    name=user_input[CONF_NAME],
                    action=user_input[CONF_ACTION],
                    action_data=user_input.get(CONF_ACTION_DATA),
                    exclude_entry_id=entry.entry_id,
                )
                updates = custom_receiver_data(
                    user_input[CONF_NAME],
                    user_input[CONF_ACTION],
                    user_input.get(CONF_ACTION_DATA),
                )
            else:
                name = user_input[CONF_NAME].strip()
                error = ERROR_NAME_REQUIRED if not name else None
                updates = {CONF_NAME: name}
            if error is None:
                return self.async_update_reload_and_abort(
                    entry,
                    title=updates[CONF_NAME],
                    data_updates=updates,
                    reason="reconfigure_successful",
                )
            errors["base"] = error

        schema = (
            _custom_schema() if custom else vol.Schema({vol.Required(CONF_NAME): str})
        )
        suggested = user_input or dict(entry.data)
        return self.async_show_form(
            step_id="reconfigure_custom" if custom else "reconfigure",
            data_schema=self.add_suggested_values_to_schema(schema, suggested),
            errors=errors,
        )

    async def async_step_reconfigure_custom(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Submit of the custom receiver's reconfigure form."""
        return await self.async_step_reconfigure(user_input)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow."""
        return ComSystemOptionsFlow()


class ComSystemOptionsFlow(OptionsFlow):
    """Handle options (stub; hub history limits arrive later)."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show the options form: the people for receivers."""
        if self.config_entry.data.get(CONF_ENTRY_TYPE) not in RECEIVER_ENTRY_TYPES:
            if user_input is not None:
                return self.async_create_entry(data=self.config_entry.options)
            return self.async_show_form(step_id="init")

        if user_input is not None:
            return self.async_create_entry(data=user_input)

        options = self.config_entry.options
        schema = vol.Schema(
            {
                vol.Optional(CONF_PEOPLE): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="person", multiple=True)
                ),
            }
        )
        return self.async_show_form(
            step_id="receiver",
            data_schema=self.add_suggested_values_to_schema(schema, options),
        )

    async def async_step_receiver(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Save the receiver's people."""
        return await self.async_step_init(user_input)
