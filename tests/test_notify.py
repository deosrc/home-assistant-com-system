"""Tests for the notify.com_system action and the dispatcher."""

from unittest.mock import AsyncMock

import pytest
import voluptuous as vol
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.com_system.const import (
    CONF_ENTRY_TYPE,
    CONF_NAME,
    CONF_PEOPLE,
    CONF_RECEIVER_TYPE,
    DOMAIN,
    ENTRY_TYPE_CUSTOM_RECEIVER,
)
from custom_components.com_system.receiver_type import (
    CustomReceiverType,
    ReceiverType,
    register_receiver_type,
    unregister_receiver_type,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.service import async_get_all_descriptions
from homeassistant.setup import async_setup_component


class _OkType(ReceiverType):
    type_id = "test_ok"
    name = "Test OK"

    def __init__(self) -> None:
        self.deliver = AsyncMock(return_value=[])

    async def async_deliver(self, hass, receiver, notification):
        return await self.deliver(receiver, notification)


class _BrokenType(ReceiverType):
    type_id = "test_broken"
    name = "Test broken"

    async def async_deliver(self, hass, receiver, notification):
        raise RuntimeError("boom")


@pytest.fixture
def types():
    """Register test receiver types for the test."""
    ok = _OkType()
    register_receiver_type(ok)
    register_receiver_type(_BrokenType())
    yield ok
    unregister_receiver_type("test_ok")
    unregister_receiver_type("test_broken")


async def _add(hass, name, type_id="test_ok", people=()):
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=name,
        data={
            CONF_ENTRY_TYPE: ENTRY_TYPE_CUSTOM_RECEIVER,
            CONF_NAME: name,
            CONF_RECEIVER_TYPE: type_id,
        },
        options={CONF_PEOPLE: list(people)},
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def _send(hass: HomeAssistant, **data):
    return await hass.services.async_call(
        "notify", "com_system", data, blocking=True, return_response=True
    )


async def test_action_registered_with_schema(hass: HomeAssistant) -> None:
    """The action exists, supports a response and has UI metadata."""
    assert await async_setup_component(hass, DOMAIN, {})
    assert hass.services.has_service("notify", "com_system")
    description = (await async_get_all_descriptions(hass))["notify"]["com_system"]
    assert {"message", "title", "person", "area_id", "entity_id"} <= set(
        description["fields"]
    )


async def test_invalid_input_rejected(hass: HomeAssistant) -> None:
    """A missing message or unknown field fails before delivery."""
    assert await async_setup_component(hass, DOMAIN, {})
    with pytest.raises(vol.Invalid):
        await _send(hass, title="no message")
    with pytest.raises(vol.Invalid):
        await _send(hass, message="hi", person=["light.nope"])
    with pytest.raises(vol.Invalid):
        await _send(hass, message="hi", priority="high")


async def test_delivers_to_each_receiver(hass: HomeAssistant, types) -> None:
    """The default goes to receivers with a person; results are per receiver."""
    assert await async_setup_component(hass, DOMAIN, {})
    alice = await _add(hass, "Alice", people=["person.alice"])
    await _add(hass, "Shared")  # no person or area: not in the default

    response = await _send(hass, message="Hello", title="Hi")

    assert response["counts"] == {"delivered": 1, "failed": 0, "skipped": 0}
    [result] = response["results"]
    assert result == {
        "entry_id": alice.entry_id,
        "name": "Alice",
        "type": "Test OK",
        "result": "delivered",
        "reason": None,
        "warnings": [],
    }
    types.deliver.assert_awaited_once()
    assert types.deliver.await_args.args[1] == {"message": "Hello", "title": "Hi"}


async def test_failure_does_not_block_others(hass: HomeAssistant, types) -> None:
    """A raising receiver is reported failed and the others still deliver."""
    assert await async_setup_component(hass, DOMAIN, {})
    await _add(hass, "A good", people=["person.a"])
    await _add(hass, "B broken", "test_broken", people=["person.a"])
    await _add(hass, "C custom", "custom", people=["person.a"])
    await _add(hass, "D unknown", "gone", people=["person.a"])

    response = await _send(hass, message="x")

    by_name = {r["name"]: r for r in response["results"]}
    assert [r["name"] for r in response["results"]] == sorted(by_name)
    assert by_name["A good"]["result"] == "delivered"
    assert by_name["B broken"]["result"] == "failed"
    assert by_name["B broken"]["reason"] == "boom"
    assert by_name["C custom"]["result"] == "failed"
    assert "not implemented" in by_name["C custom"]["reason"]
    assert by_name["D unknown"]["result"] == "failed"
    assert response["counts"] == {"delivered": 1, "failed": 3, "skipped": 0}


async def test_disabled_receiver_is_skipped(hass: HomeAssistant, types) -> None:
    """A disabled receiver is skipped with a reason, others are delivered."""
    assert await async_setup_component(hass, DOMAIN, {})
    await _add(hass, "On", people=["person.a"])
    await _add(hass, "Off", people=["person.a"])
    await hass.services.async_call(
        "switch", "turn_off", {"entity_id": "switch.off_enabled"}, blocking=True
    )

    response = await _send(hass, message="x")

    by_name = {r["name"]: r for r in response["results"]}
    assert by_name["Off"]["result"] == "skipped"
    assert by_name["Off"]["reason"] == "Receiver is disabled"
    assert by_name["On"]["result"] == "delivered"
    assert response["counts"]["skipped"] == 1


async def test_warnings_returned_and_recorded(hass: HomeAssistant, types) -> None:
    """Warnings from the type are in the response and on the entity."""
    assert await async_setup_component(hass, DOMAIN, {})
    await _add(hass, "Alice", people=["person.alice"])
    types.deliver.return_value = ["dropped title"]

    response = await _send(hass, message="x", title="t")

    assert response["results"][0]["warnings"] == ["dropped title"]
    state = hass.states.get("notification_receiver.alice")
    assert state.attributes["event_type"] == "delivered"
    assert state.attributes["message"] == "x"
    assert state.attributes["warnings"] == ["dropped title"]


async def test_attempts_recorded_for_failed_and_skipped(
    hass: HomeAssistant, types
) -> None:
    """Failed and skipped attempts update the receiver entity too."""
    assert await async_setup_component(hass, DOMAIN, {})
    await _add(hass, "Broken", "test_broken", people=["person.a"])
    await _add(hass, "Off", people=["person.a"])
    await hass.services.async_call(
        "switch", "turn_off", {"entity_id": "switch.off_enabled"}, blocking=True
    )
    await _add(hass, "On", people=["person.a"])

    await _send(hass, message="x")

    assert (
        hass.states.get("notification_receiver.broken").attributes["event_type"]
        == "failed"
    )
    assert (
        hass.states.get("notification_receiver.off").attributes["event_type"]
        == "skipped"
    )


async def test_targets(hass: HomeAssistant, types) -> None:
    """Person and receiver entity targets select receivers."""
    assert await async_setup_component(hass, DOMAIN, {})
    await _add(hass, "Alice", people=["person.alice"])
    await _add(hass, "Bob", people=["person.bob"])
    await _add(hass, "Shared")

    by_person = await _send(hass, message="x", person="person.bob")
    assert [r["name"] for r in by_person["results"]] == ["Bob"]

    named = await _send(
        hass,
        message="x",
        person=["person.alice"],
        entity_id=["notification_receiver.shared"],
    )
    assert [r["name"] for r in named["results"]] == ["Alice", "Shared"]


async def test_raises_when_nothing_can_be_attempted(hass: HomeAssistant, types) -> None:
    """No match, or only disabled matches, raises; unknown entities match nothing."""
    assert await async_setup_component(hass, DOMAIN, {})
    with pytest.raises(ServiceValidationError, match="No receiver matches"):
        await _send(hass, message="x")

    await _add(hass, "Off", people=["person.a"])
    await hass.services.async_call(
        "switch", "turn_off", {"entity_id": "switch.off_enabled"}, blocking=True
    )
    with pytest.raises(ServiceValidationError, match="disabled"):
        await _send(hass, message="x", person="person.a")
    with pytest.raises(ServiceValidationError, match="No receiver matches"):
        await _send(hass, message="x", entity_id="notification_receiver.nope")


async def test_foreign_entity_matches_nothing(hass: HomeAssistant, types) -> None:
    """A notification_receiver entity of another integration is ignored."""
    assert await async_setup_component(hass, DOMAIN, {})
    await _add(hass, "Alice", people=["person.alice"])
    er.async_get(hass).async_get_or_create(
        "notification_receiver", "other", "1", suggested_object_id="other"
    )
    with pytest.raises(ServiceValidationError):
        await _send(hass, message="x", entity_id="notification_receiver.other")


def test_custom_type_unchanged() -> None:
    """The generic type keeps its id."""
    assert CustomReceiverType.type_id == "custom"
