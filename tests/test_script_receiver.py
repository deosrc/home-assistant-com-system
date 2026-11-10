"""Tests for script receivers: detection and delivery."""

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.com_system.const import (
    CONF_ENTRY_TYPE,
    CONF_NAME,
    CONF_RECEIVER_TYPE,
    CONF_SOURCE_ID,
    DATA_REGISTRY,
    DOMAIN,
    ENTRY_TYPE_HUB,
    ENTRY_TYPE_RECEIVER,
    RECEIVER_TYPE_CUSTOM,
)
from custom_components.com_system.dispatcher import async_dispatch
from custom_components.com_system.receiver_type import (
    get_receiver_type,
    is_notification_script,
)
from custom_components.com_system.targets import ResolvedTargets
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

OBJECT_FIELD = {"notification": {"selector": {"object": {}}}}


def test_is_notification_script() -> None:
    assert is_notification_script({"fields": OBJECT_FIELD})
    assert not is_notification_script({"fields": {}})
    assert not is_notification_script({})
    assert not is_notification_script(
        {"fields": {"notification": {"selector": {"text": {}}}}}
    )
    assert not is_notification_script(
        {"fields": {**OBJECT_FIELD, "other": {"selector": {"text": {}}}}}
    )
    assert not is_notification_script(
        {"fields": {"message": {"selector": {"object": {}}}}}
    )


async def _scripts(hass: HomeAssistant) -> None:
    assert await async_setup_component(
        hass,
        "script",
        {
            "script": {
                "speaker": {
                    "alias": "Speaker",
                    "fields": {
                        "notification": {"selector": {"object": {}}},
                    },
                    "sequence": [],
                },
                "plain": {"sequence": []},
                "two_fields": {
                    "fields": {
                        "notification": {"selector": {"object": {}}},
                        "x": {"selector": {"text": {}}},
                    },
                    "sequence": [],
                },
            }
        },
    )


async def test_detects_only_notification_scripts(hass: HomeAssistant) -> None:
    await _scripts(hass)
    candidates = await get_receiver_type(RECEIVER_TYPE_CUSTOM).async_detect(hass)
    assert [(c.source_id, c.name) for c in candidates] == [("speaker", "Speaker")]


async def test_delivery_passes_notification_to_script(hass: HomeAssistant) -> None:
    await _scripts(hass)
    MockConfigEntry(domain=DOMAIN, data={CONF_ENTRY_TYPE: ENTRY_TYPE_HUB}).add_to_hass(
        hass
    )
    assert await async_setup_component(hass, DOMAIN, {})
    calls = []
    hass.services.async_register("script", "speaker", lambda call: calls.append(call))
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Speaker",
        data={
            CONF_ENTRY_TYPE: ENTRY_TYPE_RECEIVER,
            CONF_RECEIVER_TYPE: RECEIVER_TYPE_CUSTOM,
            CONF_NAME: "Speaker",
            CONF_SOURCE_ID: "speaker",
        },
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    receiver = hass.data[DOMAIN][DATA_REGISTRY].get(entry.entry_id)
    results = await async_dispatch(
        hass,
        ResolvedTargets(receivers=[receiver], skipped=[]),
        {"title": "Hi", "message": "there"},
    )
    assert results[0].result == "delivered"
    assert calls[0].data == {"notification": {"title": "Hi", "message": "there"}}


async def test_delivery_fails_when_script_missing(hass: HomeAssistant) -> None:
    assert await async_setup_component(hass, DOMAIN, {})
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Gone",
        data={
            CONF_ENTRY_TYPE: ENTRY_TYPE_RECEIVER,
            CONF_RECEIVER_TYPE: RECEIVER_TYPE_CUSTOM,
            CONF_NAME: "Gone",
            CONF_SOURCE_ID: "gone",
        },
    )
    entry.add_to_hass(hass)
    receiver = hass.data[DOMAIN][DATA_REGISTRY].get(entry.entry_id)
    results = await async_dispatch(
        hass, ResolvedTargets(receivers=[receiver], skipped=[]), {"message": "x"}
    )
    assert results[0].result == "failed"
    assert "script gone" in results[0].reason.lower()
