"""Tests for target resolution."""

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.com_system.const import (
    CONF_ENTRY_TYPE,
    CONF_NAME,
    CONF_PEOPLE,
    CONF_RECEIVER_TYPE,
    DOMAIN,
    ENTRY_TYPE_CUSTOM_RECEIVER,
    ENTRY_TYPE_RECEIVER,
    RECEIVER_TYPE_PERSISTENT_NOTIFICATION,
)
from custom_components.com_system.targets import resolve_targets
from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component


async def _add(hass: HomeAssistant, name: str, people=(), area=None, **data):
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=name,
        data={CONF_ENTRY_TYPE: ENTRY_TYPE_CUSTOM_RECEIVER, CONF_NAME: name, **data},
        options={CONF_PEOPLE: list(people)},
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    if area:
        device = dr.async_get(hass).async_get_device_by_identifier(
            (DOMAIN, entry.entry_id), entry.entry_id
        )
        dr.async_get(hass).async_update_device(device.id, area_id=area)
    return entry


async def _setup(hass: HomeAssistant) -> dict:
    assert await async_setup_component(hass, DOMAIN, {})
    kitchen = ar.async_get(hass).async_create("Kitchen").id
    lounge = ar.async_get(hass).async_create("Lounge").id
    e = {
        "alice": await _add(hass, "Alice phone", ["person.alice"]),
        "bob": await _add(hass, "Bob phone", ["person.bob"]),
        "echo": await _add(hass, "Echo", area=kitchen),
        "both": await _add(hass, "Both", ["person.bob"], area=lounge),
        "shared": await _add(hass, "Shared tablet"),
        "kitchen": kitchen,
        "lounge": lounge,
    }
    persistent = MockConfigEntry(
        domain=DOMAIN,
        title="Persistent notification",
        data={
            CONF_ENTRY_TYPE: ENTRY_TYPE_RECEIVER,
            CONF_NAME: "Persistent notification",
            CONF_RECEIVER_TYPE: RECEIVER_TYPE_PERSISTENT_NOTIFICATION,
        },
    )
    persistent.add_to_hass(hass)
    await hass.config_entries.async_setup(persistent.entry_id)
    await hass.async_block_till_done()
    e["persistent"] = persistent
    return e


def _ids(receivers) -> set[str]:
    return {r.entry_id for r in receivers}


async def test_default_is_all_people_and_areas(hass: HomeAssistant) -> None:
    """With no targets, receivers with a person or area; not shared, not persistent."""
    e = await _setup(hass)
    result = resolve_targets(hass)
    assert _ids(result.receivers) == {
        e[k].entry_id for k in ("alice", "bob", "echo", "both")
    }
    assert result.skipped == ()


async def test_union_of_people_areas_and_receivers(hass: HomeAssistant) -> None:
    """A receiver matches any listed person, area or name."""
    e = await _setup(hass)
    result = resolve_targets(
        hass,
        people=["person.alice"],
        areas=[e["kitchen"]],
        receivers=[e["shared"].entry_id],
    )
    assert _ids(result.receivers) == {
        e[k].entry_id for k in ("alice", "echo", "shared")
    }


async def test_person_and_area_match_once(hass: HomeAssistant) -> None:
    """A receiver matching by person and by area appears once."""
    e = await _setup(hass)
    result = resolve_targets(hass, people=["person.bob"], areas=[e["lounge"]])
    assert [r.entry_id for r in result.receivers].count(e["both"].entry_id) == 1
    assert _ids(result.receivers) == {e["bob"].entry_id, e["both"].entry_id}


async def test_shared_receiver_not_reached_by_person_or_default(
    hass: HomeAssistant,
) -> None:
    """A receiver with no person or area is only reached by name."""
    e = await _setup(hass)
    assert e["shared"].entry_id not in _ids(resolve_targets(hass).receivers)
    assert e["shared"].entry_id not in _ids(
        resolve_targets(hass, people=["person.alice"]).receivers
    )


async def test_persistent_notification_only_when_named(hass: HomeAssistant) -> None:
    """The persistent notification receiver ignores people, areas and default."""
    e = await _setup(hass)
    pid = e["persistent"].entry_id
    assert pid not in _ids(resolve_targets(hass).receivers)
    # Even in an area, it is not reached by area.
    device = dr.async_get(hass).async_get_device_by_identifier((DOMAIN, pid), pid)
    dr.async_get(hass).async_update_device(device.id, area_id=e["kitchen"])
    assert pid not in _ids(resolve_targets(hass).receivers)
    assert pid not in _ids(resolve_targets(hass, areas=[e["kitchen"]]).receivers)
    assert pid in _ids(resolve_targets(hass, receivers=[pid]).receivers)


async def test_disabled_receivers_are_skipped(hass: HomeAssistant) -> None:
    """Disabled receivers are skipped however they were targeted."""
    e = await _setup(hass)
    await hass.services.async_call(
        "switch",
        "turn_off",
        {"entity_id": "switch.alice_phone_enabled"},
        blocking=True,
    )
    for result in (
        resolve_targets(hass),
        resolve_targets(hass, people=["person.alice"]),
        resolve_targets(hass, receivers=[e["alice"].entry_id]),
    ):
        assert e["alice"].entry_id not in _ids(result.receivers)
        assert _ids(result.skipped) == {e["alice"].entry_id}


async def test_unknown_targets_match_nothing(hass: HomeAssistant) -> None:
    """Unknown people, areas and receivers resolve to no receivers."""
    await _setup(hass)
    result = resolve_targets(
        hass, people=["person.nobody"], areas=["nowhere"], receivers=["nope"]
    )
    assert result.receivers == () and result.skipped == ()


async def test_result_is_ordered_by_name(hass: HomeAssistant) -> None:
    """Receivers come back ordered by name."""
    await _setup(hass)
    names = [r.name for r in resolve_targets(hass).receivers]
    assert names == sorted(names, key=str.casefold)
