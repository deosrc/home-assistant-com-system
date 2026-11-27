"""Tests for per-receiver notification conditions."""

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.com_system.conditions import RawConditionSelector
from custom_components.com_system.const import (
    CONF_CONDITIONS,
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
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

TEMPLATE = "{{ 'secret' not in notification.message }}"


async def _add(hass: HomeAssistant, conditions=None, name="Persistent"):
    assert await async_setup_component(hass, "persistent_notification", {})
    assert await async_setup_component(hass, DOMAIN, {})
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=name,
        data={
            CONF_ENTRY_TYPE: ENTRY_TYPE_RECEIVER,
            CONF_RECEIVER_TYPE: RECEIVER_TYPE_PERSISTENT_NOTIFICATION,
            CONF_NAME: name,
        },
        options={CONF_CONDITIONS: conditions} if conditions is not None else {},
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def _data(hass: HomeAssistant, entry: MockConfigEntry, **extra) -> dict:
    entity_id = er.async_get(hass).async_get_entity_id(
        "notification_receiver", DOMAIN, f"{entry.entry_id}_receiver"
    )
    return {
        "receivers": {"active_choice": "Select", "Select": {"entity_id": [entity_id]}},
        **extra,
    }


async def _send(hass: HomeAssistant, entry: MockConfigEntry, message: str):
    response = await hass.services.async_call(
        "notify",
        "com_system",
        _data(hass, entry, message=message),
        blocking=True,
        return_response=True,
    )
    return response["results"][0]


async def test_no_conditions_passes(hass: HomeAssistant) -> None:
    entry = await _add(hass)
    assert (await _send(hass, entry, "hi"))["result"] == "delivered"


async def test_template_condition_skips(hass: HomeAssistant) -> None:
    entry = await _add(hass, [{"condition": "template", "value_template": TEMPLATE}])
    assert (await _send(hass, entry, "hello"))["result"] == "delivered"
    result = await _send(hass, entry, "a secret")
    assert result["result"] == "skipped"
    assert result["reason"] == "Conditions did not pass"
    assert len(pn._async_get_or_create_notifications(hass)) == 1


async def test_shorthand_and_variables(hass: HomeAssistant) -> None:
    entry = await _add(
        hass,
        [
            "{{ receiver.name == 'Persistent' }}",
            "{{ receiver.type_id == 'persistent_notification' }}",
            "{{ resolved_targets[0].kind == 'receiver' }}",
            "{{ notification.title is none }}",
            "{{ notification.targets.receivers is defined }}",
        ],
    )
    assert (await _send(hass, entry, "hi"))["result"] == "delivered"


async def test_all_conditions_must_pass(hass: HomeAssistant) -> None:
    entry = await _add(hass, ["{{ true }}", "{{ false }}"])
    assert (await _send(hass, entry, "hi"))["result"] == "skipped"


async def test_disabled_condition_is_ignored(hass: HomeAssistant) -> None:
    entry = await _add(
        hass,
        [
            {
                "condition": "template",
                "value_template": "{{ false }}",
                "enabled": False,
            }
        ],
    )
    assert (await _send(hass, entry, "hi"))["result"] == "delivered"


async def test_error_skips_and_is_recorded(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    entry = await _add(hass, ["{{ 1 / 0 }}"])
    result = await _send(hass, entry, "hi")
    assert result["result"] == "skipped"
    assert result["reason"].startswith("Condition error")
    assert "errored" in caplog.text
    state = hass.states.get("notification_receiver.persistent")
    assert state.attributes["event_type"] == "skipped"
    assert not pn._async_get_or_create_notifications(hass)


async def test_invalid_stored_conditions_are_an_error(hass: HomeAssistant) -> None:
    entry = await _add(hass, [{"condition": "nonsense"}])
    result = await _send(hass, entry, "hi")
    assert result["result"] == "skipped"
    assert result["reason"].startswith("Condition error")


async def test_disabled_reason_wins(hass: HomeAssistant) -> None:
    """Conditions are not evaluated for a disabled receiver."""
    entry = await _add(hass, ["{{ 1 / 0 }}"])
    await hass.services.async_call(
        "switch",
        "turn_off",
        {"entity_id": "switch.persistent_notifications_enabled"},
        blocking=True,
    )
    response = await hass.services.async_call(
        "notify",
        "com_system",
        _data(hass, entry, message="hi"),
        blocking=True,
        return_response=True,
    )
    assert [(r["result"], r["reason"]) for r in response["results"]] == [
        ("skipped", "Receiver is disabled")
    ]


async def test_options_flow_stores_raw_conditions(hass: HomeAssistant) -> None:
    entry = await _add(hass)
    conditions = [
        {"condition": "template", "value_template": TEMPLATE},
        {"condition": "time", "after": "08:00:00", "before": "22:00:00"},
    ]
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["step_id"] == "receiver"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_CONDITIONS: conditions}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_CONDITIONS] == conditions
    # Cleared in the form: removed.
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(result["flow_id"], {})
    assert CONF_CONDITIONS not in entry.options


async def test_options_flow_rejects_invalid_and_keeps_people(
    hass: HomeAssistant,
) -> None:
    entry = await _add(hass)
    hass.config_entries.async_update_entry(entry, options={CONF_PEOPLE: ["person.a"]})
    result = await hass.config_entries.options.async_init(entry.entry_id)
    with pytest.raises(Exception):  # noqa: B017
        await hass.config_entries.options.async_configure(
            result["flow_id"], {CONF_CONDITIONS: [{"condition": "template"}]}
        )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_CONDITIONS: ["{{ true }}"]}
    )
    assert entry.options[CONF_PEOPLE] == ["person.a"]
    assert entry.options[CONF_CONDITIONS] == ["{{ true }}"]


def test_selector_returns_input_unchanged() -> None:
    value = [{"condition": "template", "value_template": TEMPLATE}]
    assert RawConditionSelector()(value) is value
    assert RawConditionSelector().serialize() == {"selector": {"condition": {}}}


async def test_preview_evaluates_conditions(
    hass: HomeAssistant, hass_ws_client
) -> None:
    assert await async_setup_component(hass, "websocket_api", {})
    entry = await _add(hass, [{"condition": "template", "value_template": TEMPLATE}])
    client = await hass_ws_client(hass)
    base = {"type": "com_system/notify/preview", **_data(hass, entry)}

    async def outcome(**notification) -> dict:
        await client.send_json({"id": outcome.n, **base, "notification": notification})
        outcome.n += 1
        msg = await client.receive_json()
        return msg["result"]["receivers"][0]

    outcome.n = 1
    assert (await outcome(message="hi"))["outcome"] == "targeted"
    skipped = await outcome(message="a secret")
    assert skipped["outcome"] == "skipped"
    assert skipped["reason"] == "Conditions did not pass"


async def test_receivers_list_counts_conditions(
    hass: HomeAssistant, hass_ws_client
) -> None:
    assert await async_setup_component(hass, "websocket_api", {})
    await _add(hass, ["{{ true }}", "{{ true }}"])
    client = await hass_ws_client(hass)
    await client.send_json({"id": 1, "type": "com_system/receivers/list"})
    msg = await client.receive_json()
    assert msg["result"]["receivers"][0]["conditions"] == 2
