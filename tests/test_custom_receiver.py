"""Tests for custom receivers: flows, validation, delivery, editing."""

from unittest.mock import AsyncMock

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.com_system.const import (
    CONF_ACTION,
    CONF_ACTION_DATA,
    CONF_ENTRY_TYPE,
    CONF_NAME,
    CONF_PEOPLE,
    CONF_RECEIVER_TYPE,
    DATA_REGISTRY,
    DOMAIN,
    ENTRY_TYPE_CUSTOM_RECEIVER,
    ENTRY_TYPE_HUB,
    RECEIVER_TYPE_CUSTOM,
)
from custom_components.com_system.dispatcher import async_dispatch
from custom_components.com_system.targets import ResolvedTargets
from homeassistant import config_entries
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.setup import async_setup_component


async def _setup(hass: HomeAssistant) -> None:
    MockConfigEntry(domain=DOMAIN, data={CONF_ENTRY_TYPE: ENTRY_TYPE_HUB}).add_to_hass(
        hass
    )
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()
    hass.services.async_register("notify", "speaker", AsyncMock())


async def _add(hass: HomeAssistant, name="Speaker", **extra) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=name,
        data={
            CONF_ENTRY_TYPE: ENTRY_TYPE_CUSTOM_RECEIVER,
            CONF_RECEIVER_TYPE: RECEIVER_TYPE_CUSTOM,
            CONF_NAME: name,
            CONF_ACTION: "notify.speaker",
            CONF_ACTION_DATA: {"message": "{{ title }}: {{ message }}"},
            **extra,
        },
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_user_flow_creates_custom_receiver(hass: HomeAssistant) -> None:
    await _setup(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["step_id"] == "custom_receiver"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_NAME: " Kitchen ", CONF_ACTION: "Notify.Speaker", CONF_ACTION_DATA: {}},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_NAME] == "Kitchen"
    assert result["data"][CONF_ACTION] == "notify.speaker"


async def test_flow_validation_errors(hass: HomeAssistant) -> None:
    await _setup(hass)
    await _add(hass, "Speaker")
    cases = [
        ({CONF_NAME: "speaker", CONF_ACTION: "notify.speaker"}, "name_exists"),
        ({CONF_NAME: "A", CONF_ACTION: "nodot"}, "invalid_action"),
        ({CONF_NAME: "A", CONF_ACTION: "notify.nope"}, "unknown_action"),
        (
            {
                CONF_NAME: "A",
                CONF_ACTION: "notify.speaker",
                CONF_ACTION_DATA: {"x": "{{ "},
            },
            "invalid_template",
        ),
    ]
    for user_input, error in cases:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == {"base": error}


async def test_reconfigure_custom(hass: HomeAssistant) -> None:
    await _setup(hass)
    entry = await _add(hass)
    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_NAME: "Renamed", CONF_ACTION: "notify.speaker", CONF_ACTION_DATA: {}},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.title == "Renamed"
    assert entry.data[CONF_ACTION_DATA] == {}


async def test_delivery_renders_templates(hass: HomeAssistant) -> None:
    await _setup(hass)
    calls: list[ServiceCall] = []

    async def handler(call: ServiceCall) -> None:
        calls.append(call)

    hass.services.async_register("notify", "speaker", handler)
    entry = await _add(hass)
    receiver = hass.data[DOMAIN][DATA_REGISTRY].get(entry.entry_id)
    results = await async_dispatch(
        hass,
        ResolvedTargets(receivers=[receiver], skipped=[]),
        {"title": "Hi", "message": "there"},
    )
    assert results[0].result == "delivered"
    assert calls[0].data == {"message": "Hi: there"}


async def test_delivery_fails_when_action_missing(hass: HomeAssistant) -> None:
    await _setup(hass)
    entry = await _add(hass, **{CONF_ACTION: "notify.gone"})
    receiver = hass.data[DOMAIN][DATA_REGISTRY].get(entry.entry_id)
    results = await async_dispatch(
        hass, ResolvedTargets(receivers=[receiver], skipped=[]), {"message": "x"}
    )
    assert results[0].result == "failed"
    assert "notify.gone" in results[0].reason


async def test_ws_create_update_remove(hass: HomeAssistant, hass_ws_client) -> None:
    await _setup(hass)
    client = await hass_ws_client(hass)

    async def call(msg):
        await client.send_json({"id": call.n, **msg})
        call.n += 1
        return await client.receive_json()

    call.n = 1
    msg = await call(
        {
            "type": "com_system/receivers/create",
            "name": "Hall",
            "action": "notify.speaker",
            "people": ["person.alice"],
        }
    )
    assert msg["success"], msg
    entry_id = msg["result"]["entry_id"]
    assert msg["result"]["action"] == "notify.speaker"
    assert msg["result"]["people"] == ["person.alice"]

    msg = await call(
        {
            "type": "com_system/receivers/create",
            "name": "hall",
            "action": "notify.speaker",
        }
    )
    assert msg["error"]["code"] == "name_exists"

    msg = await call(
        {
            "type": "com_system/receivers/update",
            "entry_id": entry_id,
            "name": "Hallway",
            "people": [],
            "action_data": {"message": "{{ message }}"},
        }
    )
    assert msg["success"], msg
    assert msg["result"]["name"] == "Hallway"
    assert msg["result"]["people"] == []
    assert msg["result"]["action_data"] == {"message": "{{ message }}"}

    msg = await call(
        {"type": "com_system/receivers/update", "entry_id": entry_id, "action": "x.y"}
    )
    assert msg["error"]["code"] == "unknown_action"

    msg = await call({"type": "com_system/receivers/remove", "entry_id": entry_id})
    assert msg["success"]
    msg = await call({"type": "com_system/receivers/get", "entry_id": entry_id})
    assert msg["error"]["code"] == "not_found"


async def test_ws_update_people_on_discovered_receiver(
    hass: HomeAssistant, hass_ws_client
) -> None:
    await _setup(hass)
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Phone",
        data={
            CONF_ENTRY_TYPE: "receiver",
            CONF_RECEIVER_TYPE: "pushover",
            CONF_NAME: "Phone",
            "source_id": "s",
        },
    )
    entry.add_to_hass(hass)
    client = await hass_ws_client(hass)
    await client.send_json(
        {
            "id": 1,
            "type": "com_system/receivers/update",
            "entry_id": entry.entry_id,
            "people": ["person.bob"],
        }
    )
    msg = await client.receive_json()
    assert msg["success"], msg
    assert entry.options[CONF_PEOPLE] == ["person.bob"]
    await client.send_json(
        {
            "id": 2,
            "type": "com_system/receivers/update",
            "entry_id": entry.entry_id,
            "action": "a.b",
        }
    )
    assert (await client.receive_json())["error"]["code"] == "not_custom"
