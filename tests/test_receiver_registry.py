"""Tests for the receiver model, type definitions and registry."""

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.com_system.const import (
    CONF_AREAS,
    CONF_ENTRY_TYPE,
    CONF_NAME,
    CONF_PEOPLE,
    CONF_RECEIVER_TYPE,
    DOMAIN,
    ENTRY_TYPE_CUSTOM_RECEIVER,
    ENTRY_TYPE_HUB,
    RECEIVER_TYPE_CUSTOM,
)
from custom_components.com_system.receiver_type import (
    CustomReceiverType,
    ReceiverType,
    get_receiver_type,
    register_receiver_type,
    unregister_receiver_type,
)
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.setup import async_setup_component


def _receiver(name: str, **kwargs) -> MockConfigEntry:
    data = {CONF_ENTRY_TYPE: ENTRY_TYPE_CUSTOM_RECEIVER, CONF_NAME: name}
    data.update(kwargs.pop("data", {}))
    return MockConfigEntry(domain=DOMAIN, title=name, data=data, **kwargs)


async def _registry(hass: HomeAssistant):
    assert await async_setup_component(hass, DOMAIN, {})
    return hass.data[DOMAIN]["registry"]


async def test_registry_without_hub_and_any_order(hass: HomeAssistant) -> None:
    """Receivers are listed without a hub, whatever order entries exist in."""
    _receiver("B").add_to_hass(hass)
    MockConfigEntry(domain=DOMAIN, data={CONF_ENTRY_TYPE: ENTRY_TYPE_HUB}).add_to_hass(
        hass
    )
    _receiver("A").add_to_hass(hass)
    registry = await _registry(hass)
    assert sorted(r.name for r in registry.all()) == ["A", "B"]


async def test_registry_follows_entry_changes(hass: HomeAssistant) -> None:
    """Adding, updating and removing entries is reflected."""
    registry = await _registry(hass)
    assert registry.all() == []

    entry = _receiver("A")
    entry.add_to_hass(hass)
    assert registry.get(entry.entry_id).name == "A"

    hass.config_entries.async_update_entry(entry, options={CONF_PEOPLE: ["person.x"]})
    assert registry.get(entry.entry_id).people == ("person.x",)

    await hass.config_entries.async_remove(entry.entry_id)
    assert registry.get(entry.entry_id) is None


async def test_legacy_entry_is_custom(hass: HomeAssistant) -> None:
    """An entry with no stored type is a custom receiver."""
    entry = _receiver("Old")
    entry.add_to_hass(hass)
    registry = await _registry(hass)
    assert registry.get(entry.entry_id).type_id == RECEIVER_TYPE_CUSTOM


async def test_lookup_by_person_and_area(hass: HomeAssistant) -> None:
    """Receivers are found by their associations."""
    a = _receiver("A", options={CONF_PEOPLE: ["person.x"], CONF_AREAS: ["kitchen"]})
    b = _receiver("B", options={CONF_PEOPLE: ["person.y"]})
    a.add_to_hass(hass)
    b.add_to_hass(hass)
    registry = await _registry(hass)
    assert [r.entry_id for r in registry.by_person("person.x")] == [a.entry_id]
    assert [r.entry_id for r in registry.by_area("kitchen")] == [a.entry_id]
    assert registry.by_person("person.z") == []


async def test_unknown_type_is_kept(hass: HomeAssistant) -> None:
    """A receiver of an unregistered type stays listed with no type."""
    entry = _receiver("X", data={CONF_RECEIVER_TYPE: "nonexistent"})
    entry.add_to_hass(hass)
    registry = await _registry(hass)
    receiver = registry.get(entry.entry_id)
    assert receiver is not None
    assert registry.type_of(receiver) is None


def test_custom_type_declares_no_capabilities() -> None:
    """The generic type has no capabilities."""
    assert isinstance(get_receiver_type(RECEIVER_TYPE_CUSTOM), CustomReceiverType)
    assert get_receiver_type(RECEIVER_TYPE_CUSTOM).capabilities == frozenset()


def test_register_extra_type_and_reject_duplicate() -> None:
    """Types can be added; ids are unique."""

    class Extra(ReceiverType):
        type_id = "extra"
        name = "Extra"

    register_receiver_type(Extra())
    try:
        assert get_receiver_type("extra") is not None
        with pytest.raises(ValueError):
            register_receiver_type(Extra())
    finally:
        unregister_receiver_type("extra")


async def test_custom_receiver_flow_stores_type_and_options(
    hass: HomeAssistant,
) -> None:
    """The flow stores the type; the options flow saves people and areas."""
    MockConfigEntry(domain=DOMAIN, data={CONF_ENTRY_TYPE: ENTRY_TYPE_HUB}).add_to_hass(
        hass
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["step_id"] == "custom_receiver"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_NAME: "Lounge"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_RECEIVER_TYPE] == RECEIVER_TYPE_CUSTOM

    entry = result["result"]
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["step_id"] == "receiver"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_PEOPLE: ["person.x"], CONF_AREAS: ["kitchen"]}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == {CONF_PEOPLE: ["person.x"], CONF_AREAS: ["kitchen"]}
