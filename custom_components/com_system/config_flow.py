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

from .const import (
    CONF_ENTRY_TYPE,
    CONF_NAME,
    DOMAIN,
    ENTRY_TYPE_CUSTOM_RECEIVER,
    ENTRY_TYPE_HUB,
)


class ComSystemConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the config flows."""

    VERSION = 1

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
        """Add a custom receiver (stub: name only)."""
        if user_input is not None:
            return self.async_create_entry(
                title=user_input[CONF_NAME],
                data={
                    CONF_ENTRY_TYPE: ENTRY_TYPE_CUSTOM_RECEIVER,
                    CONF_NAME: user_input[CONF_NAME],
                },
            )
        return self.async_show_form(
            step_id="custom_receiver",
            data_schema=vol.Schema({vol.Required(CONF_NAME): str}),
        )

    async def async_step_integration_discovery(
        self, discovery_info: dict[str, Any]
    ) -> ConfigFlowResult:
        """Handle a receiver discovery raised by the hub (stub)."""
        return self.async_abort(reason="not_implemented")

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Reconfigure a hub or receiver entry (stub)."""
        return self.async_abort(reason="not_implemented")

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
        """Show the options form."""
        if user_input is not None:
            return self.async_create_entry(data=self.config_entry.options)
        return self.async_show_form(step_id="init")
