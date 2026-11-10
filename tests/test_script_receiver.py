"""Tests for script receivers: detection and delivery."""

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.com_system.const import (
    CONF_ENTRY_TYPE,
    CONF_NAME,
    CONF_RECEIVER_TYPE,
    CONF_SOURCE_ID,
    DATA_REGISTRY,
    DOMAIN,
    ENTRY_TYPE_HUB,
    ENTRY_TYPE_RECEIVER,
    RECEIVER_TYPE_CUSTOM,
)
from custom_components.com_system.dispatcher import async_dispatch
from custom_components.com_system.receiver_type import (
    get_receiver_type,
    is_notification_script,
)
from custom_components.com_system.targets import ResolvedTargets
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

OBJECT_FIELD = {"notification": {"selector": {"object": {}}}}


def test_is_notification_script() -> None:
    assert is_notification_script({"fields": OBJECT_FIELD})
    assert not is_notification_script({"fields": {}})
    assert not is_notification_script({})
    assert not is_notification_script(
        {"fields": {"notification": {"selector": {"text": {}}}}}
    )
    optional = {"other": {"selector": {"text": {}}}}
    assert is_notification_script({"fields": {**OBJECT_FIELD, **optional}})
    required = {"other": {"selector": {"text": {}}, "required": True}}
    assert not is_notification_script({"fields": {**OBJECT_FIELD, **required}})
    assert not is_notification_script(
        {"fields": {"message": {"selector": {"object": {}}}}}
    )


async def _scripts(hass: HomeAssistant) -> None:
    assert await async_setup_component(
        hass,
        "script",
        {
            "script": {
                "speaker": {
                    "alias": "Speaker",
                    "fields": {
                        "notification": {"selector": {"object": {}}},
                    },
                    "sequence": [],
                },
                "plain": {"sequence": []},
                "two_fields": {
                    "fields": {
                        "notification": {"selector": {"object": {}}},
                        "x": {"selector": {"text": {}}, "required": True},
                    },
                    "sequence": [],
                },
            }
        },
    )


async def test_detects_only_notification_scripts(hass: HomeAssistant) -> None:
    await _scripts(hass)
    candidates = await get_receiver_type(RECEIVER_TYPE_CUSTOM).async_detect(hass)
    assert [(c.source_id, c.name) for c in candidates] == [("speaker", "Speaker")]


async def test_delivery_passes_notification_to_script(hass: HomeAssistant) -> None:
    await _scripts(hass)
    MockConfigEntry(domain=DOMAIN, data={CONF_ENTRY_TYPE: ENTRY_TYPE_HUB}).add_to_hass(
        hass
    )
    assert await async_setup_component(hass, DOMAIN, {})
    calls = []
    hass.services.async_register("script", "speaker", lambda call: calls.append(call))
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Speaker",
        data={
            CONF_ENTRY_TYPE: ENTRY_TYPE_RECEIVER,
            CONF_RECEIVER_TYPE: RECEIVER_TYPE_CUSTOM,
            CONF_NAME: "Speaker",
            CONF_SOURCE_ID: "speaker",
        },
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    receiver = hass.data[DOMAIN][DATA_REGISTRY].get(entry.entry_id)
    results = await async_dispatch(
        hass,
        ResolvedTargets(receivers=[receiver], skipped=[]),
        {"title": "Hi", "message": "there"},
    )
    assert results[0].result == "delivered"
    assert calls[0].data == {"notification": {"title": "Hi", "message": "there"}}


async def test_delivery_fails_when_script_missing(hass: HomeAssistant) -> None:
    assert await async_setup_component(hass, DOMAIN, {})
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Gone",
        data={
            CONF_ENTRY_TYPE: ENTRY_TYPE_RECEIVER,
            CONF_RECEIVER_TYPE: RECEIVER_TYPE_CUSTOM,
            CONF_NAME: "Gone",
            CONF_SOURCE_ID: "gone",
        },
    )
    entry.add_to_hass(hass)
    receiver = hass.data[DOMAIN][DATA_REGISTRY].get(entry.entry_id)
    results = await async_dispatch(
        hass, ResolvedTargets(receivers=[receiver], skipped=[]), {"message": "x"}
    )
    assert results[0].result == "failed"
    assert "script gone" in results[0].reason.lower()


async def _check(hass, hass_ws_client, entity_id):
    client = await hass_ws_client(hass)
    await client.send_json(
        {"id": 1, "type": "com_system/scripts/check", "entity_id": entity_id}
    )
    msg = await client.receive_json()
    assert msg["success"], msg
    return msg["result"]


async def test_check_reports_problems(hass: HomeAssistant, hass_ws_client) -> None:
    await _scripts(hass)
    assert await async_setup_component(hass, DOMAIN, {})
    result = await _check(hass, hass_ws_client, "script.plain")
    assert not result["can_rescan"]
    assert [c["ok"] for c in result["checks"]] == [True, False]
    result = await _check(hass, hass_ws_client, "script.two_fields")
    assert not result["can_rescan"]
    assert (
        "required but only notification is passed: x" in result["checks"][-1]["message"]
    )
    result = await _check(hass, hass_ws_client, "script.missing")
    assert [c["ok"] for c in result["checks"]] == [False]


async def test_check_registered_and_rescan(hass: HomeAssistant, hass_ws_client) -> None:
    await _scripts(hass)
    MockConfigEntry(domain=DOMAIN, data={CONF_ENTRY_TYPE: ENTRY_TYPE_HUB}).add_to_hass(
        hass
    )
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()
    # Startup detection may already have offered it; clear that first.
    for flow in hass.config_entries.flow.async_progress_by_handler(DOMAIN):
        hass.config_entries.flow.async_abort(flow["flow_id"])

    # Fine and not yet a receiver: a rescan would offer it.
    result = await _check(hass, hass_ws_client, "script.speaker")
    assert all(c["ok"] for c in result["checks"])
    assert result["can_rescan"] is True

    client = await hass_ws_client(hass)
    await client.send_json({"id": 2, "type": "com_system/scripts/rescan"})
    assert (await client.receive_json())["success"]
    await hass.async_block_till_done()
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert any(f["context"]["title_placeholders"]["name"] == "Speaker" for f in flows)

    # Now it is waiting, so no rescan is needed.
    result = await _check(hass, hass_ws_client, "script.speaker")
    assert result["can_rescan"] is False
    assert "waiting" in result["checks"][-1]["message"]

    # Once added it is registered.
    flow = next(
        f for f in flows if f["context"]["title_placeholders"]["name"] == "Speaker"
    )
    await hass.config_entries.flow.async_configure(flow["flow_id"], {})
    await hass.async_block_till_done()
    result = await _check(hass, hass_ws_client, "script.speaker")
    assert result["checks"][-1] == {
        "id": "registered",
        "ok": False,
        "message": "It is already a receiver.",
    }
    assert result["can_rescan"] is False
