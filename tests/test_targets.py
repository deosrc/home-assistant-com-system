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
from homeassistant.helpers import entity_registry as er
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


async def test_no_targets_targets_nothing(hass: HomeAssistant) -> None:
    """A group that is not given is not targeted, so no targets match nothing."""
    await _setup(hass)
    result = resolve_targets(hass)
    assert result.receivers == ()
    assert result.skipped == ()


async def test_groups_are_independent(hass: HomeAssistant) -> None:
    """People are not targeted unless given, except through a targeted area."""
    e = await _setup(hass)
    # Only areas: receivers with a person but no area are not reached.
    result = resolve_targets(hass, areas=[e["kitchen"], e["lounge"]])
    assert _ids(result.receivers) == {e["echo"].entry_id, e["both"].entry_id}
    # Only all people: receivers with only an area are not reached.
    assert _ids(resolve_targets(hass, all_people=True).receivers) == {
        e[k].entry_id for k in ("alice", "bob", "both")
    }
    # All areas: only receivers with an area.
    assert _ids(resolve_targets(hass, all_areas=True).receivers) == {
        e[k].entry_id for k in ("echo", "both")
    }


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


async def test_shared_receiver_only_reached_by_name(
    hass: HomeAssistant,
) -> None:
    """A receiver with no person or area is only reached by name."""
    e = await _setup(hass)
    shared = e["shared"].entry_id
    assert shared not in _ids(resolve_targets(hass, all_people=True).receivers)
    assert shared not in _ids(resolve_targets(hass, all_areas=True).receivers)
    assert e["shared"].entry_id not in _ids(
        resolve_targets(hass, people=["person.alice"]).receivers
    )


async def test_persistent_notification_follows_its_mapping(
    hass: HomeAssistant,
) -> None:
    """The persistent notification receiver is reached only as it is mapped."""
    e = await _setup(hass)
    pid = e["persistent"].entry_id
    # With no person or area it is only reached when named.
    assert pid not in _ids(resolve_targets(hass, all_people=True).receivers)
    assert pid not in _ids(resolve_targets(hass, all_areas=True).receivers)
    assert pid not in _ids(resolve_targets(hass, people=["person.carol"]).receivers)
    assert pid in _ids(resolve_targets(hass, receivers=[pid]).receivers)

    # Mapped to a person, people targets reach it like any receiver.
    hass.config_entries.async_update_entry(
        e["persistent"], options={CONF_PEOPLE: ["person.carol"]}
    )
    await hass.async_block_till_done()
    assert pid in _ids(resolve_targets(hass, people=["person.carol"]).receivers)
    assert pid in _ids(resolve_targets(hass, all_people=True).receivers)
    assert pid not in _ids(resolve_targets(hass, people=["person.alice"]).receivers)

    # Given an area, area targets reach it too.
    device = dr.async_get(hass).async_get_device_by_identifier((DOMAIN, pid), pid)
    dr.async_get(hass).async_update_device(device.id, area_id=e["kitchen"])
    assert pid in _ids(resolve_targets(hass, areas=[e["kitchen"]]).receivers)


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
        resolve_targets(hass, all_people=True),
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
    names = [r.name for r in resolve_targets(hass, all_people=True).receivers]
    assert names == sorted(names, key=str.casefold)


async def test_all_people(hass: HomeAssistant) -> None:
    """all_people matches receivers with a person, not areas-only or shared."""
    e = await _setup(hass)
    result = resolve_targets(hass, all_people=True)
    assert _ids(result.receivers) == {e[k].entry_id for k in ("alice", "bob", "both")}
    # Combined with an area it is a union.
    result = resolve_targets(hass, all_people=True, areas=[e["kitchen"]])
    assert _ids(result.receivers) == {
        e[k].entry_id for k in ("alice", "bob", "both", "echo")
    }


async def test_area_is_the_receiver_entitys(hass: HomeAssistant) -> None:
    """Only the notification_receiver entity's area counts, not the switch's."""
    e = await _setup(hass)
    shared = e["shared"].entry_id
    er.async_get(hass).async_update_entity(
        "switch.shared_tablet_enabled", area_id=e["kitchen"]
    )
    assert shared not in _ids(resolve_targets(hass, areas=[e["kitchen"]]).receivers)
    assert shared not in _ids(resolve_targets(hass, all_areas=True).receivers)
