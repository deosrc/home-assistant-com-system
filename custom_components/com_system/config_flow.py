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
    CONF_DISCOVERY_TYPE,
    CONF_ENTRY_TYPE,
    CONF_HISTORY_MAX_AGE_DAYS,
    CONF_HISTORY_MAX_COUNT,
    CONF_NAME,
    CONF_PEOPLE,
    CONF_RECEIVER_TYPE,
    CONF_SOURCE_ID,
    DEFAULT_HISTORY_MAX_AGE_DAYS,
    DEFAULT_HISTORY_MAX_COUNT,
    DOMAIN,
    ENTRY_TYPE_HUB,
    ENTRY_TYPE_RECEIVER,
    RECEIVER_ENTRY_TYPES,
    RECEIVER_TYPE_CUSTOM,
)
from .detection import discovery_unique_id
from .receiver_type import get_receiver_type


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
        """Create the hub. Receivers are added from discoveries."""
        if self._hub_exists():
            return self.async_abort(reason="receivers_are_discovered")

        if user_input is not None:
            return self.async_create_entry(
                title="Com System",
                data={CONF_ENTRY_TYPE: ENTRY_TYPE_HUB},
            )
        return self.async_show_form(step_id="user")

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
        """Rename a receiver. The hub has nothing to reconfigure."""
        entry = self._get_reconfigure_entry()
        if entry.data.get(CONF_ENTRY_TYPE) not in RECEIVER_ENTRY_TYPES:
            return self.async_abort(reason="not_implemented")
        if user_input is not None:
            name = user_input[CONF_NAME].strip()
            return self.async_update_reload_and_abort(
                entry,
                title=name,
                data_updates={CONF_NAME: name},
                reason="reconfigure_successful",
            )
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema({vol.Required(CONF_NAME): str}), dict(entry.data)
            ),
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow."""
        return ComSystemOptionsFlow()


class ComSystemOptionsFlow(OptionsFlow):
    """Handle options: the hub's history limits and a receiver's people."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show the options form: the people for receivers."""
        if self.config_entry.data.get(CONF_ENTRY_TYPE) not in RECEIVER_ENTRY_TYPES:
            if user_input is not None:
                return self.async_create_entry(data=user_input)
            schema = vol.Schema(
                {
                    vol.Required(
                        CONF_HISTORY_MAX_COUNT, default=DEFAULT_HISTORY_MAX_COUNT
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=1,
                            max=10000,
                            step=1,
                            mode=selector.NumberSelectorMode.BOX,
                        )
                    ),
                    vol.Required(
                        CONF_HISTORY_MAX_AGE_DAYS, default=DEFAULT_HISTORY_MAX_AGE_DAYS
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=1,
                            max=3650,
                            step=1,
                            mode=selector.NumberSelectorMode.BOX,
                            unit_of_measurement="days",
                        )
                    ),
                }
            )
            return self.async_show_form(
                step_id="init",
                data_schema=self.add_suggested_values_to_schema(
                    schema, self.config_entry.options
                ),
            )

        receiver_type = get_receiver_type(
            self.config_entry.data.get(CONF_RECEIVER_TYPE, RECEIVER_TYPE_CUSTOM)
        )
        if receiver_type is not None and not receiver_type.supports_people:
            if user_input is not None:
                return self.async_create_entry(data=self.config_entry.options)
            return self.async_show_form(step_id="no_options")

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

    async def async_step_no_options(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Finish the form of a type with nothing to configure."""
        return await self.async_step_init(user_input)
