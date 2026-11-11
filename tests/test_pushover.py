"""Tests for the Pushover receiver type."""

from types import SimpleNamespace

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.com_system.const import (
    CONF_ENTRY_TYPE,
    CONF_NAME,
    CONF_PEOPLE,
    CONF_RECEIVER_TYPE,
    CONF_SOURCE_ID,
    DOMAIN,
    ENTRY_TYPE_RECEIVER,
    RECEIVER_TYPE_PUSHOVER,
)
from custom_components.com_system.receiver_type import get_receiver_type
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


async def _add(hass: HomeAssistant, people=()) -> MockConfigEntry:
    MockConfigEntry(
        domain="pushover",
        title="Phone",
        unique_id="user1",
        data={"name": "My Phone", "user_key": "key"},
    ).add_to_hass(hass)
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Phone",
        data={
            CONF_ENTRY_TYPE: ENTRY_TYPE_RECEIVER,
            CONF_RECEIVER_TYPE: RECEIVER_TYPE_PUSHOVER,
            CONF_NAME: "Phone",
            CONF_SOURCE_ID: "user1:pixel",
        },
        options={CONF_PEOPLE: list(people)},
    )
    entry.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()
    return entry


def _receiver(hass: HomeAssistant):
    registry = hass.data[DOMAIN]["registry"]
    [receiver] = registry.all()
    return registry, receiver


async def test_delivers_message_and_title(hass: HomeAssistant) -> None:
    """Message and title go to notify.<slugified entry name> for the device."""
    calls = []
    hass.services.async_register("notify", "my_phone", calls.append)
    await _add(hass)
    registry, receiver = _receiver(hass)

    warnings = await registry.type_of(receiver).async_deliver(
        hass, receiver, {"message": "Hi", "title": "T"}
    )

    assert warnings == []
    assert calls[0].data == {"message": "Hi", "title": "T", "target": ["pixel"]}


async def test_title_is_optional(hass: HomeAssistant) -> None:
    """Without a title none is sent."""
    calls = []
    hass.services.async_register("notify", "my_phone", calls.append)
    await _add(hass)
    registry, receiver = _receiver(hass)

    await registry.type_of(receiver).async_deliver(hass, receiver, {"message": "Hi"})

    assert calls[0].data == {"message": "Hi", "target": ["pixel"]}


async def test_missing_action_fails(hass: HomeAssistant) -> None:
    """A missing notify action raises so the dispatcher reports failed."""
    await _add(hass)
    registry, receiver = _receiver(hass)

    with pytest.raises(Exception, match=r"notify\.my_phone"):
        await registry.type_of(receiver).async_deliver(
            hass, receiver, {"message": "Hi"}
        )


async def test_person_is_manual(hass: HomeAssistant) -> None:
    """The person comes from the receiver's options."""
    await _add(hass, people=["person.alice"])
    registry, receiver = _receiver(hass)
    assert registry.people_of(receiver) == ("person.alice",)


async def test_detects_each_device(hass: HomeAssistant) -> None:
    """One candidate per device the account lists; none when not loaded."""
    entry = MockConfigEntry(
        domain="pushover",
        title="Phone",
        unique_id="user1",
        data={"name": "My Phone", "user_key": "key"},
    )
    entry.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, {})
    pushover_type = get_receiver_type(RECEIVER_TYPE_PUSHOVER)

    assert await pushover_type.async_detect(hass) == []

    api = SimpleNamespace(validate=lambda key: {"status": 1, "devices": ["a", "b"]})
    entry.runtime_data = SimpleNamespace(api=api)
    candidates = await pushover_type.async_detect(hass)
    assert [(c.source_id, c.name) for c in candidates] == [
        ("user1:a", "Phone a"),
        ("user1:b", "Phone b"),
    ]


async def test_detection_survives_api_failure(hass: HomeAssistant) -> None:
    """A failing API call offers nothing instead of raising."""

    def boom(key):
        raise OSError("offline")

    entry = MockConfigEntry(
        domain="pushover", title="Phone", unique_id="user1", data={"user_key": "key"}
    )
    entry.add_to_hass(hass)
    entry.runtime_data = SimpleNamespace(api=SimpleNamespace(validate=boom))
    assert await async_setup_component(hass, DOMAIN, {})

    assert await get_receiver_type(RECEIVER_TYPE_PUSHOVER).async_detect(hass) == []
