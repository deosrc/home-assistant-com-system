"""Tests for the notification channel store."""

import pytest
import voluptuous as vol
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.com_system.channels import (
    apply_defaults,
    async_create_channel,
    async_delete_channel,
)
from custom_components.com_system.const import (
    CONF_CHANNELS,
    CONF_ENTRY_TYPE,
    CONF_NAME,
    CONF_RECEIVER_TYPE,
    CONF_SOURCE_ID,
    DOMAIN,
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


async def _add_channel(hass: HomeAssistant, name: str, **defaults):
    """Create a channel; return its description."""
    return await async_create_channel(hass, name, defaults)


def _hub(hass: HomeAssistant):
    return next(
        e
        for e in hass.config_entries.async_entries(DOMAIN)
        if e.data.get(CONF_ENTRY_TYPE) == ENTRY_TYPE_HUB
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


async def test_channel_entity_is_on_the_hub(hass: HomeAssistant) -> None:
    """A channel is a notification_channel entity of the hub entry."""
    await _setup(hass)
    info = await _add_channel(hass, "Doors", priority="high")
    assert info["entity_id"].startswith("notification_channel.")
    state = hass.states.get(info["entity_id"])
    assert state.state == "Doors"
    assert state.attributes["priority"] == "high"
    registered = er.async_get(hass).async_get(info["entity_id"])
    assert registered.config_entry_id == _hub(hass).entry_id
    # No config entry is created for it: only the hub and the receiver exist.
    assert len(hass.config_entries.async_entries(DOMAIN)) == 2


async def test_send_applies_channel_defaults(hass: HomeAssistant) -> None:
    """The channel's defaults apply, the call wins, and the app gets the name."""
    receiver, calls = await _setup(hass)
    info = await _add_channel(
        hass,
        "Doors",
        title="Door",
        priority="high",
        data={"mobile_app": {"tag": "d"}},
    )
    response = await async_send_to(
        hass,
        receiver.entry_id,
        {"message": "Knock", "title": "Mine", "channel": info["entity_id"]},
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


async def test_delete_sends_remove_channel_to_android(hass: HomeAssistant) -> None:
    """Deleting a channel tells Android receivers to delete it."""
    _, calls = await _setup(hass)
    info = await _add_channel(hass, "Doors")
    await async_delete_channel(hass, info["channel_id"])
    assert calls[-1].data == {"message": "remove_channel", "data": {"channel": "Doors"}}
    assert hass.states.get(info["entity_id"]) is None
    assert er.async_get(hass).async_get(info["entity_id"]) is None


async def test_delete_skips_ios(hass: HomeAssistant) -> None:
    """iOS devices are not sent remove_channel."""
    _, calls = await _setup(hass, os_name="iOS")
    info = await _add_channel(hass, "Doors")
    await async_delete_channel(hass, info["channel_id"])
    assert not calls


async def test_editing_hub_data_syncs_entities(hass: HomeAssistant) -> None:
    """Changes made to the hub's data directly (not by the panel) still apply."""
    _, calls = await _setup(hass)
    hub = _hub(hass)
    hass.config_entries.async_update_entry(
        hub,
        data={
            **hub.data,
            CONF_CHANNELS: {"c1": {"name": "Doors", "defaults": {"priority": "low"}}},
        },
    )
    await hass.async_block_till_done()
    entity_id = er.async_get(hass).async_get_entity_id(
        "notification_channel", DOMAIN, f"{hub.entry_id}_c1"
    )
    assert hass.states.get(entity_id).state == "Doors"
    hass.config_entries.async_update_entry(
        hub, data={**hub.data, CONF_CHANNELS: {"c1": {"name": "Gates", "defaults": {}}}}
    )
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == "Gates"
    assert calls[-1].data["data"] == {"channel": "Doors"}
    hass.config_entries.async_update_entry(hub, data={**hub.data, CONF_CHANNELS: {}})
    await hass.async_block_till_done()
    assert hass.states.get(entity_id) is None
    assert calls[-1].data["data"] == {"channel": "Gates"}


async def test_options_flow_save_keeps_channels(hass: HomeAssistant) -> None:
    """The hub's options flow does not touch the stored channels."""
    await _setup(hass)
    info = await _add_channel(hass, "Doors", priority="high")
    hub = _hub(hass)
    result = await hass.config_entries.options.async_init(hub.entry_id)
    done = await hass.config_entries.options.async_configure(
        result["flow_id"], {"history_max_count": 10, "history_max_age_days": 5}
    )
    assert done["type"] == "create_entry"
    await hass.async_block_till_done()
    assert hass.states.get(info["entity_id"]).state == "Doors"
    assert info["channel_id"] in hub.data[CONF_CHANNELS]


async def _action(hass: HomeAssistant, service: str, data: dict, response=True):
    return await hass.services.async_call(
        DOMAIN, service, data, blocking=True, return_response=response
    )


async def test_actions_create_update_delete(hass: HomeAssistant) -> None:
    """The channel actions create, rename, replace the defaults and delete."""
    _, calls = await _setup(hass)
    info = await _action(
        hass, "create_channel", {"name": "Doors", "priority": "high", "title": "T"}
    )
    assert info["name"] == "Doors"
    assert info["defaults"] == {"priority": "high", "title": "T"}
    entity_id = info["entity_id"]
    assert hass.states.get(entity_id).state == "Doors"

    with pytest.raises(ServiceValidationError, match="already exists"):
        await _action(hass, "create_channel", {"name": "doors"})
    with pytest.raises(vol.Invalid):
        await _action(hass, "create_channel", {"name": "Bad", "image": "nope"})

    # Updating replaces the defaults (priority is cleared) and renames.
    updated = await _action(
        hass,
        "update_channel",
        {"channel": entity_id, "name": "Entrances", "title": "New"},
    )
    assert updated["name"] == "Entrances"
    assert updated["defaults"] == {"title": "New"}
    assert calls[-1].data == {"message": "remove_channel", "data": {"channel": "Doors"}}
    assert hass.states.get(entity_id).state == "Entrances"

    # Without a name the current one is kept.
    kept = await _action(hass, "update_channel", {"channel": entity_id})
    assert kept["name"] == "Entrances"
    assert kept["defaults"] == {}

    await _action(hass, "delete_channel", {"channel": entity_id}, response=False)
    assert calls[-1].data["data"] == {"channel": "Entrances"}
    assert hass.states.get(entity_id) is None


async def test_actions_reject_other_entities(hass: HomeAssistant) -> None:
    """Only this integration's channel entities can be updated or deleted."""
    await _setup(hass)
    hass.states.async_set("notification_channel.other", "x")
    with pytest.raises(ServiceValidationError, match="not a Com System channel"):
        await _action(
            hass, "delete_channel", {"channel": "notification_channel.other"}, False
        )


async def test_ws_lists_channels(hass: HomeAssistant, hass_ws_client) -> None:
    """The panel reads channels over websocket."""
    await _setup(hass)
    await _add_channel(hass, "Beta")
    await _add_channel(hass, "alpha", priority="low")
    client = await hass_ws_client(hass)
    await client.send_json({"id": 1, "type": "com_system/channels/list"})
    msg = await client.receive_json()
    channels = msg["result"]["channels"]
    assert [c["name"] for c in channels] == ["alpha", "Beta"]
    assert channels[0]["defaults"] == {"priority": "low"}


async def test_channel_defaults_include_mobile_app_fields(hass: HomeAssistant) -> None:
    """Click action, actions, tag and car UI are channel defaults."""
    receiver, calls = await _setup(hass)
    actions = [{"id": "OPEN", "label": "Open"}]
    channel = await _add_channel(
        hass,
        "Doors",
        click_action="/lovelace/cams",
        actions=actions,
        tag="door",
        car_ui=True,
    )
    await async_send_to(
        hass,
        receiver.entry_id,
        {"message": "Hi", "channel": channel["entity_id"], "tag": "mine"},
    )
    sent = calls[0].data["data"]
    assert sent["clickAction"] == "/lovelace/cams"
    assert sent["actions"] == [{"action": "OPEN", "title": "Open"}]
    assert sent["car_ui"] is True
    assert sent["tag"] == "mine"  # the call wins
    assert sent["channel"] == "Doors"


async def test_channel_actions_match_notify_content_fields(
    hass: HomeAssistant,
) -> None:
    """AGENTS.md: the channel actions' content fields mirror notify's."""
    from homeassistant.helpers.service import async_get_all_descriptions

    assert await async_setup_component(hass, DOMAIN, {})
    descriptions = await async_get_all_descriptions(hass)
    notify = descriptions["notify"]["com_system"]["fields"]
    for service in ("create_channel", "update_channel"):
        fields = descriptions[DOMAIN][service]["fields"]
        for key in (
            "title",
            "priority",
            "image",
            "click_action",
            "actions",
            "tag",
            "car_ui",
            "data",
        ):
            assert _covers(notify[key]["selector"], fields[key]["selector"]), (
                service,
                key,
            )
            assert fields[key].get("example") == notify[key].get("example")


def _covers(expected, actual) -> bool:
    """Whether ``actual`` has everything in ``expected`` (None is empty).

    Home Assistant fills in defaults when it reads a selector from YAML, so
    the two are compared on what the notify action declares.
    """
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(
            k in actual and _covers(v, actual[k]) for k, v in expected.items()
        )
    if isinstance(expected, list):
        return (
            isinstance(actual, list)
            and len(expected) == len(actual)
            and all(_covers(e, a) for e, a in zip(expected, actual, strict=True))
        )
    return expected is None or expected == actual
