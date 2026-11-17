"""Tests for diagnostics."""

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.com_system.const import (
    CONF_ENTRY_TYPE,
    CONF_NAME,
    DOMAIN,
    ENTRY_TYPE_CUSTOM_RECEIVER,
    ENTRY_TYPE_HUB,
)
from custom_components.com_system.diagnostics import (
    async_get_config_entry_diagnostics,
)
from homeassistant.core import HomeAssistant


async def test_hub_diagnostics_redacts_and_lists_receivers(hass: HomeAssistant) -> None:
    hub = MockConfigEntry(domain=DOMAIN, data={CONF_ENTRY_TYPE: ENTRY_TYPE_HUB})
    hub.add_to_hass(hass)
    receiver = MockConfigEntry(
        domain=DOMAIN,
        title="Secret room",
        data={CONF_ENTRY_TYPE: ENTRY_TYPE_CUSTOM_RECEIVER, CONF_NAME: "Secret room"},
    )
    receiver.add_to_hass(hass)

    hub_diag = await async_get_config_entry_diagnostics(hass, hub)
    assert [r["entry_id"] for r in hub_diag["receivers"]] == [receiver.entry_id]

    diag = await async_get_config_entry_diagnostics(hass, receiver)
    assert diag["entry"]["data"][CONF_NAME] == "**REDACTED**"
    assert diag["entry"]["title"] == "**REDACTED**"
    assert "Secret room" not in str(diag)
