"""Tests for the notification channel store."""

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.com_system.channels import apply_defaults
from custom_components.com_system.const import (
    CONF_ENTRY_TYPE,
    CONF_NAME,
    CONF_RECEIVER_TYPE,
    CONF_SOURCE_ID,
    DATA_CHANNELS,
    DOMAIN,
    ENTRY_TYPE_HUB,
    ENTRY_TYPE_RECEIVER,
    RECEIVER_TYPE_MOBILE_APP,
)
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
from homeassistant.setup import async_setup_component


async def _setup(hass: HomeAssistant, os_name: str = "Android"):
    """A hub and one mobile app receiver; returns the notify calls."""
    MockConfigEntry(domain=DOMAIN, data={CONF_ENTRY_TYPE: ENTRY_TYPE_HUB}).add_to_hass(
        hass
    )
    MockConfigEntry(
        domain="mobile_app",
        title="Pixel",
        data={"device_id": "abc", "device_name": "Pixel", "os_name": os_name},
    ).add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, {})
    receiver = MockConfigEntry(
        domain=DOMAIN,
        title="Pixel",
        data={
            CONF_ENTRY_TYPE: ENTRY_TYPE_RECEIVER,
            CONF_RECEIVER_TYPE: RECEIVER_TYPE_MOBILE_APP,
            CONF_SOURCE_ID: "abc",
            CONF_NAME: "Pixel",
        },
    )
    receiver.add_to_hass(hass)
    await hass.config_entries.async_setup(receiver.entry_id)
    await hass.async_block_till_done()
    calls: list[ServiceCall] = []
    hass.services.async_register("notify", "mobile_app_pixel", calls.append)
    return receiver, calls


def _store(hass: HomeAssistant):
    return hass.data[DOMAIN][DATA_CHANNELS]


def test_apply_defaults_call_wins() -> None:
    """Call values beat defaults; data is deep-merged."""
    result = apply_defaults(
        {"message": "m", "priority": "low", "data": {"a": {"x": 1}}},
        {
            "priority": "high",
            "title": "T",
            "data": {"a": {"x": 0, "y": 2}, "b": {"z": 3}},
        },
    )
    assert result == {
        "message": "m",
        "priority": "low",
        "title": "T",
        "data": {"a": {"x": 1, "y": 2}, "b": {"z": 3}},
    }


async def test_store_crud(hass: HomeAssistant) -> None:
    """Channels can be created, listed, renamed and removed."""
    await _setup(hass)
    store = _store(hass)
    await store.async_set("Doors", {"priority": "high"})
    await store.async_set("Alerts", {})
    assert [c["name"] for c in await store.async_list()] == ["Alerts", "Doors"]
    await store.async_set("Entrances", {"priority": "high"}, previous_name="Doors")
    assert await store.async_get("Doors") is None
    assert await store.async_get("Entrances") == {"priority": "high"}
    with pytest.raises(ServiceValidationError):
        await store.async_set("Alerts", {}, previous_name="Entrances")
    with pytest.raises(ServiceValidationError):
        await store.async_set("New", {}, previous_name="Missing")
    await store.async_remove("Alerts")
    with pytest.raises(ServiceValidationError):
        await store.async_remove("Alerts")


async def test_send_applies_channel_defaults(hass: HomeAssistant) -> None:
    """The channel's defaults apply, the call wins, and the app gets the channel."""
    receiver, calls = await _setup(hass)
    await _store(hass).async_set(
        "Doors",
        {"title": "Door", "priority": "high", "data": {"mobile_app": {"tag": "d"}}},
    )
    entry_id = receiver.entry_id
    response = await async_send_to(
        hass, entry_id, {"message": "Knock", "title": "Mine", "channel": "Doors"}
    )
    assert response["counts"]["delivered"] == 1
    data = calls[0].data
    assert data["title"] == "Mine"
    assert data["data"]["channel"] == "Doors"
    assert data["data"]["importance"] == "high"
    assert data["data"]["tag"] == "d"


async def async_send_to(hass, entry_id, data):
    """Send through the action, targeting one receiver by entity id."""
    from homeassistant.helpers import entity_registry as er

    entity_id = next(
        e.entity_id
        for e in er.async_entries_for_config_entry(er.async_get(hass), entry_id)
        if e.domain == "notification_receiver"
    )
    return await hass.services.async_call(
        "notify",
        "com_system",
        {
            **data,
            "receivers": {
                "active_choice": "Select",
                "Select": {"entity_id": [entity_id]},
            },
        },
        blocking=True,
        return_response=True,
    )


async def test_unknown_channel_is_rejected(hass: HomeAssistant) -> None:
    """A call naming a missing channel fails and sends nothing."""
    receiver, calls = await _setup(hass)
    with pytest.raises(ServiceValidationError, match="does not exist"):
        await async_send_to(hass, receiver.entry_id, {"message": "x", "channel": "No"})
    assert not calls


async def test_remove_sends_remove_channel_to_android(hass: HomeAssistant) -> None:
    """Removing a channel tells Android receivers to delete it."""
    _, calls = await _setup(hass)
    await _store(hass).async_set("Doors", {})
    await _store(hass).async_remove("Doors")
    assert len(calls) == 1
    assert calls[0].data == {"message": "remove_channel", "data": {"channel": "Doors"}}


async def test_remove_skips_ios(hass: HomeAssistant) -> None:
    """iOS devices are not sent remove_channel."""
    _, calls = await _setup(hass, os_name="iOS")
    await _store(hass).async_set("Doors", {})
    await _store(hass).async_remove("Doors")
    assert not calls
