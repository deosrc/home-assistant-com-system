"""Tests for automatic receiver detection and discovery flows."""

from unittest.mock import patch

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.com_system.const import (
    CONF_ENTRY_TYPE,
    CONF_NAME,
    CONF_RECEIVER_TYPE,
    CONF_SOURCE_ID,
    DOMAIN,
    ENTRY_TYPE_HUB,
    ENTRY_TYPE_RECEIVER,
    RECEIVER_TYPE_MOBILE_APP,
    RECEIVER_TYPE_PERSISTENT_NOTIFICATION,
    RECEIVER_TYPE_PUSHOVER,
)
from custom_components.com_system.detection import ReceiverDetector
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component


async def _setup_hub(hass: HomeAssistant) -> MockConfigEntry:
    hub = MockConfigEntry(domain=DOMAIN, data={CONF_ENTRY_TYPE: ENTRY_TYPE_HUB})
    hub.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()
    return hub


def _add_device(hass: HomeAssistant, domain: str, device_id: str, name: str):
    source = MockConfigEntry(domain=domain, title=name)
    source.add_to_hass(hass)
    return dr.async_get(hass).async_get_or_create(
        config_entry_id=source.entry_id,
        identifiers={(domain, device_id)},
        name=name,
    )


def _add_phone(hass: HomeAssistant, device_id: str, name: str):
    return _add_device(hass, "mobile_app", device_id, name)


def _flows(hass: HomeAssistant) -> dict[str, dict]:
    return {
        f["context"]["unique_id"]: f for f in hass.config_entries.flow.async_progress()
    }


async def test_hub_offers_discoveries(hass: HomeAssistant) -> None:
    """Each source device and the persistent notification are offered once."""
    _add_phone(hass, "abc", "Pixel")
    _add_phone(hass, "def", "iPhone")
    other = MockConfigEntry(domain="mobile_app")
    other.add_to_hass(hass)
    hub = await _setup_hub(hass)

    flows = _flows(hass)
    assert set(flows) == {
        "mobile_app_abc",
        "mobile_app_def",
        "persistent_notification_persistent_notification",
    }

    # Detecting again does not duplicate pending flows.
    await hub.runtime_data.async_detect()
    await hass.async_block_till_done()
    assert len(hass.config_entries.flow.async_progress()) == 3


async def test_nothing_offered_without_sources(hass: HomeAssistant) -> None:
    """Only the always-present persistent notification receiver is offered."""
    await _setup_hub(hass)
    assert set(_flows(hass)) == {"persistent_notification_persistent_notification"}


async def test_unimplemented_types_not_offered(hass: HomeAssistant) -> None:
    """Types without delivery yet are not offered, even with sources present."""
    MockConfigEntry(domain="pushover", title="Phone", unique_id="user1").add_to_hass(
        hass
    )
    _add_device(hass, "music_assistant", "player1", "Player")
    await _setup_hub(hass)
    assert set(_flows(hass)) == {"persistent_notification_persistent_notification"}


async def test_disabled_device_not_offered(hass: HomeAssistant) -> None:
    """A disabled source device is not offered."""
    device = _add_phone(hass, "p1", "Phone")
    _add_phone(hass, "p2", "Other")
    dr.async_get(hass).async_update_device(
        device.id, disabled_by=dr.DeviceEntryDisabler.USER
    )
    await _setup_hub(hass)
    flows = _flows(hass)
    assert f"{RECEIVER_TYPE_MOBILE_APP}_p1" not in flows
    assert f"{RECEIVER_TYPE_MOBILE_APP}_p2" in flows


async def test_disabled_source_entry_not_offered(hass: HomeAssistant) -> None:
    """A disabled source config entry is not offered."""
    MockConfigEntry(
        domain="webostv",
        title="TV",
        unique_id="tv1",
        disabled_by=config_entries.ConfigEntryDisabler.USER,
    ).add_to_hass(hass)
    await _setup_hub(hass)
    assert "webostv_tv1" not in _flows(hass)


async def test_webostv_offered(hass: HomeAssistant) -> None:
    """A webOS TV config entry is offered as a receiver."""
    MockConfigEntry(domain="webostv", title="TV", unique_id="tv1").add_to_hass(hass)
    await _setup_hub(hass)
    assert "webostv_tv1" in _flows(hass)


async def test_confirm_creates_enabled_receiver(hass: HomeAssistant) -> None:
    """Confirming a discovery creates the receiver entry for the device."""
    _add_phone(hass, "abc", "Pixel")
    await _setup_hub(hass)
    flow = _flows(hass)["mobile_app_abc"]
    assert flow["step_id"] == "confirm"

    result = await hass.config_entries.flow.async_configure(flow["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Pixel"
    assert result["data"] == {
        CONF_ENTRY_TYPE: ENTRY_TYPE_RECEIVER,
        CONF_RECEIVER_TYPE: RECEIVER_TYPE_MOBILE_APP,
        CONF_SOURCE_ID: "abc",
        CONF_NAME: "Pixel",
    }
    registry = hass.data[DOMAIN]["registry"]
    assert [r.source_id for r in registry.all()] == ["abc"]
    assert "mobile_app_abc" not in _flows(hass)


async def test_ignored_is_not_offered_again(hass: HomeAssistant) -> None:
    """An ignored discovery stays ignored on later detection."""
    _add_phone(hass, "abc", "Pixel")
    hub = await _setup_hub(hass)
    flow = _flows(hass)["mobile_app_abc"]
    # What the Ignore button does: an ignore flow for the same unique id.
    await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IGNORE},
        data={"unique_id": flow["context"]["unique_id"], "title": "Pixel"},
    )
    await hass.async_block_till_done()
    assert "mobile_app_abc" not in _flows(hass)

    await hub.runtime_data.async_detect()
    await hass.async_block_till_done()
    assert "mobile_app_abc" not in _flows(hass)
    assert hass.data[DOMAIN]["registry"].all() == []


async def test_deleted_receiver_is_offered_again(hass: HomeAssistant) -> None:
    """Deleting a receiver makes the next detection offer it again."""
    _add_phone(hass, "abc", "Pixel")
    hub = await _setup_hub(hass)
    flow = _flows(hass)["mobile_app_abc"]
    await hass.config_entries.flow.async_configure(flow["flow_id"], {})
    await hass.async_block_till_done()
    receiver = hass.data[DOMAIN]["registry"].all()[0]

    await hass.config_entries.async_remove(receiver.entry_id)
    await hub.runtime_data.async_detect()
    await hass.async_block_till_done()
    assert "mobile_app_abc" in _flows(hass)


async def test_removed_source_keeps_receiver(hass: HomeAssistant) -> None:
    """A receiver whose source is gone is kept and reported unavailable."""
    device = _add_phone(hass, "abc", "Pixel")
    hub = await _setup_hub(hass)
    flow = _flows(hass)["mobile_app_abc"]
    await hass.config_entries.flow.async_configure(flow["flow_id"], {})
    await hass.async_block_till_done()
    registry = hass.data[DOMAIN]["registry"]
    receiver = registry.all()[0]
    receiver_type = registry.type_of(receiver)
    assert receiver_type.is_source_available(hass, receiver)

    dr.async_get(hass).async_remove_device(device.id)
    await hub.runtime_data.async_detect()
    await hass.async_block_till_done()
    assert [r.source_id for r in registry.all()] == ["abc"]
    assert not receiver_type.is_source_available(hass, receiver)
    assert "mobile_app_abc" not in _flows(hass)


async def test_returned_source_reloads_receiver(hass: HomeAssistant) -> None:
    """A receiver is reloaded when its source device comes back."""
    device = _add_phone(hass, "abc", "Pixel")
    hub = await _setup_hub(hass)
    flow = _flows(hass)["mobile_app_abc"]
    await hass.config_entries.flow.async_configure(flow["flow_id"], {})
    await hass.async_block_till_done()
    entry_id = hass.data[DOMAIN]["registry"].all()[0].entry_id
    detector: ReceiverDetector = hub.runtime_data
    await detector.async_detect()

    dr.async_get(hass).async_remove_device(device.id)
    await detector.async_detect()
    with patch.object(hass.config_entries, "async_reload") as reload:
        await detector.async_detect()
        reload.assert_not_called()
        _add_phone(hass, "abc", "Pixel")
        await detector.async_detect()
        reload.assert_called_once_with(entry_id)


async def test_persistent_notification_receiver(hass: HomeAssistant) -> None:
    """The persistent notification receiver is always available."""
    await _setup_hub(hass)
    flow = _flows(hass)["persistent_notification_persistent_notification"]
    result = await hass.config_entries.flow.async_configure(flow["flow_id"], {})
    assert result["data"][CONF_RECEIVER_TYPE] == RECEIVER_TYPE_PERSISTENT_NOTIFICATION
    registry = hass.data[DOMAIN]["registry"]
    receiver = registry.all()[0]
    assert registry.type_of(receiver).is_source_available(hass, receiver)


async def test_discovery_without_hub_aborts(hass: HomeAssistant) -> None:
    """A discovery is refused when there is no hub."""
    assert await async_setup_component(hass, DOMAIN, {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_INTEGRATION_DISCOVERY},
        data={
            "receiver_type": RECEIVER_TYPE_PUSHOVER,
            CONF_SOURCE_ID: "x",
            CONF_NAME: "x",
        },
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_available"


async def test_receiver_entities_attach_to_source_device(
    hass: HomeAssistant,
) -> None:
    """A mobile app receiver's entities share the phone's own device."""
    device = _add_phone(hass, "abc", "Pixel")
    await _setup_hub(hass)
    flow = _flows(hass)["mobile_app_abc"]
    result = await hass.config_entries.flow.async_configure(flow["flow_id"], {})
    await hass.async_block_till_done()

    entities = er.async_entries_for_config_entry(
        er.async_get(hass), result["result"].entry_id
    )
    assert entities
    assert {e.device_id for e in entities} == {device.id}
