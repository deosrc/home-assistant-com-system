"""Tests for the persistent notification receiver type."""

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.com_system.const import (
    CONF_ENTRY_TYPE,
    CONF_NAME,
    CONF_PEOPLE,
    CONF_RECEIVER_TYPE,
    DOMAIN,
    ENTRY_TYPE_RECEIVER,
    RECEIVER_TYPE_PERSISTENT_NOTIFICATION,
)
from homeassistant.components import persistent_notification as pn
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import ServiceValidationError
from homeassistant.setup import async_setup_component


async def _add(hass: HomeAssistant, people=()) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Persistent notification",
        data={
            CONF_ENTRY_TYPE: ENTRY_TYPE_RECEIVER,
            CONF_RECEIVER_TYPE: RECEIVER_TYPE_PERSISTENT_NOTIFICATION,
            CONF_NAME: "Persistent notification",
        },
        options={CONF_PEOPLE: list(people)},
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def _stored(hass: HomeAssistant) -> dict:
    return pn._async_get_or_create_notifications(hass)


async def _send(hass: HomeAssistant, entry: MockConfigEntry, **data):
    return await hass.services.async_call(
        "notify",
        "com_system",
        {
            "receivers": {
                "active_choice": "Select",
                "Select": {"entity_id": [_receiver_entity(hass, entry)]},
            },
            **data,
        },
        blocking=True,
        return_response=True,
    )


def _receiver_entity(hass: HomeAssistant, entry: MockConfigEntry) -> str:
    from homeassistant.helpers import entity_registry as er

    [entity] = [
        e
        for e in er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
        if e.domain == "notification_receiver"
    ]
    return entity.entity_id


async def test_creates_notification(hass: HomeAssistant) -> None:
    """Named explicitly, the receiver creates a notification with title."""
    assert await async_setup_component(hass, "persistent_notification", {})
    assert await async_setup_component(hass, DOMAIN, {})
    entry = await _add(hass)

    response = await _send(hass, entry, message="Hello", title="Hi")

    assert response["counts"] == {"delivered": 1, "failed": 0, "skipped": 0}
    [notification] = _stored(hass).values()
    assert notification["message"] == "Hello"
    assert notification["title"] == "Hi"


async def test_title_is_optional(hass: HomeAssistant) -> None:
    """Without a title none is sent."""
    assert await async_setup_component(hass, "persistent_notification", {})
    assert await async_setup_component(hass, DOMAIN, {})
    entry = await _add(hass)

    await _send(hass, entry, message="Only message")

    [notification] = _stored(hass).values()
    assert notification["title"] is None


async def test_create_only(hass: HomeAssistant) -> None:
    """Each notification creates its own; none replaces another."""
    assert await async_setup_component(hass, "persistent_notification", {})
    assert await async_setup_component(hass, DOMAIN, {})
    entry = await _add(hass)

    await _send(hass, entry, message="One")
    await _send(hass, entry, message="Two")

    assert sorted(n["message"] for n in _stored(hass).values()) == ["One", "Two"]


async def test_not_reached_by_everyone(hass: HomeAssistant) -> None:
    """With no person or area it is only used when named."""
    assert await async_setup_component(hass, "persistent_notification", {})
    assert await async_setup_component(hass, DOMAIN, {})
    await _add(hass)

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            "notify",
            "com_system",
            {
                "message": "Hello",
                "person": {"active_choice": "Everyone", "Everyone": True},
            },
            blocking=True,
            return_response=True,
        )
    assert not _stored(hass)


async def test_people_option_hidden(hass: HomeAssistant) -> None:
    """The options form has no people field and stored people are ignored."""
    entry = await _add(hass, people=["person.alice"])

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["step_id"] == "no_options"
    assert not result["data_schema"]
    result = await hass.config_entries.options.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY

    registry = hass.data[DOMAIN]["registry"]
    [receiver] = registry.all()
    assert registry.people_of(receiver) == ()
