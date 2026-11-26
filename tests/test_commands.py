"""Tests for commands (``com_system.clear_notification``)."""

import pytest
import voluptuous as vol
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
    RECEIVER_TYPE_CUSTOM,
    RECEIVER_TYPE_MOBILE_APP,
    RECEIVER_TYPE_PERSISTENT_NOTIFICATION,
)
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component


async def _setup(hass: HomeAssistant, os_name: str = "Android"):
    """A hub, a mobile app receiver and a persistent notification receiver."""
    MockConfigEntry(domain=DOMAIN, data={CONF_ENTRY_TYPE: ENTRY_TYPE_HUB}).add_to_hass(
        hass
    )
    MockConfigEntry(
        domain="mobile_app",
        title="Pixel",
        data={"device_id": "abc", "device_name": "Pixel", "os_name": os_name},
    ).add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, {})
    entries = []
    for receiver_type, source_id, name in (
        (RECEIVER_TYPE_MOBILE_APP, "abc", "Pixel"),
        (RECEIVER_TYPE_PERSISTENT_NOTIFICATION, None, "Persistent"),
    ):
        data = {
            CONF_ENTRY_TYPE: ENTRY_TYPE_RECEIVER,
            CONF_RECEIVER_TYPE: receiver_type,
            CONF_NAME: name,
        }
        if source_id:
            data[CONF_SOURCE_ID] = source_id
        entry = MockConfigEntry(
            domain=DOMAIN, title=name, data=data, options={CONF_PEOPLE: []}
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        entries.append(entry)
    await hass.async_block_till_done()
    calls: list[ServiceCall] = []
    hass.services.async_register("notify", "mobile_app_pixel", calls.append)
    return entries, calls


def _target(hass: HomeAssistant, *entries) -> dict:
    registry = er.async_get(hass)
    ids = [
        e.entity_id
        for entry in entries
        for e in er.async_entries_for_config_entry(registry, entry.entry_id)
        if e.domain == "notification_receiver"
    ]
    return {"active_choice": "Select", "Select": {"entity_id": ids}}


async def _clear(hass: HomeAssistant, data: dict):
    return await hass.services.async_call(
        DOMAIN, "clear_notification", data, blocking=True, return_response=True
    )


async def test_clear_notification_sends_app_command(hass: HomeAssistant) -> None:
    (mobile, _), calls = await _setup(hass)
    response = await _clear(hass, {"tag": "door", "receivers": _target(hass, mobile)})
    assert len(calls) == 1
    assert calls[0].data == {
        "message": "clear_notification",
        "data": {"tag": "door"},
    }
    assert response["counts"] == {"delivered": 1, "failed": 0, "skipped": 0}


async def test_clear_notification_works_on_ios(hass: HomeAssistant) -> None:
    (mobile, _), calls = await _setup(hass, os_name="iOS")
    await _clear(hass, {"tag": "door", "receivers": _target(hass, mobile)})
    assert len(calls) == 1


async def test_clear_notification_dismisses_persistent(hass: HomeAssistant) -> None:
    (_, persistent), _ = await _setup(hass)
    dismissed: list[ServiceCall] = []
    hass.services.async_register("persistent_notification", "dismiss", dismissed.append)
    response = await _clear(
        hass, {"tag": "door", "receivers": _target(hass, persistent)}
    )
    assert dismissed[0].data == {"notification_id": "com_system_tag_door"}
    assert response["counts"]["delivered"] == 1


async def test_unsupported_receiver_is_skipped(hass: HomeAssistant) -> None:
    (mobile, _), calls = await _setup(hass)
    script = MockConfigEntry(
        domain=DOMAIN,
        title="Script",
        data={
            CONF_ENTRY_TYPE: ENTRY_TYPE_RECEIVER,
            CONF_RECEIVER_TYPE: RECEIVER_TYPE_CUSTOM,
            CONF_SOURCE_ID: "notify_me",
            CONF_NAME: "Script",
        },
    )
    script.add_to_hass(hass)
    await hass.config_entries.async_setup(script.entry_id)
    await hass.async_block_till_done()
    response = await _clear(
        hass, {"tag": "door", "receivers": _target(hass, mobile, script)}
    )
    assert len(calls) == 1
    by_name = {r["name"]: r for r in response["results"]}
    assert by_name["Pixel"]["result"] == "delivered"
    assert by_name["Script"]["result"] == "skipped"
    assert "does not support" in by_name["Script"]["reason"]


async def test_missing_notify_action_fails_the_receiver(hass: HomeAssistant) -> None:
    (mobile, _), _ = await _setup(hass)
    hass.services.async_remove("notify", "mobile_app_pixel")
    response = await _clear(hass, {"tag": "door", "receivers": _target(hass, mobile)})
    assert response["counts"]["failed"] == 1


async def test_requires_targets_and_tag(hass: HomeAssistant) -> None:
    (mobile, _), _ = await _setup(hass)
    with pytest.raises(ServiceValidationError):
        await _clear(hass, {"tag": "door"})
    with pytest.raises(vol.Invalid):
        await _clear(hass, {"receivers": _target(hass, mobile)})


async def test_no_match_is_not_an_error(hass: HomeAssistant) -> None:
    """Targets that match no receiver give an empty response."""
    await _setup(hass)
    response = await _clear(
        hass,
        {
            "tag": "door",
            "receivers": {"entity_id": ["notification_receiver.nope"]},
        },
    )
    assert response["results"] == []
    assert response["counts"] == {"delivered": 0, "failed": 0, "skipped": 0}


async def test_commands_are_not_recorded_in_history(hass: HomeAssistant) -> None:
    from custom_components.com_system.const import DATA_HISTORY

    (mobile, _), _ = await _setup(hass)
    await _clear(hass, {"tag": "door", "receivers": _target(hass, mobile)})
    assert not await hass.data[DOMAIN][DATA_HISTORY].async_list()


def test_every_command_is_described() -> None:
    """Each command has fields in services.yaml, strings and an icon."""
    import json
    from pathlib import Path

    import yaml

    from custom_components.com_system.commands import COMMANDS

    root = Path(__file__).parent.parent / "custom_components" / "com_system"
    services = yaml.safe_load((root / "services.yaml").read_text())
    strings = json.loads((root / "strings.json").read_text())
    translations = json.loads((root / "translations" / "en.json").read_text())
    icons = json.loads((root / "icons.json").read_text())
    for command in COMMANDS.values():
        fields = set(services[command.command_id]["fields"])
        assert fields == {"people", "receivers"} | {str(k) for k in command.schema}
        for texts in (strings, translations):
            assert set(texts["services"][command.command_id]["fields"]) == fields
        assert command.command_id in icons["services"]
