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
    assert result["step_id"] == "receiver"
    assert "people" not in result["data_schema"].schema
    assert "conditions" in result["data_schema"].schema


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


ACTIONS = [{"action": "OPEN", "title": "Open"}, {"action": "SHUT", "title": "Shut"}]
TYPED = [{"id": "OPEN", "label": "Open", "uri": "/x"}, {"id": "SHUT", "label": "Shut"}]


async def _send_with_actions(hass: HomeAssistant) -> tuple[dict, list[ServiceCall]]:
    await _setup_hub(hass)
    _phone(hass)
    hass.states.async_set("person.alice", "home", {"user_id": USER})
    calls: list[ServiceCall] = []
    hass.services.async_register("notify", "mobile_app_pixel", calls.append)
    await _receiver(hass)
    response = await hass.services.async_call(
        "notify",
        "com_system",
        {
            "message": "Door",
            "tag": "door",
            "people": ["person.alice"],
            "data": {"mobile_app": {"actions": ACTIONS, "action_data": {"x": 1}}},
        },
        blocking=True,
        return_response=True,
    )
    return response, calls


async def test_actions_carry_notification_id(hass: HomeAssistant) -> None:
    """Action IDs are sent with the notification and receiver encoded."""
    response, calls = await _send_with_actions(hass)
    sent = calls[0].data["data"]
    prefix = f"com_system:{response['id']}:{response['results'][0]['entry_id']}:door:"
    assert sent["actions"] == [
        {"action": f"{prefix}OPEN", "title": "Open"},
        {"action": f"{prefix}SHUT", "title": "Shut"},
    ]
    assert sent["action_data"] == {"x": 1}  # the user's own keys are untouched


def test_action_encoding_round_trips() -> None:
    """An action id may itself contain colons; other values do not decode."""
    from custom_components.com_system.mobile_app import decode_action, encode_action

    assert decode_action(encode_action("n", "r", "a:b")) == ("n", "r", None, "a:b")
    # A tag may contain colons and other awkward characters.
    tag = "front door: 1/é"
    assert decode_action(encode_action("n", "r", "a:b", tag)) == (
        "n",
        "r",
        tag,
        "a:b",
    )
    assert decode_action("OPEN") is None
    assert decode_action("com_system::r::a") is None
    assert decode_action("com_system:n:r:a") is None  # the old, tagless form
    assert decode_action(None) is None


async def test_uri_actions_are_not_encoded(hass: HomeAssistant) -> None:
    """An action that opens a URI sends no response, so it is left as is."""
    calls = await _deliver(
        hass,
        {"id": "n1", "actions": [{"id": "GO", "label": "Go", "uri": "/x"}]},
    )
    assert calls[0].data["data"]["actions"] == [
        {"action": "GO", "title": "Go", "uri": "/x"}
    ]


async def test_no_action_data_without_actions(hass: HomeAssistant) -> None:
    """A notification with no actions is sent without action_data."""
    await _setup_hub(hass)
    _phone(hass)
    calls: list[ServiceCall] = []
    hass.services.async_register("notify", "mobile_app_pixel", calls.append)
    entry = await _receiver(hass)
    receiver = _registry(hass).get(entry.entry_id)
    await (
        _registry(hass)
        .type_of(receiver)
        .async_deliver(hass, receiver, {"id": "n1", "message": "Hi"})
    )
    assert "data" not in calls[0].data


async def test_action_response_fires_event_and_is_stored(hass: HomeAssistant) -> None:
    """Pressing an action fires com_system_action and is stored in history."""
    response, calls = await _send_with_actions(hass)
    events = []
    hass.bus.async_listen("com_system_action", events.append)
    hass.bus.async_fire(
        "mobile_app_notification_action",
        {
            "action": calls[0].data["data"]["actions"][0]["action"],
            "action_1_key": "x",
            "reply_text": "ok",
            "device_id": "abc",
        },
    )
    await hass.async_block_till_done()
    assert len(events) == 1
    assert events[0].data == {
        "notification_id": response["id"],
        "receiver_id": response["results"][0]["entry_id"],
        "tag": "door",
        "receiver": "Pixel",
        "person": "person.alice",
        "action": "OPEN",
        "reply_text": "ok",
    }
    records = await hass.data[DOMAIN]["history"].async_list()
    assert records[0]["id"] == response["id"]
    stored = records[0]["responses"]
    assert len(stored) == 1
    assert stored[0]["action"] == "OPEN"
    assert stored[0]["person"] == "person.alice"
    assert "time" in stored[0]


async def test_foreign_action_events_are_ignored(hass: HomeAssistant) -> None:
    """An action event from a notification Com System did not send is ignored."""
    await _setup_hub(hass)
    events = []
    hass.bus.async_listen("com_system_action", events.append)
    hass.bus.async_fire("mobile_app_notification_action", {"action": "OPEN"})
    await hass.async_block_till_done()
    assert not events


async def test_response_to_pruned_notification_still_fires(
    hass: HomeAssistant,
) -> None:
    """A response whose notification left history is fired but not stored."""
    await _setup_hub(hass)
    events = []
    hass.bus.async_listen("com_system_action", events.append)
    hass.bus.async_fire(
        "mobile_app_notification_action",
        {"action": "com_system:gone:missing:front%20door:OPEN"},
    )
    await hass.async_block_till_done()
    assert events[0].data["notification_id"] == "gone"
    assert events[0].data["receiver"] is None
    # The tag travels in the action ID, so it survives the record being gone.
    assert events[0].data["tag"] == "front door"


async def _deliver(hass: HomeAssistant, notification: dict) -> list[ServiceCall]:
    await _setup_hub(hass)
    _phone(hass)
    calls: list[ServiceCall] = []
    hass.services.async_register("notify", "mobile_app_pixel", calls.append)
    entry = await _receiver(hass)
    receiver = _registry(hass).get(entry.entry_id)
    await (
        _registry(hass)
        .type_of(receiver)
        .async_deliver(hass, receiver, {"message": "Hi", **notification})
    )
    return calls


async def test_click_action_tag_and_car_ui_are_mapped(hass: HomeAssistant) -> None:
    """The typed fields become the companion app's data keys."""
    calls = await _deliver(
        hass, {"click_action": "/lovelace/cams", "tag": "door", "car_ui": True}
    )
    assert calls[0].data["data"] == {
        "clickAction": "/lovelace/cams",
        "url": "/lovelace/cams",
        "tag": "door",
        "car_ui": True,
    }


async def test_car_ui_false_is_not_sent(hass: HomeAssistant) -> None:
    """Car UI off sends nothing."""
    calls = await _deliver(hass, {"car_ui": False})
    assert "data" not in calls[0].data


def _entry_id(calls: list[ServiceCall]) -> str:
    return calls[0].data["data"]["actions"][1]["action"].split(":")[2]


async def test_typed_actions_get_tracking_and_data_block_wins(
    hass: HomeAssistant,
) -> None:
    """Actions field is sent with tracking; the mobile_app block overrides."""
    calls = await _deliver(
        hass,
        {
            "id": "n1",
            "tag": "a",
            "actions": TYPED,
            "data": {"tag": "b"},
        },
    )
    sent = calls[0].data["data"]
    # id and label are the app's action and title; other keys pass through.
    # The id is the app's action (encoded, so a response can be matched), the
    # label its title; a uri action is not encoded and other keys pass through.
    assert sent["actions"] == [
        {"action": "OPEN", "title": "Open", "uri": "/x"},
        {
            "action": "com_system:n1:" + _entry_id(calls) + ":b:SHUT",
            "title": "Shut",
        },
    ]
    assert sent["tag"] == "b"


async def test_action_fields_validated_and_dropped_elsewhere(
    hass: HomeAssistant,
) -> None:
    """Bad actions are rejected; other types drop the fields with warnings."""
    import voluptuous as vol

    from custom_components.com_system.content import (
        apply_capabilities,
        validate_actions,
    )
    from custom_components.com_system.receiver_type import ReceiverType

    with pytest.raises(vol.Invalid):
        validate_actions([{"label": "No id"}])
    assert validate_actions({"id": "A", "label": "T", "behavior": "x"}) == [
        {"id": "A", "label": "T", "behavior": "x"}
    ]

    class Plain(ReceiverType):
        type_id = "plain"
        name = "Plain"
        capabilities = frozenset({"title"})

    content, warnings = apply_capabilities(
        Plain(), {"message": "m", "tag": "t", "car_ui": True, "actions": TYPED}
    )
    assert content == {"message": "m"}
    assert warnings == [
        "Plain does not support these properties, which were dropped: "
        "actions, tag, car_ui"
    ]
