"""Tests for mobile app receivers: person link, personal/shared, delivery."""

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.com_system.const import (
    CONF_ENTRY_TYPE,
    CONF_NAME,
    CONF_PEOPLE,
    CONF_RECEIVER_TYPE,
    CONF_SOURCE_ID,
    DOMAIN,
    ENTRY_TYPE_HUB,
    ENTRY_TYPE_RECEIVER,
    RECEIVER_TYPE_MOBILE_APP,
)
from custom_components.com_system.mobile_app import linked_person
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

SELECT = "select.pixel_device_use"
USER = "user-1"


async def _setup_hub(hass: HomeAssistant) -> None:
    MockConfigEntry(domain=DOMAIN, data={CONF_ENTRY_TYPE: ENTRY_TYPE_HUB}).add_to_hass(
        hass
    )
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()


def _phone(hass: HomeAssistant, with_tracker: bool = False) -> MockConfigEntry:
    """A mobile_app registration with its device (and optionally tracker)."""
    source = MockConfigEntry(
        domain="mobile_app",
        title="Pixel",
        data={"device_id": "abc", "device_name": "Pixel", "user_id": USER},
    )
    source.add_to_hass(hass)
    dr.async_get(hass).async_get_or_create(
        config_entry_id=source.entry_id,
        identifiers={("mobile_app", "abc")},
        name="Pixel",
    )
    if with_tracker:
        er.async_get(hass).async_get_or_create(
            "device_tracker",
            "mobile_app",
            "abc",
            suggested_object_id="pixel",
            config_entry=source,
        )
    return source


async def _receiver(hass: HomeAssistant, **options) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Pixel",
        data={
            CONF_ENTRY_TYPE: ENTRY_TYPE_RECEIVER,
            CONF_RECEIVER_TYPE: RECEIVER_TYPE_MOBILE_APP,
            CONF_SOURCE_ID: "abc",
            CONF_NAME: "Pixel",
        },
        options=options,
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def _registry(hass: HomeAssistant):
    return hass.data[DOMAIN]["registry"]


def _people(hass: HomeAssistant, entry) -> tuple[str, ...]:
    registry = _registry(hass)
    return registry.people_of(registry.get(entry.entry_id))


async def test_person_from_registering_user(hass: HomeAssistant) -> None:
    """Step 1: the person linked to the user the app registered with."""
    await _setup_hub(hass)
    _phone(hass)
    hass.states.async_set("person.bob", "home", {"user_id": "other"})
    hass.states.async_set("person.alice", "home", {"user_id": USER})
    entry = await _receiver(hass)
    assert _people(hass, entry) == ("person.alice",)
    assert hass.states.get(SELECT).state == "personal"


async def test_person_from_device_tracker(hass: HomeAssistant) -> None:
    """Step 2: no user-linked person, so the person owning the tracker."""
    await _setup_hub(hass)
    _phone(hass, with_tracker=True)
    await async_setup_component(
        hass,
        "person",
        {
            "person": [
                {
                    "id": "a",
                    "name": "Alice",
                    "device_trackers": ["device_tracker.pixel"],
                }
            ]
        },
    )
    await hass.async_block_till_done()
    entry = await _receiver(hass)
    assert _people(hass, entry) == ("person.alice",)


async def test_no_person_is_shared_by_default(hass: HomeAssistant) -> None:
    """With no person the receiver starts shared and has no people."""
    await _setup_hub(hass)
    _phone(hass)
    entry = await _receiver(hass)
    assert hass.states.get(SELECT).state == "shared"
    assert _people(hass, entry) == ()
    assert linked_person(hass, _registry(hass).get(entry.entry_id)) is None


async def test_shared_hides_person_and_personal_restores(hass: HomeAssistant) -> None:
    """Shared is never reached by person; personal brings the person back."""
    await _setup_hub(hass)
    _phone(hass)
    hass.states.async_set("person.alice", "home", {"user_id": USER})
    entry = await _receiver(hass)
    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": SELECT, "option": "shared"},
        blocking=True,
    )
    assert _people(hass, entry) == ()
    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": SELECT, "option": "personal"},
        blocking=True,
    )
    assert _people(hass, entry) == ("person.alice",)


async def test_stored_people_are_ignored(hass: HomeAssistant) -> None:
    """The person comes from the link; a stored people option does nothing."""
    await _setup_hub(hass)
    _phone(hass)
    hass.states.async_set("person.alice", "home", {"user_id": USER})
    entry = await _receiver(hass, **{CONF_PEOPLE: ["person.bob"]})
    assert _people(hass, entry) == ("person.alice",)


async def test_options_flow_has_no_people_field(hass: HomeAssistant) -> None:
    """The options form of a mobile app receiver does not offer people."""
    await _setup_hub(hass)
    _phone(hass)
    entry = await _receiver(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["step_id"] == "no_options"
    assert not result.get("data_schema")


async def test_audience_is_restored(hass: HomeAssistant) -> None:
    """The choice survives a reload."""
    await _setup_hub(hass)
    _phone(hass)
    hass.states.async_set("person.alice", "home", {"user_id": USER})
    entry = await _receiver(hass)
    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": SELECT, "option": "shared"},
        blocking=True,
    )
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(SELECT).state == "shared"


async def test_other_types_have_no_select(hass: HomeAssistant) -> None:
    """Only mobile app receivers get the select."""
    await _setup_hub(hass)
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_ENTRY_TYPE: "custom_receiver", CONF_NAME: "Office"},
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.async_entity_ids("select") == []


async def test_delivery_calls_device_action(hass: HomeAssistant) -> None:
    """Message and title go to notify.mobile_app_<device>."""
    await _setup_hub(hass)
    _phone(hass)
    calls: list[ServiceCall] = []
    hass.services.async_register("notify", "mobile_app_pixel", calls.append)
    entry = await _receiver(hass)
    receiver = _registry(hass).get(entry.entry_id)
    mobile = _registry(hass).type_of(receiver)
    assert (
        await mobile.async_deliver(hass, receiver, {"message": "Hi", "title": "T"})
        == []
    )
    assert calls[0].data == {"message": "Hi", "title": "T"}
    await mobile.async_deliver(hass, receiver, {"message": "Only"})
    assert calls[1].data == {"message": "Only"}


async def test_delivery_fails_without_action(hass: HomeAssistant) -> None:
    """A missing notify action is a failure with a clear reason."""
    await _setup_hub(hass)
    _phone(hass)
    entry = await _receiver(hass)
    receiver = _registry(hass).get(entry.entry_id)
    with pytest.raises(Exception, match=r"notify\.mobile_app_pixel"):
        await (
            _registry(hass)
            .type_of(receiver)
            .async_deliver(hass, receiver, {"message": "Hi"})
        )


async def test_notify_by_person_reaches_personal_only(hass: HomeAssistant) -> None:
    """End to end: a person target reaches a personal device, not a shared one."""
    await _setup_hub(hass)
    _phone(hass)
    hass.states.async_set("person.alice", "home", {"user_id": USER})
    calls: list[ServiceCall] = []
    hass.services.async_register("notify", "mobile_app_pixel", calls.append)
    await _receiver(hass)
    data = {"message": "Hi", "people": ["person.alice"]}
    await hass.services.async_call(
        "notify", "com_system", data, blocking=True, return_response=True
    )
    assert len(calls) == 1
    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": SELECT, "option": "shared"},
        blocking=True,
    )
    with pytest.raises(Exception, match="No"):
        await hass.services.async_call(
            "notify", "com_system", data, blocking=True, return_response=True
        )
    assert len(calls) == 1
