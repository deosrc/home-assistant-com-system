"""Tests for the notification history store."""

from datetime import timedelta

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.com_system.const import (
    CONF_ENTRY_TYPE,
    CONF_HISTORY_MAX_AGE_DAYS,
    CONF_HISTORY_MAX_COUNT,
    DATA_HISTORY,
    DOMAIN,
    ENTRY_TYPE_HUB,
)
from custom_components.com_system.notify import async_send
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from .test_panel import _add_custom, _call


async def _setup(hass: HomeAssistant, options: dict | None = None) -> MockConfigEntry:
    hub = MockConfigEntry(
        domain=DOMAIN, data={CONF_ENTRY_TYPE: ENTRY_TYPE_HUB}, options=options or {}
    )
    hub.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()
    return hub


async def _send(hass: HomeAssistant, message: str) -> None:
    await async_send(
        hass,
        {
            "message": message,
            "receivers": {
                "active_choice": "Select",
                "Select": {"entity_id": ["notification_receiver.office"]},
            },
        },
    )


async def test_records_notification_and_results(hass: HomeAssistant) -> None:
    """A send is recorded with its content and each receiver's result."""
    await _setup(hass)
    entry = await _add_custom(hass, "Office")
    await _send(hass, "hello")
    history = hass.data[DOMAIN][DATA_HISTORY]
    [record] = await history.async_list()
    assert record["notification"]["message"] == "hello"
    [result] = [r for r in record["results"] if r["entry_id"] == entry.entry_id]
    assert result["result"] in ("delivered", "failed")
    last = await history.async_last_attempt(entry.entry_id)
    assert last["notification"]["message"] == "hello"
    assert await history.async_last_attempt("missing") is None


async def test_capped_by_count_read_at_use_time(hass: HomeAssistant) -> None:
    """Changing the hub's option applies without reloading anything."""
    hub = await _setup(hass, {CONF_HISTORY_MAX_COUNT: 2})
    await _add_custom(hass, "Office")
    for i in range(3):
        await _send(hass, f"m{i}")
    history = hass.data[DOMAIN][DATA_HISTORY]
    records = await history.async_list()
    assert [r["notification"]["message"] for r in records] == ["m2", "m1"]
    hass.config_entries.async_update_entry(hub, options={CONF_HISTORY_MAX_COUNT: 1})
    assert len(await history.async_list()) == 1


async def test_capped_by_age(hass: HomeAssistant) -> None:
    """Records older than the age limit are dropped."""
    await _setup(hass, {CONF_HISTORY_MAX_AGE_DAYS: 1})
    await _add_custom(hass, "Office")
    await _send(hass, "old")
    history = hass.data[DOMAIN][DATA_HISTORY]
    [record] = await history.async_list()
    record["time"] = (dt_util.utcnow() - timedelta(days=2)).isoformat()
    assert await history.async_list() == []


async def test_defaults_without_options(hass: HomeAssistant) -> None:
    """The defaults apply when the hub has no options."""
    await _setup(hass)
    assert hass.data[DOMAIN][DATA_HISTORY].limits() == (200, 30)


async def test_history_websocket(hass: HomeAssistant, hass_ws_client) -> None:
    """The websocket returns recent notifications, newest first."""
    await _setup(hass)
    await _add_custom(hass, "Office")
    await _send(hass, "a")
    await _send(hass, "b")
    client = await hass_ws_client(hass)
    msg = await _call(client, {"type": "com_system/history/list", "limit": 1})
    assert [n["notification"]["message"] for n in msg["result"]["notifications"]] == [
        "b"
    ]


async def test_hub_options_flow_sets_limits(hass: HomeAssistant) -> None:
    """The hub's options flow stores the limits."""
    hub = await _setup(hass)
    result = await hass.config_entries.options.async_init(hub.entry_id)
    assert result["step_id"] == "init"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_HISTORY_MAX_COUNT: 50, CONF_HISTORY_MAX_AGE_DAYS: 7},
    )
    assert hub.options == {CONF_HISTORY_MAX_COUNT: 50, CONF_HISTORY_MAX_AGE_DAYS: 7}
    assert hass.data[DOMAIN][DATA_HISTORY].limits() == (50, 7)
