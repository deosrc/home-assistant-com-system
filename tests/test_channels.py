"""Tests for the notification channel store."""

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.com_system.channels import apply_defaults
from custom_components.com_system.const import (
    CONF_ENTRY_TYPE,
    CONF_NAME,
    CONF_RECEIVER_TYPE,
    CONF_SOURCE_ID,
    DOMAIN,
    ENTRY_TYPE_CHANNEL,
    ENTRY_TYPE_HUB,
    ENTRY_TYPE_RECEIVER,
    RECEIVER_TYPE_MOBILE_APP,
)
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er
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


async def _add_channel(hass: HomeAssistant, name: str, **options):
    """Create a channel entry and return its entity id."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=name,
        data={CONF_ENTRY_TYPE: ENTRY_TYPE_CHANNEL},
        options=options,
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry, next(
        e.entity_id
        for e in er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
    )


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


async def test_channel_entity(hass: HomeAssistant) -> None:
    """A channel is a notification_channel entity with its defaults."""
    await _setup(hass)
    _, entity_id = await _add_channel(hass, "Doors", priority="high")
    assert entity_id.startswith("notification_channel.")
    state = hass.states.get(entity_id)
    assert state.state == "Doors"
    assert state.attributes["priority"] == "high"


async def test_send_applies_channel_defaults(hass: HomeAssistant) -> None:
    """The channel's defaults apply, the call wins, and the app gets the name."""
    receiver, calls = await _setup(hass)
    _, channel = await _add_channel(
        hass,
        "Doors",
        title="Door",
        priority="high",
        data={"mobile_app": {"tag": "d"}},
    )
    response = await async_send_to(
        hass,
        receiver.entry_id,
        {"message": "Knock", "title": "Mine", "channel": channel},
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


async def test_non_channel_entity_is_rejected(hass: HomeAssistant) -> None:
    """A channel entity that is not Com System's is rejected, sending nothing."""
    receiver, calls = await _setup(hass)
    hass.states.async_set("notification_channel.other", "x")
    with pytest.raises(ServiceValidationError, match="not a Com System channel"):
        await async_send_to(
            hass,
            receiver.entry_id,
            {"message": "x", "channel": "notification_channel.other"},
        )
    assert not calls


async def test_remove_sends_remove_channel_to_android(hass: HomeAssistant) -> None:
    """Removing a channel tells Android receivers to delete it."""
    _, calls = await _setup(hass)
    entry, _ = await _add_channel(hass, "Doors")
    await hass.config_entries.async_remove(entry.entry_id)
    assert len(calls) == 1
    assert calls[0].data == {"message": "remove_channel", "data": {"channel": "Doors"}}


async def test_remove_skips_ios(hass: HomeAssistant) -> None:
    """iOS devices are not sent remove_channel."""
    _, calls = await _setup(hass, os_name="iOS")
    entry, _ = await _add_channel(hass, "Doors")
    await hass.config_entries.async_remove(entry.entry_id)
    assert not calls


async def _call(client, msg: dict) -> dict:
    client.next_id = getattr(client, "next_id", 0) + 1
    await client.send_json({"id": client.next_id, **msg})
    return await client.receive_json()


async def test_ws_create_update_remove(hass: HomeAssistant, hass_ws_client) -> None:
    """The panel creates, renames, lists and deletes channels."""
    _, calls = await _setup(hass)
    client = await hass_ws_client(hass)
    created = await _call(
        client,
        {
            "type": "com_system/channels/set",
            "name": "Doors",
            "defaults": {"priority": "high"},
        },
    )
    assert created["success"]
    info = created["result"]
    assert info["name"] == "Doors"
    assert info["defaults"] == {"priority": "high"}
    assert hass.states.get(info["entity_id"]).state == "Doors"

    dupe = await _call(client, {"type": "com_system/channels/set", "name": "doors"})
    assert dupe["error"]["code"] == "channel_error"
    bad = await _call(
        client,
        {
            "type": "com_system/channels/set",
            "name": "Bad",
            "defaults": {"image": "nope"},
        },
    )
    assert bad["error"]["code"] == "channel_error"

    updated = await _call(
        client,
        {
            "type": "com_system/channels/set",
            "entry_id": info["entry_id"],
            "name": "Entrances",
            "defaults": {"priority": "low"},
        },
    )
    assert updated["result"]["name"] == "Entrances"
    # The old name is dropped from Android devices.
    assert calls[-1].data == {"message": "remove_channel", "data": {"channel": "Doors"}}
    await hass.async_block_till_done()
    assert hass.states.get(info["entity_id"]).attributes["priority"] == "low"

    listed = await _call(client, {"type": "com_system/channels/list"})
    assert [c["name"] for c in listed["result"]["channels"]] == ["Entrances"]

    removed = await _call(
        client, {"type": "com_system/channels/remove", "entry_id": info["entry_id"]}
    )
    assert removed["success"]
    assert calls[-1].data["data"] == {"channel": "Entrances"}
    missing = await _call(
        client, {"type": "com_system/channels/remove", "entry_id": info["entry_id"]}
    )
    assert missing["error"]["code"] == "not_found"


async def test_options_flow_points_to_the_panel(hass: HomeAssistant) -> None:
    """A channel is edited in the panel, not by the options flow."""
    await _setup(hass)
    entry, _ = await _add_channel(hass, "Doors", priority="high")
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == "abort"
    assert result["reason"] == "managed_in_panel"
    assert dict(entry.options) == {"priority": "high"}
