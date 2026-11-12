"""Tests for the webOS TV receiver type."""

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.com_system.const import (
    CONF_ENTRY_TYPE,
    CONF_NAME,
    CONF_RECEIVER_TYPE,
    CONF_SOURCE_ID,
    DOMAIN,
    ENTRY_TYPE_HUB,
    ENTRY_TYPE_RECEIVER,
    RECEIVER_TYPE_WEBOSTV,
)
from custom_components.com_system.webostv import async_deliver_webostv
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component


async def _setup_tv(hass: HomeAssistant, area: str | None = None):
    """A webostv entry with its device, and a Com System receiver for it."""
    MockConfigEntry(domain=DOMAIN, data={CONF_ENTRY_TYPE: ENTRY_TYPE_HUB}).add_to_hass(
        hass
    )
    assert await async_setup_component(hass, DOMAIN, {})
    source = MockConfigEntry(domain="webostv", title="Living Room TV", unique_id="tv1")
    source.add_to_hass(hass)
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=source.entry_id,
        identifiers={("webostv", "tv1")},
        name="Living Room TV",
    )
    if area:
        area_entry = ar.async_get(hass).async_create(area)
        dr.async_get(hass).async_update_device(device.id, area_id=area_entry.id)
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Living Room TV",
        data={
            CONF_ENTRY_TYPE: ENTRY_TYPE_RECEIVER,
            CONF_RECEIVER_TYPE: RECEIVER_TYPE_WEBOSTV,
            CONF_SOURCE_ID: "tv1",
            CONF_NAME: "Living Room TV",
        },
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry, device


def _calls(hass: HomeAssistant) -> list[ServiceCall]:
    calls: list[ServiceCall] = []

    async def handler(call: ServiceCall) -> None:
        calls.append(call)

    hass.services.async_register("notify", "living_room_tv", handler)
    return calls


async def test_discovered(hass: HomeAssistant) -> None:
    """A TV is offered as a receiver (the type is discoverable)."""
    await _setup_tv(hass)
    from custom_components.com_system.receiver_type import get_receiver_type

    assert get_receiver_type(RECEIVER_TYPE_WEBOSTV).discoverable


async def test_area_and_no_person_from_tv_device(hass: HomeAssistant) -> None:
    """The receiver is on the TV's device, so its area is the TV's."""
    entry, device = await _setup_tv(hass, area="Lounge")
    registry = hass.data[DOMAIN]["registry"]
    receiver = registry.get(entry.entry_id)
    assert registry.areas_of(receiver) == (
        ar.async_get(hass).async_get_area_by_name("Lounge").id,
    )
    assert registry.people_of(receiver) == ()
    entities = er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
    assert {e.device_id for e in entities} == {device.id}


async def test_delivers_message(hass: HomeAssistant) -> None:
    """The message goes to notify.<slugified entry title>."""
    entry, _ = await _setup_tv(hass)
    calls = _calls(hass)
    response = await hass.services.async_call(
        "notify",
        "com_system",
        {
            "message": "Dinner",
            "receivers": {
                "active_choice": "Select",
                "Select": {
                    "entity_id": [
                        e.entity_id
                        for e in er.async_entries_for_config_entry(
                            er.async_get(hass), entry.entry_id
                        )
                        if e.domain == "notification_receiver"
                    ]
                },
            },
        },
        blocking=True,
        return_response=True,
    )
    assert response["results"][0]["result"] == "delivered"
    assert [c.data for c in calls] == [{"message": "Dinner"}]


async def test_icon_passed_in_data(hass: HomeAssistant) -> None:
    """The icon goes in data; other keys are not read."""
    entry, _ = await _setup_tv(hass)
    calls = _calls(hass)
    receiver = hass.data[DOMAIN]["registry"].get(entry.entry_id)
    warnings = await async_deliver_webostv(
        hass,
        receiver,
        {"message": "Hi", "data": {"icon": "/a.png", "other": 1}},
    )
    assert warnings == []
    assert calls[0].data == {"message": "Hi", "data": {"icon": "/a.png"}}


async def test_missing_action_fails(hass: HomeAssistant) -> None:
    """With no notify action the delivery raises."""
    entry, _ = await _setup_tv(hass)
    receiver = hass.data[DOMAIN]["registry"].get(entry.entry_id)
    with pytest.raises(Exception, match=r"notify\.living_room_tv"):
        await async_deliver_webostv(hass, receiver, {"message": "Hi"})


async def test_removed_tv_fails(hass: HomeAssistant) -> None:
    """A TV whose config entry is gone raises."""
    entry, _ = await _setup_tv(hass)
    receiver = hass.data[DOMAIN]["registry"].get(entry.entry_id)
    for source in hass.config_entries.async_entries("webostv"):
        hass.config_entries.async_update_entry(source, unique_id="other")
    with pytest.raises(Exception, match="no longer configured"):
        await async_deliver_webostv(hass, receiver, {"message": "Hi"})
