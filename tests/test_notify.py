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
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import floor_registry as fr
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


EVERYONE = {"active_choice": "Everyone", "Everyone": True}


def _select(*entity_ids: str, **target) -> dict:
    """A receivers value choosing Select with the given receiver entities."""
    if entity_ids:
        target["entity_id"] = list(entity_ids)
    return {"active_choice": "Select", "Select": target}


async def _send(hass: HomeAssistant, **data):
    return await hass.services.async_call(
        "notify", "com_system", data, blocking=True, return_response=True
    )


async def test_action_registered_with_schema(hass: HomeAssistant) -> None:
    """The action exists, supports a response and has UI metadata."""
    assert await async_setup_component(hass, DOMAIN, {})
    assert hass.services.has_service("notify", "com_system")
    description = (await async_get_all_descriptions(hass))["notify"]["com_system"]
    assert {"title", "message", "people", "receivers"} <= set(description["fields"])


async def test_invalid_input_rejected(hass: HomeAssistant) -> None:
    """A missing message or unknown field fails before delivery."""
    assert await async_setup_component(hass, DOMAIN, {})
    with pytest.raises(vol.Invalid):
        await _send(hass, title="no message")
    with pytest.raises(vol.Invalid):
        await _send(hass, message="hi", people=["light.nope"])
    with pytest.raises(vol.Invalid):
        await _send(hass, message="hi", priority="high")


async def test_delivers_to_each_receiver(hass: HomeAssistant, types) -> None:
    """The default goes to receivers with a person; results are per receiver."""
    assert await async_setup_component(hass, DOMAIN, {})
    alice = await _add(hass, "Alice", people=["person.alice"])
    await _add(hass, "Shared")  # no person or area: not in the default

    response = await _send(hass, message="Hello", title="Hi", people=EVERYONE)

    assert response["counts"] == {"delivered": 1, "failed": 0, "skipped": 0}
    [result] = response["results"]
    assert result == {
        "entry_id": alice.entry_id,
        "name": "Alice",
        "type": "Test OK",
        "result": "delivered",
        "reason": None,
        "warnings": [],
        "reasons": [{"kind": "everyone"}],
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

    response = await _send(hass, message="x", people=EVERYONE)

    by_name = {r["name"]: r for r in response["results"]}
    assert [r["name"] for r in response["results"]] == sorted(by_name)
    assert by_name["A good"]["result"] == "delivered"
    assert by_name["B broken"]["result"] == "failed"
    assert by_name["B broken"]["reason"] == "boom"
    assert by_name["C custom"]["result"] == "failed"
    assert "is not available" in by_name["C custom"]["reason"]
    assert by_name["D unknown"]["result"] == "failed"
    assert response["counts"] == {"delivered": 1, "failed": 3, "skipped": 0}


async def test_disabled_receiver_is_skipped(hass: HomeAssistant, types) -> None:
    """A disabled receiver is skipped with a reason, others are delivered."""
    assert await async_setup_component(hass, DOMAIN, {})
    await _add(hass, "On", people=["person.a"])
    await _add(hass, "Off", people=["person.a"])
    await hass.services.async_call(
        "switch",
        "turn_off",
        {"entity_id": "switch.off_notifications_enabled"},
        blocking=True,
    )

    response = await _send(hass, message="x", people=EVERYONE)

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

    response = await _send(hass, message="x", title="t", people=EVERYONE)

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
        "switch",
        "turn_off",
        {"entity_id": "switch.off_notifications_enabled"},
        blocking=True,
    )
    await _add(hass, "On", people=["person.a"])

    await _send(hass, message="x", people=EVERYONE)

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

    by_person = await _send(hass, message="x", people="person.bob")
    assert [r["name"] for r in by_person["results"]] == ["Bob"]

    named = await _send(
        hass,
        message="x",
        people=["person.alice"],
        receivers=_select("notification_receiver.shared"),
    )
    assert [r["name"] for r in named["results"]] == ["Alice", "Shared"]


async def test_raises_when_nothing_can_be_attempted(hass: HomeAssistant, types) -> None:
    """No match, or only disabled matches, raises; unknown entities match nothing."""
    assert await async_setup_component(hass, DOMAIN, {})
    with pytest.raises(ServiceValidationError, match="No targets given"):
        await _send(hass, message="x")
    with pytest.raises(ServiceValidationError, match="No receiver matches"):
        await _send(hass, message="x", people=EVERYONE)

    await _add(hass, "Off", people=["person.a"])
    await hass.services.async_call(
        "switch",
        "turn_off",
        {"entity_id": "switch.off_notifications_enabled"},
        blocking=True,
    )
    with pytest.raises(ServiceValidationError, match="disabled"):
        await _send(hass, message="x", people="person.a")
    with pytest.raises(ServiceValidationError, match="No receiver matches"):
        await _send(hass, message="x", receivers=_select("notification_receiver.nope"))


async def test_foreign_entity_matches_nothing(hass: HomeAssistant, types) -> None:
    """A notification_receiver entity of another integration is ignored."""
    assert await async_setup_component(hass, DOMAIN, {})
    await _add(hass, "Alice", people=["person.alice"])
    er.async_get(hass).async_get_or_create(
        "notification_receiver", "other", "1", suggested_object_id="other"
    )
    with pytest.raises(ServiceValidationError):
        await _send(hass, message="x", receivers=_select("notification_receiver.other"))


def test_custom_type_unchanged() -> None:
    """The generic type keeps its id."""
    assert CustomReceiverType.type_id == "custom"


async def test_people_choice(hass: HomeAssistant, types) -> None:
    """Everyone reaches every receiver with a person; individuals only theirs."""
    assert await async_setup_component(hass, DOMAIN, {})
    await _add(hass, "Alice", people=["person.alice"])
    await _add(hass, "Bob", people=["person.bob"])
    await _add(hass, "Shared")

    everyone = await _send(
        hass, message="x", people={"active_choice": "Everyone", "Everyone": True}
    )
    assert [r["name"] for r in everyone["results"]] == ["Alice", "Bob"]

    individuals = await _send(
        hass,
        message="x",
        people={"active_choice": "Individuals", "Individuals": ["person.bob"]},
    )
    assert [r["name"] for r in individuals["results"]] == ["Bob"]

    # A plain list still means individuals.
    plain = await _send(hass, message="x", people=["person.alice"])
    assert [r["name"] for r in plain["results"]] == ["Alice"]

    # Everyone is combined with the other targets as a union.
    union = await _send(
        hass,
        message="x",
        people={"active_choice": "Everyone", "Everyone": True},
        receivers=_select("notification_receiver.shared"),
    )
    assert [r["name"] for r in union["results"]] == ["Alice", "Bob", "Shared"]

    # Individuals with nobody chosen is no person target: here, no targets.
    with pytest.raises(ServiceValidationError, match="No receiver matches"):
        await _send(
            hass,
            message="x",
            people={"active_choice": "Individuals", "Individuals": []},
            receivers=_select("notification_receiver.nope"),
        )


async def test_people_choice_invalid(hass: HomeAssistant) -> None:
    """An unknown choice or a non-person entity is rejected."""
    assert await async_setup_component(hass, DOMAIN, {})
    with pytest.raises(vol.Invalid):
        await _send(hass, message="x", people={"active_choice": "Nobody"})
    with pytest.raises(vol.Invalid):
        await _send(
            hass,
            message="x",
            people={"active_choice": "Individuals", "Individuals": ["light.a"]},
        )


async def test_description_order_and_people_selector(hass: HomeAssistant) -> None:
    """Title comes first and people are a choose selector."""
    assert await async_setup_component(hass, DOMAIN, {})
    fields = (await async_get_all_descriptions(hass))["notify"]["com_system"]["fields"]
    assert list(fields) == ["title", "message", "people", "receivers"]
    # The form starts with Everyone and All Areas, as the Test page does.
    assert fields["people"]["default"] == {
        "active_choice": "Everyone",
        "Everyone": True,
    }
    assert fields["receivers"]["default"] == {
        "active_choice": "All Areas",
        "All Areas": True,
    }
    choices = fields["people"]["selector"]["choose"]["choices"]
    assert list(choices) == ["Individuals", "Everyone"]
    assert choices["Individuals"]["selector"]["entity"] == {
        "domain": "person",
        "multiple": True,
    }
    choices = fields["receivers"]["selector"]["choose"]["choices"]
    assert list(choices) == ["Select", "All Areas"]
    assert choices["Select"]["selector"]["target"] == {
        "entity": {"domain": "notification_receiver", "integration": "com_system"}
    }


async def test_receivers_choice(hass: HomeAssistant, types) -> None:
    """All Areas reaches receivers with an area; Select the chosen ones."""
    assert await async_setup_component(hass, DOMAIN, {})
    kitchen = ar.async_get(hass).async_create("Kitchen").id
    floor = fr.async_get(hass).async_create("Ground").floor_id
    ar.async_get(hass).async_update(kitchen, floor_id=floor)
    alice = await _add(hass, "Alice", people=["person.alice"])
    echo = await _add(hass, "Echo")
    shared = await _add(hass, "Shared")
    device = dr.async_get(hass).async_get_device_by_identifier(
        (DOMAIN, echo.entry_id), echo.entry_id
    )
    dr.async_get(hass).async_update_device(device.id, area_id=kitchen)

    names = lambda response: [r["name"] for r in response["results"]]  # noqa: E731

    all_areas = await _send(
        hass,
        message="x",
        receivers={"active_choice": "All Areas", "All Areas": True},
    )
    assert names(all_areas) == ["Echo"]

    # Select by area, floor and device, and by receiver; all are a union.
    assert names(
        await _send(hass, message="x", receivers=_select(area_id=[kitchen]))
    ) == ["Echo"]
    assert names(
        await _send(hass, message="x", receivers=_select(floor_id=[floor]))
    ) == ["Echo"]
    assert names(
        await _send(hass, message="x", receivers=_select(device_id=[device.id]))
    ) == ["Echo"]
    assert names(
        await _send(
            hass,
            message="x",
            receivers=_select("notification_receiver.shared", area_id=[kitchen]),
        )
    ) == ["Echo", "Shared"]
    # A plain target dict means Select.
    assert names(
        await _send(
            hass, message="x", receivers={"entity_id": ["notification_receiver.alice"]}
        )
    ) == ["Alice"]
    assert alice and shared

    # Something selected that matches nothing is still a target.
    for target in (
        _select(floor_id=["nope"]),
        _select(device_id=["nope"]),
        _select(label_id=["nope"]),
        _select(area_id=["nope"]),
    ):
        with pytest.raises(ServiceValidationError, match="No receiver matches"):
            await _send(hass, message="x", receivers=target)


async def test_receivers_choice_invalid(hass: HomeAssistant) -> None:
    """An unknown choice or a non-receiver entity is rejected."""
    assert await async_setup_component(hass, DOMAIN, {})
    with pytest.raises(vol.Invalid):
        await _send(hass, message="x", receivers={"active_choice": "Nobody"})
    with pytest.raises(vol.Invalid):
        await _send(hass, message="x", receivers=_select("light.kitchen"))


async def test_ungiven_group_is_not_targeted(hass: HomeAssistant, types) -> None:
    """Without people, a receiver is only reached through a targeted area."""
    assert await async_setup_component(hass, DOMAIN, {})
    kitchen = ar.async_get(hass).async_create("Kitchen").id
    await _add(hass, "Alice", people=["person.alice"])
    echo = await _add(hass, "Echo", people=["person.bob"])
    device = dr.async_get(hass).async_get_device_by_identifier(
        (DOMAIN, echo.entry_id), echo.entry_id
    )
    dr.async_get(hass).async_update_device(device.id, area_id=kitchen)

    # No people given: Alice is not reached, Echo is, through its area.
    response = await _send(hass, message="x", receivers=_select(area_id=[kitchen]))
    assert [r["name"] for r in response["results"]] == ["Echo"]
    # No receivers given: only people are targeted.
    response = await _send(hass, message="x", people=EVERYONE)
    assert [r["name"] for r in response["results"]] == ["Alice", "Echo"]
    response = await _send(hass, message="x", people=["person.alice"])
    assert [r["name"] for r in response["results"]] == ["Alice"]
