"""Tests for the receiver entities: enabled switch and receiver entity."""

from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    mock_restore_cache,
)

from custom_components.com_system.const import (
    CONF_ENTRY_TYPE,
    CONF_NAME,
    CONF_PEOPLE,
    DATA_ENTITIES,
    DOMAIN,
    ENTRY_TYPE_CUSTOM_RECEIVER,
    ENTRY_TYPE_HUB,
    RESULT_FAILED,
)
from custom_components.com_system.receiver_type import (
    CustomReceiverType,
    register_receiver_type,
    unregister_receiver_type,
)
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

SWITCH = "switch.office_enabled"
RECEIVER = "notification_receiver.office"


def _entry(**options) -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        title="Office",
        data={CONF_ENTRY_TYPE: ENTRY_TYPE_CUSTOM_RECEIVER, CONF_NAME: "Office"},
        options=options,
    )


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def test_entities_share_the_receiver_device(hass: HomeAssistant) -> None:
    """Both entities are created and grouped on one device."""
    entry = _entry()
    await _setup(hass, entry)
    ent_reg = er.async_get(hass)
    switch = ent_reg.async_get(SWITCH)
    receiver = ent_reg.async_get(RECEIVER)
    assert switch and receiver
    assert switch.device_id == receiver.device_id is not None
    device = dr.async_get(hass).async_get(switch.device_id)
    assert device.name == "Office"
    assert hass.states.get(SWITCH).state == STATE_ON
    assert hass.states.get(RECEIVER).state == STATE_UNKNOWN


async def test_hub_creates_no_entities(hass: HomeAssistant) -> None:
    """The hub entry has no entities."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_ENTRY_TYPE: ENTRY_TYPE_HUB})
    await _setup(hass, entry)
    assert er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id) == []


async def test_switch_toggles_with_standard_actions(hass: HomeAssistant) -> None:
    """The enabled switch uses the standard switch actions."""
    await _setup(hass, _entry())
    for service, state in (
        ("turn_off", STATE_OFF),
        ("turn_on", STATE_ON),
        ("toggle", STATE_OFF),
    ):
        await hass.services.async_call(
            "switch", service, {"entity_id": SWITCH}, blocking=True
        )
        assert hass.states.get(SWITCH).state == state


async def test_switch_state_is_restored(hass: HomeAssistant) -> None:
    """A disabled receiver stays disabled after a restart."""
    mock_restore_cache(hass, [State(SWITCH, STATE_OFF)])
    await _setup(hass, _entry())
    assert hass.states.get(SWITCH).state == STATE_OFF


async def test_receiver_entity_records_attempts(hass: HomeAssistant) -> None:
    """The receiver entity shows the last attempt's time, result and content."""
    entry = _entry(**{CONF_PEOPLE: ["person.alex"]})
    await _setup(hass, entry)
    area = ar.async_get(hass).async_create("Office")
    device_id = er.async_get(hass).async_get(SWITCH).device_id
    dr.async_get(hass).async_update_device(device_id, area_id=area.id)
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    state = hass.states.get(RECEIVER)
    assert state.attributes["receiver_type"] == "custom"
    assert state.attributes["people"] == ["person.alex"]
    assert state.attributes["areas"] == [area.id]
    assert state.attributes["event_types"] == ["delivered", "failed", "skipped"]

    entity = hass.data[DOMAIN][DATA_ENTITIES][entry.entry_id]["receiver"]
    entity.async_record_attempt(
        RESULT_FAILED,
        {"title": "Hi", "message": "Door open", "priority": "high", "other": 1},
        ["Dropped actions"],
    )
    state = hass.states.get(RECEIVER)
    assert state.state != STATE_UNKNOWN
    assert state.attributes["event_type"] == "failed"
    assert state.attributes["title"] == "Hi"
    assert state.attributes["message"] == "Door open"
    assert state.attributes["priority"] == "high"
    assert "other" not in state.attributes
    assert state.attributes["warnings"] == ["Dropped actions"]


async def test_receiver_entity_has_no_actions(hass: HomeAssistant) -> None:
    """The new domain registers no services."""
    await _setup(hass, _entry())
    assert not hass.services.has_service("notification_receiver", "turn_on")
    assert "notification_receiver" not in hass.services.async_services()


async def test_unload_removes_entities_from_lookup(hass: HomeAssistant) -> None:
    """Unloading a receiver unloads both entities."""
    entry = _entry()
    await _setup(hass, entry)
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(SWITCH).state == "unavailable"
    assert hass.states.get(RECEIVER).state == "unavailable"
    assert entry.entry_id not in hass.data[DOMAIN][DATA_ENTITIES]


async def test_attaches_to_source_device(hass: HomeAssistant) -> None:
    """A type with a source device puts the entities on that device."""

    class TvType(CustomReceiverType):
        type_id = "tv"
        name = "TV"

        def source_device_identifiers(self, receiver):
            return {("webostv", receiver.source_id)}

    register_receiver_type(TvType())
    try:
        other = MockConfigEntry(domain="webostv")
        other.add_to_hass(hass)
        device = dr.async_get(hass).async_get_or_create(
            config_entry_id=other.entry_id,
            identifiers={("webostv", "tv1")},
            name="Living room TV",
        )
        entry = MockConfigEntry(
            domain=DOMAIN,
            title="TV",
            data={
                CONF_ENTRY_TYPE: ENTRY_TYPE_CUSTOM_RECEIVER,
                CONF_NAME: "TV",
                "receiver_type": "tv",
                "source_id": "tv1",
            },
        )
        await _setup(hass, entry)
        ent_reg = er.async_get(hass)
        entities = er.async_entries_for_config_entry(ent_reg, entry.entry_id)
        assert len(entities) == 2
        assert {e.device_id for e in entities} == {device.id}
    finally:
        unregister_receiver_type("tv")
