"""Tests for the notification action received trigger."""

import pytest
import voluptuous as vol

from custom_components.com_system.const import DOMAIN, EVENT_ACTION
from custom_components.com_system.trigger import ActionReceivedTrigger
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.setup import async_setup_component


async def _automation(hass: HomeAssistant, options: dict) -> list[ServiceCall]:
    calls: list[ServiceCall] = []
    hass.services.async_register("test", "seen", calls.append)
    assert await async_setup_component(hass, DOMAIN, {})
    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": {
                "trigger": {"trigger": f"{DOMAIN}.action_received", "options": options},
                "action": {
                    "action": "test.seen",
                    "data": {
                        "action": "{{ trigger.action }}",
                        "tag": "{{ trigger.tag }}",
                    },
                },
            }
        },
    )
    await hass.async_block_till_done()
    return calls


def _fire(hass: HomeAssistant, **data) -> None:
    base = {"notification_id": "n1", "tag": "door", "action": "OPEN"}
    hass.bus.async_fire(EVENT_ACTION, {**base, **data})


async def test_fires_for_action_and_tag(hass: HomeAssistant) -> None:
    """The action and the tag must both match."""
    calls = await _automation(hass, {"action": "OPEN", "tag": "door"})
    _fire(hass, action="SHUT")
    _fire(hass, tag="other")
    await hass.async_block_till_done()
    assert not calls
    _fire(hass)
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0].data == {"action": "OPEN", "tag": "door"}


async def test_fires_for_action_and_notification_id(hass: HomeAssistant) -> None:
    """A notification id narrows it to one notification."""
    calls = await _automation(hass, {"action": "OPEN", "notification_id": "n1"})
    _fire(hass, notification_id="n2")
    await hass.async_block_till_done()
    assert not calls
    _fire(hass)
    await hass.async_block_till_done()
    assert len(calls) == 1


async def test_both_given_must_both_match(hass: HomeAssistant) -> None:
    """With a notification id and a tag, both must match."""
    calls = await _automation(
        hass, {"action": "OPEN", "notification_id": "n1", "tag": "door"}
    )
    _fire(hass, tag="other")
    await hass.async_block_till_done()
    assert not calls
    _fire(hass)
    await hass.async_block_till_done()
    assert len(calls) == 1


@pytest.mark.parametrize(
    "options",
    [
        {"action": "OPEN"},  # neither notification id nor tag
        {"action": "OPEN", "tag": ""},
        {"tag": "door"},  # no action
        {"action": "", "tag": "door"},
    ],
)
async def test_invalid_options_rejected(hass: HomeAssistant, options: dict) -> None:
    """The action is required, with a notification id or a tag."""
    with pytest.raises(vol.Invalid):
        await ActionReceivedTrigger.async_validate_config(hass, {"options": options})


async def test_missing_notification_id_and_tag_message(hass: HomeAssistant) -> None:
    """The error says what is needed."""
    with pytest.raises(vol.Invalid, match="require either a notification Id or a tag"):
        await ActionReceivedTrigger.async_validate_config(
            hass, {"options": {"action": "OPEN"}}
        )


def test_every_trigger_has_an_icon() -> None:
    """Each trigger has an entry in icons.json."""
    import json
    from pathlib import Path

    from custom_components.com_system.trigger import TRIGGERS

    icons = json.loads(
        (
            Path(__file__).parent.parent / "custom_components/com_system/icons.json"
        ).read_text()
    )
    assert set(icons["triggers"]) == set(TRIGGERS)
