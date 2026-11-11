"""Tests for Alexa Media Player receivers."""

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.com_system.const import (
    CONF_ENTRY_TYPE,
    CONF_NAME,
    CONF_RECEIVER_TYPE,
    CONF_SOURCE_ID,
    DOMAIN,
    ENTRY_TYPE_HUB,
    ENTRY_TYPE_RECEIVER,
    RECEIVER_TYPE_ALEXA_MEDIA,
)
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component


async def _setup(hass: HomeAssistant) -> MockConfigEntry:
    MockConfigEntry(domain=DOMAIN, data={CONF_ENTRY_TYPE: ENTRY_TYPE_HUB}).add_to_hass(
        hass
    )
    assert await async_setup_component(hass, DOMAIN, {})
    source = MockConfigEntry(domain="alexa_media", title="Account")
    source.add_to_hass(hass)
    dr.async_get(hass).async_get_or_create(
        config_entry_id=source.entry_id,
        identifiers={("alexa_media", "G090XX")},
        name="Kitchen Echo",
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Kitchen Echo",
        data={
            CONF_ENTRY_TYPE: ENTRY_TYPE_RECEIVER,
            CONF_RECEIVER_TYPE: RECEIVER_TYPE_ALEXA_MEDIA,
            CONF_SOURCE_ID: "G090XX",
            CONF_NAME: "Kitchen Echo",
        },
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def _deliver(hass: HomeAssistant, entry: MockConfigEntry, notification: dict):
    registry = hass.data[DOMAIN]["registry"]
    receiver = registry.get(entry.entry_id)
    return registry.type_of(receiver).async_deliver(hass, receiver, notification)


async def test_offered_as_discovery(hass: HomeAssistant) -> None:
    """An Echo device without a receiver is offered (the test's has no id)."""
    await _setup(hass)
    hub = hass.config_entries.async_entries(DOMAIN)[0]
    await hub.runtime_data.async_detect()
    await hass.async_block_till_done()
    ids = {f["context"]["unique_id"] for f in hass.config_entries.flow.async_progress()}
    assert "alexa_media_G090XX" in ids
    assert "persistent_notification_persistent_notification" in ids


async def test_delivery_announces_to_device(hass: HomeAssistant) -> None:
    """The generic notify action is called with the serial as target."""
    entry = await _setup(hass)
    calls: list[ServiceCall] = []
    hass.services.async_register("notify", "alexa_media", calls.append)

    assert await _deliver(hass, entry, {"message": "Hi", "title": "T"}) == []
    assert calls[0].data == {
        "message": "Hi",
        "title": "T",
        "target": ["G090XX"],
        "data": {"type": "announce"},
    }
    await _deliver(hass, entry, {"message": "Only"})
    assert "title" not in calls[1].data


async def test_delivery_fails_without_integration(hass: HomeAssistant) -> None:
    """A missing notify action is a failure with a clear reason."""
    entry = await _setup(hass)
    with pytest.raises(HomeAssistantError, match=r"notify\.alexa_media"):
        await _deliver(hass, entry, {"message": "Hi"})


async def test_unavailable_when_device_removed(hass: HomeAssistant) -> None:
    """Removing the Echo device makes the receiver's source unavailable."""
    entry = await _setup(hass)
    registry = hass.data[DOMAIN]["registry"]
    receiver = registry.get(entry.entry_id)
    alexa = registry.type_of(receiver)
    assert alexa.is_source_available(hass, receiver)
    device_registry = dr.async_get(hass)
    [source] = hass.config_entries.async_entries("alexa_media")
    [device] = dr.async_entries_for_config_entry(device_registry, source.entry_id)
    device_registry.async_remove_device(device.id)
    assert not alexa.is_source_available(hass, receiver)
