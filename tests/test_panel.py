"""Tests for the admin-only panel and its websocket commands."""

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.com_system.const import (
    CONF_ENTRY_TYPE,
    CONF_NAME,
    CONF_RECEIVER_TYPE,
    CONF_SOURCE_ID,
    DOMAIN,
    ENTRY_TYPE_CUSTOM_RECEIVER,
    ENTRY_TYPE_HUB,
    ENTRY_TYPE_RECEIVER,
    RECEIVER_TYPE_MOBILE_APP,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

COMMANDS = [
    {"type": "com_system/ping"},
    {"type": "com_system/dashboard"},
    {"type": "com_system/receivers/list"},
    {"type": "com_system/receivers/set_enabled", "entry_id": "x", "enabled": False},
    {"type": "com_system/discoveries/list"},
    {"type": "com_system/scripts/check", "entity_id": "script.x"},
    {"type": "com_system/scripts/rescan"},
    {"type": "com_system/notify/preview"},
    {"type": "com_system/notify/test", "message": "x"},
    {"type": "com_system/history/list"},
]


async def _setup(hass: HomeAssistant) -> MockConfigEntry:
    hub = MockConfigEntry(domain=DOMAIN, data={CONF_ENTRY_TYPE: ENTRY_TYPE_HUB})
    hub.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()
    return hub


async def _add_custom(hass: HomeAssistant, name: str) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=name,
        data={
            CONF_ENTRY_TYPE: ENTRY_TYPE_CUSTOM_RECEIVER,
            CONF_NAME: name,
            CONF_SOURCE_ID: name.lower(),
        },
    )
    # A script receiver is available while its script exists.
    hass.services.async_register("script", name.lower(), lambda call: None)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def _call(client, msg: dict) -> dict:
    client.next_id = getattr(client, "next_id", 0) + 1
    await client.send_json({"id": client.next_id, **msg})
    return await client.receive_json()


async def test_panel_registered_admin_only(hass: HomeAssistant) -> None:
    """The panel is in the sidebar for admins only."""
    await _setup(hass)
    panel = hass.data["frontend_panels"]["com-system"]
    assert panel.require_admin is True
    assert panel.sidebar_title == "Com System"


async def test_panel_dev_url(hass: HomeAssistant, monkeypatch) -> None:
    """COM_SYSTEM_PANEL_DEV_URL loads the panel from the Vite dev server."""
    url = "http://localhost:5173/src/com-system-panel.ts"
    monkeypatch.setenv("COM_SYSTEM_PANEL_DEV_URL", url)
    await _setup(hass)
    config = hass.data["frontend_panels"]["com-system"].config
    assert config["_panel_custom"]["module_url"] == url


async def test_ping_admin(hass: HomeAssistant, hass_ws_client) -> None:
    """An admin gets a pong."""
    await _setup(hass)
    msg = await _call(await hass_ws_client(hass), {"type": "com_system/ping"})
    assert msg["success"] and msg["result"] == {"pong": True}


@pytest.mark.parametrize("command", COMMANDS)
async def test_commands_reject_non_admin(
    hass: HomeAssistant, hass_ws_client, hass_read_only_access_token, command
) -> None:
    """Every command requires an admin user."""
    await _setup(hass)
    client = await hass_ws_client(hass, hass_read_only_access_token)
    msg = await _call(client, command)
    assert not msg["success"]
    assert msg["error"]["code"] == "unauthorized"


async def test_dashboard_empty(hass: HomeAssistant, hass_ws_client) -> None:
    """With no receivers every count is zero.

    The persistent notification receiver is always offered, so one discovery
    is pending.
    """
    await _setup(hass)
    msg = await _call(await hass_ws_client(hass), {"type": "com_system/dashboard"})
    assert msg["result"] == {
        "total": 0,
        "enabled": 0,
        "disabled": 0,
        "unavailable": 0,
        "pending_discoveries": 1,
        "by_type": {},
    }


async def test_receivers_list_and_enable_disable(
    hass: HomeAssistant, hass_ws_client
) -> None:
    """The list shows type and state; set_enabled drives the switch."""
    await _setup(hass)
    entry = await _add_custom(hass, "Office")
    client = await hass_ws_client(hass)

    msg = await _call(client, {"type": "com_system/receivers/list"})
    [receiver] = msg["result"]["receivers"]
    assert receiver["entry_id"] == entry.entry_id
    assert receiver["name"] == "Office"
    assert receiver["type_id"] == "custom"
    assert receiver["type"] == "Script"
    assert receiver["enabled"] is True
    device = dr.async_get(hass).async_get_device_by_identifier(
        (DOMAIN, entry.entry_id), entry.entry_id
    )
    assert receiver["device_id"] == device.id
    assert receiver["available"] is True
    assert receiver["entity_id"] == "switch.office_notifications_enabled"
    assert receiver["receiver_entity_id"] == "notification_receiver.office"

    msg = await _call(
        client,
        {
            "type": "com_system/receivers/set_enabled",
            "entry_id": entry.entry_id,
            "enabled": False,
        },
    )
    assert msg["success"]
    assert hass.states.get("switch.office_notifications_enabled").state == "off"

    msg = await _call(client, {"type": "com_system/dashboard"})
    assert msg["result"]["total"] == 1
    assert msg["result"]["enabled"] == 0
    assert msg["result"]["disabled"] == 1
    assert msg["result"]["by_type"] == {"Script": 1}

    await _call(
        client,
        {
            "type": "com_system/receivers/set_enabled",
            "entry_id": entry.entry_id,
            "enabled": True,
        },
    )
    assert hass.states.get("switch.office_notifications_enabled").state == "on"


async def test_receiver_area_comes_from_its_device(
    hass: HomeAssistant, hass_ws_client
) -> None:
    """The receiver's area is the area of its device."""
    await _setup(hass)
    entry = await _add_custom(hass, "Office")
    area = ar.async_get(hass).async_create("Study")
    registry = er.async_get(hass)
    device_id = registry.async_get("switch.office_notifications_enabled").device_id
    dr.async_get(hass).async_update_device(device_id, area_id=area.id)

    msg = await _call(await hass_ws_client(hass), {"type": "com_system/receivers/list"})
    [receiver] = msg["result"]["receivers"]
    assert receiver["entry_id"] == entry.entry_id
    assert receiver["areas"] == [area.id]


async def test_set_enabled_unknown_receiver(
    hass: HomeAssistant, hass_ws_client
) -> None:
    """An unknown receiver is a not_found error."""
    await _setup(hass)
    msg = await _call(
        await hass_ws_client(hass),
        {
            "type": "com_system/receivers/set_enabled",
            "entry_id": "missing",
            "enabled": False,
        },
    )
    assert not msg["success"]
    assert msg["error"]["code"] == "not_found"


async def test_unloaded_and_unknown_type_receivers_are_listed(
    hass: HomeAssistant, hass_ws_client
) -> None:
    """A receiver that is not loaded or has an unknown type stays listed."""
    await _setup(hass)
    unloaded = await _add_custom(hass, "Office")
    await hass.config_entries.async_unload(unloaded.entry_id)
    unknown = MockConfigEntry(
        domain=DOMAIN,
        title="Mystery",
        data={
            CONF_ENTRY_TYPE: ENTRY_TYPE_RECEIVER,
            CONF_RECEIVER_TYPE: "gone",
            CONF_NAME: "Mystery",
        },
    )
    unknown.add_to_hass(hass)

    client = await hass_ws_client(hass)
    msg = await _call(client, {"type": "com_system/receivers/list"})
    by_name = {r["name"]: r for r in msg["result"]["receivers"]}
    assert by_name["Office"]["available"] is False
    assert by_name["Mystery"]["available"] is False
    assert by_name["Mystery"]["type"] == "gone"
    assert by_name["Mystery"]["type_known"] is False
    assert by_name["Mystery"]["enabled"] is None

    msg = await _call(client, {"type": "com_system/dashboard"})
    assert msg["result"]["total"] == 2
    assert msg["result"]["unavailable"] == 2


async def test_source_gone_is_unavailable(hass: HomeAssistant, hass_ws_client) -> None:
    """A receiver whose source device was removed is shown unavailable."""
    source = MockConfigEntry(domain="mobile_app", title="Pixel")
    source.add_to_hass(hass)
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=source.entry_id,
        identifiers={("mobile_app", "abc")},
        name="Pixel",
    )
    await _setup(hass)
    phone = MockConfigEntry(
        domain=DOMAIN,
        title="Pixel",
        data={
            CONF_ENTRY_TYPE: ENTRY_TYPE_RECEIVER,
            CONF_RECEIVER_TYPE: RECEIVER_TYPE_MOBILE_APP,
            CONF_SOURCE_ID: "abc",
            CONF_NAME: "Pixel",
        },
    )
    phone.add_to_hass(hass)
    await hass.config_entries.async_setup(phone.entry_id)
    await hass.async_block_till_done()

    client = await hass_ws_client(hass)
    msg = await _call(client, {"type": "com_system/receivers/list"})
    assert msg["result"]["receivers"][0]["available"] is True

    dr.async_get(hass).async_remove_device(device.id)
    msg = await _call(client, {"type": "com_system/receivers/list"})
    assert msg["result"]["receivers"][0]["available"] is False


async def test_pending_discoveries(hass: HomeAssistant, hass_ws_client) -> None:
    """Detected sources appear as pending discoveries until added."""
    source = MockConfigEntry(domain="mobile_app", title="Pixel")
    source.add_to_hass(hass)
    dr.async_get(hass).async_get_or_create(
        config_entry_id=source.entry_id,
        identifiers={("mobile_app", "abc")},
        name="Pixel",
    )
    hub = await _setup(hass)
    await hub.runtime_data.async_detect()
    await hass.async_block_till_done()

    client = await hass_ws_client(hass)
    msg = await _call(client, {"type": "com_system/discoveries/list"})
    names = {(d["name"], d["type"]) for d in msg["result"]["discoveries"]}
    assert ("Pixel", "Mobile app") in names
    assert all(d["flow_id"] for d in msg["result"]["discoveries"])

    msg = await _call(client, {"type": "com_system/dashboard"})
    assert msg["result"]["pending_discoveries"] == len(names)


async def test_notify_preview_and_test(hass: HomeAssistant, hass_ws_client) -> None:
    """Preview resolves without sending; test goes through the action."""
    await _setup(hass)
    on = await _add_custom(hass, "Alpha")
    off = await _add_custom(hass, "Beta")
    await hass.services.async_call(
        "switch",
        "turn_off",
        {"entity_id": "switch.beta_notifications_enabled"},
        blocking=True,
    )
    client = await hass_ws_client(hass)
    targets = {
        "receivers": {
            "active_choice": "Select",
            "Select": {
                "entity_id": [
                    "notification_receiver.alpha",
                    "notification_receiver.beta",
                ]
            },
        }
    }

    msg = await _call(client, {"type": "com_system/notify/preview", **targets})
    assert msg["result"]["receivers"] == [
        {
            "entry_id": on.entry_id,
            "name": "Alpha",
            "type": "Script",
            "outcome": "reached",
            "reason": None,
        },
        {
            "entry_id": off.entry_id,
            "name": "Beta",
            "type": "Script",
            "outcome": "skipped",
            "reason": "Receiver is disabled",
        },
    ]

    msg = await _call(
        client, {"type": "com_system/notify/test", "message": "hi", **targets}
    )
    assert msg["success"]
    # Alpha's script runs; Beta is skipped.
    assert msg["result"]["counts"] == {"delivered": 1, "failed": 0, "skipped": 1}

    msg = await _call(client, {"type": "com_system/notify/test", "message": "hi"})
    assert not msg["success"]
    assert msg["error"]["code"] == "send_failed"


async def test_notify_preview_people_choice(
    hass: HomeAssistant, hass_ws_client
) -> None:
    """Preview takes the people choice, or a plain list."""
    await _setup(hass)
    entry = await _add_custom(hass, "Alpha")
    hass.config_entries.async_update_entry(entry, options={"people": ["person.a"]})
    await hass.async_block_till_done()
    client = await hass_ws_client(hass)

    for person in (
        {"active_choice": "Everyone", "Everyone": True},
        {"active_choice": "Individuals", "Individuals": ["person.a"]},
        ["person.a"],
    ):
        msg = await _call(
            client, {"type": "com_system/notify/preview", "people": person}
        )
        assert [r["name"] for r in msg["result"]["receivers"]] == ["Alpha"], person

    msg = await _call(
        client, {"type": "com_system/notify/preview", "people": {"active_choice": "x"}}
    )
    assert not msg["success"]
